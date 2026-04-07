"""Agent to create outreach messages for email and LinkedIn."""

import json
import logging
import os
import time

from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from a2a_common.stream import A2AStream
from a2a_common.mcp_urls import MCP_CRAWL4AI_URL, MCP_GOOGLE_URL
from agent_outreach.workflow.create_text import create_text
from agent_outreach.workflow.get_news import get_news
from agent_outreach.workflow.get_contact import get_linkedin_and_email, get_ceo
from agent_outreach.workflow.models import AgentState, ResponseFormat
from agent_outreach.workflow.parse_query import extract_urls, extract_user_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# de-noise the logfiles
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

load_dotenv()
memory = MemorySaver()


class OutreachAgent:
    """Agent to create outreach messages for email and LinkedIn."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, agent, workflow: CompiledStateGraph):
        self.agent = agent
        self.workflow = workflow
        a2a_stream = A2AStream(self.workflow)
        self.stream = a2a_stream.stream

    @classmethod
    async def create(cls):
        """Creates the agent with the MCP tools specified in its configuration"""
        tools = []
        try:
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
        # catch ExceptionGroup and any networking errors if MCP servers are unaccessible
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Failed to connect to MCP servers, will continue with incomplete toolset: %s",
                repr(e)
            )
        cls.agent = create_agent(
            model=os.getenv("AGENT_MODEL", "openai:gpt-4.1-mini"),
            tools=tools,
            checkpointer=memory,
            response_format=ResponseFormat,
        )

        workflow = await cls._create_workflow()
        return cls(cls.agent, workflow)

    @classmethod
    async def _create_workflow(cls) -> CompiledStateGraph:
        """Create a workflow for the agent."""
        workflow = StateGraph(AgentState)

        workflow.add_node("extract_query", extract_user_query)
        workflow.add_node("extract_urls", extract_urls)
        workflow.add_node("get_ceo", get_ceo)
        workflow.add_node("get_linkedin_and_email", get_linkedin_and_email)
        workflow.add_node("get_news", get_news)
        workflow.add_node("get_email_text", cls.get_email_text)
        workflow.add_node("get_message_text", cls.get_message_text)
        workflow.add_node("finalize", cls.finalize)

        workflow.add_edge(START, "extract_query")
        workflow.add_edge("extract_query", "extract_urls")
        workflow.add_edge("extract_urls", "get_news")
        workflow.add_edge("get_news", "get_ceo")
        workflow.add_edge("get_ceo", "get_linkedin_and_email")

        # run both message creations in parallel; merge to finalize
        workflow.add_edge("get_linkedin_and_email", "get_email_text")
        workflow.add_edge("get_linkedin_and_email", "get_message_text")
        workflow.add_edge("get_email_text", "finalize")
        workflow.add_edge("get_message_text", "finalize")

        workflow.add_edge("finalize", END)

        return workflow.compile(checkpointer=memory)


    @classmethod
    async def get_email_text(cls, state: AgentState) -> dict:
        """Create the email message."""
        response = await create_text(
            agent=cls.agent,
            state=state,
            medium="email",
        )
        return {"response_email": response}

    @classmethod
    async def get_message_text(cls, state: AgentState) -> dict:
        """Create the LinkedIn message."""
        response = await create_text(
            agent=cls.agent,
            state=state,
            medium="message",
        )
        return {"response_message": response}

    @classmethod
    def finalize(cls, state: AgentState) -> dict:
        """Check both messages, then set to completed."""
        response_email = state.get("response_email")
        response_message = state.get("response_message")
        end_time = time.perf_counter()
        start_time = state.get("start_time", 0.0)
        if start_time is not None:
            logger.info(
                "🏁 Workflow completed in %s seconds", int(end_time - float(start_time))
            )

        if response_email and response_message:
            return {
                "status": "completed",
                "response": json.dumps(
                    {
                        "email": response_email.strip(),
                        "message": response_message.strip(),
                        "ceo_name": str(state.get("recipient", "")).strip(),
                        "ceo_email": str(state.get("ceo_email", "")).strip(),
                        "ceo_linkedin": str(state.get("ceo_linkedin", "")).strip(),
                    }
                ),
            }
        else:
            return {"status": "error"}
