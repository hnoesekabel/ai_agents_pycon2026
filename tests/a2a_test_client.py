"""Shared A2A test client for agent communication."""

import asyncio
import logging
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, Client, ClientFactory, ClientConfig
from a2a.types import AgentCard, Message, TextPart, Part, Role, TaskState, Task
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH, EXTENDED_AGENT_CARD_PATH


async def run_a2a_client(host: str, port: int, query: str) -> None:
    """Connect to an A2A agent and run a query."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    base_url = f"http://{host}:{port}"

    async with httpx.AsyncClient(timeout=90) as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=base_url,
        )

        # Fetch Public Agent Card and Initialize Client
        final_agent_card_to_use: AgentCard | None = None

        try:
            logger.info(
                "Attempting to fetch public agent card from: %s",
                f"{base_url}{AGENT_CARD_WELL_KNOWN_PATH}"
            )
            _public_card = await resolver.get_agent_card()
            logger.info("Successfully fetched public agent card:")
            logger.info(_public_card.model_dump_json(indent=2, exclude_none=True))
            final_agent_card_to_use = _public_card
            logger.info(
                "\nUsing PUBLIC agent card for client initialization (default)."
            )

            if _public_card.supports_authenticated_extended_card:
                try:
                    logger.info(
                        "\nPublic card supports authenticated extended card. "
                        "Attempting to fetch from: %s",
                        f"{base_url}{EXTENDED_AGENT_CARD_PATH}"
                    )
                    auth_headers_dict = {
                        "Authorization": "Bearer dummy-token-for-extended-card"
                    }
                    _extended_card = await resolver.get_agent_card(
                        relative_card_path=EXTENDED_AGENT_CARD_PATH,
                        http_kwargs={"headers": auth_headers_dict},
                    )
                    logger.info(
                        "Successfully fetched authenticated extended agent card:"
                    )
                    logger.info(
                        _extended_card.model_dump_json(indent=2, exclude_none=True)
                    )
                    final_agent_card_to_use = _extended_card
                    logger.info(
                        "\nUsing AUTHENTICATED EXTENDED agent card for client "
                        "initialization."
                    )
                except Exception as e_extended:  # pylint: disable=broad-except
                    logger.warning(
                        "Failed to fetch extended agent card: %s - proceed with public card.",
                        e_extended,
                        exc_info=True,
                    )
            elif _public_card:
                logger.info(
                    "\nPublic card does not indicate support for extended card. Using public card."
                )

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Critical error fetching public agent card: %s",
                e, exc_info=True
            )
            raise RuntimeError(
                "Failed to fetch the public agent card. Cannot continue."
            ) from e

        factory = ClientFactory(ClientConfig(httpx_client=httpx_client))
        client = factory.create(final_agent_card_to_use)
        logger.info("A2AClient initialized.")

        try:
            await handle_conversation(client, query)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error("Error when handling the conversation: %s", e)
        finally:
            await asyncio.sleep(0.1)


async def handle_conversation(
    client: Client,
    text: str,
    task_id: str | None = None,
    context_id: str | None = None
):
    """Handle streaming conversation with the agent."""
    message = build_message(text, task_id, context_id)
    logging.info("Processing: %s", text)
    try:
        async for update in client.send_message(message):
            if isinstance(update, tuple):
                task, _ = update
                if task:
                    await handle_task(task, update, client)
    except asyncio.CancelledError:
        pass
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.info("Stream error: %s", e)


def build_message(
    text: str,
    task_id: str | None = None,
    context_id: str | None = None
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


async def handle_task(task: Task, update: tuple, client: Client) -> str | None:
    """Handle the incoming task from the agent.

    Task has a state, that could be "completed", then return the result.
    Or it could be "input_required", then show the agent's request for more info.
    """
    latest_task_id = task.id if hasattr(task, "id") else None
    latest_context_id = task.context_id if hasattr(task, "context_id") else None

    if hasattr(task, "status") and hasattr(task.status, "state"):

        if task.status.state == TaskState.completed:
            if content := extract_text_content(update):
                logging.info("\n%s", content)
            return content

        if task.status.state == TaskState.input_required:
            if (hasattr(task.status, "message")
                and hasattr(task.status.message, "parts")
                and task.status.message
            ):
                for part in task.status.message.parts:
                    if hasattr(part, 'root') and hasattr(part.root, 'text'):
                        logging.info("\n%s", part.root.text)  # type: ignore

            follow_up = input("\nYour reply: ")
            await handle_conversation(
                client,
                follow_up,
                latest_task_id,
                latest_context_id
            )
            return None


def extract_text_content(update: tuple) -> str | None:
    """Extract text content from streaming updates."""
    try:
        if isinstance(update, tuple) and len(update) >= 2:
            task, _ = update
            if hasattr(task, 'artifacts') and task.artifacts:
                for artifact in task.artifacts:
                    if hasattr(artifact, 'parts') and artifact.parts:
                        for part in artifact.parts:
                            if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                return part.root.text
        return None
    except Exception:  # pylint: disable=broad-except
        return None
