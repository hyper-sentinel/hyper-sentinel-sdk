"""
Polymarket Prediction Market Scraper + Trading
Fetches active markets from the Gamma Markets API (read-only).
Executes trades via the CLOB API using py-clob-client (auth required).

Read-only:  No key needed — browse markets, get prices, orderbooks
Trading:    Requires POLYMARKET_PRIVATE_KEY + POLYMARKET_FUNDER in .env

⚠️ TRADING EXECUTES REAL BETS WITH REAL USDC ON POLYGON.

Requires: pip install py-clob-client
Docs:     https://github.com/Polymarket/py-clob-client
"""

import os
import json
from typing import Optional
import requests


GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon


# ════════════════════════════════════════════════════════════════
# CLOB CLIENT (AUTHENTICATED — for trading)
# ════════════════════════════════════════════════════════════════

def _get_clob_client(read_only: bool = False):
    """
    Initialize the Polymarket CLOB client.
    read_only=True returns an unauthenticated client (for prices/orderbooks).
    read_only=False returns an authenticated client (for trading).
    """
    try:
        from py_clob_client.client import ClobClient
    except ImportError:
        raise ImportError("py-clob-client not installed. Run: uv add py-clob-client")

    if read_only:
        return ClobClient(CLOB_HOST)

    private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "").strip()
    funder = os.getenv("POLYMARKET_FUNDER", "").strip()

    if not private_key:
        return None

    # signature_type=0 for standard EOA (MetaMask/direct private key)
    # signature_type=1 for email/Magic wallet
    sig_type = int(os.getenv("POLYMARKET_SIG_TYPE", "0"))

    client = ClobClient(
        CLOB_HOST,
        key=private_key,
        chain_id=CHAIN_ID,
        signature_type=sig_type,
        funder=funder if funder else None,
    )
    client.set_api_creds(client.create_or_derive_api_creds())
    return client


# ════════════════════════════════════════════════════════════════
# READ-ONLY TOOLS (no auth needed)
# ════════════════════════════════════════════════════════════════

def get_polymarket_markets(limit: int = 20, min_volume: float = 10000) -> dict:
    """
    Fetch active prediction markets sorted by volume.

    Args:
        limit: Number of markets to return (1-50)
        min_volume: Minimum total volume to include

    Returns:
        Dict with active markets including question, outcomes, prices, volume.
    """
    try:
        url = f"{GAMMA_BASE_URL}/markets"
        params = {
            "limit": min(limit, 50),
            "order": "volume24hr",
            "ascending": "false",
            "active": "true",
            "closed": "false",
        }

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        markets = resp.json()

        results = []
        for m in markets:
            outcomes = m.get("outcomes", "")
            prices = m.get("outcomePrices", "")
            if isinstance(outcomes, str):
                try:
                    outcomes = json.loads(outcomes)
                except Exception:
                    outcomes = []
            if isinstance(prices, str):
                try:
                    prices = json.loads(prices)
                except Exception:
                    prices = []

            vol = float(m.get("volume", 0) or 0)
            if vol >= min_volume:
                # Build outcome display
                outcome_display = []
                for i, outcome in enumerate(outcomes):
                    price = float(prices[i]) if i < len(prices) else 0
                    pct = round(price * 100, 1)
                    outcome_display.append(f"{outcome}: {pct}%")

                results.append({
                    "question": m.get("question", ""),
                    "condition_id": m.get("conditionId", ""),
                    "outcomes": outcome_display,
                    "volume": vol,
                    "volume_24hr": float(m.get("volume24hr", 0) or 0),
                    "liquidity": float(m.get("liquidity", 0) or 0),
                    "end_date": m.get("endDate", ""),
                    "slug": m.get("slug", ""),
                })

        return {
            "total_markets": len(results),
            "markets": results[:limit],
        }

    except Exception as e:
        return {"error": f"Polymarket error: {str(e)}"}


def search_polymarket(query: str, limit: int = 10) -> dict:
    """
    Search prediction markets by keyword.

    Args:
        query: Search terms (e.g. 'Trump', 'Fed rate', 'Bitcoin ETF')
        limit: Number of results (1-20)

    Returns:
        Dict with matching markets.
    """
    try:
        url = f"{GAMMA_BASE_URL}/markets"
        params = {
            "limit": min(limit, 20),
            "active": "true",
            "closed": "false",
        }

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        markets = resp.json()

        query_lower = query.lower()
        results = []
        for m in markets:
            question = m.get("question", "")
            if query_lower in question.lower():
                outcomes = m.get("outcomes", "")
                prices = m.get("outcomePrices", "")
                if isinstance(outcomes, str):
                    try:
                        outcomes = json.loads(outcomes)
                    except Exception:
                        outcomes = []
                if isinstance(prices, str):
                    try:
                        prices = json.loads(prices)
                    except Exception:
                        prices = []

                outcome_display = []
                for i, outcome in enumerate(outcomes):
                    price = float(prices[i]) if i < len(prices) else 0
                    pct = round(price * 100, 1)
                    outcome_display.append(f"{outcome}: {pct}%")

                # Get token IDs for trading
                tokens = []
                clob_tokens = m.get("clobTokenIds", "")
                if isinstance(clob_tokens, str):
                    try:
                        clob_tokens = json.loads(clob_tokens)
                    except Exception:
                        clob_tokens = []
                if isinstance(clob_tokens, list):
                    for i, tid in enumerate(clob_tokens):
                        label = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
                        tokens.append({"outcome": label, "token_id": tid})

                results.append({
                    "question": question,
                    "condition_id": m.get("conditionId", ""),
                    "outcomes": outcome_display,
                    "tokens": tokens,
                    "volume": float(m.get("volume", 0) or 0),
                    "liquidity": float(m.get("liquidity", 0) or 0),
                    "slug": m.get("slug", ""),
                })

        return {
            "query": query,
            "total_results": len(results),
            "markets": results[:limit],
        }

    except Exception as e:
        return {"error": f"Polymarket search error: {str(e)}"}


def get_polymarket_orderbook(token_id: str) -> dict:
    """
    Get the orderbook for a specific outcome token on Polymarket.

    Args:
        token_id: The CLOB token ID for a specific outcome (from search_polymarket)

    Returns:
        Dict with bids, asks, midpoint, spread.
    """
    try:
        client = _get_clob_client(read_only=True)

        mid_raw = client.get_midpoint(token_id)
        book = client.get_order_book(token_id)

        # py-clob-client returns dicts like {'mid': '0.484'}
        mid = float(mid_raw.get("mid", mid_raw) if isinstance(mid_raw, dict) else mid_raw)

        bids = []
        asks = []

        if hasattr(book, "bids"):
            for b in book.bids[:10]:
                bids.append({"price": b.price, "size": b.size})
        if hasattr(book, "asks"):
            for a in book.asks[:10]:
                asks.append({"price": a.price, "size": a.size})

        best_bid = bids[0]["price"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        spread = round(float(best_ask) - float(best_bid), 4) if best_bid and best_ask else None

        return {
            "token_id": token_id[:16] + "...",
            "midpoint": mid,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "bids": bids[:5],
            "asks": asks[:5],
        }

    except Exception as e:
        return {"error": f"Polymarket orderbook error: {str(e)}"}


def get_polymarket_price(token_id: str) -> dict:
    """
    Get the current price for a specific outcome token.

    Args:
        token_id: The CLOB token ID for a specific outcome

    Returns:
        Dict with buy price, sell price, and midpoint.
    """
    try:
        client = _get_clob_client(read_only=True)

        mid_raw = client.get_midpoint(token_id)
        buy_raw = client.get_price(token_id, side="BUY")
        sell_raw = client.get_price(token_id, side="SELL")

        # py-clob-client may return dicts like {'mid': '0.484'} or {'price': '0.50'}
        mid = float(mid_raw.get("mid", mid_raw) if isinstance(mid_raw, dict) else mid_raw)
        buy_price = float(buy_raw.get("price", buy_raw) if isinstance(buy_raw, dict) else buy_raw)
        sell_price = float(sell_raw.get("price", sell_raw) if isinstance(sell_raw, dict) else sell_raw)

        return {
            "token_id": token_id[:16] + "...",
            "midpoint": mid,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "implied_probability": f"{round(mid * 100, 1)}%",
        }

    except Exception as e:
        return {"error": f"Polymarket price error: {str(e)}"}


# ════════════════════════════════════════════════════════════════
# TRADING TOOLS (auth required — POLYMARKET_PRIVATE_KEY)
# ════════════════════════════════════════════════════════════════

def buy_polymarket(token_id: str, amount: float, order_type: str = "market") -> dict:
    """
    Buy shares of a prediction market outcome on Polymarket.

    ⚠️ THIS EXECUTES A REAL BET WITH REAL USDC.

    Args:
        token_id: The CLOB token ID for the outcome you want to buy
                  (get from search_polymarket → tokens → token_id)
        amount: Dollar amount of USDC to spend (e.g. 10.0 = $10)
        order_type: 'market' for instant fill, 'limit' not supported here
                    (use place_polymarket_limit for limit orders)

    Returns:
        Order confirmation or error.
    """
    client = _get_clob_client()
    if not client:
        return {"error": "POLYMARKET_PRIVATE_KEY not set. Run 'add polymarket' to configure."}

    try:
        from py_clob_client.clob_types import MarketOrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY

        order_args = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=BUY,
            order_type=OrderType.FOK,  # Fill-or-Kill for market orders
        )
        signed = client.create_market_order(order_args)
        resp = client.post_order(signed, OrderType.FOK)

        return {
            "status": "SUCCESS",
            "action": "BUY",
            "token_id": token_id[:16] + "...",
            "amount_usdc": amount,
            "order_type": "market (FOK)",
            "response": str(resp)[:500],
        }

    except Exception as e:
        return {"error": f"Polymarket buy error: {str(e)}"}


def sell_polymarket(token_id: str, amount: float) -> dict:
    """
    Sell shares of a prediction market outcome on Polymarket.

    ⚠️ THIS EXECUTES A REAL TRADE WITH REAL USDC.

    Args:
        token_id: The CLOB token ID for the outcome you want to sell
        amount: Dollar amount of shares to sell

    Returns:
        Order confirmation or error.
    """
    client = _get_clob_client()
    if not client:
        return {"error": "POLYMARKET_PRIVATE_KEY not set. Run 'add polymarket' to configure."}

    try:
        from py_clob_client.clob_types import MarketOrderArgs, OrderType
        from py_clob_client.order_builder.constants import SELL

        order_args = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=SELL,
            order_type=OrderType.FOK,
        )
        signed = client.create_market_order(order_args)
        resp = client.post_order(signed, OrderType.FOK)

        return {
            "status": "SUCCESS",
            "action": "SELL",
            "token_id": token_id[:16] + "...",
            "amount_usdc": amount,
            "order_type": "market (FOK)",
            "response": str(resp)[:500],
        }

    except Exception as e:
        return {"error": f"Polymarket sell error: {str(e)}"}


def place_polymarket_limit(token_id: str, side: str, price: float, size: float) -> dict:
    """
    Place a limit order on a prediction market outcome.

    ⚠️ THIS PLACES A REAL ORDER WITH REAL USDC.

    Args:
        token_id: The CLOB token ID for the outcome
        side: 'buy' or 'sell'
        price: Price per share (0.01 to 0.99 — represents probability)
        size: Number of shares to buy/sell

    Returns:
        Order confirmation or error.
    """
    client = _get_clob_client()
    if not client:
        return {"error": "POLYMARKET_PRIVATE_KEY not set. Run 'add polymarket' to configure."}

    try:
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY, SELL

        order_side = BUY if side.lower() == "buy" else SELL

        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=order_side,
        )
        signed = client.create_order(order_args)
        resp = client.post_order(signed, OrderType.GTC)

        return {
            "status": "SUCCESS",
            "action": f"LIMIT {side.upper()}",
            "token_id": token_id[:16] + "...",
            "price": price,
            "size": size,
            "cost_usdc": round(price * size, 2),
            "order_type": "limit (GTC)",
            "response": str(resp)[:500],
        }

    except Exception as e:
        return {"error": f"Polymarket limit order error: {str(e)}"}


def get_polymarket_positions() -> dict:
    """
    Get your open orders and recent trades on Polymarket.

    Returns:
        Dict with open orders and trade history.
    """
    client = _get_clob_client()
    if not client:
        return {"error": "POLYMARKET_PRIVATE_KEY not set. Run 'add polymarket' to configure."}

    try:
        from py_clob_client.clob_types import OpenOrderParams

        # Get open orders
        open_orders = client.get_orders(OpenOrderParams())
        formatted_orders = []
        for o in open_orders[:20]:
            formatted_orders.append({
                "id": o.get("id", "N/A"),
                "market": o.get("market", "N/A"),
                "side": o.get("side", "N/A"),
                "price": o.get("price", "N/A"),
                "size": o.get("original_size", o.get("size", "N/A")),
                "size_matched": o.get("size_matched", "0"),
                "status": o.get("status", "N/A"),
            })

        # Get recent trades
        trades = client.get_trades()
        formatted_trades = []
        for t in (trades[:10] if trades else []):
            formatted_trades.append({
                "id": t.get("id", "N/A"),
                "market": t.get("market", "N/A"),
                "side": t.get("side", "N/A"),
                "price": t.get("price", "N/A"),
                "size": t.get("size", "N/A"),
                "status": t.get("status", "N/A"),
            })

        return {
            "total_open_orders": len(formatted_orders),
            "open_orders": formatted_orders,
            "recent_trades_count": len(formatted_trades),
            "recent_trades": formatted_trades,
        }

    except Exception as e:
        return {"error": f"Polymarket positions error: {str(e)}"}


def cancel_polymarket_order(order_id: str) -> dict:
    """
    Cancel an open order on Polymarket.

    Args:
        order_id: Order ID from get_polymarket_positions

    Returns:
        Cancellation confirmation.
    """
    client = _get_clob_client()
    if not client:
        return {"error": "POLYMARKET_PRIVATE_KEY not set. Run 'add polymarket' to configure."}

    try:
        resp = client.cancel(order_id)

        return {
            "status": "CANCELLED",
            "order_id": order_id,
            "response": str(resp)[:200],
        }

    except Exception as e:
        return {"error": f"Polymarket cancel error: {str(e)}"}


def cancel_all_polymarket_orders() -> dict:
    """
    Cancel ALL open orders on Polymarket.

    Returns:
        Cancellation confirmation.
    """
    client = _get_clob_client()
    if not client:
        return {"error": "POLYMARKET_PRIVATE_KEY not set. Run 'add polymarket' to configure."}

    try:
        resp = client.cancel_all()

        return {
            "status": "ALL_CANCELLED",
            "response": str(resp)[:200],
        }

    except Exception as e:
        return {"error": f"Polymarket cancel all error: {str(e)}"}
