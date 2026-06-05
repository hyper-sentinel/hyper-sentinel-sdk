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
