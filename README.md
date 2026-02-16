# MyCourseView MCP Server

MCP server for [MyCourseView](https://www.mycourseville.com/) - Chulalongkorn University's course management system.

Works with Gemini CLI, Claude Desktop, Kiro, and other MCP-compatible clients.

## Features

| Tool | Description |
|------|-------------|
| `mcv_get_courses` | Get enrolled courses (optionally filter by year/semester) |
| `mcv_get_assignments` | Get assignments across all courses |
| `mcv_get_course_assignments` | Get assignments for a specific course |
| `mcv_get_course_materials` | Get course materials with download URLs |
| `mcv_get_material_content` | Get material details and S3 download links |
| `mcv_get_announcements` | Get course announcements |
| `mcv_get_assignment_detail` | Get assignment questions, choices, and due dates |
| `mcv_validate_session` | Check if session is valid |

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager

### Get Your Cookie

1. Log in to [MyCourseView](https://www.mycourseville.com/)
2. Open DevTools (`F12` or `Cmd+Option+I`)
3. Go to Console tab
4. Run: `document.cookie`
5. Copy the entire output

### Gemini CLI

Edit `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "mcv": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcv-mcp", "mcv-mcp"],
      "env": {
        "MCV_COOKIE": "your_cookie_here"
      }
    }
  }
}
```

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "mcv": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcv-mcp", "mcv-mcp"],
      "env": {
        "MCV_COOKIE": "your_cookie_here"
      }
    }
  }
}
```

### Kiro

Edit `.kiro/settings/mcp.json` in your workspace:

```json
{
  "mcpServers": {
    "mcv": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcv-mcp", "mcv-mcp"],
      "env": {
        "MCV_COOKIE": "your_cookie_here"
      }
    }
  }
}
```

## Usage Examples

Once configured, you can ask:

- "Show me my courses this semester"
- "What assignments do I have?"
- "Get materials for course 12345"
- "Show assignment details for assignment 67890 in course 12345"
- "List announcements for my Data Structures course"

## Credits

Based on:
- [mcv-api-python-unofficial](https://github.com/CEDT-Chula/mcv-api-python-unofficial)
- [mcv-discord-bot](https://github.com/CEDT-Chula/mcv-discord-bot)

## Disclaimer

This is an unofficial API wrapper. Use at your own risk.
