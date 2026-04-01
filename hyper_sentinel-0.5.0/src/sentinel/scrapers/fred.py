"""
FRED Economic Data Scraper — Federal Reserve Bank of St. Louis

Provides access to macroeconomic indicators via the FRED API.
Requires a free API key from: https://fred.stlouisfed.org/docs/api/api_key.html
"""

import os
from datetime import datetime, timedelta

import requests

FRED_BASE_URL = "https://api.stlouisfed.org/fred"


def _get_api_key() -> str:
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise ValueError("FRED_API_KEY not set. Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html")
    return key


def get_fred_series(series_id: str, period: str = "1y") -> dict:
    """
    Get a FRED data series by ID (e.g., 'GDP', 'CPIAUCSL', 'UNRATE', 'DFF').

    Returns the most recent observations and metadata.
    """
    api_key = _get_api_key()

    # Calculate observation start date from period
    period_map = {"3m": 90, "6m": 180, "1y": 365, "2y": 730, "5y": 1825, "10y": 3650}
    days = period_map.get(period, 365)
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Get series info
    info_resp = requests.get(f"{FRED_BASE_URL}/series", params={
        "api_key": api_key, "series_id": series_id, "file_type": "json"
    }, timeout=10)

    # Get observations
    obs_resp = requests.get(f"{FRED_BASE_URL}/series/observations", params={
        "api_key": api_key, "series_id": series_id, "file_type": "json",
        "observation_start": start_date, "sort_order": "desc", "limit": 100,
    }, timeout=10)

    info_data = info_resp.json()
    obs_data = obs_resp.json()

    series_info = info_data.get("seriess", [{}])[0] if info_data.get("seriess") else {}
    observations = obs_data.get("observations", [])

    # Filter out missing values
    valid_obs = [
        {"date": o["date"], "value": float(o["value"])}
        for o in observations if o.get("value") and o["value"] != "."
    ]

    return {
        "series_id": series_id.upper(),
        "title": series_info.get("title", series_id),
        "units": series_info.get("units", ""),
        "frequency": series_info.get("frequency", ""),
        "seasonal_adjustment": series_info.get("seasonal_adjustment", ""),
        "last_updated": series_info.get("last_updated", ""),
        "latest_value": valid_obs[0]["value"] if valid_obs else None,
        "latest_date": valid_obs[0]["date"] if valid_obs else None,
        "observation_count": len(valid_obs),
        "observations": valid_obs[:20],  # Most recent 20
    }


def search_fred(query: str, limit: int = 10) -> list[dict]:
    """
    Search FRED for data series by keyword.

    Example queries: 'GDP', 'inflation', 'unemployment', 'interest rate', 'housing starts'
    """
    api_key = _get_api_key()
    resp = requests.get(f"{FRED_BASE_URL}/series/search", params={
        "api_key": api_key, "search_text": query, "file_type": "json",
        "limit": limit, "order_by": "popularity", "sort_order": "desc",
    }, timeout=10)

    data = resp.json()
    results = []
    for s in data.get("seriess", []):
        results.append({
            "series_id": s["id"],
            "title": s.get("title", ""),
            "frequency": s.get("frequency", ""),
            "units": s.get("units", ""),
            "seasonal_adjustment": s.get("seasonal_adjustment", ""),
            "popularity": s.get("popularity", 0),
            "last_updated": s.get("last_updated", ""),
        })
    return results


# Pre-built dashboard of key economic indicators
ECONOMIC_INDICATORS = {
    "GDP": "Gross Domestic Product",
    "GDPC1": "Real GDP (chained 2017 dollars)",
    "CPIAUCSL": "Consumer Price Index (All Urban Consumers)",
    "CPILFESL": "Core CPI (Excluding Food & Energy)",
    "UNRATE": "Unemployment Rate",
    "PAYEMS": "Total Nonfarm Payrolls",
    "DFF": "Federal Funds Effective Rate",
    "DGS10": "10-Year Treasury Constant Maturity Rate",
    "DGS2": "2-Year Treasury Constant Maturity Rate",
    "T10Y2Y": "10Y-2Y Treasury Spread (Yield Curve)",
    "VIXCLS": "CBOE Volatility Index (VIX)",
    "DEXUSEU": "USD/EUR Exchange Rate",
    "HOUST": "Housing Starts",
    "UMCSENT": "University of Michigan Consumer Sentiment",
    "M2SL": "M2 Money Supply",
}


def get_economic_dashboard() -> list[dict]:
    """
    Get a snapshot of key US economic indicators.

    Returns the latest value for GDP, CPI, unemployment, fed funds rate,
    Treasury yields, VIX, and more.
    """
    api_key = _get_api_key()
    results = []

    for series_id, description in ECONOMIC_INDICATORS.items():
        try:
            resp = requests.get(f"{FRED_BASE_URL}/series/observations", params={
                "api_key": api_key, "series_id": series_id, "file_type": "json",
                "sort_order": "desc", "limit": 1,
            }, timeout=5)
            data = resp.json()
            obs = data.get("observations", [])
            if obs and obs[0].get("value") and obs[0]["value"] != ".":
                results.append({
                    "indicator": description,
                    "series_id": series_id,
                    "value": float(obs[0]["value"]),
                    "date": obs[0]["date"],
                })
            else:
                results.append({
                    "indicator": description,
                    "series_id": series_id,
                    "value": None,
                    "date": None,
                    "note": "No recent data",
                })
        except Exception:
            results.append({
                "indicator": description,
                "series_id": series_id,
                "error": "Failed to fetch",
            })

    return results
