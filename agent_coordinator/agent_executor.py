"""A2A Agent Executor for the Coordinator Agent."""

from a2a_common.base_executor import BaseAgentExecutor
from agent_coordinator.agent import CoordinatorAgent


class CoordinatorAgentExecutor(BaseAgentExecutor):
    """Handle the agent execution for the Coordinator Agent."""

    def __init__(self, agent: CoordinatorAgent):
        self.agent = agent
