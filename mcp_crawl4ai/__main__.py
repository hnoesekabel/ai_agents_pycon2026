"""MCP Server for Crawl4AI."""

import os
import logging
import argparse

from crawl4ai import (
    AsyncWebCrawler,
    CacheMode,
    ContentTypeFilter,
    CrawlerRunConfig,
    FilterChain,
    URLPatternFilter,
)
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy, BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from mcp.server.fastmcp import FastMCP

# prepare the MCP server with name, host and port
mcp = FastMCP(
    name="Crawl4AI",
    host=os.getenv("HOST_MCP_CRAWL4AI", "localhost"),
    port=int(os.getenv("PORT_MCP_CRAWL4AI", "9000")),
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Crawl4AI MCP server")

@mcp.tool()
async def deep_crawl(
    url: str,
    keywords: list[str] | None = None,
    max_pages: int = 200,
    max_depth: int = 3
) -> list[dict]:
    """Crawl a website domain and return the content of all discovered pages.

    Starting from the given URL, follows internal links to collect pages within
    the same domain. Use this tool when you need to gather information from
    multiple pages of a website.

    Crawling strategy:
    - If keywords are provided: prioritizes pages that mention those keywords
    (best for targeted research on a specific topic).
    - If no keywords are provided: crawls breadth-first, exhausting all pages
    at each depth level before going deeper (best for full site discovery).

    Args:
        url (str): Starting URL for the crawl. All discovered links must belong
            to the same domain (e.g. starting at 'https://example.com/intro'
            will also crawl 'https://example.com/about', but not
            'https://other.com').
        keywords (list[str] | None, optional): Keywords used to score and
            prioritize pages. Pages mentioning these keywords are crawled and
            ranked higher. Omit or pass None for breadth-first crawling.
            Example: ["pricing", "enterprise", "API"].
            Defaults to None.
        max_pages (int, optional): Maximum number of pages to crawl and return.
            Increase for large sites, decrease to limit scope. Defaults to 200.
        max_depth (int, optional): Maximum number of link-hops from the starting
            URL. Depth 1 = only pages directly linked from the starting URL.
            Defaults to 3.

    Returns:
        list[dict]: One entry per crawled page, each containing:
            - url (str): The full URL of the page.
            - score (float): Relevance score based on keyword matches (0 if no
                keywords were provided).
            - content (str): Full page content as Markdown text.
    """
    # go for HTML and plain text documents, ignore any binary files
    filter_chain = FilterChain(
        [
            URLPatternFilter(
                patterns=["*.zip", "*.pdf", "*.jpg", "*.png", "*.jpeg", "*.gif"],
                reverse=True,
            ),
            ContentTypeFilter(
                allowed_types=["text/html", "text/plain"],
            ),
        ]
    )
    # set the strategy: if keywords are given, score pages; otherwise breadth first
    strategy = (
        BestFirstCrawlingStrategy(
            max_depth=max_depth,
            max_pages=max_pages,
            include_external=False,
            url_scorer=KeywordRelevanceScorer(keywords=keywords or [], weight=0.7),
            filter_chain=filter_chain,
        )
        if keywords is not None
        else BFSDeepCrawlStrategy(
            max_depth=max_depth,
            max_pages=max_pages,
            include_external=False,
            filter_chain=filter_chain,
        )
    )
    # build the list of result pages with URL, content, and score (if applicable)
    results = []
    async with AsyncWebCrawler() as crawler:
        async for result in await crawler.arun(
            url,
            config=CrawlerRunConfig(
                deep_crawl_strategy=strategy,
                scraping_strategy=LXMLWebScrapingStrategy(),
                cache_mode=CacheMode.ENABLED,
                verbose=False,
                stream=True,
                page_timeout=20 * 1000,  # 20 seconds
                markdown_generator=DefaultMarkdownGenerator(
                    content_source="cleaned_html",
                    options={
                        "ignore_links": True,
                        "ignore_images": True,
                        "escape_html": False,
                    },
                ),
                excluded_tags=["a"],
                exclude_external_links=True,
                exclude_social_media_links=True,
                exclude_external_images=True,
                exclude_all_images=True,
            ),
        ):
            if result.success:
                results.append(
                    {
                        "url": result.url,
                        "score": result.metadata.get("score", 0),
                        "content": result.markdown[
                            :
                        ],  # only [:] produces results
                    }
                )

        return results


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
