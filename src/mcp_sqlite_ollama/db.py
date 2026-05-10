from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "week9_mcp.db"

_DANGEROUS_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|vacuum|pragma|reindex)\b",
    re.IGNORECASE,
)


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS customers;

            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                segment TEXT NOT NULL,
                status TEXT NOT NULL,
                current_channel TEXT NOT NULL
            );

            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                amount_usd REAL NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );
            """
        )

        conn.executemany(
            """
            INSERT INTO customers
                (customer_id, full_name, email, segment, status, current_channel)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (123, "Joao Silva", "joao.silva@example.com", "enterprise", "active", "whatsapp"),
                (124, "Ana Costa", "ana.costa@example.com", "mid-market", "active", "chat"),
                (125, "Marcos Lima", "marcos.lima@example.com", "startup", "at_risk", "voice"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO orders
                (order_id, customer_id, order_date, amount_usd, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (9001, 123, "2026-04-12", 1490.00, "paid"),
                (9002, 123, "2026-04-27", 780.50, "paid"),
                (9003, 124, "2026-05-02", 245.00, "pending"),
                (9004, 125, "2026-05-04", 99.90, "failed"),
            ],
        )


def ensure_database(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        initialize_database(db_path)
        return

    try:
        existing_tables = set(list_tables(db_path))
    except sqlite3.DatabaseError:
        initialize_database(db_path)
        return

    if not {"customers", "orders"}.issubset(existing_tables):
        initialize_database(db_path)


def list_tables(db_path: Path = DB_PATH) -> list[str]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    return [row["name"] for row in rows]


def describe_table(table_name: str, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    if table_name not in list_tables(db_path):
        raise ValueError(f"Unknown table: {table_name}")

    with connect(db_path) as conn:
        rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()

    return [
        {
            "name": row["name"],
            "type": row["type"],
            "not_null": bool(row["notnull"]),
            "primary_key": bool(row["pk"]),
        }
        for row in rows
    ]


def database_schema(db_path: Path = DB_PATH) -> str:
    sections: list[str] = []
    for table in list_tables(db_path):
        columns = describe_table(table, db_path)
        column_text = ", ".join(
            f"{column['name']} {column['type']}{' primary key' if column['primary_key'] else ''}"
            for column in columns
        )
        sections.append(f"- {table}: {column_text}")
    return "\n".join(sections)


def get_customer_by_id(customer_id: int, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                c.customer_id,
                c.full_name,
                c.email,
                c.segment,
                c.status,
                c.current_channel,
                COALESCE(SUM(o.amount_usd), 0) AS lifetime_value_usd,
                COUNT(o.order_id) AS order_count
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.customer_id
            WHERE c.customer_id = ?
            GROUP BY c.customer_id
            """,
            (customer_id,),
        ).fetchone()

    return dict(row) if row else None


def validate_readonly_select(sql: str) -> str:
    normalized = sql.strip()
    if not normalized:
        raise ValueError("SQL cannot be empty.")
    if ";" in normalized.rstrip(";"):
        raise ValueError("Only one SQL statement is allowed.")
    normalized = normalized.rstrip(";").strip()
    if not re.match(r"^(select|with)\b", normalized, re.IGNORECASE):
        raise ValueError("Only SELECT or WITH queries are allowed.")
    if _DANGEROUS_SQL.search(normalized):
        raise ValueError("Write, schema, attachment, and pragma statements are not allowed.")
    return normalized


def query_readonly(sql: str, limit: int = 20, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    safe_sql = validate_readonly_select(sql)
    bounded_limit = max(1, min(limit, 100))

    with connect(db_path) as conn:
        conn.execute("PRAGMA query_only = ON")
        rows = conn.execute(f"SELECT * FROM ({safe_sql}) LIMIT ?", (bounded_limit,)).fetchall()

    return [dict(row) for row in rows]
