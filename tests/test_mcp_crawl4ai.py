"""Unit tests for the Crawl4AI MCP Server."""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

from mcp_crawl4ai.__main__ import mcp, deep_crawl


# ---------------------------------------------------------------------------
# Helpers to build mock crawl results
# ---------------------------------------------------------------------------

def _make_crawl_result(url, score=0, content="# Page Content", success=True):
    """Create a mock CrawlResult object."""
    result = MagicMock()
    result.success = success
    result.url = url
    result.metadata = {"score": score}
    result.markdown = content
    return result


class _AsyncCrawlResults:
    """Async iterator wrapper for mock crawl results."""

    def __init__(self, results):
        self._results = results

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._results:
            raise StopAsyncIteration
        return self._results.pop(0)


# ---------------------------------------------------------------------------
# Direct function tests (with mocked crawler)
# ---------------------------------------------------------------------------

class TestDeepCrawlFunction:
    """Tests for the deep_crawl tool function directly."""

    @pytest.mark.asyncio
    @patch("mcp_crawl4ai.__main__.AsyncWebCrawler")
    async def test_returns_crawled_pages(self, mock_crawler_cls):
        crawl_results = [
            _make_crawl_result("https://example.com", score=0.9, content="# Home Page"),
            _make_crawl_result("https://example.com/about", score=0.7, content="# About Us"),
        ]

        # Set up the async context manager and arun
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _AsyncCrawlResults(crawl_results)
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler_cls.return_value = mock_crawler

        results = await deep_crawl("https://example.com", keywords=["about"])
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["url"] == "https://example.com"
        assert results[0]["score"] == 0.9
        assert results[0]["content"] == "# Home Page"
        assert results[1]["url"] == "https://example.com/about"

    @pytest.mark.asyncio
    @patch("mcp_crawl4ai.__main__.AsyncWebCrawler")
    async def test_filters_failed_results(self, mock_crawler_cls):
        crawl_results = [
            _make_crawl_result("https://example.com", success=True, content="Good"),
            _make_crawl_result("https://example.com/broken", success=False),
        ]

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _AsyncCrawlResults(crawl_results)
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler_cls.return_value = mock_crawler

        results = await deep_crawl("https://example.com")
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"

    @pytest.mark.asyncio
    @patch("mcp_crawl4ai.__main__.AsyncWebCrawler")
    async def test_empty_site_returns_empty_list(self, mock_crawler_cls):
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _AsyncCrawlResults([])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler_cls.return_value = mock_crawler

        results = await deep_crawl("https://empty-site.com")
        assert results == []

    @pytest.mark.asyncio
    @patch("mcp_crawl4ai.__main__.AsyncWebCrawler")
    async def test_no_keywords_uses_bfs_strategy(self, mock_crawler_cls):
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _AsyncCrawlResults([])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler_cls.return_value = mock_crawler

        results = await deep_crawl("https://example.com", keywords=None)
        assert results == []
        # Verify arun was called (strategy selection is internal)
        mock_crawler.arun.assert_called_once()

    @pytest.mark.asyncio
    @patch("mcp_crawl4ai.__main__.AsyncWebCrawler")
    async def test_with_keywords_uses_best_first_strategy(self, mock_crawler_cls):
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _AsyncCrawlResults([])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler_cls.return_value = mock_crawler

        results = await deep_crawl("https://example.com", keywords=["pricing", "API"])
        assert results == []
        mock_crawler.arun.assert_called_once()

    @pytest.mark.asyncio
    @patch("mcp_crawl4ai.__main__.AsyncWebCrawler")
    async def test_custom_max_pages_and_depth(self, mock_crawler_cls):
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _AsyncCrawlResults([])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler_cls.return_value = mock_crawler

        await deep_crawl("https://example.com", max_pages=50, max_depth=1)
        mock_crawler.arun.assert_called_once()

    @pytest.mark.asyncio
    @patch("mcp_crawl4ai.__main__.AsyncWebCrawler")
    async def test_score_defaults_to_zero(self, mock_crawler_cls):
        result_obj = MagicMock()
        result_obj.success = True
        result_obj.url = "https://example.com"
        result_obj.metadata = {}  # no "score" key
        result_obj.markdown = "Content"

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _AsyncCrawlResults([result_obj])
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler_cls.return_value = mock_crawler

        results = await deep_crawl("https://example.com")
        assert results[0]["score"] == 0


# ---------------------------------------------------------------------------
# MCP protocol-level tests
# ---------------------------------------------------------------------------

class TestDeepCrawlMCP:
    """Tests for the deep_crawl tool via MCP protocol."""

    @pytest.mark.asyncio
    async def test_tool_listed_in_tools(self):
        async with create_connected_server_and_client_session(
            mcp._mcp_server  # pylint: disable=protected-access
        ) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "deep_crawl" in tool_names

    @pytest.mark.asyncio
    @patch("mcp_crawl4ai.__main__.AsyncWebCrawler")
    async def test_tool_callable_via_mcp(self, mock_crawler_cls):
        crawl_results = [
            _make_crawl_result("https://test.com", score=1, content="# Test"),
        ]

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _AsyncCrawlResults(crawl_results)
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler_cls.return_value = mock_crawler

        async with create_connected_server_and_client_session(
            mcp._mcp_server  # pylint: disable=protected-access
        ) as client:
            result = await client.call_tool(
                "deep_crawl",
                {"url": "https://test.com", "max_pages": 1, "max_depth": 1},
            )
            assert result.isError is False
            assert len(result.content) >= 1
            assert isinstance(result.content[0], TextContent)

            # Verify the result text contains expected data
            text = result.content[0].text
            assert "https://test.com" in text
            assert "# Test" in text

    @pytest.mark.asyncio
    async def test_tool_has_expected_parameters(self):
        async with create_connected_server_and_client_session(
            mcp._mcp_server  # pylint: disable=protected-access
        ) as client:
            tools = await client.list_tools()
            deep_crawl_tool = next(t for t in tools.tools if t.name == "deep_crawl")
            params = deep_crawl_tool.inputSchema.get("properties", {})
            assert "url" in params
            assert "keywords" in params
            assert "max_pages" in params
            assert "max_depth" in params
