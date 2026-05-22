"""
MCP Server: Filesystem
Lets Claude read, write, list, and search files within a sandboxed directory.

Usage:
    ALLOWED_DIR=/path/to/workspace python -m servers.filesystem

Tools exposed:
    - list_files(path, pattern)
    - read_file(path)
    - write_file(path, content)
    - search_in_files(query, path, file_pattern)
    - get_file_info(path)
    - delete_file(path)            — requires ALLOW_DELETES=true
"""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

ALLOWED_DIR = Path(os.environ.get("ALLOWED_DIR", ".")).resolve()
ALLOW_DELETES = os.environ.get("ALLOW_DELETES", "false").lower() == "true"

app = Server("filesystem")


def _safe_path(rel_path: str) -> Path:
    """Resolve path and ensure it stays within ALLOWED_DIR."""
    p = (ALLOWED_DIR / rel_path).resolve()
    if not str(p).startswith(str(ALLOWED_DIR)):
        raise PermissionError(f"Path escapes allowed directory: {rel_path}")
    return p


@app.list_tools()
async def list_tools():
    tools = [
        Tool(
            name="list_files",
            description="List files and directories in a path",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": ".", "description": "Relative path within workspace"},
                    "pattern": {"type": "string", "default": "*", "description": "Glob pattern e.g. '*.py'"},
                    "recursive": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="read_file",
            description="Read the contents of a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_lines": {"type": "integer", "default": 200},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="write_file",
            description="Write or overwrite a file with new content",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean", "default": False},
                },
                "required": ["path", "content"],
            },
        ),
        Tool(
            name="search_in_files",
            description="Search for a string or regex pattern inside files",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "file_pattern": {"type": "string", "default": "*"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_file_info",
            description="Get metadata for a file (size, modified date, type)",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ),
    ]
    if ALLOW_DELETES:
        tools.append(Tool(
            name="delete_file",
            description="Delete a file (requires ALLOW_DELETES=true)",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ))
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "list_files":
            base = _safe_path(arguments.get("path", "."))
            pattern = arguments.get("pattern", "*")
            recursive = arguments.get("recursive", False)
            if recursive:
                files = [p.relative_to(ALLOWED_DIR) for p in base.rglob(pattern) if p.is_file()]
            else:
                files = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name))
                files = [f for f in files if fnmatch.fnmatch(f.name, pattern)]
            lines = []
            for f in files[:100]:
                rel = f.relative_to(ALLOWED_DIR) if f.is_absolute() else f
                icon = "📄" if Path(ALLOWED_DIR / rel).is_file() else "📁"
                lines.append(f"{icon} {rel}")
            result = f"Contents of {arguments.get('path', '.')}:\n" + "\n".join(lines) + f"\n\n({len(lines)} items)"

        elif name == "read_file":
            p = _safe_path(arguments["path"])
            if not p.exists():
                result = f"File not found: {arguments['path']}"
            else:
                lines = p.read_text(errors="replace").splitlines()
                max_lines = arguments.get("max_lines", 200)
                shown = lines[:max_lines]
                result = "\n".join(shown)
                if len(lines) > max_lines:
                    result += f"\n\n[... {len(lines) - max_lines} more lines not shown]"

        elif name == "write_file":
            p = _safe_path(arguments["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if arguments.get("append") else "w"
            with open(p, mode, encoding="utf-8") as f:
                f.write(arguments["content"])
            result = f"Written: {arguments['path']} ({len(arguments['content'])} chars)"

        elif name == "search_in_files":
            import re
            base = _safe_path(arguments.get("path", "."))
            pattern = arguments.get("file_pattern", "*")
            query = arguments["query"]
            matches = []
            for p in base.rglob(pattern):
                if not p.is_file():
                    continue
                try:
                    for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                        if re.search(query, line, re.IGNORECASE):
                            rel = p.relative_to(ALLOWED_DIR)
                            matches.append(f"{rel}:{i}: {line.strip()}")
                            if len(matches) >= arguments.get("max_results", 20):
                                break
                except Exception:
                    continue
                if len(matches) >= arguments.get("max_results", 20):
                    break
            result = f"Matches for '{query}':\n" + "\n".join(matches) if matches else f"No matches for '{query}'"

        elif name == "get_file_info":
            p = _safe_path(arguments["path"])
            if not p.exists():
                result = f"Not found: {arguments['path']}"
            else:
                import datetime
                stat = p.stat()
                result = (
                    f"Path: {arguments['path']}\n"
                    f"Type: {'file' if p.is_file() else 'directory'}\n"
                    f"Size: {stat.st_size:,} bytes\n"
                    f"Modified: {datetime.datetime.fromtimestamp(stat.st_mtime)}\n"
                    f"Extension: {p.suffix or 'none'}"
                )

        elif name == "delete_file" and ALLOW_DELETES:
            p = _safe_path(arguments["path"])
            if not p.exists():
                result = f"File not found: {arguments['path']}"
            else:
                p.unlink()
                result = f"Deleted: {arguments['path']}"

        else:
            result = f"Unknown tool: {name}"

    except PermissionError as e:
        result = f"Permission denied: {e}"
    except Exception as e:
        result = f"Error: {e}"

    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
