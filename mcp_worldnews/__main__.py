"""MCP Server for World News API."""

import logging
import os
import argparse

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from worldnewsapi.configuration import Configuration
from worldnewsapi.api_client import ApiClient
from worldnewsapi.api.news_api import NewsApi
from worldnewsapi.exceptions import ApiException


mcp = FastMCP(
    name="WorldNews",
    host=os.getenv("HOST_MCP_NEWS", "localhost"),
    port=int(os.getenv("PORT_MCP_NEWS", "9002")),
)
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

configuration = Configuration(
    host = "https://api.worldnewsapi.com",
)
configuration.api_key['apiKey'] = os.getenv("WORLD_NEWS_API_KEY", "")
configuration.api_key['headerApiKey'] = os.getenv("WORLD_NEWS_API_KEY", "")


@mcp.tool()
async def news_search(keywords: str, nr_results: int = 10) -> str:
    """Search for global news articles using high-relevance keywords.

    This tool is essential for gathering current information about companies, products,
    or emerging topics. It is particularly useful for researching fresh news that can be
    distilled into an outreach message.

    Args:
        keywords (str): One or more search terms. Use broad terms for more results or specific
            phrases for targeted searches.
            Example: "Anthropic" or "NVIDIA earnings report March 2026".
        nr_results (int, optional): The maximum number of news articles to retrieve (1-100).
            Higher numbers provide broader context; lower numbers focus on relevant top results.
            Defaults to 10.

    Returns:
        str: A JSON string containing the search results. Key fields in the JSON include:
            - "available": The total number of news items matching the query.
            - "news": A list of article objects, each containing:
                - "title": The headline of the article.
                - "text": The full or partial text of the article.
                - "summary": A concise preview or excerpt.
                - "url": The source link for the full story.
                - "publish_date": When the article was released.
                - "sentiment": A numerical score (e.g., -1 to 1) indicating the article's tone.
                - "authors": A list of individuals credited with the work.
    """
    with ApiClient(configuration) as api_client:
        api_instance = NewsApi(api_client)
        try:
            api_response = api_instance.search_news(
                text=keywords,
                text_match_indexes="title,content",
                number=nr_results,
            )
            return api_response.to_json()

        except ApiException as e:
            logger.error("Exception when calling NewsApi->extract_news: %s\n", e)
            return "{}"


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
