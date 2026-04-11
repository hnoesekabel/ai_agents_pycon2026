"""Unit tests for the World News MCP Server (mocked API, no API key needed)."""

import json
from unittest.mock import patch, MagicMock

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

from mcp_worldnews.__main__ import mcp, news_search


# ---------------------------------------------------------------------------
# Direct function tests (with mocked WorldNews API)
# ---------------------------------------------------------------------------

class TestNewsSearchFunction:
    """Tests for the news_search tool function directly."""

    @pytest.mark.asyncio
    @patch("mcp_worldnews.__main__.ApiClient")
    async def test_returns_json_with_news(self, mock_api_client_cls):
        # Set up mock chain: ApiClient -> NewsApi -> search_news
        mock_api_response = MagicMock()
        mock_api_response.to_json.return_value = json.dumps({
            "available": 100,
            "number": 2,
            "news": [
                {
                    "title": "Anthropic Raises $5B",
                    "text": "Anthropic announced a major funding round.",
                    "summary": "Big AI funding.",
                    "url": "https://news.example.com/anthropic",
                    "publish_date": "2026-03-15",
                    "sentiment": 0.8,
                    "authors": ["John Reporter"],
                },
                {
                    "title": "Claude 4 Released",
                    "text": "Anthropic releases Claude 4.",
                    "summary": "New model release.",
                    "url": "https://news.example.com/claude4",
                    "publish_date": "2026-03-10",
                    "sentiment": 0.9,
                    "authors": ["Jane Writer"],
                },
            ],
        })

        mock_api_instance = MagicMock()
        mock_news_api = MagicMock()
        mock_news_api.search_news.return_value = mock_api_response
        mock_api_instance.__enter__ = MagicMock(return_value=mock_api_instance)
        mock_api_instance.__exit__ = MagicMock(return_value=False)
        mock_api_client_cls.return_value = mock_api_instance

        with patch("mcp_worldnews.__main__.NewsApi", return_value=mock_news_api):
            result = await news_search("Anthropic", nr_results=2)

        data = json.loads(result)
        assert data["available"] == 100
        assert len(data["news"]) == 2
        assert data["news"][0]["title"] == "Anthropic Raises $5B"

    @pytest.mark.asyncio
    @patch("mcp_worldnews.__main__.ApiClient")
    async def test_returns_empty_on_api_exception(self, mock_api_client_cls):
        from worldnewsapi.exceptions import ApiException

        mock_api_instance = MagicMock()
        mock_news_api = MagicMock()
        mock_news_api.search_news.side_effect = ApiException(status=429, reason="Rate limited")
        mock_api_instance.__enter__ = MagicMock(return_value=mock_api_instance)
        mock_api_instance.__exit__ = MagicMock(return_value=False)
        mock_api_client_cls.return_value = mock_api_instance

        with patch("mcp_worldnews.__main__.NewsApi", return_value=mock_news_api):
            result = await news_search("test")

        assert result == "{}"

    @pytest.mark.asyncio
    @patch("mcp_worldnews.__main__.ApiClient")
    async def test_empty_news_results(self, mock_api_client_cls):
        mock_api_response = MagicMock()
        mock_api_response.to_json.return_value = json.dumps({
            "available": 0,
            "number": 0,
            "news": [],
        })

        mock_api_instance = MagicMock()
        mock_news_api = MagicMock()
        mock_news_api.search_news.return_value = mock_api_response
        mock_api_instance.__enter__ = MagicMock(return_value=mock_api_instance)
        mock_api_instance.__exit__ = MagicMock(return_value=False)
        mock_api_client_cls.return_value = mock_api_instance

        with patch("mcp_worldnews.__main__.NewsApi", return_value=mock_news_api):
            result = await news_search("nonexistent_keyword_xyz", nr_results=5)

        data = json.loads(result)
        assert data["available"] == 0
        assert data["news"] == []

    @pytest.mark.asyncio
    @patch("mcp_worldnews.__main__.ApiClient")
    async def test_search_passes_correct_parameters(self, mock_api_client_cls):
        mock_api_response = MagicMock()
        mock_api_response.to_json.return_value = '{"available": 0, "number": 0, "news": []}'

        mock_api_instance = MagicMock()
        mock_news_api = MagicMock()
        mock_news_api.search_news.return_value = mock_api_response
        mock_api_instance.__enter__ = MagicMock(return_value=mock_api_instance)
        mock_api_instance.__exit__ = MagicMock(return_value=False)
        mock_api_client_cls.return_value = mock_api_instance

        with patch("mcp_worldnews.__main__.NewsApi", return_value=mock_news_api):
            await news_search("NVIDIA", nr_results=3)

        mock_news_api.search_news.assert_called_once_with(
            text="NVIDIA",
            text_match_indexes="title,content",
            number=3,
        )


# ---------------------------------------------------------------------------
# MCP protocol-level tests
# ---------------------------------------------------------------------------

class TestNewsSearchMCP:
    """Tests for the news_search tool via MCP protocol."""

    @pytest.mark.asyncio
    async def test_tool_listed_in_tools(self):
        async with create_connected_server_and_client_session(
            mcp._mcp_server  # pylint: disable=protected-access
        ) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "news_search" in tool_names

    @pytest.mark.asyncio
    @patch("mcp_worldnews.__main__.ApiClient")
    async def test_tool_callable_via_mcp(self, mock_api_client_cls):
        mock_api_response = MagicMock()
        mock_api_response.to_json.return_value = json.dumps({
            "available": 1,
            "number": 1,
            "news": [{"title": "Test News", "url": "https://example.com"}],
        })

        mock_api_instance = MagicMock()
        mock_news_api = MagicMock()
        mock_news_api.search_news.return_value = mock_api_response
        mock_api_instance.__enter__ = MagicMock(return_value=mock_api_instance)
        mock_api_instance.__exit__ = MagicMock(return_value=False)
        mock_api_client_cls.return_value = mock_api_instance

        with patch("mcp_worldnews.__main__.NewsApi", return_value=mock_news_api):
            async with create_connected_server_and_client_session(
                mcp._mcp_server  # pylint: disable=protected-access
            ) as client:
                result = await client.call_tool(
                    "news_search",
                    {"keywords": "test", "nr_results": 1},
                )
                assert result.isError is False
                assert len(result.content) == 1
                assert isinstance(result.content[0], TextContent)

                data = json.loads(result.content[0].text)
                assert "news" in data
                assert data["news"][0]["title"] == "Test News"
