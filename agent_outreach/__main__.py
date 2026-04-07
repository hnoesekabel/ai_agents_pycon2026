"""Start A2A server for Evaluation Agent."""

import asyncio
import logging
import os
import sys
import httpx
import uvicorn
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_outreach.agent import OutreachAgent
from agent_outreach.agent_executor import OutreachAgentExecutor

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BIND_HOST = "0.0.0.0"
CARD_HOST = os.getenv("HOST_OUTREACH", "localhost")
PORT = int(os.getenv("PORT_OUTREACH", "10002"))


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


async def main_async():
    """Creates the Company Information Agent card and starts the server."""
    try:
        if not os.getenv("CHAT_MODEL"):
            raise MissingAPIKeyError("CHAT_MODEL environment variable not set.")

        # general capabilities: streams responses, and supports push notifications
        capabilities = AgentCapabilities(streaming=True, push_notifications=True)
        # describe the agent skillset, and provide examples
        skill = AgentSkill(
            id="outreach_agent",
            name="Outreach Agent",
            description="Create outreach messages for email and LinkedIn to contact a company.",
            tags=[
                "email outreach",
                "linkedin outreach",
                "contact company",
                "contact person",
                "create outreach",
                "create message",
            ],
            examples=[
                "Please draft an email to the CEO of TD Reply GmbH (https://www.tdreply.de/).",
                "What is a good LinkedIn message to the CEO of TD Reply (https://www.tdreply.de/)?",
                "Help me draft an outreach message to the CEO of TD Reply.",
            ],
        )
        # create agent card with key info, capabilities and skills
        agent_card = AgentCard(
            name="Outreach Agent",
            description="Create outreach messages for email and LinkedIn to contact a company.",
            url=f"http://{CARD_HOST}:{PORT}/",
            version="1.0.0",
            default_input_modes=OutreachAgent.SUPPORTED_CONTENT_TYPES,
            default_output_modes=OutreachAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        # prepare a webserver to receive requests via A2A
        httpx_client = httpx.AsyncClient()
        push_config_store = InMemoryPushNotificationConfigStore()
        push_sender = BasePushNotificationSender(
            httpx_client=httpx_client, config_store=push_config_store
        )
        # create the actual agent and have its executor handle requests
        agent = await OutreachAgent.create()
        request_handler = DefaultRequestHandler(
            agent_executor=OutreachAgentExecutor(agent),
            task_store=InMemoryTaskStore(),
            push_config_store=push_config_store,
            push_sender=push_sender,
        )
        # start the A2A webserver
        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        ).build()
        server_instance = uvicorn.Server(
            uvicorn.Config(
                server,
                host=BIND_HOST,
                port=PORT
            )
        )
        await server_instance.serve()

    except MissingAPIKeyError as e:
        logger.error("Error: %s", e)
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("An error occurred during server startup: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except RuntimeError as e:
        logger.error("An error occurred: %s", e)
