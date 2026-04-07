"""Get email and LinkedIn URL for CEO of company."""

import os
import json
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from agent_outreach.prompts.get_ceo_email import PROMPT_CEO_EMAIL
from agent_outreach.prompts.get_contact import PROMPT_CONTACT
from agent_outreach.workflow.models import AgentState
from a2a_common.mcp_urls import MCP_CRAWL4AI_URL, MCP_GOOGLE_URL


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_linkedin_and_email(state: AgentState) -> dict:
    """Get the email and LinkedIn profile link for the recipient."""
    agent = await _get_agent()

    recipient = state.get("recipient") or ""
    user_query = state.get("user_query") or ""
    question = PROMPT_CEO_EMAIL.format(
        ceo=recipient,
        company=state.get("name") or "",
        url=state.get("url") or "",
        query=user_query,
    )
    response = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
    result_text = response["messages"][-1].content

    try:
        (ceo, email, linkedin) = result_text.split(",")
        logger.info("📞 Got contact information: %s - %s - %s", ceo, email, linkedin)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("❌ Error getting contact information: %s", e)
        logger.error("❌ Response was: %s", response)
        return {"ceo_email": "", "ceo_linkedin": ""}

    if "linkedin.com/in" not in linkedin:
        linkedin = await _search_for_linkedin(ceo, str(state.get("name")))

    return {"recipient": ceo, "ceo_email": email, "ceo_linkedin": linkedin}

async def _search_for_linkedin(ceo: str, company: str) -> str:
    """Fallback Google search for the CEO LinkedIn profile URL."""
    mcp_client = MultiServerMCPClient(
        {
            "search": {
                "url": MCP_GOOGLE_URL,
                "transport": "streamable_http",
            },
        }
    )
    tools = await mcp_client.get_tools()
    tool = next((t for t in tools if t.name == "web_search"), None)

    if tool is None:
        logger.error("❌ Tool 'web_search' not found.")
        return ""

    responses = await tool.ainvoke({
        "query": f"{ceo} {company} linkedin profile",
        "use_cse": True,
    })
    linkedin = ""
    for item in responses:
        # tool already returns dictionaries, no need to parse JSON
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except json.JSONDecodeError:
                continue

        if "linkedin.com/in" in item.get("link", ""):
            linkedin = item["link"]
            break

    logger.info("📞 Found LinkedIn profile URL through search: %s", linkedin)
    return linkedin

async def get_ceo(state: AgentState) -> dict:
    """Find a contact for a company."""
    agent = await _get_agent()
    user_query = state.get("user_query") or ""
    question = PROMPT_CONTACT.format(
        name=state.get("name"),
        url=state.get("url"),
        query=user_query,
    )
    response = await agent.ainvoke({
        "messages": [
            HumanMessage(content=question),
        ]
    })
    ceo_name = (response["messages"][-1].content or "").strip()
    return {"recipient": ceo_name}

async def _get_agent():
    mcp_client = MultiServerMCPClient(
        {
            "crawl4ai": {
                "url": MCP_CRAWL4AI_URL,
                "transport": "streamable_http",
            },
            "google_search": {
                "url": MCP_GOOGLE_URL,
                "transport": "streamable_http",
            },
        }
    )
    tools = await mcp_client.get_tools()
    search_agent = create_agent(
        model=ChatOpenAI(
            model=os.getenv("CHAT_MODEL", "gpt-4.1-mini"),
            temperature=0,
        ),
        tools=tools,
    )
    return search_agent
