"""
Cryptocurrency price scraper using CoinGecko (free, no API key required).

Includes:
- 300-second price cache (v0.9.2: extended from 60s to reduce 429s under burst)
- 10s timeout (instead of 30s) for fast failure
- CoinGecko Demo API key header for higher free-tier rate limits
- tenacity retry with exponential backoff on 429/5xx (v0.9.2)
- Graceful degradation: persistent 429 returns a clear error dict instead of crashing
"""

import os
import time
import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    RetryError,
)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Optional CoinGecko Demo API key (free, 30 calls/min vs 10 without)
# Set COINGECKO_API_KEY in environment / ~/.sentinel/config to unlock higher limits.
_CG_API_KEY = os.getenv("COINGECKO_API_KEY", "").strip()

# Headers to avoid rate limiting / bot blocking
_HEADERS = {
    "User-Agent": "Sentinel/1.0",
    "Accept": "application/json",
}
if _CG_API_KEY:
    # Use x-cg-demo-api-key for Demo keys; Pro keys use x-cg-pro-api-key.
    # Demo key prefix is "CG-" (30 req/min); Pro keys are longer.
    if _CG_API_KEY.startswith("CG-"):
        _HEADERS["x-cg-demo-api-key"] = _CG_API_KEY
    else:
        _HEADERS["x-cg-pro-api-key"] = _CG_API_KEY

# Price cache: {coin_id: (timestamp, data)}
_price_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300  # 5 minutes — extended from 60s to reduce burst 429s

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


def _is_rate_limit_or_server_error(exc: BaseException) -> bool:
    """tenacity predicate: retry on 429 and 5xx responses."""
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code in (429, 500, 502, 503, 504)
    return False


def _cg_get(url: str, params: dict | None = None) -> requests.Response:
    """GET a CoinGecko endpoint with tenacity retry on 429/5xx.

    Raises requests.HTTPError on persistent failure so callers can handle it.
    Up to 3 attempts: waits 2s, then 8s (exponential, jitter off for predictability).
    """
    @retry(
        retry=retry_if_exception(_is_rate_limit_or_server_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _do_get() -> requests.Response:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        return resp

    return _do_get()


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

    try:
        resp = _cg_get(url, params)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 429:
            return {
                "error": "CoinGecko rate limit hit (429). Add a COINGECKO_API_KEY env var for "
                         "higher limits (free demo key at coingecko.com/api), or retry in ~30s.",
                "coin_id": coin_id,
                "source": "coingecko",
            }
        if status == 404:
            return {"error": f"Coin '{coin_id}' not found on CoinGecko. Try search_crypto first.", "coin_id": coin_id}
        return {"error": f"CoinGecko HTTP {status}: {e}", "coin_id": coin_id}
    except Exception as e:
        return {"error": f"CoinGecko request failed: {e}", "coin_id": coin_id}

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
        "source": "coingecko",
    }

    # Cache the result
    _price_cache[coin_id] = (time.time(), result)
    return result


def get_crypto_top_n(n: int = 20) -> list[dict]:
    """Get top N cryptocurrencies ranked by market cap."""
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc",
              "per_page": min(n, 250), "page": 1, "sparkline": "false"}

    try:
        resp = _cg_get(url, params)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 429:
            return [{"error": "CoinGecko rate limit (429). Retry shortly or add COINGECKO_API_KEY."}]
        return [{"error": f"CoinGecko HTTP {status}"}]
    except Exception as e:
        return [{"error": f"CoinGecko request failed: {e}"}]

    return [
        {
            "rank": c.get("market_cap_rank"),
            "symbol": c.get("symbol", "").upper(),
            "name": c.get("name"),
            "current_price": c.get("current_price"),
            "market_cap": c.get("market_cap"),
            "price_change_pct_24h": c.get("price_change_percentage_24h"),
            "source": "coingecko",
        }
        for c in resp.json()
    ]


def search_crypto(query: str) -> list[dict]:
    """Search for a cryptocurrency by name or symbol."""
    try:
        resp = _cg_get(f"{COINGECKO_BASE}/search", {"query": query})
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 429:
            return [{"error": "CoinGecko rate limit (429). Retry shortly or add COINGECKO_API_KEY."}]
        return [{"error": f"CoinGecko HTTP {status}"}]
    except Exception as e:
        return [{"error": f"CoinGecko search failed: {e}"}]

    return [
        {
            "id": c.get("id"),
            "symbol": c.get("symbol", "").upper(),
            "name": c.get("name"),
            "market_cap_rank": c.get("market_cap_rank"),
            "source": "coingecko",
        }
        for c in resp.json().get("coins", [])[:10]
    ]
