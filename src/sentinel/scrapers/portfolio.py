"""
Portfolio Tracker — Aggregate equity and positions across all venues.

Supports: Hyperliquid (crypto + TradFi), Aster DEX, Polymarket.
Each venue is queried independently; failures are isolated so one
offline venue doesn't break the entire summary.

v0.4.0 — Phase 1
"""


def get_portfolio_summary() -> dict:
    """
    Get a unified portfolio summary across all connected trading venues.
    Aggregates equity, positions, and PnL from Hyperliquid, Aster, and Polymarket.

    Returns:
        Dict with total equity, per-venue breakdowns, top positions, and PnL.
    """
    venues = {}
    total_equity = 0.0
    total_unrealized_pnl = 0.0
    all_positions = []
    errors = []

    # ── Hyperliquid ──────────────────────────────────────────
    try:
        from sentinel.scrapers.hyperliquid import get_hl_account_info, get_hl_positions

        account = get_hl_account_info()
        if "error" not in account:
            hl_equity = float(account.get("account_value", 0))
            total_equity += hl_equity

            positions_data = get_hl_positions()
            hl_positions = positions_data.get("positions", [])
            hl_pnl = sum(float(p.get("unrealized_pnl", 0)) for p in hl_positions)
            total_unrealized_pnl += hl_pnl

            for p in hl_positions:
                coin = p.get("coin", "?")
                asset_type = "tradfi" if str(coin).startswith("xyz:") else "crypto"
                all_positions.append({
                    "venue": "hyperliquid",
                    "coin": coin,
                    "asset_type": asset_type,
                    "size": p.get("size", "0"),
                    "entry_price": p.get("entry_price", "0"),
                    "mark_price": p.get("mark_price", "0"),
                    "unrealized_pnl": p.get("unrealized_pnl", "0"),
                    "leverage": p.get("leverage", "1"),
                })

            venues["hyperliquid"] = {
                "status": "connected",
                "equity": hl_equity,
                "margin_used": float(account.get("total_margin_used", 0)),
                "withdrawable": float(account.get("withdrawable", 0)),
                "positions": len(hl_positions),
                "unrealized_pnl": round(hl_pnl, 2),
            }
        else:
            venues["hyperliquid"] = {"status": "not_configured", "note": account.get("error", "")}
    except Exception as e:
        errors.append(f"Hyperliquid: {str(e)}")
        venues["hyperliquid"] = {"status": "error", "error": str(e)}

    # ── Aster DEX ────────────────────────────────────────────
    try:
        from sentinel.scrapers.aster import aster_balance, aster_positions

        balance = aster_balance()
        if isinstance(balance, list):
            # aster_balance returns a list of asset balances
            aster_equity = 0.0
            for b in balance:
                aster_equity += float(b.get("balance", 0))

            positions_data = aster_positions()
            aster_positions_list = []
            aster_pnl = 0.0

            if isinstance(positions_data, list):
                aster_positions_list = positions_data
                aster_pnl = sum(float(p.get("unrealized_pnl", 0)) for p in positions_data)
                total_unrealized_pnl += aster_pnl

                for p in positions_data:
                    all_positions.append({
                        "venue": "aster",
                        "coin": p.get("symbol", "?"),
                        "asset_type": "crypto",
                        "size": str(p.get("size", 0)),
                        "entry_price": str(p.get("entry_price", 0)),
                        "mark_price": str(p.get("mark_price", 0)),
                        "unrealized_pnl": str(p.get("unrealized_pnl", 0)),
                        "leverage": str(p.get("leverage", 1)),
                    })

            total_equity += aster_equity
            venues["aster"] = {
                "status": "connected",
                "equity": round(aster_equity, 2),
                "positions": len(aster_positions_list),
                "unrealized_pnl": round(aster_pnl, 2),
            }
        elif isinstance(balance, dict) and balance.get("error"):
            venues["aster"] = {"status": "not_configured", "note": balance.get("message", "")}
        else:
            venues["aster"] = {"status": "not_configured"}
    except Exception as e:
        errors.append(f"Aster: {str(e)}")
        venues["aster"] = {"status": "error", "error": str(e)}

    # ── Polymarket ───────────────────────────────────────────
    try:
        from sentinel.scrapers.polymarket import get_polymarket_positions

        pm_data = get_polymarket_positions()
        if "error" not in pm_data:
            pm_orders = pm_data.get("total_open_orders", 0)
            pm_trades = pm_data.get("recent_trades_count", 0)

            venues["polymarket"] = {
                "status": "connected",
                "open_orders": pm_orders,
                "recent_trades": pm_trades,
            }
        else:
            venues["polymarket"] = {"status": "not_configured", "note": pm_data.get("error", "")}
    except Exception as e:
        errors.append(f"Polymarket: {str(e)}")
        venues["polymarket"] = {"status": "error", "error": str(e)}

    # ── Sort positions by absolute PnL ───────────────────────
    all_positions.sort(key=lambda p: abs(float(p.get("unrealized_pnl", 0))), reverse=True)

    # ── Count connected venues ───────────────────────────────
    connected = sum(1 for v in venues.values() if v.get("status") == "connected")

    return {
        "total_equity": round(total_equity, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "connected_venues": connected,
        "total_venues": len(venues),
        "total_positions": len(all_positions),
        "venues": venues,
        "top_positions": all_positions[:10],
        "errors": errors if errors else None,
    }


def get_portfolio_risk() -> dict:
    """
    Analyze portfolio risk: concentration, total leverage exposure, and venue diversification.

    Returns:
        Dict with risk metrics including concentration %, max leverage, and allocation breakdown.
    """
    summary = get_portfolio_summary()
    if summary.get("total_equity", 0) == 0:
        return {
            "risk_level": "N/A",
            "reason": "No equity detected across venues",
            "summary": summary,
        }

    total_equity = summary["total_equity"]
    positions = summary.get("top_positions", [])

    # ── Concentration risk ───────────────────────────────────
    position_values = []
    for p in positions:
        size = abs(float(p.get("size", 0)))
        mark = float(p.get("mark_price", 0))
        notional = size * mark
        position_values.append({
            "coin": p.get("coin", "?"),
            "venue": p.get("venue", "?"),
            "notional": round(notional, 2),
            "pct_of_equity": round((notional / total_equity * 100) if total_equity > 0 else 0, 1),
        })

    position_values.sort(key=lambda x: x["notional"], reverse=True)

    # ── Leverage exposure ────────────────────────────────────
    max_leverage = 0
    total_notional = 0.0
    for p in positions:
        lev = float(p.get("leverage", 1))
        size = abs(float(p.get("size", 0)))
        mark = float(p.get("mark_price", 0))
        total_notional += size * mark
        if lev > max_leverage:
            max_leverage = lev

    effective_leverage = round(total_notional / total_equity, 1) if total_equity > 0 else 0

    # ── Venue allocation ─────────────────────────────────────
    venue_allocation = {}
    for v_name, v_data in summary.get("venues", {}).items():
        if v_data.get("status") == "connected":
            v_eq = v_data.get("equity", 0)
            venue_allocation[v_name] = {
                "equity": round(v_eq, 2),
                "pct": round((v_eq / total_equity * 100) if total_equity > 0 else 0, 1),
            }

    # ── Risk level ───────────────────────────────────────────
    if effective_leverage > 10:
        risk_level = "🔴 HIGH"
    elif effective_leverage > 3:
        risk_level = "🟡 MEDIUM"
    else:
        risk_level = "🟢 LOW"

    top_concentration = position_values[0]["pct_of_equity"] if position_values else 0
    if top_concentration > 50:
        risk_level = "🔴 HIGH"
    elif top_concentration > 30 and risk_level == "🟢 LOW":
        risk_level = "🟡 MEDIUM"

    return {
        "risk_level": risk_level,
        "total_equity": total_equity,
        "total_notional": round(total_notional, 2),
        "effective_leverage": f"{effective_leverage}x",
        "max_position_leverage": f"{max_leverage}x",
        "top_concentration": f"{top_concentration}% in {position_values[0]['coin']}" if position_values else "N/A",
        "position_count": len(positions),
        "venue_allocation": venue_allocation,
        "position_breakdown": position_values[:5],
        "unrealized_pnl": summary.get("total_unrealized_pnl", 0),
    }
