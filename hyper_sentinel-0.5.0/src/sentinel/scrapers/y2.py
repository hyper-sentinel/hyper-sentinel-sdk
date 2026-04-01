"""
Y2 News & Intelligence Scraper
Fetches real-time news with sentiment analysis and AI-generated recaps via the Y2 API.

Requires: pip install y2-py
API key: https://y2.dev/app/developers/api-keys (Y2_API_KEY in .env)
"""

import os



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

        return {
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
            news_result = get_news_sentiment(topics=topics, limit=5)
            if "error" in news_result:
                return news_result

            headlines = [item["headline"] for item in news_result.get("news", [])]
            return {
                "topics": topics,
                "timeframe": timeframe,
                "note": "No AI recap available for this window. Here are the latest headlines instead.",
                "overall_sentiment": news_result.get("overall_sentiment", "MIXED"),
                "headlines": headlines,
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

        return {
            "total_reports": len(items),
            "reports": items,
        }

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
