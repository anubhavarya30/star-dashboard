#!/usr/bin/env python3
"""
STAR — Crawl4AI MCP server (free, self-hosted, no API key). Exposes web scraping
to Claude Code so we can pull data points (SEC filings, earnings, news, any page)
into research. Backed by Crawl4AI (62k★) → clean LLM-ready markdown via a real
headless browser, so JS-heavy sites work.

Wire into Claude Code:
  claude mcp add crawl4ai --scope user -- \
    /Users/anubhavarya/star/star-dashboard/venv/bin/python3 \
    /Users/anubhavarya/star/star-dashboard/engine/crawl_mcp.py
"""
from mcp.server.fastmcp import FastMCP
from crawl4ai import AsyncWebCrawler

mcp = FastMCP("crawl4ai")


@mcp.tool()
async def scrape(url: str) -> str:
    """Scrape a single URL and return its main content as clean markdown.
    Use for news articles, SEC filings, company pages, earnings info, etc."""
    try:
        async with AsyncWebCrawler() as c:
            r = await c.arun(url=url)
            md = r.markdown or ""
            return md[:20000] if md else "(no content extracted)"
    except Exception as e:
        return f"scrape failed: {type(e).__name__}: {e}"


@mcp.tool()
async def extract(url: str, question: str) -> str:
    """Scrape a URL and return only the parts relevant to `question`
    (keyword-filtered). Good for pulling a specific data point from a long page."""
    try:
        async with AsyncWebCrawler() as c:
            r = await c.arun(url=url)
            md = r.markdown or ""
            if not md:
                return "(no content)"
            terms = [w.lower() for w in question.split() if len(w) > 3]
            hits = [ln for ln in md.splitlines() if any(t in ln.lower() for t in terms)]
            return ("\n".join(hits)[:8000]) if hits else md[:4000]
    except Exception as e:
        return f"extract failed: {type(e).__name__}: {e}"


if __name__ == "__main__":
    mcp.run()   # stdio transport
