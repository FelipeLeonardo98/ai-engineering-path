from __future__ import annotations

from mcp_sqlite_ollama.db import DB_PATH, initialize_database


def main() -> None:
    initialize_database()
    print(f"Initialized SQLite database at {DB_PATH}")


if __name__ == "__main__":
    main()
