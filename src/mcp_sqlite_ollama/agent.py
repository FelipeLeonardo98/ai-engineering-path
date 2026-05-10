from __future__ import annotations

import argparse
import asyncio
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
- Use query_readonly only for SELECT analysis.
- Never generate write SQL. No INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, ATTACH, or VACUUM.
- If the question cannot be answered from the local database, choose "none".
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


def _route_simple_question(question: str) -> dict[str, Any] | None:
    lowered = question.lower()
    customer_match = re.search(r"\bcustomer\s+(\d+)\b", lowered)

    if "table" in lowered and any(word in lowered for word in ["what", "list", "exist", "available"]):
        return {"tool": "list_tables", "arguments": {}, "reason": "Deterministic table listing route."}

    if customer_match and any(word in lowered for word in ["spent", "spend", "total", "amount", "value"]):
        customer_id = int(customer_match.group(1))
        return {
            "tool": "query_readonly",
            "arguments": {
                "sql": (
                    "SELECT c.customer_id, c.full_name, "
                    "COALESCE(SUM(o.amount_usd), 0) AS lifetime_value_usd "
                    "FROM customers c "
                    "LEFT JOIN orders o ON o.customer_id = c.customer_id "
                    f"WHERE c.customer_id = {customer_id} "
                    "GROUP BY c.customer_id"
                )
            },
            "reason": "Deterministic customer spending route.",
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


async def choose_tool(question: str) -> dict[str, Any]:
    deterministic_decision = _route_simple_question(question)
    if deterministic_decision is not None:
        return deterministic_decision

    prompt = f"{SYSTEM_PROMPT}\n\nAvailable schema:\n{db.database_schema()}\n\nUser question: {question}"
    raw = await ollama_generate(prompt)
    decision = _extract_json(raw)
    return _normalize_decision(decision)


async def answer_from_tool(question: str, tool_name: str, tool_result: str) -> str:
    prompt = f"""Answer the user from the MCP tool result.
The MCP tool result is authoritative.
Be concise.
If the result contains customer fields or numeric values, use them directly.
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

            decision = await choose_tool(question)
            tool_name = decision.get("tool", "none")
            if tool_name == "none":
                return "I do not have enough local SQLite data to answer that question."
            if tool_name not in tool_names:
                return f"Ollama selected unavailable tool '{tool_name}'. Available tools: {sorted(tool_names)}"

            result = await session.call_tool(tool_name, arguments=decision.get("arguments", {}))
            tool_text = _content_to_text(result)
            final_answer = await answer_from_tool(question, tool_name, tool_text)
            return final_answer


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
