"""Base A2A Agent Executor with shared workflow logic."""

import asyncio
import logging
from typing import Annotated

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
    Message,
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError

logger = logging.getLogger(__name__)


class ExecutorState(TypedDict):
    """Store the executor state."""

    question: str
    messages: Annotated[list, add_messages]
    task: Task
    updater: TaskUpdater


class BaseAgentExecutor(AgentExecutor):
    """Shared executor logic for all A2A agents.

    Subclasses must set `self.agent` in their `__init__`.
    """

    agent: object  # set by subclass

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task - currently not supported."""
        logger.warning("Cancel operation not supported")
        raise ServerError(error=UnsupportedOperationError())

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Handle incoming requests and stream events back."""
        if not self._validate_request(context):
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()
        logger.info("Received query: %s...", query[:100])

        task = context.current_task
        if not task and isinstance(context.message, Message):
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id) if task else None

        if task and updater:
            app = await self._build_graph(task, updater)
            state = ExecutorState(
                question=query,
                messages=[],
                task=task,
                updater=updater,
            )
            logger.info("Starting executor workflow")
            await app.ainvoke(state)
            logger.info("Executor workflow completed")
        else:
            logger.error("Error running executor: task or updater not found.")

    def _validate_request(self, context: RequestContext) -> bool:
        """Check if the incoming request from user is valid."""
        return bool(context)

    async def _build_graph(self, task: Task, updater: TaskUpdater) -> CompiledStateGraph:
        """Build the executor workflow as a LangGraph state graph."""
        workflow = StateGraph(ExecutorState)
        workflow.add_node("task", lambda state: {"task": task})
        workflow.add_node("updater", lambda state: {"updater": updater})
        workflow.add_node("run_agent", self._run_agent)

        workflow.set_entry_point("task")
        workflow.add_edge("task", "updater")
        workflow.add_edge("updater", "run_agent")
        workflow.add_edge("run_agent", END)

        return workflow.compile()

    async def _run_agent(self, state: ExecutorState) -> None:
        """Stream agent responses and update task status accordingly."""
        try:
            logger.info("Running agent workflow")

            async for item in self.agent.stream(state):
                is_task_complete = item["is_task_complete"]
                require_user_input = item["require_user_input"]
                updater = state["updater"]
                task = state["task"]
                content = item["content"]

                if not is_task_complete and not require_user_input:
                    if not content:
                        continue
                    logger.info("Working...")
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(content, task.context_id, task.id),
                    )
                elif require_user_input:
                    logger.info("Requesting user input")
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(content, task.context_id, task.id),
                        final=True,
                    )
                    await asyncio.sleep(0.1)
                    break
                else:
                    logger.info("Task complete, adding artifact")
                    await updater.add_artifact(
                        [Part(root=TextPart(text=content))],
                        name="result",
                    )
                    await updater.complete()
                    break
        except Exception as e:
            logger.error("Error running agent: %s", e, exc_info=True)
            raise ServerError(error=InternalError()) from e
