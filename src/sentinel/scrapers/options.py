"""
Sentinel Options Analysis — Options chain analysis for stocks/ETFs.

Uses yfinance (already a dependency) to fetch options data.
Only works for TradFi assets with listed options — not crypto.

Usage:
    from sentinel.scrapers.options import get_options_analysis
    result = get_options_analysis("AAPL")
"""

import logging
from typing import Optional

logger = logging.getLogger("sentinel.options")


def get_options_analysis(symbol: str) -> dict:
    """Get options analysis for a stock/ETF — P/C ratio, IV, ATM options, sentiment.

    Args:
        symbol: Stock/ETF ticker — AAPL, TSLA, SPY, QQQ, MSFT
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed. Run: pip install yfinance"}

    try:
        ticker = yf.Ticker(symbol.upper())
        expirations = ticker.options

        if not expirations:
            return {"error": f"No options data for {symbol}. Options only available for stocks/ETFs."}

        # Use nearest expiration
        nearest_exp = expirations[0]
        chain = ticker.option_chain(nearest_exp)
        calls = chain.calls
        puts = chain.puts

        if calls.empty or puts.empty:
            return {"error": f"Empty options chain for {symbol} at {nearest_exp}"}

        # Get current price
        info = ticker.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0

        # Put/Call ratio (by open interest)
        total_call_oi = calls["openInterest"].sum() if "openInterest" in calls.columns else 0
        total_put_oi = puts["openInterest"].sum() if "openInterest" in puts.columns else 0
        pc_ratio = round(float(total_put_oi / total_call_oi), 4) if total_call_oi > 0 else None

        # Average implied volatility
        avg_call_iv = float(calls["impliedVolatility"].mean()) if "impliedVolatility" in calls.columns else None
        avg_put_iv = float(puts["impliedVolatility"].mean()) if "impliedVolatility" in puts.columns else None
        avg_iv = round((avg_call_iv + avg_put_iv) / 2, 4) if avg_call_iv and avg_put_iv else None

        # ATM options — closest to current price
        atm_call = _find_atm(calls, current_price)
        atm_put = _find_atm(puts, current_price)

        # Most active by volume
        most_active = _most_active(calls, puts, top_n=5)

        # Sentiment verdict
        sentiment, sentiment_detail = _sentiment_verdict(pc_ratio, avg_iv)

        result = {
            "symbol": symbol.upper(),
            "current_price": round(current_price, 2) if current_price else None,
            "nearest_expiry": nearest_exp,
            "total_expirations": len(expirations),
            "put_call_ratio": pc_ratio,
            "avg_implied_volatility": avg_iv,
            "total_call_oi": int(total_call_oi) if total_call_oi else 0,
            "total_put_oi": int(total_put_oi) if total_put_oi else 0,
        }

        if atm_call:
            result["atm_call"] = atm_call
        if atm_put:
            result["atm_put"] = atm_put
        if most_active:
            result["most_active"] = most_active

        result["sentiment"] = sentiment
        result["verdict"] = sentiment_detail

        return result

    except Exception as e:
        return {"error": f"Options analysis failed for {symbol}: {e}"}


def _find_atm(options_df, current_price: float) -> Optional[dict]:
    """Find the at-the-money option closest to current price."""
    if options_df.empty or current_price == 0:
        return None

    try:
        idx = (options_df["strike"] - current_price).abs().idxmin()
        row = options_df.loc[idx]

        return {
            "strike": float(row["strike"]),
            "price": round(float(row.get("lastPrice", 0)), 2),
            "volume": int(row.get("volume", 0)) if not _is_nan(row.get("volume")) else 0,
            "open_interest": int(row.get("openInterest", 0)) if not _is_nan(row.get("openInterest")) else 0,
            "iv": round(float(row.get("impliedVolatility", 0)), 4),
        }
    except Exception:
        return None


def _most_active(calls, puts, top_n: int = 5) -> list:
    """Get most active contracts by volume."""
    active = []

    for df, opt_type in [(calls, "call"), (puts, "put")]:
        if "volume" not in df.columns:
            continue
        sorted_df = df.dropna(subset=["volume"]).nlargest(top_n, "volume")
        for _, row in sorted_df.iterrows():
            active.append({
                "strike": float(row["strike"]),
                "type": opt_type,
                "volume": int(row["volume"]),
                "price": round(float(row.get("lastPrice", 0)), 2),
            })

    active.sort(key=lambda x: x["volume"], reverse=True)
    return active[:top_n]


def _sentiment_verdict(pc_ratio: Optional[float], avg_iv: Optional[float]) -> tuple:
    """Determine options sentiment from P/C ratio + IV."""
    if pc_ratio is None:
        return "unknown", "Insufficient data for sentiment analysis."

    if pc_ratio < 0.5:
        sentiment = "strongly_bullish"
    elif pc_ratio < 0.8:
        sentiment = "mildly_bullish"
    elif pc_ratio <= 1.2:
        sentiment = "neutral"
    elif pc_ratio <= 1.5:
        sentiment = "mildly_bearish"
    else:
        sentiment = "strongly_bearish"

    iv_note = ""
    if avg_iv:
        if avg_iv > 0.5:
            iv_note = f" IV at {avg_iv:.0%} is elevated — market expects a big move."
        elif avg_iv > 0.3:
            iv_note = f" IV at {avg_iv:.0%} is moderate."
        else:
            iv_note = f" IV at {avg_iv:.0%} is low — market expects calm."

    detail = f"Put/call ratio of {pc_ratio:.2f} suggests {sentiment.replace('_', ' ')} positioning.{iv_note}"
    return sentiment, detail


def _is_nan(val) -> bool:
    """Check if value is NaN."""
    try:
        import math
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


# ══════════════════════════════════════════════════════════════════════
# Black-Scholes Greeks
# ══════════════════════════════════════════════════════════════════════

def _compute_greeks(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call"
) -> dict:
    """Compute Black-Scholes Greeks for an option contract.

    Args:
        S: Spot (underlying) price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (annual, e.g. 0.045)
        sigma: Implied volatility (annual, e.g. 0.35)
        option_type: 'call' or 'put'

    Returns:
        dict with delta, gamma, theta (per day), vega (per 1% IV), rho (per 1% rate)
    """
    import math
    from scipy.stats import norm

    if T <= 0 or sigma <= 0 or S <= 0:
        return {}

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    pdf_d1 = norm.pdf(d1)
    discount = math.exp(-r * T)

    if option_type == "call":
        delta = norm.cdf(d1)
        theta = (-(S * pdf_d1 * sigma) / (2 * sqrt_T)
                 - r * K * discount * norm.cdf(d2)) / 365
        rho = (K * T * discount * norm.cdf(d2)) / 100
    else:
        delta = norm.cdf(d1) - 1
        theta = (-(S * pdf_d1 * sigma) / (2 * sqrt_T)
                 + r * K * discount * norm.cdf(-d2)) / 365
        rho = -(K * T * discount * norm.cdf(-d2)) / 100

    gamma = pdf_d1 / (S * sigma * sqrt_T)
    vega = S * pdf_d1 * sqrt_T / 100  # per 1% IV move

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "rho": round(rho, 4),
    }


# ══════════════════════════════════════════════════════════════════════
# Options Expirations — lightweight discovery
# ══════════════════════════════════════════════════════════════════════

def get_options_expirations(symbol: str) -> dict:
    """List all available options expiry dates for a stock/ETF, including LEAPS.

    Use this FIRST to discover valid expiry dates before calling get_options_chain.
    Returns dates only — no chain data fetched.

    Args:
        symbol: Stock/ETF ticker — AAPL, TSLA, SPY, LULU, GLD, TLT
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed. Run: pip install yfinance"}

    try:
        from datetime import date, datetime, timedelta

        ticker = yf.Ticker(symbol.upper())
        expirations = list(ticker.options)

        if not expirations:
            return {"error": f"No options data for {symbol}. Options only available for stocks/ETFs."}

        today = date.today()
        one_year = today + timedelta(days=365)

        leaps = [e for e in expirations if datetime.strptime(e, "%Y-%m-%d").date() > one_year]

        # Get current price for context
        info = ticker.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        return {
            "symbol": symbol.upper(),
            "current_price": round(current_price, 2) if current_price else None,
            "total": len(expirations),
            "expirations": expirations,
            "nearest": expirations[0],
            "furthest": expirations[-1],
            "leaps": leaps,
            "leap_count": len(leaps),
        }

    except Exception as e:
        return {"error": f"Failed to get expirations for {symbol}: {e}"}


# ══════════════════════════════════════════════════════════════════════
# Options Chain — full chain with Greeks
# ══════════════════════════════════════════════════════════════════════

def get_options_chain(
    symbol: str,
    expiry: str = None,
    option_type: str = "both",
    min_strike: float = None,
    max_strike: float = None,
    near_money: int = None,
) -> dict:
    """Get full options chain for a specific expiry with computed Greeks.

    Use get_options_expirations first to find valid expiry dates.

    Args:
        symbol: Stock/ETF ticker — AAPL, TSLA, SPY, LULU, GLD
        expiry: Expiration date YYYY-MM-DD (default: nearest available)
        option_type: 'calls', 'puts', or 'both' (default: both)
        min_strike: Minimum strike price filter
        max_strike: Maximum strike price filter
        near_money: Show N strikes above + below ATM (e.g. 5 = ~10 contracts). Overrides min/max.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed. Run: pip install yfinance"}

    try:
        from datetime import date, datetime

        ticker = yf.Ticker(symbol.upper())
        expirations = list(ticker.options)

        if not expirations:
            return {"error": f"No options data for {symbol}."}

        # Resolve expiry
        if expiry:
            if expiry not in expirations:
                # Try to find closest match
                closest = min(expirations, key=lambda e: abs(
                    datetime.strptime(e, "%Y-%m-%d").date() -
                    datetime.strptime(expiry, "%Y-%m-%d").date()
                ).days)
                expiry = closest
        else:
            expiry = expirations[0]

        # Get current price
        info = ticker.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0

        # Compute time to expiry
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        today = date.today()
        T = max((exp_date - today).days / 365.25, 0.001)
        is_leap = (exp_date - today).days > 365

        # Risk-free rate (approximate — could pull from FRED but this is fast)
        r = 0.045

        # Fetch the chain
        chain = ticker.option_chain(expiry)

        def _process_contracts(df, opt_type):
            """Convert a calls/puts DataFrame to list of dicts with Greeks."""
            if df.empty:
                return []

            # Apply filters
            filtered = df.copy()
            if near_money and current_price > 0:
                # Sort by distance from ATM, take N above and N below
                filtered["_dist"] = (filtered["strike"] - current_price).abs()
                above = filtered[filtered["strike"] >= current_price].nsmallest(near_money, "_dist")
                below = filtered[filtered["strike"] < current_price].nsmallest(near_money, "_dist")
                filtered = pd.concat([below, above]).sort_values("strike").drop(columns=["_dist"])
            else:
                if min_strike is not None:
                    filtered = filtered[filtered["strike"] >= min_strike]
                if max_strike is not None:
                    filtered = filtered[filtered["strike"] <= max_strike]

            contracts = []
            for _, row in filtered.iterrows():
                strike = float(row["strike"])
                iv = float(row.get("impliedVolatility", 0))

                # Compute Greeks
                greeks = _compute_greeks(current_price, strike, T, r, iv, opt_type) if iv > 0 else {}

                contract = {
                    "strike": strike,
                    "last": round(float(row.get("lastPrice", 0)), 2),
                    "bid": round(float(row.get("bid", 0)), 2),
                    "ask": round(float(row.get("ask", 0)), 2),
                    "volume": int(row.get("volume", 0)) if not _is_nan(row.get("volume")) else 0,
                    "open_interest": int(row.get("openInterest", 0)) if not _is_nan(row.get("openInterest")) else 0,
                    "iv": round(iv, 4),
                    "in_the_money": bool(row.get("inTheMoney", False)),
                }
                if greeks:
                    contract["greeks"] = greeks
                contracts.append(contract)

            return contracts

        import pandas as pd

        result = {
            "symbol": symbol.upper(),
            "expiry": expiry,
            "is_leap": is_leap,
            "current_price": round(current_price, 2) if current_price else None,
            "days_to_expiry": (exp_date - today).days,
        }

        # Build chain summary from FULL data (before filtering)
        all_calls = chain.calls
        all_puts = chain.puts
        total_call_oi = int(all_calls["openInterest"].sum()) if "openInterest" in all_calls.columns else 0
        total_put_oi = int(all_puts["openInterest"].sum()) if "openInterest" in all_puts.columns else 0

        summary = {
            "total_calls": len(all_calls),
            "total_puts": len(all_puts),
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "put_call_ratio": round(total_put_oi / total_call_oi, 4) if total_call_oi > 0 else None,
        }
        if "impliedVolatility" in all_calls.columns and not all_calls.empty:
            summary["avg_call_iv"] = round(float(all_calls["impliedVolatility"].mean()), 4)
        if "impliedVolatility" in all_puts.columns and not all_puts.empty:
            summary["avg_put_iv"] = round(float(all_puts["impliedVolatility"].mean()), 4)

        # Process requested side(s)
        if option_type in ("calls", "both"):
            result["calls"] = _process_contracts(all_calls, "call")
        if option_type in ("puts", "both"):
            result["puts"] = _process_contracts(all_puts, "put")

        result["chain_summary"] = summary
        return result

    except Exception as e:
        return {"error": f"Options chain failed for {symbol}: {e}"}
