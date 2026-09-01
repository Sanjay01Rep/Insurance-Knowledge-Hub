"""Tavily Search API — question text only. Never send files or document text."""

from __future__ import annotations

from config import env, reload_env, web_search_configured
from db import logger

# Official API: Tavily Search
# Docs: https://docs.tavily.com/documentation/api-reference/endpoint/search
# HTTP: POST https://api.tavily.com/search
TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"
MAX_QUERY_CHARS = 400


def search_web(question: str) -> list[dict]:
    """Search the public web with the user's question only.

    Never pass Excel/PDF/DOCX contents, chunk text, or file uploads here.
    """
    reload_env()
    query = (question or "").strip()
    if not query:
        return []
    if not web_search_configured():
        return []

    query = query[:MAX_QUERY_CHARS]
    try:
        import httpx

        response = httpx.post(
            TAVILY_SEARCH_ENDPOINT,
            headers={
                "Authorization": f"Bearer {env('TAVILY_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            },
            timeout=20.0,
        )
        if response.status_code != 200:
            logger.info("tavily http_status=%s", response.status_code)
            return []
        payload = response.json()
    except Exception:
        logger.exception("tavily request failed")
        return []

    results: list[dict] = []
    for item in payload.get("results") or []:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("content") or "").strip()
        if not title and not url:
            continue
        results.append(
            {
                "kind": "web",
                "label": title or url,
                "url": url,
                "snippet": snippet,
            }
        )
    logger.info("tavily hits=%s query_len=%s", len(results), len(query))
    return results
