"""Provide URLs for the MCP servers."""

import os


MCP_CRAWL4AI_URL = (
    f"http://{os.getenv('HOST_MCP_CRAWL4AI', 'localhost')}"
    + f":{os.getenv('PORT_MCP_CRAWL4AI', '9000')}/mcp"
)
MCP_GOOGLE_URL = (
    f"http://{os.getenv('HOST_MCP_GOOGLE', 'localhost')}"
    + f":{os.getenv('PORT_MCP_GOOGLE', '9001')}/mcp"
)
MCP_NEWS_URL = (
    f"http://{os.getenv('HOST_MCP_NEWS', 'localhost')}"
    + f":{os.getenv('PORT_MCP_NEWS', '9002')}/mcp"
)
