"""Define required models for Agent operation."""

from typing import Annotated, Any, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


def merge_dicts(left: dict, right: dict) -> dict:
    """Merge two dictionaries. Left is the current state, right is the new update."""
    if not left:
        return right
    return left | right if right else left

class AgentStateBase(TypedDict):
    """Required AgentState fields."""
    messages: Annotated[list[AnyMessage | dict[str, Any]], add_messages]


class AgentState(AgentStateBase, total=False):
    """Coordination Agent State"""

    user_query: str
    status: str | None
    response: str | None
    start_time: float | None
    end_time: float | None


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal["input_required", "completed", "error"] = (
        "input_required"
    )  # can't have "working" in here, as the LLM will hijack it
    message: str
