"""MCP Server for Google search, using Custom Search Engine."""

import asyncio
import logging
import os
import argparse

from dotenv import load_dotenv
from langchain_google_community import GoogleSearchAPIWrapper
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

load_dotenv()
mcp = FastMCP(
    name="Google-Search",
    host=os.getenv("HOST_MCP_GOOGLE", "localhost"),
    port=int(os.getenv("PORT_MCP_GOOGLE", "9001")),
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@mcp.tool()
async def web_search(query: str, nr_results: int = 10) -> list[dict]:
    """Search the web and return a list of relevant URLs for a given query.

    Use this tool when you need to discover websites or sources on a topic,
    but do not yet have specific URLs to crawl. To get the full content of any
    result, pass the returned URLs to the website crawling tool.

    Args:
        query (str): The search query. Phrase it as you would in a search engine.
            Example: "LangGraph multi-agent tutorial 2024".
        nr_results (int, optional): Maximum number of results to return.
            Increase for broader coverage, decrease for a focused top result.
            Defaults to 10.

    Returns:
        list[dict]: One entry per search result, each containing:
            - title (str): Title of the webpage.
            - url (str): Full URL of the webpage.
            - snippet (str): Short summary or excerpt from the page, as provided
                by the search engine. Use this to assess relevance before crawling.
    """
    cse_search = GoogleSearchAPIWrapper(k=nr_results)
    return await asyncio.to_thread(cse_search.results, query, nr_results)



@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: Request) -> PlainTextResponse:
    """Respond to hearbeat requests."""
    return PlainTextResponse("OK")


if __name__ == "__main__":
    # Parse arguments to allow switching transport (e.g. for testing via stdio)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        default="streamable-http",
        help="MCP transport to use: stdio or streamable-http"
    )
    args, unknown = parser.parse_known_args()
    # start up the MCP server either via stdio or streamable interface
    mcp.run(transport=args.transport)
