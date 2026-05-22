"""
MCP Server: GitHub Issues
Lets Claude list, read, create, and comment on GitHub issues.

Usage:
    python -m servers.github_issues

Tools exposed:
    - list_issues(owner, repo, state, limit)
    - get_issue(owner, repo, number)
    - create_issue(owner, repo, title, body, labels)
    - add_comment(owner, repo, number, body)
    - close_issue(owner, repo, number)
    - search_issues(query, limit)
"""
from __future__ import annotations

import json
import os
import sys

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BASE = "https://api.github.com"


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _get(path: str, params: dict | None = None) -> dict | list:
    r = requests.get(f"{BASE}{path}", headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{BASE}{path}", headers=_headers(), json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def _patch(path: str, body: dict) -> dict:
    r = requests.patch(f"{BASE}{path}", headers=_headers(), json=body, timeout=15)
    r.raise_for_status()
    return r.json()


app = Server("github-issues")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="list_issues",
            description="List issues in a GitHub repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner (username or org)"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                    "limit": {"type": "integer", "default": 20, "description": "Max number of issues"},
                },
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="get_issue",
            description="Get details of a specific GitHub issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "number": {"type": "integer", "description": "Issue number"},
                },
                "required": ["owner", "repo", "number"],
            },
        ),
        Tool(
            name="create_issue",
            description="Create a new GitHub issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string", "description": "Issue description (markdown)"},
                    "labels": {"type": "array", "items": {"type": "string"}, "default": []},
                },
                "required": ["owner", "repo", "title"],
            },
        ),
        Tool(
            name="add_comment",
            description="Add a comment to a GitHub issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "number": {"type": "integer"},
                    "body": {"type": "string"},
                },
                "required": ["owner", "repo", "number", "body"],
            },
        ),
        Tool(
            name="close_issue",
            description="Close a GitHub issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "number": {"type": "integer"},
                },
                "required": ["owner", "repo", "number"],
            },
        ),
        Tool(
            name="search_issues",
            description="Search GitHub issues across all repos",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "GitHub search query e.g. 'bug label:bug repo:owner/repo'"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "list_issues":
            owner, repo = arguments["owner"], arguments["repo"]
            data = _get(
                f"/repos/{owner}/{repo}/issues",
                params={"state": arguments.get("state", "open"), "per_page": arguments.get("limit", 20)},
            )
            issues = [
                f"#{i['number']} [{i['state']}] {i['title']} — @{i['user']['login']}"
                for i in data
                if not i.get("pull_request")
            ]
            result = f"Issues in {owner}/{repo}:\n" + "\n".join(issues) if issues else "No issues found."

        elif name == "get_issue":
            owner, repo, num = arguments["owner"], arguments["repo"], arguments["number"]
            i = _get(f"/repos/{owner}/{repo}/issues/{num}")
            comments_data = _get(f"/repos/{owner}/{repo}/issues/{num}/comments")
            comments = "\n\n".join(
                f"**@{c['user']['login']}**: {c['body']}" for c in comments_data[:5]
            )
            result = (
                f"# Issue #{i['number']}: {i['title']}\n"
                f"State: {i['state']} | Author: @{i['user']['login']}\n"
                f"Labels: {', '.join(l['name'] for l in i.get('labels', []))}\n\n"
                f"{i['body'] or '(no description)'}\n\n"
                f"--- Comments ({len(comments_data)}) ---\n{comments}"
            )

        elif name == "create_issue":
            owner, repo = arguments["owner"], arguments["repo"]
            payload = {"title": arguments["title"], "body": arguments.get("body", "")}
            if arguments.get("labels"):
                payload["labels"] = arguments["labels"]
            i = _post(f"/repos/{owner}/{repo}/issues", payload)
            result = f"Created issue #{i['number']}: {i['title']}\nURL: {i['html_url']}"

        elif name == "add_comment":
            owner, repo, num = arguments["owner"], arguments["repo"], arguments["number"]
            c = _post(f"/repos/{owner}/{repo}/issues/{num}/comments", {"body": arguments["body"]})
            result = f"Comment added: {c['html_url']}"

        elif name == "close_issue":
            owner, repo, num = arguments["owner"], arguments["repo"], arguments["number"]
            i = _patch(f"/repos/{owner}/{repo}/issues/{num}", {"state": "closed"})
            result = f"Issue #{i['number']} closed."

        elif name == "search_issues":
            data = _get("/search/issues", params={"q": arguments["query"], "per_page": arguments.get("limit", 10)})
            items = data.get("items", [])
            lines = [f"#{i['number']} {i['title']} ({i['repository_url'].split('/')[-2]}/{i['repository_url'].split('/')[-1]})" for i in items]
            result = f"Found {data.get('total_count', 0)} issues:\n" + "\n".join(lines)

        else:
            result = f"Unknown tool: {name}"

    except Exception as e:
        result = f"Error: {e}"

    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
