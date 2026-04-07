"""Workflow functions related to calling an agent through A2A protocol."""

import json
import os
import logging
import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory

from agent_coordinator.models import AgentState
from backend.a2a.conversation import handle_conversation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Map intent agent names to .env variable prefixes
AGENT_ENV_PREFIX = {
    "research": "RESEARCH",
    "outreach": "OUTREACH",
}

async def call_next_agent(state: AgentState) -> dict:
    """Call the next agent in the pending list via A2A and store its response."""
    pending = list(state.get("pending_agents", []))
    agent_responses = list(state.get("agent_responses", []))

    if not pending:
        return {"pending_agents": [], "agent_responses": agent_responses}

    agent_name = pending.pop(0)
    logger.info("📡 Calling agent: %s", agent_name)

    env_prefix = AGENT_ENV_PREFIX.get(agent_name)
    if not env_prefix:
        logger.warning("⚠️ Unknown agent '%s', skipping", agent_name)
        agent_responses.append({"agent": agent_name, "error": "unknown agent"})
        return {"pending_agents": pending, "agent_responses": agent_responses}

    host = os.getenv(f"HOST_{env_prefix}", "localhost")
    port = os.getenv(f"PORT_{env_prefix}")
    if not port:
        logger.warning("⚠️ No port configured for agent '%s', skipping", agent_name)
        agent_responses.append({"agent": agent_name, "error": "no port configured"})
        return {"pending_agents": pending, "agent_responses": agent_responses}

    base_url = f"http://{host}:{port}"

    logger.info(state)

    user_query = state.get("user_query", "")
    current_information = ""
    agent_responses = state.get("agent_responses", [])

    for entry in agent_responses:
        try:
            response = json.loads(entry.get("response", "{}"))
        except (json.JSONDecodeError, TypeError):
            current_information += entry.get("response", "") + "\n"
            continue
        message_raw = response.get("message", "")
        try:
            message = json.loads(message_raw)
        except (json.JSONDecodeError, TypeError):
            current_information += message_raw + "\n"
            continue
        if isinstance(message, dict):
            for key, value in message.items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                current_information += f"{key}: {value}\n"
        else:
            current_information += str(message) + "\n"

    logger.info(current_information)

    try:
        async with httpx.AsyncClient(timeout=90) as httpx_client:
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
            agent_card = await resolver.get_agent_card()
            client = ClientFactory(ClientConfig(httpx_client=httpx_client)).create(agent_card)
            response = await handle_conversation(client, current_information + user_query)
            logger.info("✅ Agent '%s' responded", agent_name)
            logger.info(response)
            agent_responses.append({"agent": agent_name, "response": response})
    except Exception as e:  # pylint: disable=broad-except
        logger.error("❌ Error calling agent '%s': %s", agent_name, e)
        agent_responses.append({"agent": agent_name, "error": str(e)})

    return {"pending_agents": pending, "agent_responses": agent_responses}
