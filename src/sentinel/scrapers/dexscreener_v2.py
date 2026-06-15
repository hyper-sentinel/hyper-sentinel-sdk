"""
DexScreener v2 scraper — wrapper functions for server.py ToolRegistry.

Extracted from chat.py inline dispatch code. Uses raw httpx calls.
"""

import httpx


def dexscreener_search(query: str) -> dict:
    """Search for DEX trading pairs by token name, symbol, or contract address across all chains."""
    r = httpx.get(f"https://api.dexscreener.com/latest/dex/search?q={query}", timeout=10.0)
    pairs = r.json().get("pairs", [])[:8]
    results = [{
        "name": p.get("baseToken", {}).get("name"),
        "symbol": p.get("baseToken", {}).get("symbol"),
        "price_usd": p.get("priceUsd"),
        "chain": p.get("chainId"),
        "dex": p.get("dexId"),
        "volume_24h": p.get("volume", {}).get("h24"),
        "liquidity_usd": p.get("liquidity", {}).get("usd"),
        "market_cap": p.get("marketCap"),
        "price_change_24h": p.get("priceChange", {}).get("h24"),
        "url": p.get("url"),
    } for p in pairs]
    return {"pairs": results, "source": "dexscreener"}


def dexscreener_pair(chain: str, pair_address: str) -> dict:
    """Get detailed info for a specific DEX trading pair by chain and pair address."""
    r = httpx.get(f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}", timeout=10.0)
    data = r.json()
    pairs = data.get("pairs", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    if not pairs:
        return {"error": f"Pair not found: {chain}/{pair_address}"}
    p = pairs[0]
    return {
        "name": p.get("baseToken", {}).get("name"),
        "symbol": f"{p.get('baseToken', {}).get('symbol')}/{p.get('quoteToken', {}).get('symbol')}",
        "price_usd": p.get("priceUsd"),
        "chain": p.get("chainId"),
        "dex": p.get("dexId"),
        "volume_24h": p.get("volume", {}).get("h24"),
        "liquidity_usd": p.get("liquidity", {}).get("usd"),
        "market_cap": p.get("marketCap"),
        "fdv": p.get("fdv"),
        "price_change_5m": p.get("priceChange", {}).get("m5"),
        "price_change_1h": p.get("priceChange", {}).get("h1"),
        "price_change_24h": p.get("priceChange", {}).get("h24"),
        "url": p.get("url"),
        "source": "dexscreener",
    }


def dexscreener_token_lookup(token_address: str, chain: str = "") -> dict:
    """Look up a token by contract address to find all DEX pairs across chains."""
    if chain:
        r = httpx.get(f"https://api.dexscreener.com/token-pairs/v1/{chain}/{token_address}", timeout=10.0)
    else:
        r = httpx.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}", timeout=10.0)
    data = r.json()
    pairs_raw = data if isinstance(data, list) else data.get("pairs", [])
    pairs = pairs_raw[:8]
    results = [{
        "name": p.get("baseToken", {}).get("name"),
        "symbol": p.get("baseToken", {}).get("symbol"),
        "price_usd": p.get("priceUsd"),
        "chain": p.get("chainId"),
        "dex": p.get("dexId"),
        "volume_24h": p.get("volume", {}).get("h24"),
        "liquidity_usd": p.get("liquidity", {}).get("usd"),
        "market_cap": p.get("marketCap"),
        "price_change_24h": p.get("priceChange", {}).get("h24"),
        "url": p.get("url"),
    } for p in pairs]
    return {"token": token_address, "chain": chain or "all", "pairs": results, "source": "dexscreener"}


def dexscreener_trending() -> dict:
    """Get trending/most boosted tokens on DexScreener."""
    r = httpx.get("https://api.dexscreener.com/token-boosts/top/v1", timeout=10.0)
    tokens = r.json()[:12] if isinstance(r.json(), list) else []
    results = [{
        "chain": t.get("chainId"),
        "token_address": t.get("tokenAddress"),
        "boost_amount": t.get("totalAmount"),
        "description": t.get("description", ""),
        "url": t.get("url"),
    } for t in tokens]
    return {"trending": results, "source": "dexscreener"}
