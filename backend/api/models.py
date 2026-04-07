"""Models defining incoming and outgoing message structures."""

from typing import Literal

from pydantic import BaseModel, RootModel


class ChatMessageModel(BaseModel):
    """Define data structure for a chat message within a conversation."""

    id: int
    role: Literal["user", "assistant"]
    created_at: str
    text: str


class ChatConversationModel(BaseModel):
    """Chat conversation containing chronologically ordered messages."""

    id: str
    created_at: str
    messages: list[ChatMessageModel]


class ChatHistoryModel(RootModel[dict[str, list[ChatConversationModel]]]):
    """Define data structure for the chat history grouped by date."""


class ChatHistoryResponseModel(BaseModel):
    """Full chat history payload returned by the API."""

    user_id: int
    history: ChatHistoryModel
