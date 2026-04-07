"""A2A Agent Executor for the Research Agent."""

from a2a_common.base_executor import BaseAgentExecutor
from agent_research.agent import ResearchAgent


class ResearchAgentExecutor(BaseAgentExecutor):
    """Handle the agent execution for the Research Agent."""

    def __init__(self, agent: ResearchAgent):
        self.agent = agent
