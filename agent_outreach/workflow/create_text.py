"""Create the messages based on available data."""

import logging
import os

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agent_outreach.prompts.get_email import PROMPT_EMAIL
from agent_outreach.prompts.get_message import PROMPT_MESSAGE
from agent_outreach.prompts.templates import TEMPLATE_EMAIL, TEMPLATE_MESSAGE
from agent_outreach.workflow.models import AgentState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_text(agent, state: AgentState, medium: str) -> str:
    """Create the final message to return as response."""
    # assemble the hook content
    template = TEMPLATE_EMAIL if medium == "email" else TEMPLATE_MESSAGE
    prompt = PROMPT_EMAIL if medium == "email" else PROMPT_MESSAGE

    company_data = state.get("company_data")
    if company_data is None:
        company_data = {}

    formatted_prompt = ChatPromptTemplate.from_template(prompt).format(
        template=template,
        company=state.get("name"),
        offering=company_data.get("offering", ""),
        recipient=state.get("recipient"),
        sender="Jon Doe",
        hook=state.get("news"),
    )
    messages = [
        HumanMessage(content=formatted_prompt),
    ]
    logger.info("💬 Running %s response generation...", medium)
    agent = ChatOpenAI(
        model=os.getenv("CHAT_MODEL", "gpt-4.1-mini"),
        temperature=0,
    )
    result = await agent.ainvoke(messages)
    logger.info("✅ Compiled the %s messages", medium)
    return str(result.content)
