"""Functions to find recent news about a company."""

import os
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from agent_outreach.prompts.get_news import PROMPT_NEWS
from agent_outreach.workflow.models import AgentState
from a2a_common.mcp_urls import MCP_CRAWL4AI_URL, MCP_GOOGLE_URL, MCP_NEWS_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



async def get_news(state: AgentState) -> dict:
    """Check the Internet about the most recent company news."""
    agent = await _get_agent()

    question = PROMPT_NEWS.format(
        name=state.get("name"),
        url=state.get("url"),
        linkedin=state.get("linkedin"),
    )
    response = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
    news_content = response["messages"][-1].content
    logger.info("✅ Got news")
    return {"news": news_content}

async def _get_agent():
    tools = []
    try:
        mcp_client = MultiServerMCPClient({
            "crawl4ai": {
                "url": MCP_CRAWL4AI_URL,
                "transport": "streamable_http",
            },
            "google_search": {
                "url": MCP_GOOGLE_URL,
                "transport": "streamable_http",
            },
            "news": {
                "url": MCP_NEWS_URL,
                "transport": "streamable_http",
            },
        })
        tools = await mcp_client.get_tools()
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "Failed to connect to MCP servers, will continue with incomplete toolset: %s",
            repr(e),
        )
    search_agent = create_agent(
        model=ChatOpenAI(
            model=os.getenv("CHAT_MODEL", "gpt-4.1-mini"),
            temperature=0,
        ),
        tools=tools,
    )
    return search_agent
