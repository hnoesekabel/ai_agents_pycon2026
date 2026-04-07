"""Core database functions."""

import os
import sqlite3

from db.util_sqlite import (
    run_sql_file_if_table_missing,
    table_exists,
)


class Database:
    """Core database functions."""

    def __init__(self, func_normalize=None, db_path: str | None = None) -> None:
        # get company name normalizer function if it was passed
        self._normalize_company = func_normalize

        # Use provided path or environment variable or default
        self.db_file = db_path or os.getenv("DB", "./db/db.sqlite")

        # Check if all tables exist - and add them if not
        (conn, _cursor) = self.get_cursor()
        for table, filename in (
            ("conversations", "./db/create_chat_history_table.sql"),
            ("messages", "./db/create_chat_history_table.sql"),
        ):
            if not table_exists(conn=conn, table=table):
                run_sql_file_if_table_missing(
                    db_path=self.db_file,
                    table_name=table,
                    sql_file=filename,
                )
        conn.close()


    def get_cursor(self) -> list:
        """Connect to SQLite database and return connection and cursor."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return [conn, conn.cursor()]
