"""
Elfa AI Scraper — Social Sentiment & Trending Token Intelligence
Fetches trending tokens, top social mentions, keyword searches, and
token news from Twitter/Telegram via the Elfa AI API.

API Docs: https://docs.elfa.ai/api/rest/elfa-api
Auth: x-elfa-api-key header (ELFA_API_KEY in .env)
"""

import os
import requests


BASE_URL = "https://api.elfa.ai/v2"


def _headers() -> dict | None:
    """Get auth headers for Elfa API."""
    key = os.getenv("ELFA_API_KEY", "").strip()
    if not key:
        return None
    return {"x-elfa-api-key": key, "Accept": "application/json"}


def _extract_list(response_json: dict) -> list:
    """
    Safely extract the item list from Elfa's response.

    Elfa returns two shapes:
      • { success, data: [ ... ] }              → items in data directly
      • { success, data: { total, page, data: [ ... ] } } → paginated wrapper
    """
    data = response_json.get("data", [])
    if isinstance(data, dict):
        return data.get("data", [])
    if isinstance(data, list):
        return data
    return []


def get_trending_tokens(time_window: str = "24h", min_mentions: int = 5, limit: int = 20) -> dict:
    """
    Get trending tokens by social mention volume.

    Args:
        time_window: '1h', '4h', '8h', '24h'
        min_mentions: Minimum mention count to include
        limit: Number of results (max 50)
    """
    headers = _headers()
    if not headers:
        return {"error": "ELFA_API_KEY not set. Get one at https://elfa.ai"}

    try:
        r = requests.get(
            f"{BASE_URL}/aggregations/trending-tokens",
            headers=headers,
            params={"timeWindow": time_window, "minMentions": min_mentions, "limit": min(limit, 50)},
            timeout=15,
        )
        r.raise_for_status()
        items = _extract_list(r.json())

        tokens = []
        for item in items:
            tokens.append({
                "token": item.get("token", "N/A"),
                "mentions": item.get("current_count", item.get("mentionsCount", 0)),
                "previous_mentions": item.get("previous_count", None),
                "change_pct": item.get("change_percent", None),
            })

        return {
            "time_window": time_window,
            "total_tokens": len(tokens),
            "trending": tokens[:limit],
        }
    except Exception as e:
        return {"error": f"Elfa API error: {str(e)}"}


def get_top_mentions(ticker: str, time_window: str = "24h", limit: int = 10) -> dict:
    """
    Get top social media mentions for a token/ticker.

    Args:
        ticker: Token ticker symbol (e.g. 'BTC', 'ETH', 'SOL')
        time_window: '1h', '4h', '8h', '24h'
        limit: Number of mentions to return
    """
    headers = _headers()
    if not headers:
        return {"error": "ELFA_API_KEY not set. Get one at https://elfa.ai"}

    try:
        r = requests.get(
            f"{BASE_URL}/data/top-mentions",
            headers=headers,
            params={"ticker": ticker.upper(), "timeWindow": time_window, "limit": min(limit, 50), "includeAccountDetails": True},
            timeout=15,
        )
        r.raise_for_status()
        items = _extract_list(r.json())

        mentions = []
        for item in items:
            # Account info may be nested
            account = item.get("account", {}) or {}
            mentions.append({
                "text": item.get("content", item.get("text", ""))[:280],
                "author": account.get("username", item.get("accountUsername", "N/A")),
                "platform": "twitter",
                "likes": item.get("likeCount", 0),
                "reposts": item.get("repostCount", 0),
                "views": item.get("viewCount", 0),
                "url": item.get("link", item.get("url", "")),
                "posted_at": item.get("mentionedAt", ""),
            })

        return {
            "ticker": ticker.upper(),
            "time_window": time_window,
            "total_mentions": len(mentions),
            "mentions": mentions,
        }
    except Exception as e:
        return {"error": f"Elfa API error: {str(e)}"}


def search_mentions(keywords: str, time_window: str = "24h", limit: int = 15) -> dict:
    """
    Search for social mentions by keywords or account name.

    Args:
        keywords: Search terms (e.g. 'bitcoin halving', 'ETH merge')
        time_window: '1h', '4h', '8h', '24h'
        limit: Number of results
    """
    headers = _headers()
    if not headers:
        return {"error": "ELFA_API_KEY not set. Get one at https://elfa.ai"}

    try:
        r = requests.get(
            f"{BASE_URL}/data/keyword-mentions",
            headers=headers,
            params={"keywords": keywords, "timeWindow": time_window, "limit": min(limit, 50)},
            timeout=15,
        )
        r.raise_for_status()
        items = _extract_list(r.json())

        mentions = []
        for item in items:
            account = item.get("account", {}) or {}
            mentions.append({
                "text": item.get("content", item.get("text", ""))[:280],
                "author": account.get("username", item.get("accountUsername", "N/A")),
                "platform": "twitter",
                "likes": item.get("likeCount", 0),
                "views": item.get("viewCount", 0),
                "url": item.get("link", item.get("url", "")),
            })

        return {
            "keywords": keywords,
            "time_window": time_window,
            "total_results": len(mentions),
            "mentions": mentions,
        }
    except Exception as e:
        return {"error": f"Elfa API error: {str(e)}"}


def get_trending_narratives(time_window: str = "24h", limit: int = 10) -> dict:
    """
    Get trending narratives/themes from social media analysis.

    Note: This endpoint may not be available on all Elfa API tiers.

    Args:
        time_window: '1h', '4h', '8h', '24h'
        limit: Number of narratives
    """
    headers = _headers()
    if not headers:
        return {"error": "ELFA_API_KEY not set. Get one at https://elfa.ai"}

    try:
        r = requests.get(
            f"{BASE_URL}/aggregations/trending-narratives",
            headers=headers,
            params={"timeWindow": time_window, "limit": min(limit, 20)},
            timeout=15,
        )

        # This endpoint returns 404 on some API tiers
        if r.status_code == 404:
            return {
                "error": "trending-narratives endpoint not available on your Elfa plan. "
                         "Try get_trending_tokens or search_mentions instead."
            }

        r.raise_for_status()
        items = _extract_list(r.json())

        narratives = []
        for item in items:
            narratives.append({
                "narrative": item.get("narrative", item.get("title", "N/A")),
                "description": item.get("description", ""),
                "mentions_count": item.get("mentionsCount", item.get("current_count", 0)),
                "tokens": item.get("relatedTokens", []),
            })

        return {
            "time_window": time_window,
            "total_narratives": len(narratives),
            "narratives": narratives,
        }
    except Exception as e:
        return {"error": f"Elfa API error: {str(e)}"}


def get_token_news(ticker: str, limit: int = 10) -> dict:
    """
    Get news mentions for a specific token from social media.

    Args:
        ticker: Token ticker (e.g. 'BTC', 'ETH')
        limit: Number of results
    """
    headers = _headers()
    if not headers:
        return {"error": "ELFA_API_KEY not set. Get one at https://elfa.ai"}

    try:
        r = requests.get(
            f"{BASE_URL}/data/token-news",
            headers=headers,
            params={"ticker": ticker.upper(), "limit": min(limit, 50)},
            timeout=15,
        )
        r.raise_for_status()
        items = _extract_list(r.json())

        articles = []
        for item in items:
            account = item.get("account", {}) or {}
            articles.append({
                "text": item.get("content", item.get("text", ""))[:280],
                "author": account.get("username", item.get("accountUsername", "N/A")),
                "likes": item.get("likeCount", 0),
                "views": item.get("viewCount", 0),
                "url": item.get("link", item.get("url", "")),
                "posted_at": item.get("mentionedAt", ""),
            })

        return {
            "ticker": ticker.upper(),
            "total_articles": len(articles),
            "news": articles,
        }
    except Exception as e:
        return {"error": f"Elfa API error: {str(e)}"}
