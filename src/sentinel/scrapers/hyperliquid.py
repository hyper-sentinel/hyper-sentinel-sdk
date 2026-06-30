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
# Maps user-friendly names → xyz dex coin names so the LLM can just say "GOLD" or "SPCX"
# v0.9.5: ALL 97 xyz dex assets — synced from live HL API 2026-06-30
TRADFI_ALIASES = {
    # ── Commodities ────────────────────────────────────────────
    "GOLD": "xyz:GOLD", "XAU": "xyz:GOLD",
    "SILVER": "xyz:SILVER", "XAG": "xyz:SILVER",
    "OIL": "xyz:CL", "WTIOIL": "xyz:CL", "WTI": "xyz:CL", "CL": "xyz:CL", "CRUDEOIL": "xyz:CL",
    "BRENTOIL": "xyz:BRENTOIL", "BRENT": "xyz:BRENTOIL",
    "COPPER": "xyz:COPPER", "NATGAS": "xyz:NATGAS", "NATURALGAS": "xyz:NATGAS",
    "PLATINUM": "xyz:PLATINUM", "PALLADIUM": "xyz:PALLADIUM",
    "ALUMINIUM": "xyz:ALUMINIUM", "ALUMINUM": "xyz:ALUMINIUM",
    "CORN": "xyz:CORN", "URANIUM": "xyz:URANIUM", "URNM": "xyz:URNM",
    "WHEAT": "xyz:WHEAT", "TTF": "xyz:TTF",
    # ── Indices ────────────────────────────────────────────────
    "SP500": "xyz:SP500", "S&P500": "xyz:SP500", "S&P": "xyz:SP500", "SPX": "xyz:SP500",
    "XYZ100": "xyz:XYZ100",
    "JP225": "xyz:JP225", "NIKKEI": "xyz:JP225",
    "KR200": "xyz:KR200", "KOSPI": "xyz:KR200",
    "NIFTY": "xyz:NIFTY",
    "IBOV": "xyz:IBOV",
    "VIX": "xyz:VIX", "VOL": "xyz:VOL",
    "DXY": "xyz:DXY",
    "SMH": "xyz:SMH", "XLE": "xyz:XLE",
    # ── Forex ──────────────────────────────────────────────────
    "EURUSD": "xyz:EUR", "EUR": "xyz:EUR",
    "USDJPY": "xyz:JPY", "JPY": "xyz:JPY",
    "GBP": "xyz:GBP", "GBPUSD": "xyz:GBP",
    "KRW": "xyz:KRW", "USDKRW": "xyz:KRW",
    # ── Country ETFs ──────────────────────────────────────────
    "EWJ": "xyz:EWJ", "EWT": "xyz:EWT", "EWY": "xyz:EWY", "EWZ": "xyz:EWZ",
    # ── US Stocks ──────────────────────────────────────────────
    "AAPL": "xyz:AAPL", "AMAT": "xyz:AMAT", "AMD": "xyz:AMD", "AMZN": "xyz:AMZN",
    "ARM": "xyz:ARM", "ASML": "xyz:ASML", "AVGO": "xyz:AVGO",
    "BABA": "xyz:BABA", "BB": "xyz:BB", "BE": "xyz:BE", "BX": "xyz:BX",
    "COIN": "xyz:COIN", "COST": "xyz:COST", "CRCL": "xyz:CRCL",
    "DELL": "xyz:DELL", "DKNG": "xyz:DKNG",
    "EBAY": "xyz:EBAY",
    "GME": "xyz:GME", "GOOGL": "xyz:GOOGL",
    "HIMS": "xyz:HIMS", "HOOD": "xyz:HOOD",
    "IBM": "xyz:IBM", "INTC": "xyz:INTC",
    "LITE": "xyz:LITE", "LLY": "xyz:LLY",
    "META": "xyz:META", "MRVL": "xyz:MRVL", "MSFT": "xyz:MSFT", "MSTR": "xyz:MSTR", "MU": "xyz:MU",
    "NBIS": "xyz:NBIS", "NFLX": "xyz:NFLX", "NOK": "xyz:NOK", "NOW": "xyz:NOW", "NVDA": "xyz:NVDA",
    "ORCL": "xyz:ORCL",
    "PLTR": "xyz:PLTR",
    "QCOM": "xyz:QCOM", "QNT": "xyz:QNT",
    "RIVN": "xyz:RIVN", "RKLB": "xyz:RKLB",
    "SNDK": "xyz:SNDK",
    "SPCX": "xyz:SPCX", "SPACEX": "xyz:SPCX",
    "TSLA": "xyz:TSLA", "TSM": "xyz:TSM",
    "WDC": "xyz:WDC",
    "ZM": "xyz:ZM",
    # ── International Stocks ───────────────────────────────────
    "HYUNDAI": "xyz:HYUNDAI", "IBIDEN": "xyz:IBIDEN", "KIOXIA": "xyz:KIOXIA",
    "SMSN": "xyz:SMSN", "SAMSUNG": "xyz:SMSN",
    "SKHX": "xyz:SKHX", "SOFTBANK": "xyz:SOFTBANK",
    # ── Crypto-adjacent / HL-native xyz assets ─────────────────
    "BIRD": "xyz:BIRD", "BOT": "xyz:BOT", "CBRS": "xyz:CBRS", "CRWV": "xyz:CRWV",
    "DRAM": "xyz:DRAM", "H100": "xyz:H100", "MINIMAX": "xyz:MINIMAX",
    "PURRDAT": "xyz:PURRDAT", "STRC": "xyz:STRC", "USAR": "xyz:USAR", "ZHIPU": "xyz:ZHIPU",
}

# ── Perp Dex Namespaces ──
# All dex namespaces to query for full account visibility.
# "" = native crypto perps (BTC, ETH, SOL)
# "xyz" = TradFi builder dex (GOLD, OIL, TSLA, SP500, stocks, forex)
# Add future HIP-3 dexes here — all read functions auto-expand.
_PERP_DEXES = ["", "xyz"]


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

    NOTE: With agent wallets, this may fail with "Must deposit before performing
    actions" — trades will still work without builder fees.

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
        resp = exchange.approve_builder_fee(BUILDER_FEE_ADDRESS, "0.01%")

        # Check if the approval actually succeeded
        resp_str = str(resp)
        if isinstance(resp, dict) and resp.get("status") == "err":
            return {
                "status": "FAILED",
                "reason": resp.get("response", "Unknown error"),
                "note": "Trades will still work without builder fee.",
            }

        _builder_fee_approved = True
        return {
            "status": "APPROVED",
            "builder_address": BUILDER_FEE_ADDRESS,
            "max_fee_rate": "0.01% (1 BPS)",
            "response": str(resp)[:200],
        }
    except Exception as e:
        return {"error": f"Builder fee approval failed: {str(e)}. Trades still work without it."}


def _ensure_builder_fee_approved():
    """Auto-approve builder fee on first trade of the session."""
    global _builder_fee_approved
    if _builder_fee_approved or not BUILDER_FEE_ADDRESS:
        return
    try:
        approve_hl_builder_fee()
    except Exception:
        pass  # Non-fatal — trade may still work if previously approved


def _derive_wallet() -> str:
    """Return the canonical wallet address for balance/position queries.

    Priority: HYPERLIQUID_WALLET_ADDRESS (master) > PK-derived (agent fallback).

    In Hyperliquid's Agent Wallet system, the PK is a sub-key that signs
    on behalf of the master wallet. Reads must hit the MASTER address
    (where the funds live), not the agent address (which is empty).

    v0.9.5 — supports HL agent wallets where PK ≠ wallet address.
    """
    env_wallet = os.getenv("HYPERLIQUID_WALLET_ADDRESS", "").strip()
    if env_wallet:
        return env_wallet
    # Fallback: derive from PK if no explicit wallet configured
    private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY", "").strip()
    if private_key:
        try:
            import eth_account
            return eth_account.Account.from_key(private_key).address
        except Exception:
            pass
    return ""


def _get_exchange():
    """Initialize the Hyperliquid exchange client with agent wallet support.

    If HYPERLIQUID_WALLET_ADDRESS differs from the PK-derived address,
    the PK is treated as an HL Agent Wallet — trades are signed by the
    agent key but execute on the master wallet via vault_address.
    """
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
    agent_address = account.address

    # Agent wallet detection: if user-entered wallet ≠ PK-derived address,
    # the PK is an API/agent key — pass account_address so trades execute on master.
    # NOTE: account_address (not vault_address) — HL vaults are a different mechanism.
    master_wallet = os.getenv("HYPERLIQUID_WALLET_ADDRESS", "").strip()
    account_addr = None
    if master_wallet and master_wallet.lower() != agent_address.lower():
        account_addr = master_wallet
        wallet_address = master_wallet
        import logging
        logging.getLogger("sentinel.hl").info(
            f"Agent wallet mode: signing with {agent_address[:10]}..., "
            f"trading on master {master_wallet[:10]}..."
        )
    else:
        wallet_address = agent_address

    # Load both native perps ("") and TradFi builder dex ("xyz")
    info = Info(constants.MAINNET_API_URL, skip_ws=True, perp_dexs=["", "xyz"])
    exchange = Exchange(account, constants.MAINNET_API_URL, account_address=account_addr, perp_dexs=["", "xyz"])

    return exchange, info, wallet_address


def _get_info():
    """Initialize the info client with TradFi support.

    When HYPERLIQUID_PRIVATE_KEY is set, derives the wallet from it so
    balance/position queries always hit the SAME wallet that trades execute
    from.  Falls back to HYPERLIQUID_WALLET_ADDRESS for read-only mode.
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
    except ImportError:
        raise ImportError("hyperliquid-python-sdk not installed. Run: uv add hyperliquid-python-sdk")

    wallet = _derive_wallet()
    # Load both native perps ("") and TradFi builder dex ("xyz")
    info = Info(constants.MAINNET_API_URL, skip_ws=True, perp_dexs=["", "xyz"])
    return info, wallet


def get_hl_config() -> dict:
    """
    Show the current Hyperliquid configuration status.
    Checks connectivity to both native crypto and TradFi (xyz) dexes.

    Returns:
        Wallet address, trading capability, and connection status for all dexes.
    """
    wallet = _derive_wallet()
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
            # Check native crypto dex
            user_state = info.user_state(wallet, dex="")
            config["connection"] = "Connected"
            cross_margin = user_state.get("crossMarginSummary", user_state.get("marginSummary", {}))
            config["account_value"] = cross_margin.get("accountValue", "0")
            # Check xyz (TradFi) dex
            try:
                xyz_state = info.user_state(wallet, dex="xyz")
                xyz_margin = xyz_state.get("crossMarginSummary", xyz_state.get("marginSummary", {}))
                config["xyz_connection"] = "Connected"
                config["xyz_account_value"] = xyz_margin.get("accountValue", "0")
            except Exception:
                config["xyz_connection"] = "Error"

            # Spot balance (unified account)
            try:
                import requests
                r = requests.post("https://api.hyperliquid.xyz/info", json={
                    "type": "spotClearinghouseState",
                    "user": wallet,
                }, timeout=10)
                spot_data = r.json()
                spot_usdc = 0.0
                for b in spot_data.get("balances", []):
                    if b.get("coin") == "USDC":
                        spot_usdc = float(b.get("total", 0))
                config["spot_usdc"] = str(round(spot_usdc, 2))
                # Combined total
                perps_val = float(config.get("account_value", 0))
                xyz_val = float(config.get("xyz_account_value", 0))
                config["total_balance"] = str(round(perps_val + xyz_val + spot_usdc, 2))
            except Exception:
                pass

        except Exception as e:
            config["connection"] = f"Error: {str(e)}"

    return config


def get_hl_account_info() -> dict:
    """
    Get Hyperliquid account balances and margin info across all dexes.
    Aggregates equity from both native crypto and TradFi (xyz) perps.

    Returns:
        Total account equity, margin, and per-dex breakdown.
    """
    try:
        info, wallet = _get_info()
        if not wallet:
            return {"error": "HYPERLIQUID_WALLET_ADDRESS not set in .env. Use 'add hl' to configure."}

        total_value = 0.0
        total_margin = 0.0
        total_ntl = 0.0
        withdrawable = "0"
        dex_breakdown = {}

        for dex in _PERP_DEXES:
            try:
                user_state = info.user_state(wallet, dex=dex)
                margin = user_state.get("crossMarginSummary", user_state.get("marginSummary", {}))
                val = float(margin.get("accountValue", 0))
                mgn = float(margin.get("totalMarginUsed", 0))
                ntl = float(margin.get("totalNtlPos", 0))
                total_value += val
                total_margin += mgn
                total_ntl += ntl
                if dex == "":
                    withdrawable = user_state.get("withdrawable", "0")
                dex_label = dex or "native"
                dex_breakdown[dex_label] = {
                    "account_value": str(val),
                    "margin_used": str(mgn),
                }
            except Exception:
                pass  # One dex failing shouldn't block the other

        # ── Spot balances (unified account) ──────────────────────
        spot_balances = []
        spot_value = 0.0
        try:
            r = requests.post("https://api.hyperliquid.xyz/info", json={
                "type": "spotClearinghouseState",
                "user": wallet,
            }, timeout=10)
            spot_data = r.json()
            for b in spot_data.get("balances", []):
                total = float(b.get("total", 0))
                if total > 0:
                    coin = b.get("coin", "?")
                    spot_balances.append({
                        "coin": coin,
                        "total": str(round(total, 6)),
                        "hold": b.get("hold", "0"),
                    })
                    # USDC counts toward total value
                    if coin == "USDC":
                        spot_value += total
        except Exception:
            pass  # Spot query failure shouldn't block perps data

        return {
            "wallet": wallet,
            "account_value": str(round(total_value + spot_value, 2)),
            "perps_value": str(round(total_value, 2)),
            "spot_value": str(round(spot_value, 2)),
            "spot_balances": spot_balances,
            "total_margin_used": str(round(total_margin, 2)),
            "total_ntl_pos": str(round(total_ntl, 2)),
            "withdrawable": withdrawable,
            "dex_breakdown": dex_breakdown,
        }
    except Exception as e:
        wallet = _derive_wallet()
        return {"error": f"Hyperliquid error: {str(e)}", "wallet_configured": wallet or "not set"}


def get_hl_positions() -> dict:
    """
    Get all open positions on Hyperliquid (native crypto + TradFi/xyz).

    Queries both the native dex (BTC, ETH, SOL) and the xyz builder dex
    (GOLD, SP500, OIL, TSLA, etc.) and merges results.

    Returns:
        List of positions with PnL, size, entry price, leverage, asset_type, dex.
    """
    try:
        info, wallet = _get_info()
        if not wallet:
            return {"error": "HYPERLIQUID_WALLET_ADDRESS not set in .env"}

        positions = []
        seen_coins = set()  # Deduplicate in case of Unified Account

        # Query both native and xyz (TradFi) dexes
        for dex in _PERP_DEXES:
            try:
                user_state = info.user_state(wallet, dex=dex)
            except Exception:
                continue

            for pos in user_state.get("assetPositions", []):
                p = pos.get("position", {})
                coin = p.get("coin", "N/A")
                if float(p.get("szi", 0)) != 0 and coin not in seen_coins:
                    seen_coins.add(coin)
                    positions.append({
                        "coin": coin,
                        "asset_type": "tradfi" if dex == "xyz" else "crypto",
                        "dex": dex or "native",
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
    """Get all open/pending orders on Hyperliquid (native crypto + TradFi/xyz)."""
    try:
        info, wallet = _get_info()
        if not wallet:
            return {"error": "HYPERLIQUID_WALLET_ADDRESS not set in .env"}

        formatted = []
        seen_oids = set()  # Deduplicate across dexes

        for dex in _PERP_DEXES:
            try:
                orders = info.open_orders(wallet, dex=dex)
                for o in orders:
                    oid = o.get("oid")
                    if oid not in seen_oids:
                        seen_oids.add(oid)
                        formatted.append({
                            "oid": oid,
                            "coin": o.get("coin", "N/A"),
                            "side": o.get("side", "N/A"),
                            "size": o.get("sz", "0"),
                            "price": o.get("limitPx", "0"),
                            "order_type": o.get("orderType", "N/A"),
                            "dex": dex or "native",
                        })
            except Exception:
                pass  # One dex failing shouldn't block the other

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

        # Auto-approve builder fee on first trade of session (revenue capture)
        _ensure_builder_fee_approved()

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

        # Check for builder fee errors at BOTH levels:
        # Level 1: {"status": "err", "response": "Must deposit..."}
        # Level 2: {"status": "ok", "response": {"data": {"statuses": [{"error": "Builder fee has not been approved."}]}}}
        needs_retry = False
        if isinstance(result, dict):
            # Top-level error
            resp_str = str(result.get("response", "")).lower()
            if result.get("status") == "err" and (
                "builder" in resp_str or "approved" in resp_str or "must deposit" in resp_str
            ):
                needs_retry = True
            # Nested error inside statuses
            elif result.get("status") == "ok":
                response = result.get("response", {})
                if isinstance(response, dict):
                    statuses = response.get("data", {}).get("statuses", [])
                    if statuses and isinstance(statuses[0], dict) and "error" in statuses[0]:
                        err_msg = statuses[0]["error"].lower()
                        if "builder" in err_msg or "approved" in err_msg:
                            needs_retry = True

        if needs_retry:
            result = _execute_order(use_builder=False)

        # Parse response
        if isinstance(result, dict):
            status = result.get("status", "unknown")
            response = result.get("response", {})

            if status == "ok":
                data = response.get("data", {}) if isinstance(response, dict) else {}
                statuses = data.get("statuses", [{}])
                filled_info = statuses[0] if statuses else {}

                # Check if the order actually filled or had a non-builder error
                if isinstance(filled_info, dict) and "error" in filled_info:
                    return {
                        "status": "FAILED",
                        "coin": coin,
                        "error": filled_info["error"],
                    }

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
        leverage = max(1, min(leverage, 125))  # Clamp 1-125 (HL max)

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

        # Close by opening opposite side — try with builder fee, fallback without
        _ensure_builder_fee_approved()
        builder = None
        if BUILDER_FEE_ADDRESS:
            builder = {"b": BUILDER_FEE_ADDRESS, "f": BUILDER_FEE_RATE}
        result = exchange.market_open(
            resolved, not is_long, size, None, builder=builder,
        )

        # Check for builder fee errors at both levels (same pattern as place_hl_order)
        needs_retry = False
        if isinstance(result, dict):
            resp_str = str(result.get("response", "")).lower()
            if result.get("status") == "err" and (
                "builder" in resp_str or "approved" in resp_str or "must deposit" in resp_str
            ):
                needs_retry = True
            elif result.get("status") == "ok":
                response = result.get("response", {})
                if isinstance(response, dict):
                    statuses = response.get("data", {}).get("statuses", [])
                    if statuses and isinstance(statuses[0], dict) and "error" in statuses[0]:
                        err_msg = statuses[0]["error"].lower()
                        if "builder" in err_msg or "approved" in err_msg:
                            needs_retry = True

        if needs_retry:
            result = exchange.market_open(
                resolved, not is_long, size, None, builder=None,
            )

        # Check if the close actually succeeded
        if isinstance(result, dict) and result.get("status") == "ok":
            response = result.get("response", {})
            if isinstance(response, dict):
                statuses = response.get("data", {}).get("statuses", [])
                if statuses and isinstance(statuses[0], dict):
                    if "error" in statuses[0]:
                        return {
                            "status": "FAILED",
                            "coin": resolved,
                            "error": statuses[0]["error"],
                        }

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
