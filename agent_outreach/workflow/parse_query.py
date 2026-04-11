"""Parse the user's query."""

import json
import logging
import os
import time

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from a2a_common.mcp_urls import MCP_GOOGLE_URL
from agent_outreach.prompts.get_urls import PROMPT_URLS
from agent_outreach.workflow.models import AgentState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


async def extract_user_query(state: AgentState):
    """Extract the original user query from first message."""
    start_time = time.perf_counter()
    messages = state.get("messages", [])
    user_query = ""

    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            logger.info("📝 Extracted original user query: '%s'", user_query[:100])
            break

    if not user_query:
        logger.warning("⚠️ No user query found in initial messages")
        user_query = "No query provided"

    return {
        "user_query": user_query,
        "status": "working",
        "start_time": start_time,
    }


async def extract_urls(state: AgentState) -> dict:
    """Extracts company website and its LinkedIn URL from the company name.
    Args:
        query (str): Incoming query from the user, should contain a person's
            name and/or a company name.

    Returns:
        dict: containing the extracted company, website and linkedin_url.
    """
    search_tools = []
    try:
        mcp_client = MultiServerMCPClient(
            {
                "google_search": {
                    "url": MCP_GOOGLE_URL,
                    "transport": "streamable_http",
                }
            }
        )
        search_tools = await mcp_client.get_tools()
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "Failed to connect to MCP servers, will continue with incomplete toolset: %s",
            repr(e),
        )
    model = ChatOpenAI(model=os.getenv("CHAT_MODEL", "gpt-4.1-mini"), temperature=0)
    search_agent: CompiledStateGraph = create_agent(
        model=model,
        tools=search_tools,
    )

    messages = {
        "messages": [
            SystemMessage(content=PROMPT_URLS),
            HumanMessage(content=state.get("user_query", "")),
        ]
    }
    response = await search_agent.ainvoke(messages)
    final_message = response["messages"][-1]

    # Get the content from the agent's final response)
    content = final_message.content
    content = content.replace("json", "").replace("```", "")

    try:
        result = json.loads(content)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Extraction failed: %s", e)
        result = {
            "name": None,
            "url": None,
            "linkedin": None,
        }

    logger.info("💬 Extracted URLs: %s", result)
    return result
