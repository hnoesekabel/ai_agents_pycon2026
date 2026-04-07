"""Agent to retrieve company information."""

import logging
import os
import time

from dotenv import load_dotenv
from typing_extensions import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langchain.agents import create_agent
from langchain.messages import AIMessage, ToolMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from a2a_common.stream import A2AStream
from a2a_common.mcp_urls import MCP_CRAWL4AI_URL, MCP_GOOGLE_URL
from agent_research.models import AgentState, ResponseFormat
from agent_research.prompt import AGENT_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
memory = MemorySaver()


class ResearchAgent:
    """Agent to coordinate response to user queries."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]
    tools_by_name: dict = {}

    def __init__(self, agent, workflow: CompiledStateGraph):
        self.agent = agent
        self.workflow = workflow
        a2a_stream = A2AStream(self.workflow)
        self.stream = a2a_stream.stream

    @classmethod
    async def create(cls):
        """Creates the agent with the MCP tools specified in its configuration"""
        tools = []
        # get tools for the agent from MCP servers
        try:
            mcp_client = MultiServerMCPClient(
                {
                    "crawl4ai": {
                        "url": MCP_CRAWL4AI_URL,
                        "transport": "streamable_http",
                    },
                    "googlesearch": {
                        "url": MCP_GOOGLE_URL,
                        "transport": "streamable_http"
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
        # set up the agent, provide it the system prompt, and tools
        cls.tools_by_name = {tool.name: tool for tool in tools}
        cls.agent = create_agent(
            model=os.getenv("AGENT_MODEL", "openai:gpt-4.1-mini"),
            tools=tools,
            system_prompt=AGENT_PROMPT.replace("\n", " ").strip(),
            checkpointer=memory,
            response_format=ResponseFormat,
        )
        # get the compiled workflow
        workflow = await cls._create_workflow()
        return cls(cls.agent, workflow)


    @classmethod
    async def _create_workflow(cls) -> CompiledStateGraph:
        """Create a workflow for the agent."""
        workflow = StateGraph(AgentState)
        # add the nodes
        workflow.add_node("extract_query", cls.extract_user_query)
        workflow.add_node("llm_call", cls.llm_call)
        workflow.add_node("tool_node", cls.tool_node)
        workflow.add_node("return_response", cls.return_response)
        # connect the nodes
        workflow.add_edge(START, "extract_query")
        workflow.add_edge("extract_query", "llm_call")
        workflow.add_conditional_edges(
            "llm_call",
            cls.should_continue,
            ["tool_node", "return_response"]
        )
        workflow.add_edge("tool_node", "llm_call")
        workflow.add_edge("return_response", END)
        # compile the workflow
        return workflow.compile(checkpointer=memory)


    @classmethod
    async def extract_user_query(cls, state: AgentState):
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


    @classmethod
    async def llm_call(cls, state: AgentState):
        """Run the Agent - it will decide on a tool call, or formulate a response."""
        return await cls.agent.ainvoke(input=state)


    @classmethod
    async def tool_node(cls, state: AgentState):
        """Performs a tool call and stores result in messages."""
        result = []
        # LLM can decide to call a tool, so last message should be an AIMessage
        if "messages" in state and isinstance(state["messages"][-1], AIMessage):
            for tool_call in state["messages"][-1].tool_calls:
                tool = cls.tools_by_name[tool_call["name"]]
                observation = tool.invoke(tool_call["args"])
                result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
        # add the result of the tool call as message to the AgentState
        return {"messages": result}


    @classmethod
    async def should_continue(cls, state: AgentState) -> Literal["tool_node", "return_response"]:
        """Decide if we should continue the loop or stop."""
        # check if the last message is an AIMessage and has tool calls
        messages = state["messages"] if "messages" in state else []
        if isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
            return "tool_node"
        return "return_response"


    @classmethod
    async def return_response(cls, state: AgentState) -> dict:
        """Prepare the final response and mark the process as completed."""
        # get the timing and log it
        end_time = time.perf_counter()
        start_time = state.get("start_time", 0.0)
        if start_time is not None:
            logger.info(
                "🏁 Workflow completed in %s seconds", int(end_time - float(start_time))
            )
        # take the last message, which is usually the LLM response (AIMessage)
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else {}
        response_content = (
            last_message.content
            if isinstance(last_message, AIMessage)
            else
                last_message.get("content", "")
                if isinstance(last_message, dict)
                else ""
        ) or "No response provided"
        # return changes to the AgentState, marking the process as completed
        return {
            "response": response_content,
            "status": "completed",
            "end_time": end_time,
        }
