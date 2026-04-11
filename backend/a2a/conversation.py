"""Handle the conversation with an Agent through A2A protocol."""

import asyncio
import logging
from uuid import uuid4

from a2a.client import Client
from a2a.types import Message, Part, Role, Task, TaskState, TextPart

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("a2a").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_conversation(
    client: Client, text: str, task_id: str | None = None, context_id: str | None = None
) -> str | None:
    """Handle conversation with the agent.

    Using the A2A client will automatically enable streaming support as
    indicated by the Agent Card.

    Args:
        client (Client): The client for the agent.
        text (str): The text to send to the agent. Usually the user question.
        task_id (str | None, optional): The task id. Defaults to None.
        context_id (str | None, optional): The context id. Defaults to None.
    """
    message = build_message(text, task_id, context_id)

    try:
        async for update in client.send_message(message):
            # Extract task info for continuation
            if isinstance(update, tuple):
                task, _ = update
                if task:
                    response = await handle_task(task, update)
                    if response != "None":
                        return response
    except asyncio.CancelledError:
        pass  # Handle graceful shutdown
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error when handling conversation: %s", e, exc_info=True)

    return None


def build_message(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> Message:
    """Build message payload for A2A communication."""
    return Message(
        kind="message",
        role=Role.user,
        parts=[Part(root=TextPart(kind="text", text=text))],
        message_id=uuid4().hex,
        task_id=task_id,
        context_id=context_id,
    )


async def handle_task(task: Task, update: tuple) -> str | None:
    """Handle the incoming task from the agent.

    Task has a state, that could be "completed", then print the result.
    Or it could be "input_required", then show the agent's request for more info.

    Args:
        task (Task): The task from the agent.
        update (tuple): The update from the agent.

    Returns:
        str | None: The response from the agent. None if its not relevant.
    """
    # Get status - handle both object and dict
    status = None
    if hasattr(task, "status"):
        status = task.status
    elif isinstance(task, dict) and "status" in task:
        status = task["status"]

    if not status:
        return "None"

    # Get state - handle both object and dict
    state = None
    if hasattr(status, "state"):
        state = status.state
    elif isinstance(status, dict) and "state" in status:
        state = status["state"]

    if not state:
        return "None"

    # Task is completed: return result
    if state == TaskState.completed:
        if content := extract_text_content(update):
            return content

    # Agent needs more information from user
    if state == TaskState.input_required:
        # Get message - handle both object and dict
        message = None
        if hasattr(status, "message"):
            message = status.message  # type: ignore
        elif isinstance(status, dict) and "message" in status:
            message = status["message"]

        if message:
            # Get parts - handle both object and dict
            parts = []
            if hasattr(message, "parts"):
                parts = message.parts
            elif isinstance(message, dict) and "parts" in message:
                parts = message["parts"]

            for part in parts:
                if text := _extract_text_from_part(part):
                    return text

    return "None"


def _extract_text_from_part(part) -> str | None:
    """Helper to extract text from a part, handling objects and dicts."""
    # Try object access
    if hasattr(part, "root"):
        root = part.root
        if hasattr(root, "text"):
            return root.text

    # Try dict access
    if isinstance(part, dict) and "root" in part:
        root = part["root"]
        if isinstance(root, dict) and "text" in root:
            return root["text"]
        if hasattr(root, "text"):
            return root.text  # type: ignore

    return None


def extract_text_content(update: tuple) -> str | None:
    """Extract text content from streaming updates."""
    try:
        if isinstance(update, tuple) and len(update) >= 2:
            task, _ = update
            if hasattr(task, "artifacts") and task.artifacts:
                for artifact in task.artifacts:
                    if hasattr(artifact, "parts") and artifact.parts:
                        for part in artifact.parts:
                            if text := _extract_text_from_part(part):
                                return text
        return None
    except Exception:  # pylint: disable=broad-except
        return None
