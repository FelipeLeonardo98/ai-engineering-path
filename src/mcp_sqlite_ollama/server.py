from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_sqlite_ollama import db


mcp = FastMCP(
    "week9-sqlite-mcp",
    instructions=(
        "Local learning MCP server exposing read-only SQLite context and tools. "
        "Use fixed tools when possible; use query_readonly only for SELECT-style analysis."
    ),
)


@mcp.resource("sqlite://schema")
def sqlite_schema() -> str:
    """Return the read-only SQLite schema exposed to the AI client."""
    return db.database_schema()


@mcp.tool()
def list_tables() -> list[str]:
    """List available business tables in the local SQLite database."""
    return db.list_tables()


@mcp.tool()
def describe_table(table_name: str) -> list[dict[str, Any]]:
    """Describe columns for one known SQLite table."""
    return db.describe_table(table_name)


@mcp.tool()
def get_customer_by_id(customer_id: int) -> dict[str, Any] | str:
    """Safely fetch one customer by ID, including simple order summary fields."""
    customer = db.get_customer_by_id(customer_id)
    if customer is None:
        return f"No customer found for customer_id={customer_id}."
    return customer


@mcp.tool()
def query_readonly(sql: str, limit: int = 20) -> list[dict[str, Any]]:
    """Run one SELECT-only query against SQLite with a hard result limit."""
    return db.query_readonly(sql, limit=limit)


def main() -> None:
    db.ensure_database()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
