"""Handle streaming operation for the Company Information Agent."""

from collections.abc import AsyncIterable
from typing import Any

from langchain_core.messages import HumanMessage


class A2AStream:
    """Handle streaming operation for the Company Information Agent.

    Attributes:
        workflow (Workflow): The workflow for the agent.

    Methods:
        stream(state): Stream the agent response to the user (frontend).
        get_agent_response(chunk, config): Returns the response from the agent.
    """

    def __init__(self, workflow):
        self.workflow = workflow
        self._artifacts: dict[str, str] = {}


    async def stream(self, state) -> AsyncIterable[dict[str, Any]]:
        """Stream the agent response to the user (frontend)."""
        context_id = state["task"].context_id

        inputs = {
            "messages": [
                HumanMessage(content=state["question"])
            ],
        }
        config = {
            "configurable": {"thread_id": context_id},
        }

        async for chunk in self.workflow.astream(
            inputs, config, subgraphs=True, stream_mode="values"
        ):
            if isinstance(chunk, tuple):
                yield self._get_agent_response(chunk[1], config)
            else:
                yield self._get_agent_response(chunk, config)

    def _get_agent_response(self, chunk, config):
        """Syncs the agent responses with the agent executor."""
        thread_id = config.get("configurable", {}).get("thread_id")

        # Check if process is completed; then return final response (dataset)
        if isinstance(chunk, dict) and chunk.get("status") == "completed":
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": chunk.get("response"),
            }

        result = chunk.get("result", {})
        kind = result.get("kind")
        is_task_complete = False
        require_user_input = False
        content = None

        if kind == "artifact-update":
            artifact = result.get("artifact", {})
            parts = artifact.get("parts") or []
            try:
                parts_text = parts[0].get("text", "")
            except (KeyError, IndexError):
                parts_text = ""

            if thread_id not in self._artifacts:
                self._artifacts[thread_id] = ""
            self._artifacts[thread_id] += parts_text

        elif kind == "status-update":
            status = result.get("status", {})
            state_val = status.get("state")
            final = result.get("final", False)

            if state_val in ("input-required", "auth-required"):
                require_user_input = True

            if final and state_val in ("completed", "failed", "rejected", "canceled"):
                is_task_complete = True
                content = self._artifacts.pop(thread_id, "")

        elif kind == "message":
            parts = result.get("parts") or []
            if text_parts := [
                p["text"] for p in parts if p.get("kind") == "text" and p.get("text")
            ]:
                content = "\n".join(text_parts)

        return {
            "is_task_complete": is_task_complete,
            "require_user_input": require_user_input,
            "content": content,
        }
