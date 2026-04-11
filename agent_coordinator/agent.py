"""Agent to retrieve company information."""

import logging
import os

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from a2a_common.stream import A2AStream
from agent_coordinator.models import ResponseFormat, AgentState
from agent_coordinator.workflow.routing import get_intent, extract_user_query
from agent_coordinator.workflow.agent import call_next_agent
from agent_coordinator.workflow.response import get_final_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# de-noise the logfiles
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("a2a.client").setLevel(logging.WARNING)

load_dotenv()
memory = MemorySaver()



MCP_CRAWL4AI_URL = (
    f"http://{os.getenv('HOST_MCP_CRAWL4AI', 'localhost')}"
    + f":{os.getenv('PORT_MCP_CRAWL4AI', '9000')}/mcp"
)
MCP_WIKIPEDIA_URL = (
    f"http://{os.getenv('HOST_MCP_WIKIPEDIA', 'localhost')}"
    + f":{os.getenv('PORT_MCP_WIKIPEDIA', '9001')}/mcp"
)

class CoordinatorAgent:
    """Agent to determine user intent then coordinate response to user queries."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, workflow: CompiledStateGraph):
        self.workflow = workflow
        a2a_stream = A2AStream(self.workflow)
        self.stream = a2a_stream.stream

    @classmethod
    async def create(cls):
        """Creates the agent with the MCP tools."""
        try:
            mcp_client = MultiServerMCPClient(
                {
                    "crawl4ai": {
                        "url": MCP_CRAWL4AI_URL,
                        "transport": "streamable_http",
                    },
                    "wikipedia": {
                        "url": MCP_WIKIPEDIA_URL,
                        "transport": "streamable_http"
                    },  # don't need the World News MCP server here
                }
            )
            # load tools provided by the MCP servers
            tools = await mcp_client.get_tools()
        # catch if MCP servers are not running; but continue with no tools
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Failed to connect to MCP servers: %s", e)
            tools = []

        # create a ReAct agent with these tools (unless no MCP servers are running)
        cls.agent = create_agent(
            model=os.getenv("AGENT_MODEL", "openai:gpt-4.1-mini"),
            tools=tools,
            checkpointer=memory,
            response_format=ResponseFormat,
        )
        # create a separate agent without tools and structured output
        cls.agent_notools = create_agent(
            model=os.getenv("AGENT_MODEL", "openai:gpt-4.1-mini"),
            tools=[],
        )
        cls.workflow = await cls._create_workflow()
        return cls(cls.workflow)

    @classmethod
    async def _create_workflow(cls) -> CompiledStateGraph:
        """Create a workflow for the agent."""
        workflow = StateGraph(AgentState)
        # add the nodes
        workflow.add_node("extract_query", extract_user_query)
        workflow.add_node("get_intent", cls.get_intent)
        workflow.add_node("call_next_agent", call_next_agent)
        workflow.add_node("return_response", cls.return_response)
        # connect the nodes
        workflow.add_edge(START, "extract_query")
        workflow.add_edge("extract_query", "get_intent")
        workflow.add_conditional_edges(
            "get_intent",
            cls.route_to_agent,
            {
                "call_next_agent": "call_next_agent",
                "return_response": "return_response",
            },
        )
        workflow.add_conditional_edges(
            "call_next_agent",
            cls.route_to_agent,
            {
                "call_next_agent": "call_next_agent",
                "return_response": "return_response",
            },
        )
        workflow.add_edge("return_response", END)
        # compile the workflow
        return workflow.compile(checkpointer=memory)


    @classmethod
    async def get_intent(cls, state: AgentState) -> dict:
        """Determine user intent and which agents to call."""
        logger.info("🔭 Determining user intent...")
        result = await get_intent(cls.agent_notools, state)
        # Seed pending_agents from the intent for the loop
        agents_to_call = result.get("intent", {}).get("agents_to_call", [])
        result["pending_agents"] = list(agents_to_call)
        result["agent_responses"] = []
        logger.info("📋 Agents to call: %s", agents_to_call)
        return result

    @staticmethod
    def route_to_agent(state: AgentState) -> str:
        """Route after intent: if there are agents to call, go to call_next_agent."""
        return "call_next_agent" if state.get("pending_agents") else "return_response"


    @classmethod
    async def return_response(cls, state: AgentState) -> dict:
        """Return a response to the user after agent(s) have completed their work."""
        logger.info("🔭 Returning response to user...")
        response = await get_final_response(cls.agent, state)
        logger.info(response)
        return {"response": response, "status": "completed"}
