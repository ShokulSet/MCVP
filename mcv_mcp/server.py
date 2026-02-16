"""MyCourseView MCP Server"""
import os
import json
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .client import MCVClient


_client_instance: MCVClient | None = None


def get_client() -> MCVClient:
    """Get or create MCV client instance."""
    global _client_instance
    
    if _client_instance is not None:
        return _client_instance
    
    cookie = os.environ.get("MCV_COOKIE", "")
    if not cookie:
        raise ValueError("MCV_COOKIE environment variable is required. Get it from browser: F12 -> Console -> document.cookie")
    
    _client_instance = MCVClient(cookie=cookie)
    return _client_instance


server = Server("mcv-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="mcv_validate_session",
            description="Validate if the MyCourseView session is still valid",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="mcv_get_courses_raw",
            description="Debug: Get raw API response for courses",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Year in Buddhist Era"},
                    "semester": {"type": "integer", "description": "Semester (1, 2, or 3)"},
                },
                "required": ["year", "semester"],
            },
        ),
        Tool(
            name="mcv_get_courses",
            description="Get list of enrolled courses from MyCourseView. Optionally filter by year and semester.",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Academic year in Buddhist Era (e.g., 2567). If not provided, uses current semester.",
                    },
                    "semester": {
                        "type": "integer",
                        "description": "Semester number (1, 2, or 3 for summer). If not provided, uses current semester.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="mcv_get_assignments",
            description="Get list of assignments across all courses",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of assignments to return (default: 50)",
                        "default": 50,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="mcv_get_course_assignments_raw",
            description="Debug: Get raw HTML of assignment page",
            inputSchema={
                "type": "object",
                "properties": {
                    "cv_cid": {"type": "integer", "description": "MyCourseView course ID"},
                },
                "required": ["cv_cid"],
            },
        ),
        Tool(
            name="mcv_get_course_assignments",
            description="Get assignments for a specific course by its MCV course ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "cv_cid": {
                        "type": "integer",
                        "description": "MyCourseView course ID (cv_cid)",
                    },
                },
                "required": ["cv_cid"],
            },
        ),
        Tool(
            name="mcv_get_course_materials",
            description="Get course materials/resources for a specific course with view URLs",
            inputSchema={
                "type": "object",
                "properties": {
                    "cv_cid": {
                        "type": "integer",
                        "description": "MyCourseView course ID (cv_cid)",
                    },
                },
                "required": ["cv_cid"],
            },
        ),
        Tool(
            name="mcv_get_course_materials_raw",
            description="Debug: Get raw HTML of course home page (where materials are listed)",
            inputSchema={
                "type": "object",
                "properties": {
                    "cv_cid": {
                        "type": "integer",
                        "description": "MyCourseView course ID (cv_cid)",
                    },
                },
                "required": ["cv_cid"],
            },
        ),
        Tool(
            name="mcv_get_material_content",
            description="Get material details including download URL (for PDFs hosted on S3)",
            inputSchema={
                "type": "object",
                "properties": {
                    "cv_cid": {
                        "type": "integer",
                        "description": "MyCourseView course ID (cv_cid)",
                    },
                    "material_node_id": {
                        "type": "integer",
                        "description": "Material node ID (from the view_content_node URL)",
                    },
                },
                "required": ["cv_cid", "material_node_id"],
            },
        ),
        Tool(
            name="mcv_get_announcements",
            description="Get announcements for a specific course",
            inputSchema={
                "type": "object",
                "properties": {
                    "cv_cid": {
                        "type": "integer",
                        "description": "MyCourseView course ID (cv_cid)",
                    },
                },
                "required": ["cv_cid"],
            },
        ),
        Tool(
            name="mcv_get_assignment_detail",
            description="Get assignment details including questions, choices, and due date. Use this to read assignment content before answering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cv_cid": {
                        "type": "integer",
                        "description": "MyCourseView course ID (cv_cid)",
                    },
                    "assignment_id": {
                        "type": "integer",
                        "description": "Assignment ID",
                    },
                },
                "required": ["cv_cid", "assignment_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        client = get_client()
        result: Any = None

        if name == "mcv_validate_session":
            is_valid = client.validate_session()
            result = {"valid": is_valid, "message": "Session is valid" if is_valid else "Session expired or invalid"}

        elif name == "mcv_get_courses_raw":
            year = arguments["year"]
            semester = arguments["semester"]
            result = client.get_courses_raw(year, semester)

        elif name == "mcv_get_courses":
            year = arguments.get("year")
            semester = arguments.get("semester")
            courses = client.get_courses(year, semester)
            result = [c.model_dump() for c in courses]

        elif name == "mcv_get_assignments":
            limit = arguments.get("limit", 50)
            assignments = client.get_assignments(limit)
            result = [a.model_dump() for a in assignments]

        elif name == "mcv_get_course_assignments_raw":
            cv_cid = arguments["cv_cid"]
            result = {"html": client.get_course_assignments_raw(cv_cid)}

        elif name == "mcv_get_course_assignments":
            cv_cid = arguments["cv_cid"]
            assignments = client.get_course_assignments(cv_cid)
            result = [a.model_dump() for a in assignments]

        elif name == "mcv_get_course_materials":
            cv_cid = arguments["cv_cid"]
            result = client.get_course_materials(cv_cid)

        elif name == "mcv_get_course_materials_raw":
            cv_cid = arguments["cv_cid"]
            result = {"html": client.get_course_materials_raw(cv_cid)[:10000]}

        elif name == "mcv_get_material_content":
            cv_cid = arguments["cv_cid"]
            material_node_id = arguments["material_node_id"]
            result = client.get_material_content(cv_cid, material_node_id)

        elif name == "mcv_get_announcements":
            cv_cid = arguments["cv_cid"]
            result = client.get_announcements(cv_cid)

        elif name == "mcv_get_assignment_detail":
            cv_cid = arguments["cv_cid"]
            assignment_id = arguments["assignment_id"]
            result = client.get_assignment_detail(cv_cid, assignment_id)

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


def main():
    import asyncio
    
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
