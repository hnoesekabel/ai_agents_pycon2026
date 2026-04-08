"""Unit tests for the Google Search MCP Server."""

import json
from unittest.mock import patch, MagicMock

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

from mcp_google.__main__ import mcp, web_search


# ---------------------------------------------------------------------------
# Direct function tests (with mocked Google API)
# ---------------------------------------------------------------------------

class TestWebSearchFunction:
    """Tests for the web_search tool function directly."""

    @pytest.mark.asyncio
    @patch("mcp_google.__main__.GoogleSearchAPIWrapper")
    async def test_returns_list_of_results(self, mock_wrapper_cls):
        mock_instance = MagicMock()
        mock_instance.results.return_value = [
            {"title": "Acme Corp", "url": "https://acme.com", "snippet": "Leading tech company"},
            {"title": "Acme Wikipedia", "url": "https://en.wikipedia.org/wiki/Acme", "snippet": "About Acme"},
        ]
        mock_wrapper_cls.return_value = mock_instance

        results = await web_search("Acme Corp", nr_results=2)
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["title"] == "Acme Corp"
        assert results[0]["url"] == "https://acme.com"
        assert results[0]["snippet"] == "Leading tech company"

    @pytest.mark.asyncio
    @patch("mcp_google.__main__.GoogleSearchAPIWrapper")
    async def test_default_nr_results(self, mock_wrapper_cls):
        mock_instance = MagicMock()
        mock_instance.results.return_value = []
        mock_wrapper_cls.return_value = mock_instance

        await web_search("test query")
        mock_wrapper_cls.assert_called_once_with(k=10)
        mock_instance.results.assert_called_once_with("test query", 10)

    @pytest.mark.asyncio
    @patch("mcp_google.__main__.GoogleSearchAPIWrapper")
    async def test_custom_nr_results(self, mock_wrapper_cls):
        mock_instance = MagicMock()
        mock_instance.results.return_value = [
            {"title": "Result", "url": "https://example.com", "snippet": "Example"},
        ]
        mock_wrapper_cls.return_value = mock_instance

        results = await web_search("query", nr_results=5)
        mock_wrapper_cls.assert_called_once_with(k=5)
        mock_instance.results.assert_called_once_with("query", 5)

    @pytest.mark.asyncio
    @patch("mcp_google.__main__.GoogleSearchAPIWrapper")
    async def test_empty_results(self, mock_wrapper_cls):
        mock_instance = MagicMock()
        mock_instance.results.return_value = []
        mock_wrapper_cls.return_value = mock_instance

        results = await web_search("obscure nonexistent query xyz123")
        assert results == []


# ---------------------------------------------------------------------------
# MCP protocol-level tests (with mocked Google API)
# ---------------------------------------------------------------------------

class TestWebSearchMCP:
    """Tests for the web_search tool via MCP protocol."""

    @pytest.mark.asyncio
    @patch("mcp_google.__main__.GoogleSearchAPIWrapper")
    async def test_tool_callable_via_mcp(self, mock_wrapper_cls):
        mock_instance = MagicMock()
        mock_instance.results.return_value = [
            {"title": "Test Result", "url": "https://test.com", "snippet": "A test result"},
        ]
        mock_wrapper_cls.return_value = mock_instance

        async with create_connected_server_and_client_session(
            mcp._mcp_server  # pylint: disable=protected-access
        ) as client:
            result = await client.call_tool(
                "web_search",
                {"query": "test", "nr_results": 1},
            )
            assert result.isError is False
            assert len(result.content) == 1
            assert isinstance(result.content[0], TextContent)

    @pytest.mark.asyncio
    @patch("mcp_google.__main__.GoogleSearchAPIWrapper")
    async def test_tool_listed_in_tools(self, mock_wrapper_cls):
        async with create_connected_server_and_client_session(
            mcp._mcp_server  # pylint: disable=protected-access
        ) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "web_search" in tool_names

    @pytest.mark.asyncio
    @patch("mcp_google.__main__.GoogleSearchAPIWrapper")
    async def test_tool_result_contains_expected_data(self, mock_wrapper_cls):
        mock_instance = MagicMock()
        mock_instance.results.return_value = [
            {"title": "JSON Test", "url": "https://json.com", "snippet": "Valid JSON"},
        ]
        mock_wrapper_cls.return_value = mock_instance

        async with create_connected_server_and_client_session(
            mcp._mcp_server  # pylint: disable=protected-access
        ) as client:
            result = await client.call_tool(
                "web_search",
                {"query": "json test", "nr_results": 1},
            )
            # The result text should contain the expected data
            text = result.content[0].text
            assert "JSON Test" in text
            assert "https://json.com" in text
