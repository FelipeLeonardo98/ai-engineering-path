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
            DROP TABLE IF EXISTS customer_channel_events;
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

            CREATE TABLE customer_channel_events (
                event_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                notes TEXT NOT NULL,
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
                (124, "Ana Costa", "ana.costa@example.com", "mid-market", "active", "email"),
                (125, "Marcos Lima", "marcos.lima@example.com", "startup", "at_risk", "voice"),
                (126, "Carol Souza", "carol.souza@example.com", "enterprise", "active", "voice"),
                (127, "Bruno Rocha", "bruno.rocha@example.com", "mid-market", "active", "chat"),
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
                (9005, 126, "2026-05-05", 1320.00, "paid"),
                (9006, 126, "2026-05-07", 210.75, "paid"),
                (9007, 127, "2026-05-08", 540.20, "paid"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO customer_channel_events
                (event_id, customer_id, channel, event_timestamp, event_type, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, 123, "chat", "2026-05-01 09:05:00", "support_message", "Asked about invoice status"),
                (2, 123, "whatsapp", "2026-05-01 11:20:00", "follow_up", "Confirmed payment date"),
                (3, 123, "email", "2026-05-02 15:45:00", "document_sent", "Sent invoice copy"),
                (4, 123, "whatsapp", "2026-05-03 10:10:00", "support_message", "Asked for receipt"),
                (5, 124, "email", "2026-05-01 08:30:00", "campaign_open", "Opened onboarding email"),
                (6, 124, "chat", "2026-05-01 14:15:00", "support_message", "Asked about setup"),
                (7, 124, "voice", "2026-05-02 09:00:00", "callback", "Talked with support"),
                (8, 124, "email", "2026-05-04 17:25:00", "follow_up", "Received setup checklist"),
                (9, 125, "whatsapp", "2026-05-02 12:40:00", "support_message", "Reported failed payment"),
                (10, 125, "voice", "2026-05-02 16:05:00", "callback", "Payment issue investigated"),
                (11, 125, "chat", "2026-05-03 09:50:00", "support_message", "Asked for retry link"),
                (12, 125, "voice", "2026-05-05 13:30:00", "escalation", "Escalated payment failure"),
                (13, 126, "chat", "2026-05-01 09:10:00", "support_message", "Asked about enterprise plan"),
                (14, 126, "whatsapp", "2026-05-01 10:35:00", "follow_up", "Requested proposal details"),
                (15, 126, "email", "2026-05-02 18:00:00", "document_sent", "Received proposal"),
                (16, 126, "chat", "2026-05-03 11:45:00", "support_message", "Asked about SLA"),
                (17, 126, "voice", "2026-05-03 16:20:00", "callback", "Negotiated contract"),
                (18, 127, "chat", "2026-05-04 10:00:00", "support_message", "Asked about trial"),
                (19, 127, "email", "2026-05-04 12:10:00", "campaign_open", "Opened trial guide"),
                (20, 127, "whatsapp", "2026-05-05 15:55:00", "follow_up", "Requested activation help"),
                (21, 127, "chat", "2026-05-06 09:35:00", "support_message", "Confirmed account activation"),
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

    if not {"customers", "orders", "customer_channel_events"}.issubset(existing_tables):
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
    sections.append(
        "\nBusiness meaning:\n"
        "- customers.current_channel is the latest known channel snapshot.\n"
        "- customer_channel_events stores the chronological channel journey.\n"
        "- Use event_timestamp to sort customer interactions by time.\n"
        "- Use MAX(event_timestamp) or ORDER BY event_timestamp DESC LIMIT 1 "
        "to find the latest interaction.\n"
        "- Use COUNT, GROUP BY, MIN, MAX, and ORDER BY for analytical questions."
    )
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
