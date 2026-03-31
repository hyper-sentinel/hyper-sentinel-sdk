"""
Hyperliquid Trading Scraper — Execute trades on Hyperliquid DEX
Supports market orders, limit orders, position management, and account info.
Includes TradFi/commodity perps via the XYZ builder dex (GOLD, SILVER, OIL, stocks).

IMPORTANT: This module executes REAL TRADES with REAL FUNDS.
The agent will always confirm with the user before placing orders.

Requires: pip install hyperliquid-python-sdk
Auth: HYPERLIQUID_PRIVATE_KEY + HYPERLIQUID_WALLET_ADDRESS in .env
"""

import os
import json
import requests

# ── Builder Fee Configuration ──
# Every trade placed through Sentinel earns 0.01% (1 BPS) to the Sentinel Labs wallet.
# This is the default revenue capture — override via env for custom builder addresses.
_SENTINEL_LABS_WALLET = "0x4047d682525C21831fCF95b49340FC7A74B4aA27"
BUILDER_FEE_ADDRESS = os.getenv("HYPERLIQUID_BUILDER_FEE_ADDRESS", _SENTINEL_LABS_WALLET).strip()
BUILDER_FEE_RATE = 10  # tenths of a BPS → 10 = 1 BPS = 0.01%
_builder_fee_approved = False  # Module-level flag — only approve once per session

# ── TradFi / Commodity Aliases ──
# Maps user-friendly names → xyz dex coin names so the LLM can just say "GOLD" or "oil"
TRADFI_ALIASES = {
    # Commodities
    "GOLD": "xyz:GOLD", "XAU": "xyz:GOLD",
    "SILVER": "xyz:SILVER", "XAG": "xyz:SILVER",
    "OIL": "xyz:CL", "WTIOIL": "xyz:CL", "WTI": "xyz:CL", "CL": "xyz:CL", "CRUDEOIL": "xyz:CL",
    "BRENTOIL": "xyz:BRENTOIL", "BRENT": "xyz:BRENTOIL",
    "COPPER": "xyz:COPPER", "NATGAS": "xyz:NATGAS", "NATURALGAS": "xyz:NATGAS",
    "PLATINUM": "xyz:PLATINUM", "PALLADIUM": "xyz:PALLADIUM",
    "ALUMINIUM": "xyz:ALUMINIUM", "ALUMINUM": "xyz:ALUMINIUM",
    "CORN": "xyz:CORN", "URANIUM": "xyz:URANIUM",
    # Indices
    "SP500": "xyz:SP500", "S&P500": "xyz:SP500", "S&P": "xyz:SP500", "SPX": "xyz:SP500",
    "XYZ100": "xyz:XYZ100",
    "JP225": "xyz:JP225", "NIKKEI": "xyz:JP225",
    "KR200": "xyz:KR200", "KOSPI": "xyz:KR200",
    "VIX": "xyz:VIX",
    "DXY": "xyz:DXY",
    # Forex
    "EURUSD": "xyz:EUR", "EUR": "xyz:EUR",
    "USDJPY": "xyz:JPY", "JPY": "xyz:JPY",
    # Stocks
    "TSLA": "xyz:TSLA", "NVDA": "xyz:NVDA", "AAPL": "xyz:AAPL", "MSFT": "xyz:MSFT",
    "GOOGL": "xyz:GOOGL", "AMZN": "xyz:AMZN", "META": "xyz:META", "AMD": "xyz:AMD",
    "MSTR": "xyz:MSTR", "COIN": "xyz:COIN", "HOOD": "xyz:HOOD", "PLTR": "xyz:PLTR",
    "NFLX": "xyz:NFLX", "INTC": "xyz:INTC", "MU": "xyz:MU", "ORCL": "xyz:ORCL",
    "GME": "xyz:GME", "RIVN": "xyz:RIVN", "BABA": "xyz:BABA", "COST": "xyz:COST",
    "LLY": "xyz:LLY", "TSM": "xyz:TSM", "HIMS": "xyz:HIMS", "DKNG": "xyz:DKNG",
    "SNDK": "xyz:SNDK", "CRCL": "xyz:CRCL",
}


def _resolve_coin(coin: str) -> str:
    """
    Resolve a human-friendly coin name to the correct HL API identifier.
    Native perps: 'BTC', 'ETH', 'SOL' → returned as-is (uppercased).
    TradFi perps: 'GOLD', 'OIL', 'TSLA' → resolved to 'xyz:GOLD', 'xyz:CL', 'xyz:TSLA'.
    Already-prefixed: 'xyz:GOLD' → returned as-is.
    """
    coin = coin.strip()
    # Already has a dex prefix
    if ":" in coin:
        return coin
    upper = coin.upper()
    # Check alias map first
    if upper in TRADFI_ALIASES:
        return TRADFI_ALIASES[upper]
    return upper


def approve_hl_builder_fee() -> dict:
    """
    Approve the builder fee for Hyperliquid trading (one-time per account).
    This must be called before the first trade if a BUILDER_FEE_ADDRESS is set.
    It's safe to call multiple times — Hyperliquid ignores duplicate approvals.

    Returns:
        Dict with approval status.
    """
    global _builder_fee_approved
    if not BUILDER_FEE_ADDRESS:
        return {"status": "SKIPPED", "reason": "No HYPERLIQUID_BUILDER_FEE_ADDRESS configured"}

    try:
        result = _get_exchange()
        if result[0] is None:
            return {"error": "HYPERLIQUID_PRIVATE_KEY not set in .env"}

        exchange, _, _ = result
        # max_fee_rate is in the same format as the SDK expects: "0.01%" = 1 BPS
        resp = exchange.approve_builder_fee(BUILDER_FEE_ADDRESS, "0.01%")
        _builder_fee_approved = True

        return {
            "status": "APPROVED",
            "builder_address": BUILDER_FEE_ADDRESS,
            "max_fee_rate": "0.01% (1 BPS)",
            "response": str(resp)[:200],
        }
    except Exception as e:
        return {"error": f"Builder fee approval failed: {str(e)}"}


def _ensure_builder_fee_approved():
    """Auto-approve builder fee on first trade of the session."""
    global _builder_fee_approved
    if _builder_fee_approved or not BUILDER_FEE_ADDRESS:
        return
    try:
        approve_hl_builder_fee()
    except Exception:
        pass  # Non-fatal — trade may still work if previously approved


def _get_exchange():
    """Initialize the Hyperliquid exchange client with native + TradFi (xyz) perps."""
    try:
        from hyperliquid.info import Info
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants
        import eth_account
    except ImportError:
        raise ImportError("hyperliquid-python-sdk not installed. Run: uv add hyperliquid-python-sdk")

    private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY", "").strip()
    if not private_key:
        return None, None

    account = eth_account.Account.from_key(private_key)
    wallet_address = account.address

    # Load both native perps ("") and TradFi builder dex ("xyz")
    info = Info(constants.MAINNET_API_URL, skip_ws=True, perp_dexs=["", "xyz"])
    exchange = Exchange(account, constants.MAINNET_API_URL)

    return exchange, info, wallet_address


def _get_info():
    """Initialize just the info client (read-only, no private key needed) with TradFi support."""
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
    except ImportError:
        raise ImportError("hyperliquid-python-sdk not installed. Run: uv add hyperliquid-python-sdk")

    wallet = os.getenv("HYPERLIQUID_WALLET_ADDRESS", "").strip()
    # Load both native perps ("") and TradFi builder dex ("xyz")
    info = Info(constants.MAINNET_API_URL, skip_ws=True, perp_dexs=["", "xyz"])
    return info, wallet


def get_hl_config() -> dict:
    """
    Show the current Hyperliquid configuration status.

    Returns:
        Wallet address, trading capability, and connection status.
    """
    wallet = os.getenv("HYPERLIQUID_WALLET_ADDRESS", "").strip()
    private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY", "").strip()

    config = {
        "wallet_address": wallet if wallet else "Not configured",
        "trading_enabled": bool(private_key),
        "mode": "Full trading" if private_key else ("Read-only" if wallet else "Not configured"),
    }

    # Test connection if wallet is set
    if wallet:
        try:
            info, _ = _get_info()
            user_state = info.user_state(wallet)
            config["connection"] = "Connected"
            cross_margin = user_state.get("crossMarginSummary", user_state.get("marginSummary", {}))
            config["account_value"] = cross_margin.get("accountValue", "0")
        except Exception as e:
            config["connection"] = f"Error: {str(e)}"

    return config


def get_hl_account_info() -> dict:
    """
    Get Hyperliquid account balances and margin info.

    Returns:
        Account equity, available margin, positions summary.
    """
    try:
        info, wallet = _get_info()
        if not wallet:
            return {"error": "HYPERLIQUID_WALLET_ADDRESS not set in .env. Use 'add hl' to configure."}

        user_state = info.user_state(wallet)

        margin_summary = user_state.get("marginSummary", {})
        cross_margin = user_state.get("crossMarginSummary", margin_summary)

        return {
            "wallet": wallet,
            "account_value": cross_margin.get("accountValue", "0"),
            "total_margin_used": cross_margin.get("totalMarginUsed", "0"),
            "total_ntl_pos": cross_margin.get("totalNtlPos", "0"),
            "withdrawable": user_state.get("withdrawable", "0"),
        }
    except Exception as e:
        wallet = os.getenv("HYPERLIQUID_WALLET_ADDRESS", "").strip()
        return {"error": f"Hyperliquid error: {str(e)}", "wallet_configured": wallet or "not set"}


def get_hl_positions() -> dict:
    """
    Get all open positions on Hyperliquid.

    Returns:
        List of positions with PnL, size, entry price, leverage.
    """
    try:
        info, wallet = _get_info()
        if not wallet:
            return {"error": "HYPERLIQUID_WALLET_ADDRESS not set in .env"}

        user_state = info.user_state(wallet)
        positions = []

        for pos in user_state.get("assetPositions", []):
            p = pos.get("position", {})
            if float(p.get("szi", 0)) != 0:
                positions.append({
                    "coin": p.get("coin", "N/A"),
                    "size": p.get("szi", "0"),
                    "entry_price": p.get("entryPx", "0"),
                    "mark_price": p.get("markPx", "0"),
                    "unrealized_pnl": p.get("unrealizedPnl", "0"),
                    "return_on_equity": p.get("returnOnEquity", "0"),
                    "leverage": p.get("leverage", {}).get("value", "N/A"),
                    "liquidation_price": p.get("liquidationPx", "N/A"),
                    "margin_used": p.get("marginUsed", "0"),
                })

        return {
            "total_positions": len(positions),
            "positions": positions,
        }
    except Exception as e:
        return {"error": f"Hyperliquid error: {str(e)}"}


def get_hl_orderbook(coin: str, depth: int = 5) -> dict:
    """
    Get the orderbook for a coin on Hyperliquid.

    Args:
        coin: Trading pair — crypto (BTC, ETH, SOL) or TradFi (GOLD, SILVER, OIL, TSLA, SP500)
        depth: Number of levels to show
    """
    try:
        resolved = _resolve_coin(coin)
        info, _ = _get_info()
        l2 = info.l2_snapshot(resolved)

        bids = [{"price": b["px"], "size": b["sz"]} for b in l2.get("levels", [[]])[0][:depth]]
        asks = [{"price": a["px"], "size": a["sz"]} for a in l2.get("levels", [[], []])[1][:depth]]

        mid_price = None
        if bids and asks:
            mid_price = round((float(bids[0]["price"]) + float(asks[0]["price"])) / 2, 4)

        asset_type = "tradfi" if resolved.startswith("xyz:") else "crypto"
        return {
            "coin": resolved,
            "display_name": coin.upper(),
            "asset_type": asset_type,
            "mid_price": mid_price,
            "best_bid": bids[0] if bids else None,
            "best_ask": asks[0] if asks else None,
            "bids": bids,
            "asks": asks,
        }
    except Exception as e:
        return {"error": f"Hyperliquid error: {str(e)}"}


def get_hl_open_orders() -> dict:
    """Get all open/pending orders on Hyperliquid."""
    try:
        info, wallet = _get_info()
        if not wallet:
            return {"error": "HYPERLIQUID_WALLET_ADDRESS not set in .env"}

        orders = info.open_orders(wallet)

        formatted = []
        for o in orders:
            formatted.append({
                "oid": o.get("oid"),
                "coin": o.get("coin", "N/A"),
                "side": o.get("side", "N/A"),
                "size": o.get("sz", "0"),
                "price": o.get("limitPx", "0"),
                "order_type": o.get("orderType", "N/A"),
            })

        return {
            "total_open_orders": len(formatted),
            "orders": formatted,
        }
    except Exception as e:
        return {"error": f"Hyperliquid error: {str(e)}"}


def place_hl_order(coin: str, side: str, size: float, price: float = None,
                    order_type: str = "market", reduce_only: bool = False) -> dict:
    """
    Place an order on Hyperliquid.

    ⚠️ THIS EXECUTES A REAL TRADE WITH REAL FUNDS.

    Args:
        coin: Trading pair — crypto (BTC, ETH, SOL) or TradFi (GOLD, SILVER, OIL, TSLA, SP500, NVDA)
        side: 'buy' or 'sell'
        size: Order size in coin units
        price: Limit price (required for limit orders, ignored for market)
        order_type: 'market' or 'limit'
        reduce_only: If True, only reduces existing position

    Returns:
        Order confirmation or error.
    """
    try:
        result = _get_exchange()
        if result[0] is None:
            return {"error": "HYPERLIQUID_PRIVATE_KEY not set in .env. Trading requires a private key."}

        exchange, info, wallet = result
        coin = _resolve_coin(coin)
        is_buy = side.lower() == "buy"

        def _execute_order(use_builder: bool = True):
            """Execute the order, optionally with builder fee."""
            builder = None
            if use_builder and BUILDER_FEE_ADDRESS:
                builder = {"b": BUILDER_FEE_ADDRESS, "f": BUILDER_FEE_RATE}

            if order_type == "market":
                return exchange.market_open(
                    coin, is_buy, size, None, builder=builder,
                )
            else:
                if price is None:
                    return {"status": "err", "response": "Limit orders require a price."}
                return exchange.order(
                    coin, is_buy, size, price,
                    {"limit": {"tif": "Gtc"}},
                    reduce_only=reduce_only, builder=builder,
                )

        # Try with builder fee first (earns revenue), fallback without
        result = _execute_order(use_builder=True)

        # If builder fee not approved, retry without it
        if isinstance(result, dict):
            resp_str = str(result.get("response", ""))
            if result.get("status") == "err" and ("builder" in resp_str.lower() or "approved" in resp_str.lower()):
                result = _execute_order(use_builder=False)

        # Parse response
        if isinstance(result, dict):
            status = result.get("status", "unknown")
            response = result.get("response", {})

            if status == "ok":
                data = response.get("data", {})
                statuses = data.get("statuses", [{}])
                filled_info = statuses[0] if statuses else {}

                return {
                    "status": "SUCCESS",
                    "coin": coin,
                    "side": side,
                    "size": size,
                    "order_type": order_type,
                    "price": price,
                    "reduce_only": reduce_only,
                    "details": filled_info,
                }
            else:
                return {
                    "status": "FAILED",
                    "error": str(result),
                }

        return {"status": "SUBMITTED", "response": str(result)}

    except Exception as e:
        return {"error": f"Hyperliquid order error: {str(e)}"}


def set_hl_leverage(coin: str, leverage: int, is_cross: bool = True) -> dict:
    """
    Set leverage for a coin on Hyperliquid.

    Args:
        coin: Trading pair — crypto (ETH, BTC) or TradFi (GOLD, TSLA, SP500)
        leverage: Leverage multiplier (1-50)
        is_cross: True for cross margin, False for isolated

    Returns:
        Result dict with status.
    """
    try:
        result = _get_exchange()
        if result[0] is None:
            return {"error": "HYPERLIQUID_PRIVATE_KEY not set in .env."}

        exchange, info, wallet = result
        coin = _resolve_coin(coin)
        leverage = max(1, min(leverage, 50))  # Clamp 1-50

        resp = exchange.update_leverage(
            leverage,
            coin,
            is_cross=is_cross,
        )

        return {
            "status": "SUCCESS",
            "coin": coin,
            "leverage": leverage,
            "mode": "cross" if is_cross else "isolated",
            "response": str(resp),
        }
    except Exception as e:
        return {"error": f"Leverage update failed: {str(e)}"}


def cancel_hl_order(coin: str, oid: int) -> dict:
    """
    Cancel an open order on Hyperliquid.

    Args:
        coin: Trading pair — crypto (BTC) or TradFi (GOLD, TSLA)
        oid: Order ID from get_hl_open_orders
    """
    try:
        result = _get_exchange()
        if result[0] is None:
            return {"error": "HYPERLIQUID_PRIVATE_KEY not set in .env"}

        exchange, _, _ = result
        resolved = _resolve_coin(coin)
        result = exchange.cancel(resolved, oid)

        return {
            "status": "CANCELLED",
            "coin": resolved,
            "oid": oid,
            "response": str(result),
        }
    except Exception as e:
        return {"error": f"Hyperliquid cancel error: {str(e)}"}


def close_hl_position(coin: str) -> dict:
    """
    Close an entire position on Hyperliquid (market close).

    Args:
        coin: Trading pair to close — crypto (BTC, ETH) or TradFi (GOLD, TSLA, SP500)
    """
    try:
        result = _get_exchange()
        if result[0] is None:
            return {"error": "HYPERLIQUID_PRIVATE_KEY not set in .env"}

        exchange, info, wallet = result
        resolved = _resolve_coin(coin)

        # Get current position — check both native and xyz dex
        dex = "xyz" if resolved.startswith("xyz:") else ""
        user_state = info.user_state(wallet, dex=dex)
        current_pos = None
        for pos in user_state.get("assetPositions", []):
            p = pos.get("position", {})
            if p.get("coin") == resolved and float(p.get("szi", 0)) != 0:
                current_pos = p
                break

        if not current_pos:
            return {"error": f"No open position found for {resolved}"}

        size = abs(float(current_pos["szi"]))
        is_long = float(current_pos["szi"]) > 0

        # Close by opening opposite side — with builder fee fallback
        builder = None
        if BUILDER_FEE_ADDRESS:
            builder = {"b": BUILDER_FEE_ADDRESS, "f": BUILDER_FEE_RATE}
        result = exchange.market_open(
            resolved, not is_long, size, None, builder=builder,
        )

        # If builder fee not approved, retry without it
        if isinstance(result, dict):
            resp_str = str(result.get("response", ""))
            if result.get("status") == "err" and ("builder" in resp_str.lower() or "approved" in resp_str.lower()):
                result = exchange.market_open(
                    resolved, not is_long, size, None, builder=None,
                )

        return {
            "status": "CLOSED",
            "coin": resolved,
            "closed_size": size,
            "was_long": is_long,
            "response": str(result)[:200],
        }
    except Exception as e:
        return {"error": f"Hyperliquid close error: {str(e)}"}


# ── TradFi Discovery Functions ──────────────────────────────────

def get_hl_tradfi_assets() -> dict:
    """
    List all available TradFi / commodity / stock perps on Hyperliquid (xyz dex).
    Includes live prices, max leverage, and asset categories.
    """
    try:
        HL_API = "https://api.hyperliquid.xyz/info"

        # Get xyz meta
        r_meta = requests.post(HL_API, json={"type": "meta", "dex": "xyz"}, timeout=10)
        meta = r_meta.json()
        universe = meta.get("universe", [])

        # Get live prices
        r_mids = requests.post(HL_API, json={"type": "allMids", "dex": "xyz"}, timeout=10)
        mids = r_mids.json()

        # Categorize assets
        categories = {
            "commodities": ["GOLD", "SILVER", "CL", "BRENTOIL", "COPPER", "NATGAS",
                           "PLATINUM", "PALLADIUM", "ALUMINIUM", "CORN", "URANIUM"],
            "indices": ["SP500", "XYZ100", "JP225", "KR200", "VIX", "DXY"],
            "forex": ["EUR", "JPY"],
            "stocks": [],  # Everything else
        }
        commodity_set = set(categories["commodities"])
        index_set = set(categories["indices"])
        forex_set = set(categories["forex"])

        assets = []
        for entry in universe:
            raw_name = entry["name"]  # e.g. "xyz:GOLD"
            symbol = raw_name.replace("xyz:", "")
            price_str = mids.get(raw_name, "0")

            # Determine category
            if symbol in commodity_set:
                cat = "commodity"
            elif symbol in index_set:
                cat = "index"
            elif symbol in forex_set:
                cat = "forex"
            else:
                cat = "stock"

            assets.append({
                "symbol": symbol,
                "hl_coin": raw_name,
                "category": cat,
                "price": price_str,
                "max_leverage": entry.get("maxLeverage", "?"),
                "sz_decimals": entry.get("szDecimals", "?"),
            })

        # Sort by category then symbol
        assets.sort(key=lambda x: (x["category"], x["symbol"]))

        return {
            "total_assets": len(assets),
            "dex": "xyz",
            "assets": assets,
        }
    except Exception as e:
        return {"error": f"Failed to fetch TradFi assets: {str(e)}"}


def get_hl_tradfi_price(symbol: str) -> dict:
    """
    Get the current price and market context for a TradFi asset on Hyperliquid.

    Args:
        symbol: Asset symbol — GOLD, SILVER, OIL, TSLA, SP500, NVDA, etc.
    """
    try:
        resolved = _resolve_coin(symbol)
        dex = "xyz" if resolved.startswith("xyz:") else ""

        HL_API = "https://api.hyperliquid.xyz/info"

        # Get orderbook
        r_book = requests.post(HL_API, json={"type": "l2Book", "coin": resolved}, timeout=5)
        book = r_book.json()
        levels = book.get("levels", [[], []])

        bid = float(levels[0][0]["px"]) if levels[0] else None
        ask = float(levels[1][0]["px"]) if levels[1] else None
        mid = round((bid + ask) / 2, 4) if bid and ask else None
        spread_bps = round((ask - bid) / mid * 10000, 2) if mid else None

        # Get funding rate
        import time
        now_ms = int(time.time() * 1000)
        r_fund = requests.post(HL_API, json={
            "type": "fundingHistory", "coin": resolved,
            "startTime": now_ms - 3600000,  # last hour
        }, timeout=5)
        funding = r_fund.json()
        latest_funding = funding[-1].get("fundingRate", "0") if funding else "0"

        return {
            "symbol": symbol.upper(),
            "hl_coin": resolved,
            "asset_type": "tradfi" if dex == "xyz" else "crypto",
            "mid_price": mid,
            "bid": bid,
            "ask": ask,
            "spread_bps": spread_bps,
            "funding_rate": latest_funding,
            "funding_rate_annualized": f"{float(latest_funding) * 8760 * 100:.2f}%" if latest_funding else None,
        }
    except Exception as e:
        return {"error": f"TradFi price error: {str(e)}"}
