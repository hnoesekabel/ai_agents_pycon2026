"""Utilities for working with SQLite database."""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


# Database configuration
DB_FILENAME = "db.sqlite"
DB_BUSY_TIMEOUT = 30000  # 30 seconds
MAX_RETRY_ATTEMPTS = 5
RETRY_DELAY = 0.5  # seconds

@contextmanager
def get_db_connection(db_path: str = f"db/{DB_FILENAME}"):
    """
    Context manager for database connections with proper configuration.

    Args:
        db_path (str): Path to the database file

    Yields:
        sqlite3.Connection: Configured database connection
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=DB_BUSY_TIMEOUT / 1000.0)
        # Set busy timeout to handle concurrent access
        conn.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT}")
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        # Ensure foreign keys are enforced
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def execute_with_retry(func, max_attempts: int = MAX_RETRY_ATTEMPTS):
    """
    Execute a function with retry logic for database locked errors.

    Args:
        func: Function to execute
        max_attempts (int): Maximum number of retry attempts

    Returns:
        Result of the function

    Raises:
        sqlite3.OperationalError: If all retry attempts fail
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_attempts - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                continue
            raise
    raise sqlite3.OperationalError("Max retry attempts exceeded")


def run_sql_file_if_table_missing(
        db_path: str,
        table_name: str,
        sql_file: str
) -> None:
    """This function runs a SQL file if the table is missing

    Args:
        db_path (str): database path
        table_name (str): table name
        sql_file (str): SQL file name

    Returns:
        None
    """
    sql_text = Path(sql_file).read_text(encoding="utf-8")

    def create_table():
        with get_db_connection(db_path) as conn:
            if not table_exists(conn, table_name):
                conn.executescript(sql_text)

    execute_with_retry(create_table)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """This function checks if a table exists

    Args:
        conn (sqlite3.Connection): SQLite connection
        table (str): table name

    Returns:
        bool: returns True if the table exists, otherwise False.
    """
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND LOWER(name)=LOWER(?) LIMIT 1",
        (table,)
    ).fetchone() is not None

