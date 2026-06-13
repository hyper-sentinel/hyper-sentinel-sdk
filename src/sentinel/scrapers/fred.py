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


def get_fred_series(series_id: str, period: str = "1y", limit: int = 10) -> dict:
    """
    Get a FRED data series by ID (e.g., 'GDP', 'CPIAUCSL', 'UNRATE', 'DFF').

    Returns the most recent observations and metadata.

    Args:
        series_id: FRED series ID (e.g. GDP, CPIAUCSL, UNRATE, FEDFUNDS)
        period: Lookback period — 3m, 6m, 1y, 2y, 5y, 10y. Default: 1y
        limit: Number of recent observations to return. Default: 10
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
        "observations": valid_obs[:limit],
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


# Series where YoY% change is meaningful
_YOY_SERIES = {"CPIAUCSL", "CPILFESL", "GDP", "GDPC1", "M2SL", "PAYEMS"}


def get_economic_dashboard() -> list[dict]:
    """
    Get a snapshot of key US economic indicators.

    Returns the latest value for GDP, CPI, unemployment, fed funds rate,
    Treasury yields, VIX, and more. Includes YoY% change for CPI, GDP,
    M2, and payrolls.
    """
    api_key = _get_api_key()
    results = []

    for series_id, description in ECONOMIC_INDICATORS.items():
        try:
            # For YoY series, fetch enough history to compute % change
            fetch_limit = 15 if series_id in _YOY_SERIES else 1
            resp = requests.get(f"{FRED_BASE_URL}/series/observations", params={
                "api_key": api_key, "series_id": series_id, "file_type": "json",
                "sort_order": "desc", "limit": fetch_limit,
            }, timeout=5)
            data = resp.json()
            obs = data.get("observations", [])
            valid = [o for o in obs if o.get("value") and o["value"] != "."]

            if valid:
                entry = {
                    "indicator": description,
                    "series_id": series_id,
                    "value": float(valid[0]["value"]),
                    "date": valid[0]["date"],
                }

                # Compute YoY% for applicable series
                if series_id in _YOY_SERIES and len(valid) >= 13:
                    latest = float(valid[0]["value"])
                    year_ago = float(valid[12]["value"])
                    if year_ago != 0:
                        entry["yoy_pct_change"] = round(
                            (latest - year_ago) / year_ago * 100, 2
                        )

                results.append(entry)
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


# ── Yield Curve ──────────────────────────────────────────────────

YIELD_MATURITIES = {
    "DGS3MO": "3-Month",
    "DGS6MO": "6-Month",
    "DGS1": "1-Year",
    "DGS2": "2-Year",
    "DGS5": "5-Year",
    "DGS7": "7-Year",
    "DGS10": "10-Year",
    "DGS20": "20-Year",
    "DGS30": "30-Year",
}


def get_yield_curve() -> dict:
    """Get the full US Treasury yield curve with spreads and inversion status.

    Returns yields for 3M through 30Y, key spreads (10Y-2Y, 10Y-3M, 30Y-2Y),
    and whether the curve is normal, inverted, or flat.
    """
    api_key = _get_api_key()
    curve = {}

    for series_id, label in YIELD_MATURITIES.items():
        try:
            resp = requests.get(f"{FRED_BASE_URL}/series/observations", params={
                "api_key": api_key, "series_id": series_id, "file_type": "json",
                "sort_order": "desc", "limit": 1,
            }, timeout=5)
            obs = resp.json().get("observations", [])
            if obs and obs[0].get("value") and obs[0]["value"] != ".":
                curve[label] = {
                    "yield_pct": float(obs[0]["value"]),
                    "date": obs[0]["date"],
                    "series_id": series_id,
                }
        except Exception:
            pass

    # Compute key spreads
    spreads = {}
    y10 = curve.get("10-Year", {}).get("yield_pct")
    y2 = curve.get("2-Year", {}).get("yield_pct")
    y3m = curve.get("3-Month", {}).get("yield_pct")
    y30 = curve.get("30-Year", {}).get("yield_pct")

    if y10 is not None and y2 is not None:
        spreads["10Y_minus_2Y"] = round(y10 - y2, 2)
    if y10 is not None and y3m is not None:
        spreads["10Y_minus_3M"] = round(y10 - y3m, 2)
    if y30 is not None and y2 is not None:
        spreads["30Y_minus_2Y"] = round(y30 - y2, 2)

    # Determine curve shape
    spread_10y2y = spreads.get("10Y_minus_2Y")
    if spread_10y2y is not None:
        if spread_10y2y > 0.10:
            shape = "normal"
        elif spread_10y2y < -0.10:
            shape = "inverted"
        else:
            shape = "flat"
    else:
        shape = "unknown"

    return {
        "curve": curve,
        "spreads": spreads,
        "shape": shape,
        "shape_description": {
            "normal": "Positively sloped — long-term rates above short-term. Healthy economy signal.",
            "inverted": "Negatively sloped — short-term rates above long-term. Historically precedes recessions.",
            "flat": "Minimal spread between short and long maturities. Transition or uncertainty signal.",
            "unknown": "Insufficient data to determine curve shape.",
        }.get(shape, ""),
    }
