"""
Y2 News & Intelligence Scraper
Fetches real-time news with sentiment analysis and AI-generated recaps via the Y2 API.

Requires: pip install y2-py
API key: https://y2.dev/app/developers/api-keys (Y2_API_KEY in .env)
"""

import os


_Y2_UPGRADE_HINT = (
    "Your Y2 API key authenticated successfully but returned no content. "
    "This usually means you're on Y2's free/lite tier, which does not include "
    "news articles, sentiment, recaps, or intelligence reports. "
    "Upgrade to Y2 Pro ($20/mo) for full content access: https://y2.dev/pricing  "
    "Manage your API key scopes at: https://y2.dev/app/developers/api-keys"
)



def _get_client():
    """Initialize the Y2 client."""
    try:
        from y2 import Y2
    except ImportError:
        raise ImportError(
            "y2-py package not installed. Run: uv add y2-py"
        )

    api_key = os.getenv("Y2_API_KEY")
    if not api_key:
        return None
    return Y2(api_key=api_key)


def get_news_sentiment(topics: str = "bitcoin,ethereum", limit: int = 15) -> dict:
    """
    Fetch real-time news with sentiment analysis from Y2's GloriaAI.

    Args:
        topics: Comma-separated topics (e.g. 'bitcoin,ethereum,defi', 'macro', 'ai', 'tech')
        limit:  Number of news items to return (1-50)

    Returns:
        Dict with news items including headline, sentiment (bullish/bearish/neutral), and source.
    """
    client = _get_client()
    if not client:
        return {"error": "Y2_API_KEY not set. Get one at https://y2.dev/app/developers/api-keys"}

    try:
        news = client.news.list(topics=topics, limit=min(limit, 50))

        items = []
        sentiment_counts = {"bullish": 0, "bearish": 0, "neutral": 0}

        for item in news.data:
            sentiment = getattr(item, "sentiment", "neutral") or "neutral"
            if sentiment in sentiment_counts:
                sentiment_counts[sentiment] += 1

            source = getattr(item, "author", None) or "N/A"
            ts_iso = getattr(item, "timestamp_iso", None)
            published = str(ts_iso) if ts_iso else "N/A"
            categories = getattr(item, "categories", []) or []

            items.append({
                "headline": getattr(item, "signal", "N/A"),
                "sentiment": sentiment,
                "sentiment_value": getattr(item, "sentiment_value", None),
                "source": source,
                "published": published,
                "categories": categories,
            })

        total = len(items) or 1
        bull_pct = round(sentiment_counts["bullish"] / total * 100, 1)
        bear_pct = round(sentiment_counts["bearish"] / total * 100, 1)

        if bull_pct > bear_pct + 20:
            overall = "BULLISH"
        elif bear_pct > bull_pct + 20:
            overall = "BEARISH"
        else:
            overall = "MIXED"

        result = {
            "topics": topics,
            "total_items": len(items),
            "overall_sentiment": overall,
            "sentiment_breakdown": {
                "bullish": f"{sentiment_counts['bullish']} ({bull_pct}%)",
                "bearish": f"{sentiment_counts['bearish']} ({bear_pct}%)",
                "neutral": f"{sentiment_counts['neutral']}",
            },
            "news": items,
        }

        if not items:
            result["hint"] = _Y2_UPGRADE_HINT

        return result

    except Exception as e:
        return {"error": f"Y2 API error: {str(e)}"}


def get_news_recap(topics: str = "bitcoin", timeframe: str = "24h") -> dict:
    """
    Get AI-generated news recap/summary for given topics.

    Args:
        topics:    Comma-separated topics (e.g. 'bitcoin', 'macro', 'ai,tech')
        timeframe: Time window: '12h', '24h', '3d', '7d'

    Returns:
        Dict with AI-generated summaries per topic.
    """
    client = _get_client()
    if not client:
        return {"error": "Y2_API_KEY not set. Get one at https://y2.dev/app/developers/api-keys"}

    valid_timeframes = ["12h", "24h", "3d", "7d"]
    if timeframe not in valid_timeframes:
        timeframe = "24h"

    try:
        recaps = client.news.get_recaps(topics=topics, timeframe=timeframe)

        raw = recaps.model_dump() if hasattr(recaps, "model_dump") else {"data": {}}
        data = raw.get("data", {})

        if not data:
            return {
                "topics": topics,
                "timeframe": timeframe,
                "total_recaps": 0,
                "recaps": {},
                "hint": _Y2_UPGRADE_HINT,
            }

        results = {}
        for topic, recap_data in data.items():
            if isinstance(recap_data, dict):
                results[topic] = {
                    "summary": recap_data.get("summary", recap_data.get("text", str(recap_data))),
                    "timeframe": timeframe,
                }
            else:
                results[topic] = {
                    "summary": str(recap_data),
                    "timeframe": timeframe,
                }

        return {
            "topics": topics,
            "timeframe": timeframe,
            "recaps": results,
        }

    except Exception as e:
        return {"error": f"Y2 API error: {str(e)}"}


def get_intelligence_reports(limit: int = 10) -> dict:
    """
    Get AI-generated intelligence reports from Y2.

    Args:
        limit: Number of reports to return (1-20)

    Returns:
        Dict with report summaries and metadata.
    """
    client = _get_client()
    if not client:
        return {"error": "Y2_API_KEY not set. Get one at https://y2.dev/app/developers/api-keys"}

    try:
        reports = client.reports.list(limit=min(limit, 20))
        raw = reports.model_dump() if hasattr(reports, "model_dump") else {}
        data = raw.get("data", [])

        items = []
        for report in data:
            if isinstance(report, dict):
                items.append({
                    "id": report.get("id", "N/A"),
                    "title": report.get("title", report.get("name", "N/A")),
                    "summary": report.get("summary", report.get("description", ""))[:500],
                    "created_at": report.get("created_at", report.get("createdAt", "N/A")),
                    "profile": report.get("profile_name", report.get("profileName", "")),
                })

        result = {
            "total_reports": len(items),
            "reports": items,
        }

        if not items:
            result["hint"] = _Y2_UPGRADE_HINT

        return result

    except Exception as e:
        return {"error": f"Y2 API error: {str(e)}"}


def get_report_detail(report_id: str) -> dict:
    """
    Get full content of a specific intelligence report.

    Args:
        report_id: Report ID from get_intelligence_reports

    Returns:
        Dict with full report content, sources, and summary.
    """
    client = _get_client()
    if not client:
        return {"error": "Y2_API_KEY not set. Get one at https://y2.dev/app/developers/api-keys"}

    try:
        report = client.reports.retrieve(report_id)
        raw = report.model_dump() if hasattr(report, "model_dump") else {}
        data = raw.get("data", raw)

        if isinstance(data, dict):
            return {
                "id": data.get("id", report_id),
                "title": data.get("title", data.get("name", "N/A")),
                "summary": data.get("summary", ""),
                "content": data.get("content", data.get("body", ""))[:3000],
                "sources": data.get("sources", [])[:10],
                "created_at": data.get("created_at", data.get("createdAt", "N/A")),
            }
        return {"id": report_id, "content": str(data)[:3000]}

    except Exception as e:
        return {"error": f"Y2 API error: {str(e)}"}


def get_y2_feeds() -> dict:
    """
    List all available Y2 news feed topics with descriptions.
    Shows what OSINT sources Y2 monitors — useful for discovering valid topics.

    Returns:
        Dict with available feeds and their descriptions.
    """
    client = _get_client()
    if not client:
        return {"error": "Y2_API_KEY not set. Get one at https://y2.dev/app/developers/api-keys"}

    try:
        feeds = client.news.list_feeds()
        raw = feeds.model_dump() if hasattr(feeds, "model_dump") else {}
        data = raw.get("data", [])

        items = []
        for feed in data:
            if isinstance(feed, dict):
                items.append({
                    "id": feed.get("id", "N/A"),
                    "name": feed.get("name", "N/A"),
                    "description": feed.get("description", ""),
                })

        return {
            "total_feeds": len(items),
            "feeds": items,
        }

    except Exception as e:
        return {"error": f"Y2 API error: {str(e)}"}


def get_report_audio(report_id: str) -> dict:
    """
    Get audio narration URL and metadata for a Y2 intelligence report.

    Args:
        report_id: Report ID from get_intelligence_reports

    Returns:
        Dict with audio URL, format, duration, and file size.
    """
    client = _get_client()
    if not client:
        return {"error": "Y2_API_KEY not set. Get one at https://y2.dev/app/developers/api-keys"}

    try:
        audio = client.reports.retrieve_audio(report_id)
        raw = audio.model_dump() if hasattr(audio, "model_dump") else {}
        data = raw.get("data", raw)

        if isinstance(data, dict) and data:
            return {
                "report_id": report_id,
                "url": data.get("url"),
                "format": data.get("format", "mp3"),
                "duration": data.get("duration"),
                "duration_formatted": data.get("duration_formatted"),
                "file_size": data.get("file_size"),
                "mime_type": data.get("mime_type", "audio/mpeg"),
            }
        return {"report_id": report_id, "error": "No audio available for this report"}

    except Exception as e:
        return {"error": f"Y2 API error: {str(e)}"}


def list_y2_profiles() -> dict:
    """
    List your Y2 monitoring profiles — what topics you're tracking and delivery schedule.
    Read-only. Does not create, modify, or delete profiles.

    Returns:
        Dict with profiles including topic, frequency, status, and delivery method.
    """
    client = _get_client()
    if not client:
        return {"error": "Y2_API_KEY not set. Get one at https://y2.dev/app/developers/api-keys"}

    try:
        profiles = client.profiles.list()
        raw = profiles.model_dump() if hasattr(profiles, "model_dump") else {}
        data = raw.get("data", [])

        items = []
        for entry in data:
            if isinstance(entry, dict):
                profile = entry.get("profile", {}) or {}
                items.append({
                    "profile_id": entry.get("profile_id", "N/A"),
                    "name": profile.get("name", "N/A"),
                    "topic": profile.get("topic", "N/A"),
                    "frequency": profile.get("frequency", "N/A"),
                    "status": profile.get("status", "N/A"),
                    "audio_enabled": profile.get("audio_enabled", False),
                    "delivery_method": entry.get("delivery_method", "N/A"),
                    "is_active": entry.get("is_active", False),
                })

        return {
            "total_profiles": len(items),
            "profiles": items,
        }

    except Exception as e:
        return {"error": f"Y2 API error: {str(e)}"}

