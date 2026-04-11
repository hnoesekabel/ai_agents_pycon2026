"""Define required models for Agent operation."""

from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Coordination Agent State"""

    messages: Annotated[list, add_messages]
    user_query: str
    status: str | None
    sender: str | None
    recipient: str | None
    name: str | None
    url: str | None
    linkedin: str | None
    company_id: int | None
    company_data: dict | None
    offering: str | None
    news: str | None
    response_email: str | None
    response_message: str | None
    response: str | None
    ceo_email: str | None
    ceo_linkedin: str | None
    start_time: float | None
    end_time: float | None


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal["input_required", "working", "finishing", "completed", "error"] = (
        "working"
    )
    message: dict[str, str]
