"""Database functions for chat history datasets and endpoints."""

from datetime import datetime

from backend.db.database import Database


class ChatHistoryData:
    """Database functions for chat history datasets and endpoints.

    All datasets are stored in a SQLite database.

    Methods:
        get_chat_history: Retrieve the chat history for a user.
    """

    def __init__(self):
        self.db = Database()

    def add_message(
        self,
        user_id: int,
        role: str,
        text: str,
        chat_id: str,
    ) -> None:
        """Add a message to the chat history, create a new conversation if necessary.

        Args:
            user_id (str): user ID of the user interacting with the assistant. Only needed
                if a conversation is starting and needs to be created in database.
            role (str): role of the message sender, can be "user" or "assistant".
            text (str): message to add to the chat history - either user input or assistant
                response.
            chat_id (str): ID of the conversation to add the message to.
        """
        (conn, cursor) = self.db.get_cursor()
        # determine the internal conversation ID so message is correctly assigned
        conversation_id = self._conversation_exists(user_id, chat_id)
        if conversation_id == -1:
            conversation_id = self._add_conversation(user_id, chat_id)
        # add the message
        cursor.execute(
            """
            INSERT INTO messages (conversation_id, role, text)
            VALUES (?, ?, ?)
            """,
            (conversation_id, role, text),
        )
        conn.commit()
        conn.close()

    def _conversation_exists(self, user_id: int, chat_id: str) -> int:
        """Check if a conversation for a user already exists."""
        (conn, cursor) = self.db.get_cursor()
        cursor.execute(
            "SELECT id FROM conversations WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        row = cursor.fetchone()
        conn.close()
        return int(dict(row)["id"]) if row else -1

    def _add_conversation(self, user_id: int, chat_id: str) -> int:
        """Add a new conversation for a user."""
        (conn, cursor) = self.db.get_cursor()
        cursor.execute(
            """
            INSERT INTO conversations (user_id, chat_id, date)
            VALUES (?, ?, ?)
            """,
            (user_id, chat_id, datetime.now().strftime("%Y-%m-%d")),
        )
        conn.commit()
        conn.close()
        return cursor.lastrowid

    def get_conversations(self, user_id: int) -> list[dict]:
        """Retrieve the conversations for a user.

        Args:
            user_id (str): user ID of the user for which to get the conversations.

        Returns:
            list: dataset of the conversations for the requested user.
        """
        return self._run_sql(
            """
            SELECT id, date, chat_id, created_at FROM conversations
            WHERE conversations.user_id = ?
            ORDER BY conversations.created_at DESC
            """,
            user_id,
        )

    def get_messages_in_conversation(self, conversation_id: int) -> list[dict]:
        """Retrieve all messages in a conversation."""
        return self._run_sql(
            """
            SELECT id, role, text, created_at FROM messages
            WHERE messages.conversation_id = ?
            ORDER BY messages.created_at ASC
            """,
            conversation_id,
        )

    def _run_sql(self, sql: str, iid: int) -> list[dict]:
        conn, cursor = self.db.get_cursor()
        cursor.execute(sql, (iid,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
