# mcp-servers

> A collection of production-ready MCP (Model Context Protocol) servers — plug them into Claude Desktop, Cursor, or any MCP-compatible AI assistant.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![MCP](https://img.shields.io/badge/protocol-MCP-purple)

## What is MCP?

[Model Context Protocol](https://modelcontextprotocol.io) is an open standard by Anthropic that lets AI assistants (Claude, Cursor, Windsurf, etc.) securely connect to external tools and data sources. Think of MCP servers as plugins — you run them locally and your AI assistant gains new capabilities.

## Servers Included

| Server | What It Does | Key Tools |
|--------|-------------|-----------|
| **GitHub Issues** | Read, create, comment on GitHub issues | `list_issues`, `get_issue`, `create_issue`, `add_comment`, `search_issues` |
| **PostgreSQL** | Query and inspect databases (read-safe by default) | `list_tables`, `describe_table`, `query`, `get_schema` |
| **Web Scraper** | Fetch web pages, extract structured data | `fetch_page`, `fetch_multiple`, `extract_structured`, `get_page_metadata` |
| **Filesystem** | Read/write files in a sandboxed directory | `list_files`, `read_file`, `write_file`, `search_in_files` |

## Installation

```bash
git clone https://github.com/bhupendra05/mcp-servers.git
cd mcp-servers
pip install -r requirements.txt
```

## Claude Desktop Setup

Add any server to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github-issues": {
      "command": "python",
      "args": ["-m", "servers.github_issues"],
      "cwd": "/path/to/mcp-servers",
      "env": {
        "GITHUB_TOKEN": "ghp_..."
      }
    },
    "postgres": {
      "command": "python",
      "args": ["-m", "servers.postgres"],
      "cwd": "/path/to/mcp-servers",
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost/mydb"
      }
    },
    "web-scraper": {
      "command": "python",
      "args": ["-m", "servers.web_scraper"],
      "cwd": "/path/to/mcp-servers"
    },
    "filesystem": {
      "command": "python",
      "args": ["-m", "servers.filesystem"],
      "cwd": "/path/to/mcp-servers",
      "env": {
        "ALLOWED_DIR": "/Users/you/projects"
      }
    }
  }
}
```

Restart Claude Desktop — the tools will appear automatically.

---

## Server Details

### 🐙 GitHub Issues

```bash
GITHUB_TOKEN=ghp_... python -m servers.github_issues
```

Ask Claude things like:
- *"List open bugs in bhupendra05/ai-commit"*
- *"Create an issue titled 'Add dark mode support'"*
- *"Search for issues mentioning authentication error"*

**No token needed** for public repos (60 req/hr). Add token for private repos + higher rate limits.

---

### 🐘 PostgreSQL

```bash
DATABASE_URL=postgresql://user:pass@host/db python -m servers.postgres
```

Ask Claude things like:
- *"What tables are in the database?"*
- *"Show me the schema for the users table"*
- *"SELECT the last 10 orders with total > 100"*

By default **read-only** (`SELECT` only). Enable writes:
```bash
ALLOW_WRITES=true DATABASE_URL=... python -m servers.postgres
```

---

### 🌐 Web Scraper

```bash
python -m servers.web_scraper
```

Ask Claude things like:
- *"Fetch the content of https://docs.python.org/3/library/asyncio.html"*
- *"Extract all h2 headings from https://example.com"*
- *"Get the page title and description of this URL"*

Install `beautifulsoup4` for HTML parsing:
```bash
pip install beautifulsoup4
```

---

### 📁 Filesystem

```bash
ALLOWED_DIR=/path/to/workspace python -m servers.filesystem
```

Ask Claude things like:
- *"List all Python files in the src directory"*
- *"Read the contents of config.yaml"*
- *"Search for 'TODO' across all .py files"*
- *"Write a new file called notes.md with..."*

Access is **sandboxed** to `ALLOWED_DIR` — paths outside it are rejected.

---

## Adding Your Own Server

1. Copy `servers/web_scraper.py` as a template
2. Define tools in `list_tools()`
3. Handle calls in `call_tool()`
4. Add to `claude_desktop_config.json`

The MCP SDK handles all protocol framing — you only write business logic.

## Screenshots

![mcp-servers demo](docs/demo.png)

## License

MIT © bhupendra05
