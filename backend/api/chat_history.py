"""Endpoints for handling the chat history."""

from fastapi import Depends

from backend.api.dependencies import get_userid
from backend.api.models import ChatHistoryModel, ChatHistoryResponseModel
from backend.db.chat_history import ChatHistoryData


class ChatHistory:
    """Endpoints for handling the chat history.
    Attributes:
        None

    Methods:
        get_chat_history: Get the chat history for a user.
    """

    def __init__(self):
        self.db_chat_history = ChatHistoryData()

    def get_chat_history(self, user_id: int = Depends(get_userid)) -> dict:
        """Return a mocked chat history grouped per day with alternating roles.

        If a valid company ID is given in the assistant response, add the company
        data to the message text.

        Args:
            user_id (str): user ID of the user for which to get the chat history.

        Returns:
            dict: dataset of the chat history for the requested user.
        """
        history = {}
        for conversation in self.db_chat_history.get_conversations(user_id=user_id):
            conv_date = conversation["date"]
            if conv_date not in history:
                history[conv_date] = []

            messages = self.db_chat_history.get_messages_in_conversation(
                conversation["id"]
            )

            history[conv_date].append(
                {
                    "id": conversation["chat_id"],
                    "created_at": conversation["created_at"],
                    "messages": messages,
                }
            )

        history_payload = ChatHistoryModel.model_validate(history)
        response = ChatHistoryResponseModel(
            user_id=user_id,
            history=history_payload,
        )

        return response.model_dump()
