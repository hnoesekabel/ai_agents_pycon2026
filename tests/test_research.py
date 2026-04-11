"""Unit tests for the Research Agent."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_research.models import AgentState, AgentStateBase, ResponseFormat, merge_dicts
from agent_research.agent import ResearchAgent


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

class TestMergeDicts:
    """Tests for the merge_dicts reducer."""

    def test_merge_both_populated(self):
        assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_merge_left_empty(self):
        assert merge_dicts({}, {"b": 2}) == {"b": 2}

    def test_merge_right_empty(self):
        assert merge_dicts({"a": 1}, {}) == {"a": 1}

    def test_merge_right_none(self):
        assert merge_dicts({"a": 1}, None) == {"a": 1}

    def test_merge_left_none(self):
        assert merge_dicts(None, {"x": 1}) == {"x": 1}


class TestResponseFormat:
    """Tests for the Research ResponseFormat Pydantic model."""

    def test_default_status(self):
        r = ResponseFormat(message="hello")
        assert r.status == "input_required"

    def test_completed_status(self):
        r = ResponseFormat(status="completed", message="done")
        assert r.status == "completed"
        assert r.message == "done"

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            ResponseFormat(status="working", message="bad")  # "working" not allowed


# ---------------------------------------------------------------------------
# extract_user_query
# ---------------------------------------------------------------------------

class TestExtractUserQuery:
    """Tests for the research agent extract_user_query node."""

    @pytest.mark.asyncio
    async def test_extracts_human_message(self):
        state: AgentState = {
            "messages": [HumanMessage(content="Research Acme Corp")],
        }
        result = await ResearchAgent.extract_user_query(state)
        assert result["user_query"] == "Research Acme Corp"
        assert result["status"] == "working"
        assert isinstance(result["start_time"], float)

    @pytest.mark.asyncio
    async def test_no_human_message(self):
        state: AgentState = {
            "messages": [AIMessage(content="AI response")],
        }
        result = await ResearchAgent.extract_user_query(state)
        assert result["user_query"] == "No query provided"

    @pytest.mark.asyncio
    async def test_empty_messages(self):
        state: AgentState = {"messages": []}
        result = await ResearchAgent.extract_user_query(state)
        assert result["user_query"] == "No query provided"

    @pytest.mark.asyncio
    async def test_picks_first_human_message(self):
        state: AgentState = {
            "messages": [
                AIMessage(content="hello"),
                HumanMessage(content="First query"),
                HumanMessage(content="Second query"),
            ],
        }
        result = await ResearchAgent.extract_user_query(state)
        assert result["user_query"] == "First query"


# ---------------------------------------------------------------------------
# should_continue
# ---------------------------------------------------------------------------

class TestShouldContinue:
    """Tests for the should_continue routing function."""

    @pytest.mark.asyncio
    async def test_continues_when_tool_calls_present(self):
        ai_msg = AIMessage(content="calling tool")
        ai_msg.tool_calls = [{"id": "1", "name": "web_search", "args": {"query": "test"}}]
        state: AgentState = {"messages": [ai_msg]}
        result = await ResearchAgent.should_continue(state)
        assert result == "tool_node"

    @pytest.mark.asyncio
    async def test_stops_when_no_tool_calls(self):
        ai_msg = AIMessage(content="final answer")
        ai_msg.tool_calls = []
        state: AgentState = {"messages": [ai_msg]}
        result = await ResearchAgent.should_continue(state)
        assert result == "return_response"

    @pytest.mark.asyncio
    async def test_stops_when_last_is_human_message(self):
        state: AgentState = {"messages": [HumanMessage(content="question")]}
        result = await ResearchAgent.should_continue(state)
        assert result == "return_response"


# ---------------------------------------------------------------------------
# tool_node
# ---------------------------------------------------------------------------

class TestToolNode:
    """Tests for the tool_node workflow function."""

    @pytest.mark.asyncio
    async def test_executes_tool_and_returns_messages(self):
        mock_tool = MagicMock()
        mock_tool.invoke.return_value = "search result content"

        ResearchAgent.tools_by_name = {"web_search": mock_tool}

        ai_msg = AIMessage(content="calling tool")
        ai_msg.tool_calls = [
            {"id": "call_1", "name": "web_search", "args": {"query": "Acme Corp"}},
        ]
        state: AgentState = {"messages": [ai_msg]}
        result = await ResearchAgent.tool_node(state)

        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], ToolMessage)
        assert result["messages"][0].content == "search result content"
        assert result["messages"][0].tool_call_id == "call_1"
        mock_tool.invoke.assert_called_once_with({"query": "Acme Corp"})

    @pytest.mark.asyncio
    async def test_handles_multiple_tool_calls(self):
        mock_tool_a = MagicMock()
        mock_tool_a.invoke.return_value = "result_a"
        mock_tool_b = MagicMock()
        mock_tool_b.invoke.return_value = "result_b"

        ResearchAgent.tools_by_name = {"tool_a": mock_tool_a, "tool_b": mock_tool_b}

        ai_msg = AIMessage(content="calling tools")
        ai_msg.tool_calls = [
            {"id": "c1", "name": "tool_a", "args": {}},
            {"id": "c2", "name": "tool_b", "args": {}},
        ]
        state: AgentState = {"messages": [ai_msg]}
        result = await ResearchAgent.tool_node(state)

        assert len(result["messages"]) == 2

    @pytest.mark.asyncio
    async def test_no_messages_raises_index_error(self):
        """Empty messages list causes IndexError accessing last element."""
        state: AgentState = {"messages": []}
        with pytest.raises(IndexError):
            await ResearchAgent.tool_node(state)

    @pytest.mark.asyncio
    async def test_non_ai_last_message_returns_empty(self):
        state: AgentState = {"messages": [HumanMessage(content="hello")]}
        result = await ResearchAgent.tool_node(state)
        assert result["messages"] == []


# ---------------------------------------------------------------------------
# return_response
# ---------------------------------------------------------------------------

class TestReturnResponse:
    """Tests for the return_response workflow node."""

    @pytest.mark.asyncio
    async def test_returns_ai_message_content(self):
        state: AgentState = {
            "messages": [
                HumanMessage(content="query"),
                AIMessage(content="Here is the company info."),
            ],
            "start_time": time.perf_counter(),
        }
        result = await ResearchAgent.return_response(state)
        assert result["response"] == "Here is the company info."
        assert result["status"] == "completed"
        assert "end_time" in result

    @pytest.mark.asyncio
    async def test_empty_messages_returns_no_response(self):
        state: AgentState = {"messages": [], "start_time": time.perf_counter()}
        result = await ResearchAgent.return_response(state)
        assert result["response"] == "No response provided"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_dict_message_with_content(self):
        state: AgentState = {
            "messages": [{"content": "dict response"}],
            "start_time": time.perf_counter(),
        }
        result = await ResearchAgent.return_response(state)
        assert result["response"] == "dict response"

    @pytest.mark.asyncio
    async def test_no_start_time(self):
        state: AgentState = {
            "messages": [AIMessage(content="response")],
        }
        result = await ResearchAgent.return_response(state)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_empty_ai_content_returns_fallback(self):
        state: AgentState = {
            "messages": [AIMessage(content="")],
            "start_time": time.perf_counter(),
        }
        result = await ResearchAgent.return_response(state)
        assert result["response"] == "No response provided"


# ---------------------------------------------------------------------------
# ResearchAgent class-level tests
# ---------------------------------------------------------------------------

class TestResearchAgentClass:
    """Tests for ResearchAgent static properties."""

    def test_supported_content_types(self):
        assert "text" in ResearchAgent.SUPPORTED_CONTENT_TYPES
        assert "text/plain" in ResearchAgent.SUPPORTED_CONTENT_TYPES

    def test_tools_by_name_default(self):
        assert isinstance(ResearchAgent.tools_by_name, dict)
