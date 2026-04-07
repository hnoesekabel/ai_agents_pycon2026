"""Workflow function to generate the final response for the user."""


import logging

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from agent_coordinator.models import AgentState
from agent_coordinator.prompts.final_result import PROMPT_RESULT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_final_response(agent, state: AgentState) -> dict:
    """Get the final response to answer the user."""
    query = state.get("user_query", "")
    messages: list[BaseMessage] = [SystemMessage(content=PROMPT_RESULT)]
    # include all agent responses in the final prompt as context for the final response generation
    for agent_response in state.get("agent_responses", []):
        messages.append(AIMessage(content=str(agent_response)))
    messages.append(HumanMessage(content=query))

    agent_response = await agent.ainvoke(input={"messages": messages})

    logger.info("✅ Received final response")
    logger.info(agent_response)

    # Extract the text content from the last AI message
    last_message = agent_response["messages"][-1]
    return last_message.content
