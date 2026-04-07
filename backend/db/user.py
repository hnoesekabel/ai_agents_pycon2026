"""Database functions for user-related datasets and endpoints."""

import logging

from backend.db.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserData:
    """Database functions for user-related datasets and endpoints.

    All datasets are stored in a SQLite database.

    Methods:
        add_user: create user entry for new users.
        get_watchlist: Retrieve company data of watchlist of a user.
        add_to_watchlist: Add a company to a user's watchlist.
        remove_from_watchlist: Remove a company from a user's watchlist.
        is_starred_by_user: Check if a company is on a user's watchlist.
        add_comment: add a comment to a company from the user.
    """

    def __init__(self):
        self.db = Database()

    def add_user(self, name: str, email: str, token: str, organization: str) -> int:
        """Create user entry for new users."""
        new_id = -1
        try:
            (conn, cursor) = self.db.get_cursor()
            cursor.execute(
                """
                INSERT INTO users
                (name, email, token, organization)
                VALUES (?, ?, ?, ?);
                """,
                (name, email, token, organization),
            )
            conn.commit()
            new_id = cursor.lastrowid
            conn.close()
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error adding user: %s", e)
        return new_id

    def get_user(self, user_id: int = -1, email: str = "") -> dict | None:
        """Retrieve user data from database by ID or email."""
        if user_id == -1 and not email:
            return None

        ALLOWED_COLUMNS = {"id", "email"}

        (conn, cursor) = self.db.get_cursor()
        column = "email"
        value = email
        if user_id != -1:
            column = "id"
            value = user_id

        if column not in ALLOWED_COLUMNS:
            raise ValueError(f"Invalid column: {column}")

        cursor.execute(f"SELECT * FROM users WHERE {column} = ?", (value,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_watchlist(self, user_id: int) -> list:
        """Retrieve the complete watchlist of a user."""
        (conn, cursor) = self.db.get_cursor()
        cursor.execute(
            """
            SELECT * FROM watchlist
            LEFT JOIN companies ON watchlist.company_id = companies.id
            WHERE watchlist.user_id = ?
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def add_to_watchlist(self, company_id: int, user_id: int) -> bool:
        """Add a company to a user's watchlist."""
        if not self.is_starred_by_user(company_id=company_id, user_id=user_id):
            return self._watchlist_modification(
                company_id=company_id, user_id=user_id, add=True
            )
        return True

    def remove_from_watchlist(self, company_id: int, user_id: int) -> bool:
        """Remove a company from a user's watchlist."""
        if self.is_starred_by_user(company_id=company_id, user_id=user_id):
            return self._watchlist_modification(
                company_id=company_id, user_id=user_id, add=False
            )
        return True

    def _watchlist_modification(self, company_id: int, user_id: int, add: bool) -> bool:
        """Add or remove a company from a user's watchlist."""
        sql = (
            "INSERT INTO watchlist (company_id, user_id) VALUES (?, ?);"
            if add
            else "DELETE FROM watchlist WHERE company_id = ? AND user_id = ?"
        )
        try:
            (conn, cursor) = self.db.get_cursor()
            cursor.execute(sql, (company_id, user_id))
            conn.commit()
            conn.close()
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error updating watchlist: %s", e)
            return False
        return True

    def is_starred_by_user(self, company_id: int, user_id: int) -> bool:
        """Check watchlist if a given user has starred a given company."""
        (conn, cursor) = self.db.get_cursor()
        cursor.execute(
            "SELECT * FROM watchlist WHERE company_id = ? AND user_id = ?",
            (company_id, user_id),
        )
        row = cursor.fetchone()
        conn.close()
        return bool(row)

    def add_activity(
        self, company_id: int, user_id: int, comment: str, pipeline: bool
    ) -> bool:
        """Add an activity on a company."""
        try:
            (conn, cursor) = self.db.get_cursor()
            cursor.execute(
                """
                INSERT INTO comments (company_id, user_id, comment, pipeline_activity)
                VALUES (?, ?, ?, ?);
                """,
                (company_id, user_id, comment, pipeline),
            )
            conn.commit()
            conn.close()
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error adding comment: %s", e)
            return False
        return True
