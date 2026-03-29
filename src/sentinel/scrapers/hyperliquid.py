"""
Hyperliquid Trading Scraper — Execute trades on Hyperliquid DEX
Supports market orders, limit orders, position management, and account info.

IMPORTANT: This module executes REAL TRADES with REAL FUNDS.
The agent will always confirm with the user before placing orders.

Requires: pip install hyperliquid-python-sdk
Auth: HYPERLIQUID_PRIVATE_KEY + HYPERLIQUID_WALLET_ADDRESS in .env
"""

import os
import json

# ── Builder Fee Configuration ──
# Every trade placed through Sentinel earns 0.01% to the builder wallet
BUILDER_FEE_ADDRESS = os.getenv("HYPERLIQUID_BUILDER_FEE_ADDRESS", "").strip()
BUILDER_FEE_RATE = 10  # tenths of a BPS → 10 = 1 BPS = 0.01%
_builder_fee_approved = False  # Module-level flag — only approve once per session


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
    """Initialize the Hyperliquid exchange client."""
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

    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    exchange = Exchange(account, constants.MAINNET_API_URL)

    return exchange, info, wallet_address


def _get_info():
    """Initialize just the info client (read-only, no private key needed)."""
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
    except ImportError:
        raise ImportError("hyperliquid-python-sdk not installed. Run: uv add hyperliquid-python-sdk")

    wallet = os.getenv("HYPERLIQUID_WALLET_ADDRESS", "").strip()
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
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
        coin: Trading pair (e.g. 'BTC', 'ETH', 'SOL')
        depth: Number of levels to show
    """
    try:
        info, _ = _get_info()
        l2 = info.l2_snapshot(coin.upper())

        bids = [{"price": b["px"], "size": b["sz"]} for b in l2.get("levels", [[]])[0][:depth]]
        asks = [{"price": a["px"], "size": a["sz"]} for a in l2.get("levels", [[], []])[1][:depth]]

        mid_price = None
        if bids and asks:
            mid_price = round((float(bids[0]["price"]) + float(asks[0]["price"])) / 2, 4)

        return {
            "coin": coin.upper(),
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
        coin: Trading pair (e.g. 'BTC', 'ETH', 'SOL')
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
        coin = coin.upper()
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
        coin: Trading pair (e.g. 'ETH', 'BTC')
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
        coin = coin.upper()
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
        coin: Trading pair (e.g. 'BTC')
        oid: Order ID from get_hl_open_orders
    """
    try:
        result = _get_exchange()
        if result[0] is None:
            return {"error": "HYPERLIQUID_PRIVATE_KEY not set in .env"}

        exchange, _, _ = result
        result = exchange.cancel(coin.upper(), oid)

        return {
            "status": "CANCELLED",
            "coin": coin.upper(),
            "oid": oid,
            "response": str(result),
        }
    except Exception as e:
        return {"error": f"Hyperliquid cancel error: {str(e)}"}


def close_hl_position(coin: str) -> dict:
    """
    Close an entire position on Hyperliquid (market close).

    Args:
        coin: Trading pair to close (e.g. 'BTC', 'ETH')
    """
    try:
        result = _get_exchange()
        if result[0] is None:
            return {"error": "HYPERLIQUID_PRIVATE_KEY not set in .env"}

        exchange, info, wallet = result
        coin = coin.upper()

        # Get current position
        user_state = info.user_state(wallet)
        current_pos = None
        for pos in user_state.get("assetPositions", []):
            p = pos.get("position", {})
            if p.get("coin") == coin and float(p.get("szi", 0)) != 0:
                current_pos = p
                break

        if not current_pos:
            return {"error": f"No open position found for {coin}"}

        size = abs(float(current_pos["szi"]))
        is_long = float(current_pos["szi"]) > 0

        # Close by opening opposite side — with builder fee fallback
        builder = None
        if BUILDER_FEE_ADDRESS:
            builder = {"b": BUILDER_FEE_ADDRESS, "f": BUILDER_FEE_RATE}
        result = exchange.market_open(
            coin, not is_long, size, None, builder=builder,
        )

        # If builder fee not approved, retry without it
        if isinstance(result, dict):
            resp_str = str(result.get("response", ""))
            if result.get("status") == "err" and ("builder" in resp_str.lower() or "approved" in resp_str.lower()):
                result = exchange.market_open(
                    coin, not is_long, size, None, builder=None,
                )

        return {
            "status": "CLOSED",
            "coin": coin,
            "closed_size": size,
            "was_long": is_long,
            "response": str(result)[:200],
        }
    except Exception as e:
        return {"error": f"Hyperliquid close error: {str(e)}"}
