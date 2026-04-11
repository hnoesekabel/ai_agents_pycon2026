"""Test the World News MCP Server."""

import sys
import os
import json
import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

sys.path.append(os.getcwd())

from mcp_worldnews.__main__ import mcp  # pylint: disable=wrong-import-position


@pytest.mark.asyncio
async def test_news_search():
    """Run a single news search for a company name."""
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:  # pylint: disable=protected-access
        result = await client.call_tool(
            "news_search",
            {"keywords": "Anthropic", "nr_results": 1},
        )

        # 1. Verify general execution success
        assert result.isError is False
        assert len(result.content) == 1
        assert isinstance(result.content[0], TextContent)

        # 2. Parse and verify JSON structure
        data = json.loads(result.content[0].text)
        assert isinstance(data, dict)
        assert "news" in data
        assert "available" in data
        assert "number" in data

        # 3. Verify news contents
        news_list = data["news"]
        assert isinstance(news_list, list)

        if news_list:
            article = news_list[0]
            assert "title" in article
            assert "url" in article
            assert "text" in article
            # Check if keywords were found ("Anthropic" mentioned)
            assert any("anthropic" in str(v).lower() for v in article.values())
        else:
            pytest.skip("No news found, check search parameters or API key quota.")
