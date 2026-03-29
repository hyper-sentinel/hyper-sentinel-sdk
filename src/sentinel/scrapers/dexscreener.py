"""
DexScreener API scraper — token pair data, trending, and search.
Free public API, no key required. Configurable for AI agent data ingestion.

Endpoints:
  - Search pairs across all DEXes
  - Get pairs by chain + pair address
  - Get pairs by token address
  - Get latest token profiles (boosted/trending)

Docs: https://docs.dexscreener.com
"""
import os
import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)

BASE_URL = "https://api.dexscreener.com"
TIMEOUT = int(os.getenv("DEXSCREENER_TIMEOUT", "15"))


def _get(path: str, params: dict = None) -> dict | list:
    """Make a GET request to DexScreener API."""
    try:
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


# ── Search ────────────────────────────────────────────────────────

def search_pairs(query: str) -> list:
    """
    Search for DEX pairs across all chains.
    Query can be token name, symbol, or contract address.

    Example:
        search_pairs("PEPE")
        search_pairs("So11111111111111111111111111111111111111112")
    """
    data = _get("/latest/dex/search", params={"q": query})
    if isinstance(data, dict) and "error" in data:
        return [data]
    pairs = data.get("pairs", [])
    return [_format_pair(p) for p in pairs[:20]]


# ── Token Lookup ──────────────────────────────────────────────────

def get_token_pairs(token_address: str) -> list:
    """
    Get all DEX pairs for a token address (across all chains).

    Example:
        get_token_pairs("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")  # USDC on Solana
    """
    data = _get(f"/latest/dex/tokens/{token_address}")
    if isinstance(data, dict) and "error" in data:
        return [data]
    if isinstance(data, list):
        return [_format_pair(p) for p in data[:20]]
    pairs = data.get("pairs", []) if isinstance(data, dict) else []
    return [_format_pair(p) for p in pairs[:20]]


def get_token_pairs_by_chain(chain: str, token_address: str) -> list:
    """
    Get DEX pairs for a token on a specific chain.

    Chains: solana, ethereum, bsc, arbitrum, polygon, base, avalanche, etc.

    Example:
        get_token_pairs_by_chain("solana", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    """
    data = _get(f"/latest/dex/tokens/{token_address}")
    if isinstance(data, dict) and "error" in data:
        return [data]
    if isinstance(data, list):
        return [_format_pair(p) for p in data[:20]]
    pairs = data.get("pairs", []) if isinstance(data, dict) else []
    return [_format_pair(p) for p in pairs[:20]]


# ── Pair Lookup ───────────────────────────────────────────────────

def get_pair(chain: str, pair_address: str) -> dict:
    """
    Get detailed pair info by chain and pair address.

    Example:
        get_pair("ethereum", "0xa29fe6ef9592b5d408cca961d0fb9b1faf497d6d")
    """
    data = _get(f"/latest/dex/pairs/{chain}/{pair_address}")
    if isinstance(data, dict) and "error" in data:
        return data
    pairs = data.get("pairs", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    if not pairs:
        return {"error": f"Pair not found: {chain}/{pair_address}"}
    return _format_pair(pairs[0])


# ── Trending / Boosted ────────────────────────────────────────────

def get_token_profiles() -> list:
    """Get latest updated token profiles (promoted/featured tokens)."""
    data = _get("/token-profiles/latest/v1")
    if isinstance(data, dict) and "error" in data:
        return [data]
    if isinstance(data, list):
        return [_format_profile(p) for p in data[:20]]
    return []


def get_boosted_tokens() -> list:
    """Get tokens with active boosts (promoted visibility)."""
    data = _get("/token-boosts/latest/v1")
    if isinstance(data, dict) and "error" in data:
        return [data]
    if isinstance(data, list):
        return [_format_boost(b) for b in data[:20]]
    return []


def get_top_boosted_tokens() -> list:
    """Get tokens with the most active boosts."""
    data = _get("/token-boosts/top/v1")
    if isinstance(data, dict) and "error" in data:
        return [data]
    if isinstance(data, list):
        return [_format_boost(b) for b in data[:20]]
    return []


# ── Multi-Token Lookup ────────────────────────────────────────────

def get_orders(chain: str, token_address: str) -> dict:
    """Check paid orders for a token (CTO/ads status)."""
    data = _get(f"/orders/v1/{chain}/{token_address}")
    if isinstance(data, dict) and "error" in data:
        return data
    return data


# ── Formatting Helpers ────────────────────────────────────────────

def _format_pair(pair: dict) -> dict:
    """Format a pair response into clean data for the agent."""
    base = pair.get("baseToken", {})
    quote = pair.get("quote", pair.get("quoteToken", {}))
    txns = pair.get("txns", {})
    h24 = txns.get("h24", {})

    return {
        "chain": pair.get("chainId", "?"),
        "dex": pair.get("dexId", "?"),
        "pair_address": pair.get("pairAddress", ""),
        "base_token": {
            "name": base.get("name", "?"),
            "symbol": base.get("symbol", "?"),
            "address": base.get("address", ""),
        },
        "quote_token": {
            "symbol": quote.get("symbol", "?"),
            "address": quote.get("address", ""),
        },
        "price_usd": pair.get("priceUsd", "0"),
        "price_native": pair.get("priceNative", "0"),
        "liquidity_usd": pair.get("liquidity", {}).get("usd", 0),
        "fdv": pair.get("fdv", 0),
        "market_cap": pair.get("marketCap", 0),
        "volume_24h": pair.get("volume", {}).get("h24", 0),
        "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
        "price_change_1h": pair.get("priceChange", {}).get("h1", 0),
        "price_change_5m": pair.get("priceChange", {}).get("m5", 0),
        "buys_24h": h24.get("buys", 0),
        "sells_24h": h24.get("sells", 0),
        "pair_created_at": pair.get("pairCreatedAt", ""),
        "url": pair.get("url", ""),
    }


def _format_profile(profile: dict) -> dict:
    """Format a token profile."""
    return {
        "chain": profile.get("chainId", "?"),
        "address": profile.get("tokenAddress", ""),
        "description": profile.get("description", ""),
        "icon": profile.get("icon", ""),
        "links": profile.get("links", []),
    }


def _format_boost(boost: dict) -> dict:
    """Format a boosted token."""
    return {
        "chain": boost.get("chainId", "?"),
        "address": boost.get("tokenAddress", ""),
        "amount": boost.get("amount", 0),
        "total_amount": boost.get("totalAmount", 0),
        "description": boost.get("description", ""),
        "icon": boost.get("icon", ""),
    }
