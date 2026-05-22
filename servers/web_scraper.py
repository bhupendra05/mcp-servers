"""
MCP Server: Web Scraper
Lets Claude fetch web pages, extract text, search the web, and scrape structured data.

Usage:
    python -m servers.web_scraper

Tools exposed:
    - fetch_page(url, extract_links)
    - fetch_text(url)              — clean text only, no HTML
    - extract_structured(url, css_selector)
    - get_page_title(url)
    - fetch_multiple(urls)
"""
from __future__ import annotations

import re
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("web-scraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MCP-WebScraper/1.0; +https://github.com/bhupendra05/mcp-servers)",
}


def _fetch_html(url: str, timeout: int = 15) -> str:
    import requests
    resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # Collapse blank lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)
    except ImportError:
        # Fallback: basic tag strip
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="fetch_page",
            description="Fetch a web page and return its content as clean text",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "max_chars": {"type": "integer", "default": 8000, "description": "Max characters to return"},
                    "extract_links": {"type": "boolean", "default": False},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="fetch_multiple",
            description="Fetch multiple URLs and return their text (up to 5)",
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    "max_chars_each": {"type": "integer", "default": 3000},
                },
                "required": ["urls"],
            },
        ),
        Tool(
            name="extract_structured",
            description="Extract elements from a page using a CSS selector",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "selector": {"type": "string", "description": "CSS selector e.g. 'h2', '.price', '#content p'"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["url", "selector"],
            },
        ),
        Tool(
            name="get_page_metadata",
            description="Get title, description, and Open Graph tags from a page",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "fetch_page":
            html = _fetch_html(arguments["url"])
            text = _html_to_text(html)
            max_chars = arguments.get("max_chars", 8000)
            text = text[:max_chars]
            if arguments.get("extract_links"):
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    links = [f"{a.get_text(strip=True)} → {a['href']}" for a in soup.find_all("a", href=True)[:20]]
                    text += "\n\nLinks:\n" + "\n".join(links)
                except ImportError:
                    pass
            result = text

        elif name == "fetch_multiple":
            import concurrent.futures
            urls = arguments["urls"][:5]
            max_c = arguments.get("max_chars_each", 3000)
            parts = []

            def _fetch_one(u):
                try:
                    html = _fetch_html(u, timeout=10)
                    return u, _html_to_text(html)[:max_c], None
                except Exception as e:
                    return u, "", str(e)

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                results = list(pool.map(_fetch_one, urls))

            for url, text, err in results:
                if err:
                    parts.append(f"--- {url} ---\nError: {err}")
                else:
                    parts.append(f"--- {url} ---\n{text}")
            result = "\n\n".join(parts)

        elif name == "extract_structured":
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                raise ImportError("Run: pip install beautifulsoup4")
            html = _fetch_html(arguments["url"])
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.select(arguments["selector"])[:arguments.get("limit", 20)]
            texts = [el.get_text(strip=True) for el in elements]
            result = f"Found {len(texts)} elements matching '{arguments['selector']}':\n" + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(texts))

        elif name == "get_page_metadata":
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                raise ImportError("Run: pip install beautifulsoup4")
            html = _fetch_html(arguments["url"])
            soup = BeautifulSoup(html, "html.parser")
            meta = {}
            title_tag = soup.find("title")
            if title_tag:
                meta["title"] = title_tag.get_text(strip=True)
            for tag in soup.find_all("meta"):
                name_attr = tag.get("name", tag.get("property", ""))
                content = tag.get("content", "")
                if name_attr in ("description", "og:title", "og:description", "og:image", "twitter:title"):
                    meta[name_attr] = content
            result = "\n".join(f"{k}: {v}" for k, v in meta.items())

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
