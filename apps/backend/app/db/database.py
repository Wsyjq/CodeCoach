import os
import sqlite3
from pathlib import Path

from app.db.models import COLUMN_MIGRATIONS, SCHEMA_SQL

_configured_database_path = os.getenv("CODECOACH_DATABASE_PATH", "").strip()
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATABASE_PATH = (
    Path(_configured_database_path)
    if _configured_database_path
    else PROJECT_ROOT / "data" / "runtime" / "codecoach.db"
)


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        for statement in SCHEMA_SQL:
            connection.execute(statement)
        for table_name, columns in COLUMN_MIGRATIONS.items():
            existing_columns = {
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            for column_name, definition in columns.items():
                if column_name not in existing_columns:
                    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        connection.commit()
