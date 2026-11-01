"""Web search for things outside the campus data.

Backend is picked automatically:
1. TAVILY_API_KEY set -> Tavily (AI search, free tier: 1000 requests/month)
2. otherwise          -> DuckDuckGo (ddgs package, free, no key)
"""

import os

from langchain_core.tools import tool

MAX_RESULTS = 5


def _search_tavily(query: str) -> str:
    from langchain_tavily import TavilySearch

    results = TavilySearch(max_results=MAX_RESULTS).invoke({"query": query})
    # Tavily can return a dict or a list; handle both.
    items = results.get("results", []) if isinstance(results, dict) else results
    lines = []
    for item in items:
        if isinstance(item, dict):
            lines.append(f"- {item.get('title', '')}\n  {item.get('url', '')}\n  {item.get('content', '')}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines) or "No results."


def _search_duckduckgo(query: str) -> str:
    from ddgs import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=MAX_RESULTS))
    return "\n".join(
        f"- {r.get('title', '')}\n  {r.get('href', '')}\n  {r.get('body', '')}" for r in results
    ) or "No results."


@tool
def web_search(query: str) -> str:
    """Search the web for current information outside the campus data,
    such as energy prices, regulations or news.

    Args:
        query: What to search for.
    """
    if os.environ.get("TAVILY_API_KEY"):
        try:
            return _search_tavily(query)
        except Exception as e:
            return f"Tavily search failed: {e}"
    try:
        return _search_duckduckgo(query)
    except Exception as e:
        return f"DuckDuckGo search failed: {e}"
