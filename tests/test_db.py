from __future__ import annotations

import pytest

from mcp_sqlite_ollama import db


@pytest.fixture()
def sqlite_file(tmp_path):
    path = tmp_path / "week9.db"
    db.initialize_database(path)
    return path


def test_lists_seeded_tables(sqlite_file):
    assert db.list_tables(sqlite_file) == ["customer_channel_events", "customers", "orders"]


def test_get_customer_by_id_includes_order_summary(sqlite_file):
    customer = db.get_customer_by_id(123, sqlite_file)
    assert customer is not None
    assert customer["full_name"] == "Joao Silva"
    assert customer["order_count"] == 2
    assert customer["lifetime_value_usd"] == 2270.5


def test_customer_channel_history_can_be_ordered(sqlite_file):
    rows = db.query_readonly(
        """
        SELECT e.channel, e.event_timestamp
        FROM customer_channel_events e
        JOIN customers c ON c.customer_id = e.customer_id
        WHERE LOWER(c.full_name) LIKE '%carol%'
        ORDER BY e.event_timestamp ASC
        """,
        db_path=sqlite_file,
    )
    assert [row["channel"] for row in rows] == ["chat", "whatsapp", "email", "chat", "voice"]


def test_latest_customer_channel(sqlite_file):
    rows = db.query_readonly(
        """
        SELECT e.channel, e.event_timestamp
        FROM customer_channel_events e
        JOIN customers c ON c.customer_id = e.customer_id
        WHERE LOWER(c.full_name) LIKE '%carol%'
        ORDER BY e.event_timestamp DESC
        LIMIT 1
        """,
        db_path=sqlite_file,
    )
    assert rows == [{"channel": "voice", "event_timestamp": "2026-05-03 16:20:00"}]


def test_readonly_query_allows_select(sqlite_file):
    rows = db.query_readonly(
        "SELECT customer_id, full_name FROM customers WHERE customer_id = 123",
        db_path=sqlite_file,
    )
    assert rows == [{"customer_id": 123, "full_name": "Joao Silva"}]


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE customers",
        "DELETE FROM customers",
        "SELECT * FROM customers; DROP TABLE customers",
        "PRAGMA table_info(customers)",
    ],
)
def test_readonly_query_rejects_unsafe_sql(sqlite_file, sql):
    with pytest.raises(ValueError):
        db.query_readonly(sql, db_path=sqlite_file)
