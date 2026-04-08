"""Unit tests for the Coordinator Agent."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent_coordinator.models import AgentState, ResponseFormat, merge_dicts
from agent_coordinator.workflow.routing import extract_user_query, get_intent, _parse_intent_from_text
from agent_coordinator.workflow.response import get_final_response
from agent_coordinator.workflow.agent import call_next_agent, AGENT_ENV_PREFIX
from agent_coordinator.agent import CoordinatorAgent


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

class TestMergeDicts:
    """Tests for the merge_dicts reducer."""

    def test_merge_both_populated(self):
        assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_merge_right_overwrites(self):
        assert merge_dicts({"a": 1}, {"a": 2}) == {"a": 2}

    def test_merge_left_empty(self):
        assert merge_dicts({}, {"b": 2}) == {"b": 2}

    def test_merge_right_empty(self):
        assert merge_dicts({"a": 1}, {}) == {"a": 1}

    def test_merge_right_none(self):
        assert merge_dicts({"a": 1}, None) == {"a": 1}

    def test_merge_left_none(self):
        assert merge_dicts(None, {"b": 2}) == {"b": 2}


class TestResponseFormat:
    """Tests for the ResponseFormat Pydantic model."""

    def test_default_status(self):
        r = ResponseFormat(message="hello")
        assert r.status == "input_required"

    def test_custom_status(self):
        r = ResponseFormat(status="completed", message="done")
        assert r.status == "completed"
        assert r.message == "done"

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            ResponseFormat(status="invalid_status", message="bad")


# ---------------------------------------------------------------------------
# extract_user_query
# ---------------------------------------------------------------------------

class TestExtractUserQuery:
    """Tests for the coordinator extract_user_query workflow node."""

    def test_extracts_human_message(self):
        state: AgentState = {
            "messages": [HumanMessage(content="Tell me about Acme Corp")],
        }
        result = extract_user_query(state)
        assert result["user_query"] == "Tell me about Acme Corp"
        assert result["status"] == "working"
        assert "start_time" in result

    def test_no_human_message_returns_default(self):
        state: AgentState = {
            "messages": [AIMessage(content="I am an AI")],
        }
        result = extract_user_query(state)
        assert result["user_query"] == "No query provided"

    def test_empty_messages(self):
        state: AgentState = {"messages": []}
        result = extract_user_query(state)
        assert result["user_query"] == "No query provided"

    def test_multiple_messages_takes_first_human(self):
        state: AgentState = {
            "messages": [
                AIMessage(content="System init"),
                HumanMessage(content="First question"),
                HumanMessage(content="Second question"),
            ],
        }
        result = extract_user_query(state)
        assert result["user_query"] == "First question"


# ---------------------------------------------------------------------------
# _parse_intent_from_text
# ---------------------------------------------------------------------------

class TestParseIntentFromText:
    """Tests for JSON intent parsing from LLM output."""

    def test_valid_json(self):
        text = '{"intent_summary": "research", "agents_to_call": ["research"]}'
        result = _parse_intent_from_text(text)
        assert result["intent_summary"] == "research"
        assert result["agents_to_call"] == ["research"]

    def test_json_with_markdown_fences(self):
        text = '```json\n{"agents_to_call": ["outreach"]}\n```'
        result = _parse_intent_from_text(text)
        assert result["agents_to_call"] == ["outreach"]

    def test_json_embedded_in_text(self):
        text = 'Here is the result: {"agents_to_call": ["research"]} end of response'
        result = _parse_intent_from_text(text)
        assert result["agents_to_call"] == ["research"]

    def test_invalid_json_returns_empty(self):
        result = _parse_intent_from_text("this is not json at all")
        assert result == {}

    def test_empty_string_returns_empty(self):
        result = _parse_intent_from_text("")
        assert result == {}

    def test_whitespace_around_json(self):
        text = '   \n  {"agents_to_call": ["research", "outreach"]}  \n  '
        result = _parse_intent_from_text(text)
        assert result["agents_to_call"] == ["research", "outreach"]


# ---------------------------------------------------------------------------
# get_intent (with mocked agent)
# ---------------------------------------------------------------------------

class TestGetIntent:
    """Tests for the get_intent workflow function."""

    @pytest.mark.asyncio
    async def test_returns_parsed_intent(self):
        intent_json = json.dumps({
            "intent_summary": "Research Acme Corp",
            "agents_to_call": ["research"],
        })
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {
            "messages": [AIMessage(content=intent_json)],
        }

        state: AgentState = {"user_query": "Tell me about Acme Corp", "messages": []}
        result = await get_intent(mock_agent, state)

        assert result["intent"]["agents_to_call"] == ["research"]
        assert result["intent"]["intent_summary"] == "Research Acme Corp"

    @pytest.mark.asyncio
    async def test_no_ai_message_returns_empty_intent(self):
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {
            "messages": [HumanMessage(content="hello")],
        }

        state: AgentState = {"user_query": "hello", "messages": []}
        result = await get_intent(mock_agent, state)

        assert result["intent"] == {}


# ---------------------------------------------------------------------------
# route_to_agent
# ---------------------------------------------------------------------------

class TestRouteToAgent:
    """Tests for the routing decision function."""

    def test_routes_to_call_agent_when_pending(self):
        state: AgentState = {"pending_agents": ["research"]}
        assert CoordinatorAgent.route_to_agent(state) == "call_next_agent"

    def test_routes_to_response_when_no_pending(self):
        state: AgentState = {"pending_agents": []}
        assert CoordinatorAgent.route_to_agent(state) == "return_response"

    def test_routes_to_response_when_pending_missing(self):
        state: AgentState = {}
        assert CoordinatorAgent.route_to_agent(state) == "return_response"


# ---------------------------------------------------------------------------
# call_next_agent
# ---------------------------------------------------------------------------

class TestCallNextAgent:
    """Tests for the call_next_agent workflow function."""

    @pytest.mark.asyncio
    async def test_empty_pending_returns_immediately(self):
        state: AgentState = {"pending_agents": [], "agent_responses": []}
        result = await call_next_agent(state)
        assert result["pending_agents"] == []
        assert result["agent_responses"] == []

    @pytest.mark.asyncio
    async def test_unknown_agent_is_skipped(self):
        state: AgentState = {
            "pending_agents": ["unknown_agent"],
            "agent_responses": [],
            "user_query": "test",
        }
        result = await call_next_agent(state)
        assert result["pending_agents"] == []
        assert len(result["agent_responses"]) == 1
        assert result["agent_responses"][0]["error"] == "unknown agent"

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"HOST_RESEARCH": "localhost"}, clear=False)
    async def test_no_port_configured_skips_agent(self):
        # Make sure PORT_RESEARCH is not set
        import os
        os.environ.pop("PORT_RESEARCH", None)

        state: AgentState = {
            "pending_agents": ["research"],
            "agent_responses": [],
            "user_query": "test",
        }
        result = await call_next_agent(state)
        assert len(result["agent_responses"]) == 1
        assert result["agent_responses"][0]["error"] == "no port configured"

    def test_agent_env_prefix_mapping(self):
        assert AGENT_ENV_PREFIX["research"] == "RESEARCH"
        assert AGENT_ENV_PREFIX["outreach"] == "OUTREACH"
        assert "unknown" not in AGENT_ENV_PREFIX


# ---------------------------------------------------------------------------
# get_final_response (with mocked agent)
# ---------------------------------------------------------------------------

class TestGetFinalResponse:
    """Tests for the final response generation."""

    @pytest.mark.asyncio
    async def test_returns_last_ai_message_content(self):
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {
            "messages": [
                HumanMessage(content="query"),
                AIMessage(content="Final summary of the company."),
            ],
        }

        state: AgentState = {
            "user_query": "Tell me about Acme",
            "agent_responses": [
                {"agent": "research", "response": '{"message": "company info"}'},
            ],
            "messages": [],
        }
        result = await get_final_response(mock_agent, state)
        assert result == "Final summary of the company."

    @pytest.mark.asyncio
    async def test_includes_agent_responses_in_prompt(self):
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {
            "messages": [AIMessage(content="response")],
        }

        agent_responses = [
            {"agent": "research", "response": "data1"},
            {"agent": "outreach", "response": "data2"},
        ]
        state: AgentState = {
            "user_query": "query",
            "agent_responses": agent_responses,
            "messages": [],
        }
        await get_final_response(mock_agent, state)

        # Verify the agent was called with messages including agent responses
        call_args = mock_agent.ainvoke.call_args[1]["input"]["messages"]
        # SystemMessage + 2 AIMessages (agent responses) + HumanMessage
        assert len(call_args) == 4


# ---------------------------------------------------------------------------
# CoordinatorAgent class-level tests
# ---------------------------------------------------------------------------

class TestCoordinatorAgentClass:
    """Tests for CoordinatorAgent static properties."""

    def test_supported_content_types(self):
        assert "text" in CoordinatorAgent.SUPPORTED_CONTENT_TYPES
        assert "text/plain" in CoordinatorAgent.SUPPORTED_CONTENT_TYPES
