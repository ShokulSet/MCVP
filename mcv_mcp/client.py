"""MyCourseView API Client"""
import re
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
from typing import Optional


class Course(BaseModel):
    cv_cid: int
    course_no: str
    title: str
    year: int
    semester: int


class Assignment(BaseModel):
    mcv_course_id: int
    assignment_id: int
    assignment_name: str
    course_no: Optional[str] = None


class MCVClient:
    BASE_URL = "https://www.mycourseville.com"

    def __init__(self, cookie: str):
        """
        Initialize MCV client with session cookie.
        
        Get cookie from browser: F12 -> Console -> document.cookie
        """
        self.client = httpx.Client(follow_redirects=True, timeout=30.0)
        self._set_cookie(cookie)

    def _set_cookie(self, cookie: str):
        """Set cookies from a cookie string."""
        for part in cookie.split(";"):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                self.client.cookies.set(key.strip(), value.strip(), domain=".mycourseville.com")

    def _get(self, path: str) -> httpx.Response:
        return self.client.get(f"{self.BASE_URL}{path}")

    def _post(self, path: str, data: dict) -> httpx.Response:
        return self.client.post(f"{self.BASE_URL}{path}", data=data)

    def validate_session(self) -> bool:
        """Check if the session is valid."""
        resp = self._get("/")
        return "logout" in resp.text.lower()

    def get_courses_raw(self, year: int, semester: int) -> dict:
        """Debug: Get raw API response for courses."""
        data = {
            "yearsem": f"{year}/{semester}",
            "role": "student",
            "type": "course",
        }
        resp = self._post("/courseville/ajax/cvhomepanel_get_filter", data)
        try:
            return resp.json()
        except Exception:
            return {"error": "Failed to parse JSON", "text": resp.text[:500]}

    def get_courses(self, year: Optional[int] = None, semester: Optional[int] = None) -> list[Course]:
        """Get list of enrolled courses."""
        if year is None or semester is None:
            home = self._get("/")
            soup = BeautifulSoup(home.text, "html.parser")
            
            # Try to get from dropdown selector (like Discord bot does)
            year_select = soup.select_one("#student-yearsem-select option")
            if year_select:
                match = re.search(r"(\d{4})/(\d)", year_select.text)
                if match:
                    year = int(match.group(1))
                    semester = int(match.group(2))
            
            # Fallback: try section headers
            if year is None or semester is None:
                semester_groups = soup.find_all("section", class_="courseville-courseicongroup")
                if semester_groups:
                    header = semester_groups[0].find("div", class_="courseville-header")
                    if header:
                        match = re.search(r"(\d{4})/(\d)", header.text)
                        if match:
                            year = int(match.group(1))
                            semester = int(match.group(2))

        # Default to current semester (CE year)
        if year is None or semester is None:
            from datetime import datetime
            now = datetime.now()
            year = now.year  # CE year, not BE
            if now.month >= 8:
                semester = 1
            elif now.month >= 1 and now.month <= 5:
                semester = 2
            else:
                semester = 3

        data = {
            "yearsem": f"{year}/{semester}",
            "role": "student",
            "type": "course",
        }
        resp = self._post("/courseville/ajax/cvhomepanel_get_filter", data)
        
        # Debug: return raw response if parsing fails
        try:
            result = resp.json()
        except Exception:
            return []

        courses = []
        if result.get("status") == 1 and "data" in result:
            for c in result["data"]:
                courses.append(Course(
                    cv_cid=int(c["cv_cid"]),
                    course_no=c["course_no"],
                    title=c["title"],
                    year=int(c["year"]),
                    semester=int(c["semester"]),
                ))
        return courses

    def get_assignments(self, limit: int = 50) -> list[Assignment]:
        """Get list of assignments across all courses."""
        assignments = []
        next_page = 0

        while len(assignments) < limit:
            data = {"next": str(next_page)}
            resp = self._post("/?q=courseville/ajax/loadmoreassignmentrows", data)
            result = resp.json()

            if result.get("status") == 0:
                break

            html = result.get("data", {}).get("html", "")
            if not html:
                break

            soup = BeautifulSoup(f"<table><tbody>{html}</tbody></table>", "html.parser")
            rows = soup.select("tbody tr td:nth-child(2) a")

            for link in rows:
                href = link.get("href", "")
                match = re.search(r"/(\d+)/(\d+)$", href)
                if match:
                    assignments.append(Assignment(
                        mcv_course_id=int(match.group(1)),
                        assignment_id=int(match.group(2)),
                        assignment_name=link.text.strip(),
                    ))

            if result.get("all") is True:
                break
            next_page += 10

        return assignments[:limit]

    def get_course_assignments_raw(self, cv_cid: int) -> str:
        """Debug: Get raw HTML of assignment page."""
        resp = self._get(f"/courseville/course/{cv_cid}/assignment")
        return resp.text[:5000]

    def get_course_assignments(self, cv_cid: int) -> list[Assignment]:
        """Get assignments for a specific course (with pagination)."""
        resp = self._get(f"/courseville/course/{cv_cid}/assignment")
        soup = BeautifulSoup(resp.text, "html.parser")

        assignments = []
        
        # Get initial assignments from page
        table = soup.select_one("#cv-assignment-table tbody")
        if table:
            rows = table.select("tr")
            for row in rows:
                title_cell = row.select_one("td:nth-child(2) a")
                if title_cell:
                    href = title_cell.get("href", "")
                    match = re.search(r"/worksheet/(\d+)/(\d+)", href)
                    if match:
                        assignments.append(Assignment(
                            mcv_course_id=int(match.group(1)),
                            assignment_id=int(match.group(2)),
                            assignment_name=title_cell.text.strip(),
                        ))
        
        # Check if there are more items to load
        loadmore_panel = soup.select_one("#courseville-assignment-list-loadmore-panel")
        if loadmore_panel:
            total = int(loadmore_panel.get("data-total", 0))
            next_idx = int(loadmore_panel.get("data-next", 0))
            
            # Load remaining items via AJAX
            while next_idx < total:
                data = {"cv_cid": str(cv_cid), "next": str(next_idx)}
                resp = self._post("/?q=courseville/ajax/loadmoreassignmentrows", data)
                try:
                    result = resp.json()
                    if result.get("status") != 1:
                        break
                    
                    html = result.get("data", {}).get("html", "")
                    if html:
                        more_soup = BeautifulSoup(f"<table><tbody>{html}</tbody></table>", "html.parser")
                        for row in more_soup.select("tr"):
                            title_cell = row.select_one("td:nth-child(2) a")
                            if title_cell:
                                href = title_cell.get("href", "")
                                match = re.search(r"/worksheet/(\d+)/(\d+)", href)
                                if match:
                                    assignments.append(Assignment(
                                        mcv_course_id=int(match.group(1)),
                                        assignment_id=int(match.group(2)),
                                        assignment_name=title_cell.text.strip(),
                                    ))
                    
                    # Check if all items loaded
                    if result.get("all") is True:
                        break
                    next_idx += 5
                except Exception:
                    break
        
        return assignments

    def get_course_materials_raw(self, cv_cid: int) -> str:
        """Debug: Get raw HTML of materials page."""
        resp = self._get(f"/?q=courseville/course/{cv_cid}")
        return resp.text

    def get_course_materials(self, cv_cid: int) -> list[dict]:
        """Get course materials/resources with download URLs."""
        resp = self._get(f"/?q=courseville/course/{cv_cid}")
        soup = BeautifulSoup(resp.text, "html.parser")

        materials = []
        
        # Try multiple selector patterns for materials
        # Pattern 1: Material folders with items
        folders = soup.select(".cv-course-material-folder-container, .courseville-material-folder")
        for folder in folders:
            folder_name = ""
            folder_header = folder.select_one(".cv-course-material-folder-header, .folder-header, h3, h4")
            if folder_header:
                folder_name = folder_header.text.strip()
            
            items = folder.select(".cv-course-material-item, .material-item, a[href*='view_content_node']")
            for item in items:
                if item.name == "a":
                    title = item.text.strip()
                    href = item.get("href", "")
                else:
                    title_el = item.select_one("a[href*='view_content_node'], .material-title a, a")
                    if title_el:
                        title = title_el.text.strip()
                        href = title_el.get("href", "")
                    else:
                        continue
                
                # Extract material node ID from URL
                node_id = None
                match = re.search(r"view_content_node_(\d+)", href)
                if match:
                    node_id = int(match.group(1))
                
                materials.append({
                    "folder": folder_name,
                    "title": title,
                    "view_url": href if href.startswith("http") else f"{self.BASE_URL}{href}" if href else "",
                    "material_node_id": node_id,
                })
        
        # Pattern 2: Direct material links on page
        material_links = soup.select("a[href*='view_content_node'][href*='material']")
        for link in material_links:
            href = link.get("href", "")
            title = link.text.strip()
            
            # Skip if already found
            if any(m.get("view_url", "").endswith(href) for m in materials):
                continue
            
            node_id = None
            match = re.search(r"view_content_node_(\d+)", href)
            if match:
                node_id = int(match.group(1))
            
            if title and node_id:
                materials.append({
                    "folder": "",
                    "title": title,
                    "view_url": href if href.startswith("http") else f"{self.BASE_URL}{href}",
                    "material_node_id": node_id,
                })
        
        # Pattern 3: Try the dedicated materials page
        if not materials:
            resp2 = self._get(f"/?q=courseville/course/{cv_cid}/material")
            soup2 = BeautifulSoup(resp2.text, "html.parser")
            
            material_links = soup2.select("a[href*='view_content_node']")
            for link in material_links:
                href = link.get("href", "")
                title = link.text.strip()
                
                node_id = None
                match = re.search(r"view_content_node_(\d+)", href)
                if match:
                    node_id = int(match.group(1))
                
                if title and node_id:
                    materials.append({
                        "folder": "",
                        "title": title,
                        "view_url": href if href.startswith("http") else f"{self.BASE_URL}{href}",
                        "material_node_id": node_id,
                    })
        
        return materials

    def get_announcements(self, cv_cid: int) -> list[dict]:
        """Get course announcements."""
        resp = self._get(f"/courseville/course/{cv_cid}/announcement")
        soup = BeautifulSoup(resp.text, "html.parser")

        announcements = []
        items = soup.select(".announcement-item, .cv-announcement, article")
        for item in items:
            title_el = item.select_one(".announcement-title, h3, h4, a")
            content_el = item.select_one(".announcement-content, .content, p")
            if title_el:
                announcements.append({
                    "title": title_el.text.strip(),
                    "content": content_el.text.strip() if content_el else "",
                })
        return announcements

    def close(self):
        self.client.close()

    def get_material_content(self, cv_cid: int, material_node_id: int) -> dict:
        """Get material details including download URL."""
        # View the material page to get the actual download link
        resp = self._get(f"/?q=courseville/course/{cv_cid}/view_content_node_{material_node_id}_material")
        soup = BeautifulSoup(resp.text, "html.parser")
        
        title = ""
        title_el = soup.select_one(".cv-course-material-view-title")
        if title_el:
            title = title_el.text.strip()
        
        # Find download link (usually S3 URL)
        download_url = ""
        download_link = soup.select_one("a[href*='s3.']") or soup.select_one("a[href*='amazonaws.com']")
        if download_link:
            download_url = download_link.get("href", "")
        
        # Also try to find iframe or embed for PDFs
        iframe = soup.select_one("iframe[src*='s3.']") or soup.select_one("iframe[src*='amazonaws.com']")
        if iframe:
            download_url = iframe.get("src", "")
        
        # Try to find any link with download in it
        if not download_url:
            for link in soup.select("a"):
                href = link.get("href", "")
                if "download" in href.lower() or "s3" in href or "amazonaws" in href:
                    download_url = href
                    break
        
        return {
            "cv_cid": cv_cid,
            "material_node_id": material_node_id,
            "title": title,
            "download_url": download_url,
            "page_url": f"{self.BASE_URL}/?q=courseville/course/{cv_cid}/view_content_node_{material_node_id}_material",
        }

    def get_assignment_detail(self, cv_cid: int, assignment_id: int) -> dict:
        """Get assignment details including questions with human-friendly summary."""
        resp = self._get(f"/?q=courseville/worksheet/{cv_cid}/{assignment_id}")
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Get assignment info
        title_el = soup.select_one("#courseville-worksheet-title")
        title = title_el.text.strip() if title_el else ""
        
        # Get due date
        due_date = ""
        due_el = soup.select_one(".sr-only")
        if due_el:
            match = re.search(r"Due on (.+)", due_el.text)
            if match:
                due_date = match.group(1)
        
        # Get instruction
        instruction_el = soup.select_one("#courseville-worksheet-instruction-body")
        instruction = instruction_el.text.strip() if instruction_el else ""
        
        # Get questions
        questions = []
        question_wrappers = soup.select(".cvqs-qstn-wrapper")
        
        for idx, wrapper in enumerate(question_wrappers, 1):
            qstn_nid = wrapper.get("qstn_nid", "")
            
            # Get question text
            question_el = wrapper.select_one(".cvqs-qstn-question")
            question_text = question_el.text.strip() if question_el else ""
            
            # Get question type and choices
            qstn_type = "unknown"
            choices = []
            choices_text = []
            
            # Check for multiple choice
            mc_wrapper = wrapper.select_one(".cvqs-answer-multiplechoice")
            if mc_wrapper:
                qstn_type = "multiple_choice"
                choice_items = mc_wrapper.select(".cvqs-answer-multiplechoice-choiceitem")
                for i, item in enumerate(choice_items):
                    input_el = item.select_one("input[type='radio']")
                    label_el = item.select_one(".cvqs-answer-multiplechoice-content")
                    if input_el and label_el:
                        label = label_el.text.strip()
                        choices.append({
                            "value": input_el.get("value", ""),
                            "label": label,
                        })
                        choices_text.append(f"  {chr(65+i)}) {label}")
            
            # Check for open text
            opentext_wrapper = wrapper.select_one(".cvqs-answer-opentext")
            if opentext_wrapper:
                qstn_type = "open_text"
            
            # Get points
            point_el = wrapper.select_one("[data-part='point']")
            points = int(point_el.text) if point_el else 1
            
            # Build human-friendly summary
            if qstn_type == "multiple_choice":
                summary = f"Q{idx}. {question_text} ({points} pt)\n" + "\n".join(choices_text)
            elif qstn_type == "open_text":
                summary = f"Q{idx}. {question_text} ({points} pt) [Text Answer]"
            else:
                summary = f"Q{idx}. {question_text} ({points} pt)"
            
            questions.append({
                "id": qstn_nid,
                "number": idx,
                "question": question_text,
                "type": qstn_type,
                "choices": choices,
                "points": points,
                "summary": summary,
            })
        
        # Build overall human-friendly summary
        summary_lines = [
            f"📝 {title}",
            f"⏰ Due: {due_date}",
            f"📊 Total: {len(questions)} questions",
            "",
        ]
        if instruction and instruction != "undefined":
            summary_lines.append(f"📋 Instructions: {instruction}")
            summary_lines.append("")
        
        summary_lines.append("─" * 40)
        for q in questions:
            summary_lines.append(q["summary"])
            summary_lines.append("")
        
        return {
            "cv_cid": cv_cid,
            "assignment_id": assignment_id,
            "title": title,
            "due_date": due_date,
            "instruction": instruction,
            "questions": questions,
            "total_questions": len(questions),
            "human_summary": "\n".join(summary_lines),
        }
