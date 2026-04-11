"""Discover Agent through A2A protocol and create a client."""

import logging

import httpx

from a2a.client import A2ACardResolver
from a2a.types import AgentCard
from a2a.utils.constants import EXTENDED_AGENT_CARD_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def discover_agent(host: str, port: int) -> AgentCard:
    """Discover an Agent, extract the Agent Card and create a Client.

    Will retrieve the public or extended Agent Card, depending on availability
    from the well-known URL on the given host and port.

    Args:
        host: Hostname of the Agent
        port: Port of the Agent

    Returns:
        Client: A2AClient for the Agent based on the Agent Card.
    """
    base_url = f"http://{host}:{port}"

    async with httpx.AsyncClient(timeout=90) as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=base_url,
        )
        # Fetch Public Agent Card and Initialize Client
        agent_card: AgentCard | None = None

        try:
            _public_card = await resolver.get_agent_card()
            agent_card = _public_card

            if _public_card.supports_authenticated_extended_card:
                try:
                    _extended_card = await resolver.get_agent_card(
                        relative_card_path=EXTENDED_AGENT_CARD_PATH,
                        http_kwargs={
                            "headers": {
                                "Authorization": "Bearer dummy-token-for-extended-card"
                            }
                        },
                    )
                    agent_card = _extended_card  # Update to use the extended card
                except Exception as e_extended:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Failed to fetch extended agent card: %s. "
                        "Will proceed with public card.",
                        e_extended,
                        exc_info=True,
                    )

        except Exception as e:
            raise RuntimeError(
                "Failed to fetch the public agent card. Cannot continue."
            ) from e

        return agent_card
