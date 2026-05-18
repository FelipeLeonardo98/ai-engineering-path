from __future__ import annotations

import argparse
import asyncio
import ast
import json
import os
import re
import sys
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_sqlite_ollama import db


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
#OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


SYSTEM_PROMPT = """You are a local AI engineering demo agent connected to an MCP SQLite server.
Choose exactly one MCP tool call that can help answer the user question.
Return only JSON with this shape:
{"tool": "list_tables" | "describe_table" | "get_customer_by_id" | "query_readonly" | "none", "arguments": {...}, "reason": "..."}

Rules:
- Prefer get_customer_by_id when the user asks for one customer by ID.
- Use list_tables for table inventory questions.
- Use describe_table when the user asks about columns or schema for one table.
- Use query_readonly for analytical questions involving counts, groups, dates, latest/earliest values, ordering, customer names, or channel history.
- Generate SQLite SQL only.
- Use COUNT(*) for counts, GROUP BY for grouping, ORDER BY for sorting, MIN/MAX for earliest/latest dates, and LIMIT when asking for one latest or first record.
- Use LOWER(column) for case-insensitive filters and LIKE for partial customer names.
- Use customer_channel_events for chronological customer journey or channel history questions.
- Use customers.current_channel only for the latest known channel snapshot.
- Never generate write SQL. No INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, ATTACH, or VACUUM.
- If the question cannot be answered from the local database, choose "none".
- Return the "reason" field to explain your tool choice in simple language.
- Return the "sql" argument for query_readonly decisions/tool

Examples:
- How many customers are in WhatsApp?
  {"tool": "query_readonly", "arguments": {"sql": "SELECT COUNT(*) AS customer_count FROM customers WHERE LOWER(current_channel) = 'whatsapp'"}, "reason": "Count customers by current channel."}
- How many customers are in each current channel?
  {"tool": "query_readonly", "arguments": {"sql": "SELECT current_channel, COUNT(*) AS customer_count FROM customers GROUP BY current_channel ORDER BY customer_count DESC"}, "reason": "Group customers by current channel."}
- Which channels did Carol use, oldest first?
  {"tool": "query_readonly", "arguments": {"sql": "SELECT e.channel, e.event_timestamp FROM customer_channel_events e JOIN customers c ON c.customer_id = e.customer_id WHERE LOWER(c.full_name) LIKE '%carol%' ORDER BY e.event_timestamp ASC"}, "reason": "Read Carol's chronological channel journey."}
- What was Carol's last channel?
  {"tool": "query_readonly", "arguments": {"sql": "SELECT e.channel, e.event_timestamp FROM customer_channel_events e JOIN customers c ON c.customer_id = e.customer_id WHERE LOWER(c.full_name) LIKE '%carol%' ORDER BY e.event_timestamp DESC LIMIT 1"}, "reason": "Find Carol's latest interaction."}
"""


def _extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"Ollama did not return JSON: {text}")
    return json.loads(text[start : end + 1])


def _normalize_decision(decision: dict[str, Any]) -> dict[str, Any]:
    arguments = decision.get("arguments", {})
    if isinstance(arguments, str):
        arguments = json.loads(arguments) if arguments.strip() else {}
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError(f"Tool arguments must be a JSON object, got: {arguments!r}")
    decision["arguments"] = arguments
    return decision


def _known_customer_filter(question: str) -> str | None:
    lowered = question.lower()
    try:
        rows = db.query_readonly("SELECT full_name FROM customers")
    except Exception:
        return None

    for row in rows:
        full_name = str(row["full_name"])
        name_parts = full_name.lower().split()
        if re.search(rf"\b{re.escape(full_name.lower())}\b", lowered):
            return full_name
        if name_parts and re.search(rf"\b{re.escape(name_parts[0])}\b", lowered):
            return name_parts[0]
    return None


def _extract_channel(question: str) -> str | None:
    lowered = question.lower()
    channel_aliases = {
        "whatsapp": "whatsapp",
        "zap": "whatsapp",
        "voice": "voice",
        "voz": "voice",
        "chat": "chat",
        "email": "email",
        "e-mail": "email",
    }
    for alias, channel in channel_aliases.items():
        if alias in lowered:
            return channel
    return None


def _route_simple_question(question: str) -> dict[str, Any] | None:
    lowered = question.lower()
    customer_match = re.search(r"\bcustomer\s+(\d+)\b", lowered)
    known_customer = _known_customer_filter(question)
    channel = _extract_channel(question)

    if "table" in lowered and any(word in lowered for word in ["what", "list", "exist", "available"]):
        return {"tool": "list_tables", "arguments": {}, "reason": "Deterministic table listing route."}

    if any(word in lowered for word in ["how many", "quantos", "quantas"]) and channel:
        return {
            "tool": "query_readonly",
            "arguments": {
                "sql": (
                    "SELECT current_channel, COUNT(*) AS customer_count "
                    "FROM customers "
                    f"WHERE LOWER(current_channel) = '{channel}' "
                    "GROUP BY current_channel"
                )
            },
            "reason": "Deterministic count by current channel route.",
        }

    if any(phrase in lowered for phrase in ["each current channel", "cada canal", "por canal", "by channel"]):
        return {
            "tool": "query_readonly",
            "arguments": {
                "sql": (
                    "SELECT current_channel, COUNT(*) AS customer_count "
                    "FROM customers "
                    "GROUP BY current_channel "
                    "ORDER BY current_channel ASC"
                )
            },
            "reason": "Deterministic grouping by current channel route.",
        }

    if known_customer and any(phrase in lowered for phrase in ["last channel", "ultimo canal", "último canal", "ultima canal", "última canal"]):
        return {
            "tool": "query_readonly",
            "arguments": {
                "sql": (
                    "SELECT c.full_name, e.channel, e.event_timestamp, e.event_type "
                    "FROM customer_channel_events e "
                    "JOIN customers c ON c.customer_id = e.customer_id "
                    f"WHERE LOWER(c.full_name) LIKE '%{known_customer.lower()}%' "
                    "ORDER BY e.event_timestamp DESC "
                    "LIMIT 1"
                )
            },
            "reason": "Deterministic latest channel route.",
        }

    if known_customer and any(word in lowered for word in ["channels", "canais", "passou", "history", "journey"]):
        order = "DESC" if any(word in lowered for word in ["desc", "decrescente", "newest", "recent"]) else "ASC"
        return {
            "tool": "query_readonly",
            "arguments": {
                "sql": (
                    "SELECT c.full_name, e.channel, e.event_timestamp, e.event_type "
                    "FROM customer_channel_events e "
                    "JOIN customers c ON c.customer_id = e.customer_id "
                    f"WHERE LOWER(c.full_name) LIKE '%{known_customer.lower()}%' "
                    f"ORDER BY e.event_timestamp {order}"
                )
            },
            "reason": "Deterministic customer channel history route.",
        }

    if any(phrase in lowered for phrase in ["earliest interaction", "first interaction", "primeira interação", "primeiro contato"]):
        return {
            "tool": "query_readonly",
            "arguments": {
                "sql": (
                    "SELECT c.full_name, e.channel, e.event_timestamp, e.event_type "
                    "FROM customer_channel_events e "
                    "JOIN customers c ON c.customer_id = e.customer_id "
                    "ORDER BY e.event_timestamp ASC "
                    "LIMIT 1"
                )
            },
            "reason": "Deterministic earliest interaction route.",
        }

    if customer_match:
        return {
            "tool": "get_customer_by_id",
            "arguments": {"customer_id": int(customer_match.group(1))},
            "reason": "Deterministic customer lookup route.",
        }

    return None


async def ollama_generate(prompt: str, model: str = OLLAMA_MODEL) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Could not call Ollama at {OLLAMA_URL}/api/chat with model {model}. "
            "Confirm Ollama is running and the configured model is pulled."
        ) from exc
    message = response.json().get("message", {})
    return str(message.get("content", "")).strip()


def _content_to_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(item))
    return "\n".join(parts)

def _resource_to_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "contents", []):
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(item))
    return "\n".join(parts)


def _format_query_result(tool_text: str) -> str:
    stripped = tool_text.strip()
    if stripped.startswith("{") and "\n}\n{" in stripped:
        stripped = "[" + re.sub(r"}\s*{", "},{", stripped) + "]"
    try:
        rows = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            rows = ast.literal_eval(stripped)
        except (SyntaxError, ValueError):
            return stripped

    if not rows:
        return "No rows found."
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return str(rows)

    formatted_rows: list[str] = []
    for index, row in enumerate(rows, start=1):
        if isinstance(row, dict):
            values = ", ".join(f"{key}: {value}" for key, value in row.items())
            formatted_rows.append(f"{index}. {values}")
        else:
            formatted_rows.append(f"{index}. {row}")
    return "\n".join(formatted_rows)


async def choose_tool(question: str, schema_context: str, sql_playbook: str) -> dict[str, Any]:
    deterministic_decision = _route_simple_question(question)
    if deterministic_decision is not None:
        return deterministic_decision

    prompt = f"""
        {SYSTEM_PROMPT}

        Available schema:
        {schema_context}

        SQL playbook:
        {sql_playbook}

        User question:
        {question}
        """
    raw = await ollama_generate(prompt)
    decision = _extract_json(raw)
    return _normalize_decision(decision)


async def answer_from_tool(question: str, tool_name: str, tool_result: str) -> str:
    prompt = f"""Answer the user from the MCP tool result.
The MCP tool result is authoritative.
Be concise.
If the result contains customer fields or numeric values, use them directly.
If the tool result contains multiple rows, preserve the exact row order.
Do not sort, regroup, or reinterpret rows after the SQL result is returned.
When dates or timestamps are present, print them exactly as provided.
Briefly explain which tool result supports the answer, without inventing extra reasoning.
Only say the local database does not contain enough information when the tool result is empty or explicitly says no data was found.

User question:
{question}

Tool used:
{tool_name}

Tool result:
{tool_result}
"""
    return await ollama_generate(prompt)


async def run_agent(question: str) -> str:
    db.ensure_database()
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_sqlite_ollama.server"],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}

            schema_resource = await session.read_resource("sqlite://schema")
            playbook_resource = await session.read_resource("docs://sql-playbook")

            schema_context = _resource_to_text(schema_resource)
            sql_playbook = _resource_to_text(playbook_resource)

            decision = await choose_tool(question, schema_context, sql_playbook)
            tool_name = decision.get("tool", "none")
            if tool_name == "none":
                return "I do not have enough local SQLite data to answer that question."
            if tool_name not in tool_names:
                return f"Ollama selected unavailable tool '{tool_name}'. Available tools: {sorted(tool_names)}"

            result = await session.call_tool(tool_name, arguments=decision.get("arguments", {}))
            tool_text = _content_to_text(result)

            # DEBUG
            debug_lines = [
                "Tool decision:",
                f"- tool: {tool_name}",
                f"- reason: {decision.get('reason', 'No reason provided.')}",
            ]
            sql = decision.get("arguments", {}).get("sql")
            if sql:
                debug_lines.extend([
                    "- sql:",
                    sql,
                ])

            debug_lines.append("")
            debug_lines.append("Tool result:")

            if tool_name == "query_readonly":
                final_result = _format_query_result(tool_text)
            else:
                final_result = await answer_from_tool(question, tool_name, tool_text)

            return "\n".join(debug_lines + [final_result])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask a local Ollama-backed MCP SQLite agent a question.")
    parser.add_argument("question", nargs="+", help="Question to ask the local agent.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    question = " ".join(args.question)
    print(asyncio.run(run_agent(question)))


if __name__ == "__main__":
    main()
