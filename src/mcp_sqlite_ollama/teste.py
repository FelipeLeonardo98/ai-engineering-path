from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "docs" / "sql_playbook.md"


def load_sql_playbook() -> str:
    """Load the SQL playbook content from the markdown file."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"SQL playbook not found at {DATA_DIR}")
    return DATA_DIR.read_text(encoding="utf-8")

if __name__ == "__main__":
    playbook_content = load_sql_playbook()
    print(playbook_content)
