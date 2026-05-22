"""
MCP Server: PostgreSQL
Lets Claude query, inspect, and manage a PostgreSQL database safely.

Usage:
    DATABASE_URL=postgresql://user:pass@host/db python -m servers.postgres

Tools exposed:
    - list_tables()
    - describe_table(table_name)
    - query(sql, params)          — SELECT only (read-safe)
    - execute(sql)                — INSERT/UPDATE/DELETE (requires ALLOW_WRITES=true)
    - get_schema()
"""
from __future__ import annotations

import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

DATABASE_URL = os.environ.get("DATABASE_URL", "")
ALLOW_WRITES = os.environ.get("ALLOW_WRITES", "false").lower() == "true"

app = Server("postgres")


def _get_conn():
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        raise ImportError("Run: pip install psycopg2-binary")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


@app.list_tools()
async def list_tools():
    tools = [
        Tool(
            name="list_tables",
            description="List all tables in the database",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="describe_table",
            description="Show columns, types, and constraints for a table",
            inputSchema={
                "type": "object",
                "properties": {"table_name": {"type": "string"}},
                "required": ["table_name"],
            },
        ),
        Tool(
            name="query",
            description="Run a read-only SELECT query",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT statement"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="get_schema",
            description="Get full schema DDL for all tables",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]
    if ALLOW_WRITES:
        tools.append(Tool(
            name="execute",
            description="Execute a write SQL statement (INSERT/UPDATE/DELETE). ALLOW_WRITES must be enabled.",
            inputSchema={
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        ))
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        conn = _get_conn()
        cur = conn.cursor()

        if name == "list_tables":
            cur.execute("""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            rows = cur.fetchall()
            result = "Tables:\n" + "\n".join(f"  {r['table_name']} ({r['table_type']})" for r in rows)

        elif name == "describe_table":
            tbl = arguments["table_name"]
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (tbl,))
            rows = cur.fetchall()
            if not rows:
                result = f"Table '{tbl}' not found."
            else:
                lines = [f"  {r['column_name']:30} {r['data_type']:20} {'NULL' if r['is_nullable']=='YES' else 'NOT NULL'}" for r in rows]
                result = f"Table: {tbl}\n{'Column':30} {'Type':20} Nullable\n" + "-"*65 + "\n" + "\n".join(lines)

        elif name == "query":
            sql = arguments["sql"].strip()
            if not sql.upper().startswith("SELECT"):
                result = "Error: Only SELECT queries allowed. Use 'execute' for writes (requires ALLOW_WRITES=true)."
            else:
                limit = arguments.get("limit", 50)
                # Auto-add LIMIT if not present
                if "LIMIT" not in sql.upper():
                    sql = f"{sql} LIMIT {limit}"
                cur.execute(sql)
                rows = cur.fetchall()
                if not rows:
                    result = "Query returned 0 rows."
                else:
                    headers = list(rows[0].keys())
                    lines = [" | ".join(str(r[h]) for h in headers) for r in rows]
                    result = " | ".join(headers) + "\n" + "-" * 60 + "\n" + "\n".join(lines)
                    result += f"\n\n({len(rows)} rows)"

        elif name == "get_schema":
            cur.execute("""
                SELECT table_name,
                       string_agg(column_name || ' ' || data_type, ', ' ORDER BY ordinal_position) as columns
                FROM information_schema.columns
                WHERE table_schema = 'public'
                GROUP BY table_name ORDER BY table_name
            """)
            rows = cur.fetchall()
            lines = [f"  {r['table_name']}({r['columns']})" for r in rows]
            result = "Schema:\n" + "\n".join(lines)

        elif name == "execute" and ALLOW_WRITES:
            sql = arguments["sql"].strip()
            cur.execute(sql)
            conn.commit()
            result = f"Executed. Rows affected: {cur.rowcount}"

        else:
            result = f"Unknown tool or writes not enabled: {name}"

        cur.close()
        conn.close()

    except Exception as e:
        result = f"Error: {e}"

    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
