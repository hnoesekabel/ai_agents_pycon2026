#!/usr/bin/env python3

"""FastAPI server to handle user queries to Agents and direct data access.

* send a user query to the Coordination Agent
curl -X POST -H "Content-Type: application/json" -d '{"query": "Lorem ipsum"}' http://localhost:8080/api/agent
curl -X POST -H "Content-Type: application/json" -d '{"query": "What can you tell me about TD Reply?"}' http://localhost:8080/api/agent
curl -X POST -H "Content-Type: application/json" -d '{"query": "Who is the CEO of Anthropic?"}' http://localhost:8080/api/agent
curl -X POST -H "Content-Type: application/json" -d '{"query": "Can you help me draft a message for TD Reply GmbH from Berlin, Germany (https://tdreply.de/) regarding a partnership proposal?"}' http://localhost:8080/api/agent

* get the chat history of a user
curl http://localhost:8080/api/chat_history
"""

import logging
import os
import uuid

import httpx
import uvicorn
from a2a.client import Client, ClientConfig, ClientFactory
from a2a.types import Message, TaskState
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.middleware.gzip import GZipMiddleware

from backend.a2a.conversation import (
    build_message,
    extract_text_content,
)
from backend.a2a.discovery import discover_agent
from backend.api.chat_history import ChatHistory
from backend.api.dependencies import get_userid
from backend.api.models import ChatHistoryResponseModel
from backend.db.chat_history import ChatHistoryData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class A2AAgent:
    """Handle Agent communication and A2A functions."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.db_chat_history = ChatHistoryData()


    async def handle_stream_request(
        self, request: Request, user_id: int = Depends(get_userid)
    ) -> StreamingResponse:
        """Stream the final coordinator response while storing only the final result."""
        payload_dict = await request.json()
        chat_id = str(payload_dict["chat_id"]) if payload_dict.get("chat_id") else str(uuid.uuid4())

        async def stream_response():
            final_response: str | None = None
            streamed_parts: list[str] = []
            try:
                agent_card = await discover_agent(
                    host=self.host,
                    port=self.port,
                )
                async with httpx.AsyncClient(timeout=90) as httpx_client:
                    factory = ClientFactory(
                        config=ClientConfig(httpx_client=httpx_client),
                    )
                    agent = factory.create(agent_card)
                    if not isinstance(agent, Client):
                        raise TypeError("self.agent is not an instance of Client")
                    message = build_message(
                        payload_dict["query"], context_id=chat_id
                    )
                    async for chunk in self._stream_agent_chunks(agent, message):
                        if chunk["kind"] == "chunk":
                            text = chunk["text"] or ""
                            streamed_parts.append(text)
                            yield text
                        elif chunk["kind"] == "final":
                            final_response = chunk["text"]
                            streamed_text = "".join(streamed_parts)
                            if (
                                final_response
                                and final_response.startswith(streamed_text)
                            ):
                                remainder = final_response[len(streamed_text) :]
                                if remainder:
                                    yield remainder
            except Exception:
                raise
            finally:
                if final_response is not None:
                    chat_id_final = self._add_to_chat_history(
                        user_id, "user", payload_dict["query"], chat_id
                    )
                    self._add_to_chat_history(
                        user_id,
                        "assistant",
                        str(final_response),
                        chat_id_final,
                    )

        return StreamingResponse(
            stream_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Encoding": "identity",
                "X-Accel-Buffering": "no",
            },
        )

    async def _stream_agent_chunks(self, agent: Client, message: Message):
        """Yield response chunks from an A2A streaming call."""
        accumulated_parts: list[str] = []
        try:
            async for update in agent.send_message(message):
                task, event = update if isinstance(update, tuple) else (update, None)
                state, message_text = self._extract_task_state(task)
                if state in ("working", TaskState.working):
                    if chunk_text := message_text:
                        accumulated_parts.append(chunk_text)
                        yield {"kind": "chunk", "text": chunk_text}
                    continue
                if state in ("completed", TaskState.completed):
                    final_text = (
                        extract_text_content((task, event))
                        or "".join(accumulated_parts)
                    )
                    yield {"kind": "final", "text": final_text}
                    return
                if state in ("input_required", "input-required", TaskState.input_required):
                    yield {"kind": "final", "text": message_text}
                    return
        except RuntimeError as exc:
            if "StopAsyncIteration" in str(exc):
                final_text = "".join(accumulated_parts) or None
                if final_text:
                    yield {"kind": "final", "text": final_text}
                return
            raise
        final_text = "".join(accumulated_parts) or None
        if final_text:
            yield {"kind": "final", "text": final_text}


    def _add_to_chat_history(
        self,
        user_id: int,
        role: str,
        text: str,
        chat_id: str,
    ) -> str:
        """Add the user request to the chat history and return chat_id."""
        if not chat_id:
            chat_id = str(uuid.uuid4())
        self.db_chat_history.add_message(
            user_id=user_id,
            role=role,
            text=text,
            chat_id=chat_id,
        )
        return chat_id

    def _extract_task_state(self, task) -> tuple[str | None, str | None]:
        """Extract task state and message text from A2A updates."""
        status = None
        if hasattr(task, "status"):
            status = task.status
        elif isinstance(task, dict) and "status" in task:
            status = task["status"]
        if not status:
            return None, None

        state = None
        if hasattr(status, "state"):
            state = self._normalize_task_state(status.state)
        elif isinstance(status, dict) and "state" in status:
            state = self._normalize_task_state(status["state"])

        message = None
        if hasattr(status, "message"):
            message = status.message  # type: ignore
        elif isinstance(status, dict) and "message" in status:
            message = status["message"]

        return state, self._extract_message_text(message)

    @staticmethod
    def _normalize_task_state(state) -> str | None:
        if state is None:
            return None
        return state.value if hasattr(state, "value") else state

    def _extract_message_text(self, message) -> str | None:
        if not message:
            return None
        parts = None
        if hasattr(message, "parts"):
            parts = message.parts
        elif isinstance(message, dict) and "parts" in message:
            parts = message["parts"]

        for part in parts or []:
            if text := self._extract_text_from_part(part):
                return text
        return None

    def _extract_text_from_part(self, part) -> str | None:
        if hasattr(part, "root"):
            root = part.root
            if hasattr(root, "text"):
                return root.text

        if isinstance(part, dict) and "root" in part:
            root = part["root"]
            if isinstance(root, dict) and "text" in root:
                return root["text"]
            if hasattr(root, "text"):
                return root.text  # type: ignore
        return None

    def _extract_event_state(self, event) -> str | None:
        if not event:
            return None
        status = None
        if hasattr(event, "status"):
            status = event.status
        elif isinstance(event, dict) and "status" in event:
            status = event["status"]
        if not status:
            return None
        state = None
        if hasattr(status, "state"):
            state = status.state
        elif isinstance(status, dict) and "state" in status:
            state = status["state"]
        return self._normalize_task_state(state)

    def _extract_event_text(self, event) -> str | None:
        if not event:
            return None
        artifact = None
        if hasattr(event, "artifact"):
            artifact = event.artifact
        elif isinstance(event, dict) and "artifact" in event:
            artifact = event["artifact"]
        if artifact:
            parts = None
            if hasattr(artifact, "parts"):
                parts = artifact.parts
            elif isinstance(artifact, dict) and "parts" in artifact:
                parts = artifact["parts"]
            if parts:
                for part in parts:
                    if text := self._extract_text_from_part(part):
                        return text
        result = None
        if isinstance(event, dict) and "result" in event:
            result = event["result"]
        elif hasattr(event, "result"):
            result = event.result  # type: ignore
        payload = result if result is not None else event
        if isinstance(payload, dict):
            kind = payload.get("kind")
            parts = None
            if kind == "message":
                parts = payload.get("parts")
            elif kind == "artifact-update":
                parts = (payload.get("artifact") or {}).get("parts")
            if parts:
                for part in parts:
                    if text := self._extract_text_from_part(part):
                        return text
        return None

    @staticmethod
    def _describe_event(event) -> str:
        if event is None:
            return "none"
        if isinstance(event, dict):
            if kind:= event.get("kind"):
                return f"dict:{kind}"
            return f"dict:{','.join(list(event.keys())[:3])}"
        if hasattr(event, "result"):
            result = event.result  # type: ignore
            if isinstance(result, dict) and "kind" in result:
                return f"obj:{result['kind']}"
            return "obj:result"
        return f"obj:{type(event).__name__}"


def setup(api: FastAPI) -> FastAPI:
    """Setup FastAPI with CORS; HTML files are served by nginx."""
    api.add_middleware(
        GZipMiddleware,
        minimum_size=1000,
    )
    api.add_middleware(  # allow CORS: local browser access
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return api


def routes(
    api: FastAPI,
    chat_history: ChatHistory,
    agent: A2AAgent,
) -> None:
    """Configure server endpoints to use, and which downstream functions to call."""

    config = [
        {
            "endpoint": "/chat_history",
            "method": "GET",
            "function": chat_history.get_chat_history,
            "response_model": ChatHistoryResponseModel | None,
            "dependencies": [Depends(get_userid)],
        },
        {
            "endpoint": "/agent",
            "method": "POST",
            "function": agent.handle_stream_request,
            "response_model": None,
            "dependencies": [Depends(get_userid)],
        },
    ]
    for endpoint in config:
        api.add_api_route(
            path="/api" + endpoint["endpoint"],
            endpoint=endpoint["function"],
            methods=[endpoint["method"]],
            response_model=endpoint["response_model"],
            dependencies=endpoint["dependencies"],
        )


def main():
    """Start the FastAPI server providing required APIs."""
    fastapi = FastAPI()
    fastapi = setup(fastapi)  # configure FastAPI
    coordination_agent = A2AAgent(
        host=os.getenv("HOST_COORDINATOR", "localhost"),
        port=int(os.getenv("PORT_COORDINATOR", "10000")),
    )
    routes(
        fastapi,
        ChatHistory(),
        coordination_agent,
    )  # setup the routes
    return fastapi


if __name__ == "__main__":
    uvicorn.run(
        main(),
        host="0.0.0.0",
        port=int(os.getenv("PORT_BACKEND", "8080")),
    )
