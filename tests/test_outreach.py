"""Unit tests for the Outreach Agent."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent_outreach.workflow.models import AgentState, ResponseFormat
from agent_outreach.workflow.parse_query import extract_user_query
from agent_outreach.workflow.create_text import create_text
from agent_outreach.agent import OutreachAgent


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestResponseFormat:
    """Tests for the Outreach ResponseFormat Pydantic model."""

    def test_default_status(self):
        r = ResponseFormat(message={"email": "hi", "linkedin": "hey"})
        assert r.status == "working"

    def test_completed_status(self):
        r = ResponseFormat(status="completed", message={"email": "done"})
        assert r.status == "completed"

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            ResponseFormat(status="invalid", message={"test": "bad"})


# ---------------------------------------------------------------------------
# extract_user_query
# ---------------------------------------------------------------------------

class TestExtractUserQuery:
    """Tests for the outreach extract_user_query node."""

    @pytest.mark.asyncio
    async def test_extracts_human_message(self):
        state: AgentState = {
            "messages": [HumanMessage(content="Draft email to Acme CEO")],
        }
        result = await extract_user_query(state)
        assert result["user_query"] == "Draft email to Acme CEO"
        assert result["status"] == "working"
        assert isinstance(result["start_time"], float)

    @pytest.mark.asyncio
    async def test_no_human_message(self):
        state: AgentState = {
            "messages": [AIMessage(content="ai reply")],
        }
        result = await extract_user_query(state)
        assert result["user_query"] == "No query provided"

    @pytest.mark.asyncio
    async def test_empty_messages(self):
        state: AgentState = {"messages": []}
        result = await extract_user_query(state)
        assert result["user_query"] == "No query provided"


# ---------------------------------------------------------------------------
# create_text (with mocked LLM)
# ---------------------------------------------------------------------------

class TestCreateText:
    """Tests for the create_text function."""

    @pytest.mark.asyncio
    @patch("agent_outreach.workflow.create_text.ChatOpenAI")
    async def test_creates_email_text(self, mock_openai_cls):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Dear John, ...")
        mock_openai_cls.return_value = mock_llm

        state: AgentState = {
            "messages": [],
            "name": "Acme Corp",
            "company_data": {"offering": "cloud services"},
            "recipient": "John Doe",
            "news": "Acme just raised Series B funding.",
        }
        mock_agent = AsyncMock()

        result = await create_text(agent=mock_agent, state=state, medium="email")
        assert result == "Dear John, ..."
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    @patch("agent_outreach.workflow.create_text.ChatOpenAI")
    async def test_creates_linkedin_message(self, mock_openai_cls):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Hi John, connecting about...")
        mock_openai_cls.return_value = mock_llm

        state: AgentState = {
            "messages": [],
            "name": "Acme Corp",
            "company_data": {"offering": "AI platform"},
            "recipient": "John Doe",
            "news": "Recent AI partnership.",
        }
        mock_agent = AsyncMock()

        result = await create_text(agent=mock_agent, state=state, medium="message")
        assert result == "Hi John, connecting about..."

    @pytest.mark.asyncio
    @patch("agent_outreach.workflow.create_text.ChatOpenAI")
    async def test_handles_none_company_data(self, mock_openai_cls):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="Hello")
        mock_openai_cls.return_value = mock_llm

        state: AgentState = {
            "messages": [],
            "name": "Acme",
            "company_data": None,
            "recipient": "Jane",
            "news": "news item",
        }
        mock_agent = AsyncMock()

        result = await create_text(agent=mock_agent, state=state, medium="email")
        assert result == "Hello"


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------

class TestFinalize:
    """Tests for the OutreachAgent.finalize node."""

    def test_finalize_with_both_responses(self):
        state: AgentState = {
            "response_email": "  Email body  ",
            "response_message": "  LinkedIn message  ",
            "recipient": "John Doe",
            "ceo_email": "john@acme.com",
            "ceo_linkedin": "https://linkedin.com/in/johndoe",
            "start_time": time.perf_counter(),
            "messages": [],
        }
        result = OutreachAgent.finalize(state)
        assert result["status"] == "completed"

        response_data = json.loads(result["response"])
        assert response_data["email"] == "Email body"
        assert response_data["message"] == "LinkedIn message"
        assert response_data["ceo_name"] == "John Doe"
        assert response_data["ceo_email"] == "john@acme.com"
        assert response_data["ceo_linkedin"] == "https://linkedin.com/in/johndoe"

    def test_finalize_missing_email(self):
        state: AgentState = {
            "response_email": None,
            "response_message": "LinkedIn message",
            "start_time": time.perf_counter(),
            "messages": [],
        }
        result = OutreachAgent.finalize(state)
        assert result["status"] == "error"

    def test_finalize_missing_message(self):
        state: AgentState = {
            "response_email": "Email body",
            "response_message": None,
            "start_time": time.perf_counter(),
            "messages": [],
        }
        result = OutreachAgent.finalize(state)
        assert result["status"] == "error"

    def test_finalize_both_missing(self):
        state: AgentState = {
            "response_email": None,
            "response_message": None,
            "start_time": time.perf_counter(),
            "messages": [],
        }
        result = OutreachAgent.finalize(state)
        assert result["status"] == "error"

    def test_finalize_with_no_start_time(self):
        state: AgentState = {
            "response_email": "Email",
            "response_message": "Message",
            "recipient": "Jane",
            "ceo_email": "jane@co.com",
            "ceo_linkedin": "",
            "messages": [],
        }
        result = OutreachAgent.finalize(state)
        assert result["status"] == "completed"

    def test_finalize_strips_whitespace(self):
        state: AgentState = {
            "response_email": "\n\n  Email text  \n",
            "response_message": "  Msg  ",
            "recipient": "  Name  ",
            "ceo_email": " a@b.com ",
            "ceo_linkedin": " https://linkedin.com/in/x ",
            "start_time": time.perf_counter(),
            "messages": [],
        }
        result = OutreachAgent.finalize(state)
        data = json.loads(result["response"])
        assert data["email"] == "Email text"
        assert data["message"] == "Msg"
        assert data["ceo_name"] == "Name"
        assert data["ceo_email"] == "a@b.com"
        assert data["ceo_linkedin"] == "https://linkedin.com/in/x"


# ---------------------------------------------------------------------------
# get_email_text / get_message_text
# ---------------------------------------------------------------------------

class TestGetEmailAndMessageText:
    """Tests for get_email_text and get_message_text class methods."""

    @pytest.mark.asyncio
    @patch("agent_outreach.agent.create_text", new_callable=AsyncMock)
    async def test_get_email_text(self, mock_create_text):
        mock_create_text.return_value = "Generated email"
        OutreachAgent.agent = AsyncMock()

        state: AgentState = {"messages": [], "name": "Test"}
        result = await OutreachAgent.get_email_text(state)
        assert result == {"response_email": "Generated email"}
        mock_create_text.assert_called_once_with(
            agent=OutreachAgent.agent,
            state=state,
            medium="email",
        )

    @pytest.mark.asyncio
    @patch("agent_outreach.agent.create_text", new_callable=AsyncMock)
    async def test_get_message_text(self, mock_create_text):
        mock_create_text.return_value = "Generated LinkedIn msg"
        OutreachAgent.agent = AsyncMock()

        state: AgentState = {"messages": [], "name": "Test"}
        result = await OutreachAgent.get_message_text(state)
        assert result == {"response_message": "Generated LinkedIn msg"}
        mock_create_text.assert_called_once_with(
            agent=OutreachAgent.agent,
            state=state,
            medium="message",
        )


# ---------------------------------------------------------------------------
# OutreachAgent class-level tests
# ---------------------------------------------------------------------------

class TestOutreachAgentClass:
    """Tests for OutreachAgent static properties."""

    def test_supported_content_types(self):
        assert "text" in OutreachAgent.SUPPORTED_CONTENT_TYPES
        assert "text/plain" in OutreachAgent.SUPPORTED_CONTENT_TYPES
