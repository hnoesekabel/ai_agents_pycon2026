"""A2A Agent Executor for the Outreach Agent."""

from a2a_common.base_executor import BaseAgentExecutor
from agent_outreach.agent import OutreachAgent


class OutreachAgentExecutor(BaseAgentExecutor):
    """Handle the agent execution for the Outreach Agent."""

    def __init__(self, agent: OutreachAgent):
        self.agent = agent
