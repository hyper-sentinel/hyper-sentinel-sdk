"""
Cryptocurrency price scraper using CoinGecko (free, no API key required).

Includes:
- 60-second price cache to avoid rate limits and give instant repeat queries
- 10s timeout (instead of 30s) for fast failure
- CoinGecko Demo API key header for higher free-tier rate limits
"""

import os
import time
import requests

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Optional CoinGecko Demo API key (free, 30 calls/min vs 10 without)
_CG_API_KEY = os.getenv("COINGECKO_API_KEY", "").strip()

# Headers to avoid rate limiting / bot blocking
_HEADERS = {
    "User-Agent": "Sentinel/1.0",
    "Accept": "application/json",
}
if _CG_API_KEY:
    _HEADERS["x-cg-demo-api-key"] = _CG_API_KEY

# Simple price cache: {coin_id: (timestamp, data)}
_price_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 60  # seconds

# Common symbol → CoinGecko ID mapping
SYMBOL_TO_ID = {
    "btc": "bitcoin", "eth": "ethereum", "sol": "solana",
    "ada": "cardano", "dot": "polkadot", "avax": "avalanche-2",
    "matic": "matic-network", "link": "chainlink", "doge": "dogecoin",
    "xrp": "ripple", "bnb": "binancecoin", "uni": "uniswap",
    "atom": "cosmos", "near": "near", "arb": "arbitrum",
    "op": "optimism", "sui": "sui", "apt": "aptos",
    "pepe": "pepe", "shib": "shiba-inu", "ltc": "litecoin",
    "bitcoin": "bitcoin", "ethereum": "ethereum", "solana": "solana",
    "dogecoin": "dogecoin", "cardano": "cardano", "ripple": "ripple",
}


def get_crypto_price(coin_id: str) -> dict:
    """Get current price, market cap, volume, and 24h/7d/30d changes."""
    coin_id = SYMBOL_TO_ID.get(coin_id.lower().strip(), coin_id.lower().strip())

    # Check cache first — instant response if recent
    now = time.time()
    if coin_id in _price_cache:
        cached_ts, cached_data = _price_cache[coin_id]
        if now - cached_ts < _CACHE_TTL:
            return cached_data

    url = f"{COINGECKO_BASE}/coins/{coin_id}"
    params = {"localization": "false", "tickers": "false",
              "community_data": "false", "developer_data": "false"}

    resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    market = data.get("market_data", {})

    result = {
        "id": data.get("id"),
        "symbol": data.get("symbol", "").upper(),
        "name": data.get("name"),
        "current_price": market.get("current_price", {}).get("usd"),
        "market_cap": market.get("market_cap", {}).get("usd"),
        "market_cap_rank": market.get("market_cap_rank"),
        "total_volume_24h": market.get("total_volume", {}).get("usd"),
        "price_change_pct_24h": market.get("price_change_percentage_24h"),
        "price_change_pct_7d": market.get("price_change_percentage_7d"),
        "price_change_pct_30d": market.get("price_change_percentage_30d"),
        "ath": market.get("ath", {}).get("usd"),
        "circulating_supply": market.get("circulating_supply"),
    }

    # Cache the result
    _price_cache[coin_id] = (time.time(), result)
    return result


def get_crypto_top_n(n: int = 20) -> list[dict]:
    """Get top N cryptocurrencies ranked by market cap."""
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc",
              "per_page": min(n, 250), "page": 1, "sparkline": "false"}

    resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
    resp.raise_for_status()

    return [
        {
            "rank": c.get("market_cap_rank"),
            "symbol": c.get("symbol", "").upper(),
            "name": c.get("name"),
            "current_price": c.get("current_price"),
            "market_cap": c.get("market_cap"),
            "price_change_pct_24h": c.get("price_change_percentage_24h"),
        }
        for c in resp.json()
    ]


def search_crypto(query: str) -> list[dict]:
    """Search for a cryptocurrency by name or symbol."""
    resp = requests.get(f"{COINGECKO_BASE}/search", params={"query": query}, headers=_HEADERS, timeout=10)
    resp.raise_for_status()

    return [
        {
            "id": c.get("id"),
            "symbol": c.get("symbol", "").upper(),
            "name": c.get("name"),
            "market_cap_rank": c.get("market_cap_rank"),
        }
        for c in resp.json().get("coins", [])[:10]
    ]
