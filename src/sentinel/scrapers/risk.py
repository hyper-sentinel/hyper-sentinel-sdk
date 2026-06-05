"""
Sentinel Risk Metrics — Portfolio risk analysis for any asset.

Computes Sharpe, Sortino, Calmar, VaR (3 methods), CVaR, and Max Drawdown
from kline data. Uses ta.py's klines_to_df() for data fetching.

Usage:
    from sentinel.scrapers.risk import get_risk_metrics
    result = get_risk_metrics("BTC", "1d", "hl")
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("sentinel.risk")

TRADING_DAYS = 252


def _get_returns(symbol: str, interval: str = "1d", venue: str = "hl",
                 limit: int = 365) -> Optional[pd.Series]:
    """Fetch klines and compute log returns."""
    try:
        from sentinel.scrapers.ta import klines_to_df
    except ImportError:
        logger.error("ta.py not available")
        return None

    df = klines_to_df(symbol, interval=interval, limit=limit, venue=venue)
    if df is None or len(df) < 10:
        return None

    returns = np.log(df["close"] / df["close"].shift(1)).dropna()
    return returns


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe Ratio."""
    excess = returns - risk_free_rate / TRADING_DAYS
    if excess.std() == 0:
        return 0.0
    return float(np.sqrt(TRADING_DAYS) * excess.mean() / excess.std())


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Annualized Sortino Ratio — uses downside deviation only."""
    excess = returns - risk_free_rate / TRADING_DAYS
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(np.sqrt(TRADING_DAYS) * excess.mean() / downside.std())


def max_drawdown(returns: pd.Series) -> float:
    """Maximum peak-to-trough decline."""
    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    return float(drawdown.min())


def calmar_ratio(returns: pd.Series) -> float:
    """Annualized Calmar Ratio — return / |max drawdown|."""
    mdd = max_drawdown(returns)
    if mdd == 0:
        return 0.0
    ann_return = float(returns.mean() * TRADING_DAYS)
    return ann_return / abs(mdd)


def var_historical(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historical VaR at given confidence level."""
    return float(np.percentile(returns, (1 - confidence) * 100))


def var_parametric(returns: pd.Series, confidence: float = 0.95) -> float:
    """Parametric (Gaussian) VaR."""
    from scipy import stats
    z_score = stats.norm.ppf(1 - confidence)
    return float(returns.mean() + z_score * returns.std())


def var_monte_carlo(returns: pd.Series, confidence: float = 0.95,
                    simulations: int = 10_000) -> float:
    """Monte Carlo VaR — simulated return paths."""
    mean = returns.mean()
    std = returns.std()
    simulated = np.random.normal(mean, std, simulations)
    return float(np.percentile(simulated, (1 - confidence) * 100))


def cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """Conditional VaR (Expected Shortfall) — mean loss beyond VaR."""
    var = var_historical(returns, confidence)
    tail = returns[returns <= var]
    return float(tail.mean()) if len(tail) > 0 else var


def get_risk_metrics(symbol: str, interval: str = "1d", venue: str = "hl") -> dict:
    """Get risk metrics for any asset — Sharpe, Sortino, VaR, CVaR, max drawdown.

    Args:
        symbol: Asset symbol — BTC, ETH, GOLD, TSLA, AAPL
        interval: Candle interval — 1d recommended for risk metrics
        venue: Data source — hl (Hyperliquid/YFinance), aster, tradfi
    """
    returns = _get_returns(symbol, interval=interval, venue=venue)
    if returns is None:
        return {"error": f"Failed to get return data for {symbol}"}

    s = sharpe_ratio(returns)
    so = sortino_ratio(returns)
    mdd = max_drawdown(returns)
    cal = calmar_ratio(returns)

    result = {
        "symbol": symbol.upper(),
        "interval": interval,
        "venue": venue,
        "data_points": len(returns),
        "sharpe_ratio": round(s, 4),
        "sortino_ratio": round(so, 4),
        "calmar_ratio": round(cal, 4),
        "max_drawdown": round(mdd, 4),
        "max_drawdown_pct": f"{mdd * 100:.2f}%",
        "annualized_return": round(float(returns.mean() * TRADING_DAYS), 4),
        "annualized_volatility": round(float(returns.std() * np.sqrt(TRADING_DAYS)), 4),
        "var_95_historical": round(var_historical(returns), 6),
        "var_95_parametric": round(var_parametric(returns), 6),
        "cvar_95": round(cvar(returns), 6),
    }

    try:
        result["var_95_montecarlo"] = round(var_monte_carlo(returns), 6)
    except Exception:
        result["var_95_montecarlo"] = None

    # Verdict for the AI to explain
    if s > 2.0:
        result["verdict"] = f"Excellent risk-adjusted returns. Sharpe of {s:.2f} is outstanding."
    elif s > 1.0:
        result["verdict"] = f"Good risk-adjusted returns. Sharpe of {s:.2f} suggests solid performance."
    elif s > 0.5:
        result["verdict"] = f"Moderate risk. Sharpe of {s:.2f} is acceptable but not strong."
    elif s > 0:
        result["verdict"] = f"Weak risk-adjusted returns. Sharpe of {s:.2f} — risk may not be justified."
    else:
        result["verdict"] = f"Negative returns. Sharpe of {s:.2f} — this asset is losing money risk-adjusted."

    return result
