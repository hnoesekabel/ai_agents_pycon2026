"""Workflow functions related to discern user intent and route to the right agent(s)."""


import contextlib
import json
import logging
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from agent_coordinator.models import AgentState
from agent_coordinator.prompts.intent import PROMPT_INTENT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_user_query(state: AgentState) -> dict:
    """Extract the original user query from first message."""
    # get the timing
    start_time = time.perf_counter()
    messages = state.get("messages", [])
    user_query = ""
    # get the HumanMessage and place it in the AgentState (for doc purpose only)
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            logger.info("📝 Extracted original user query: '%s'", user_query[:100])
            break

    if not user_query:
        logger.warning("⚠️ No user query found in initial messages")
        user_query = "No query provided"
    # add the user query to the AgentState and set status to "working"
    return {
        "user_query": user_query,
        "status": "working",
        "start_time": start_time,
    }


async def get_intent(agent, state: AgentState) -> dict:
    """Get the user's intent from the CoordinatorAgent's state."""
    query = state.get("user_query", "")
    messages = [
        SystemMessage(content=PROMPT_INTENT),
        HumanMessage(content=query),
    ]

    agent_response = await agent.ainvoke(input={"messages": messages})

    # Ensure we keep conversation messages, so workflow can continue.
    output_state: dict = {
        "messages": agent_response.get("messages", []),
    }

    ai_message = next(
        (
            msg
            for msg in reversed(output_state["messages"])
            if msg.__class__.__name__ == "AIMessage"
        ),
        None,
    )
    if ai_message is not None:
        intent_data = _parse_intent_from_text(ai_message.content)
        output_state["intent"] = intent_data
    else:
        output_state["intent"] = {}

    logger.info("📊 Parsed intent data: %s", output_state["intent"])
    logger.info(output_state)

    return output_state

def _parse_intent_from_text(text: str) -> dict:
    """Try to parse JSON intent from model output text."""
    # trim whitespace
    text = text.strip()

    # directly parse JSON if possible
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(text)
    if match := re.search(r"(\{(?:.|\n)*\})", text):
        with contextlib.suppress(json.JSONDecodeError):
            return json.loads(match[1])
    logger.warning("Unable to parse intent JSON from model output. Output: %s", text)
    return {}
