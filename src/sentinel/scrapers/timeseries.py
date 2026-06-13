"""
Sentinel Time Series Analysis — ARIMA forecast, GARCH volatility, stationarity.

Uses statsmodels for ARIMA/ADF and arch for GARCH.
All data fetched via ta.py's klines_to_df().

Usage:
    from sentinel.scrapers.timeseries import get_timeseries_forecast
    result = get_timeseries_forecast("BTC", "1d", "hl")
"""

import logging
import warnings
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("sentinel.timeseries")

try:
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.tsa.arima.model import ARIMA
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

try:
    from arch import arch_model
    HAS_ARCH = True
except ImportError:
    HAS_ARCH = False


def _get_close_series(symbol: str, interval: str = "1d", venue: str = "hl",
                      limit: int = 365) -> Optional[pd.Series]:
    """Fetch close prices via ta.py."""
    try:
        from sentinel.scrapers.ta import klines_to_df
    except ImportError:
        return None

    df = klines_to_df(symbol, interval=interval, limit=limit, venue=venue)
    if df is None or len(df) < 30:
        return None

    return df["close"].dropna()


def test_stationarity(series: pd.Series) -> dict:
    """Run ADF stationarity test."""
    if not HAS_STATSMODELS:
        return {"error": "statsmodels not installed. Run: pip install statsmodels"}

    try:
        adf_stat, adf_p, adf_lags, adf_nobs, adf_crit, _ = adfuller(series, autolag="AIC")
        is_stationary = adf_p < 0.05

        if is_stationary:
            interpretation = "Stationary — price is mean-reverting, not trending"
        else:
            interpretation = "Non-stationary — price is trending, not mean-reverting"

        return {
            "adf_statistic": round(float(adf_stat), 4),
            "adf_pvalue": round(float(adf_p), 6),
            "is_stationary": bool(is_stationary),
            "interpretation": interpretation,
        }
    except Exception as e:
        return {"error": f"ADF test failed: {e}"}


def fit_arima(series: pd.Series, forecast_steps: int = 5) -> dict:
    """Auto-fit ARIMA(1,1,1) model with forecast."""
    if not HAS_STATSMODELS:
        return {"error": "statsmodels not installed. Run: pip install statsmodels"}

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ARIMA(series, order=(1, 1, 1))
            fitted = model.fit()

        forecast_obj = fitted.get_forecast(steps=forecast_steps)
        forecast = forecast_obj.predicted_mean
        conf_int = forecast_obj.conf_int()

        return {
            "model": "ARIMA(1,1,1)",
            "aic": round(float(fitted.aic), 2),
            "forecast": [round(float(v), 2) for v in forecast.values],
            "forecast_lower": [round(float(v), 2) for v in conf_int.iloc[:, 0].values],
            "forecast_upper": [round(float(v), 2) for v in conf_int.iloc[:, 1].values],
            "current_price": round(float(series.iloc[-1]), 2),
            "forecast_direction": "up" if forecast.iloc[-1] > series.iloc[-1] else "down",
        }
    except Exception as e:
        return {"error": f"ARIMA failed: {e}"}


def fit_garch(series: pd.Series, forecast_horizon: int = 5) -> dict:
    """Fit GARCH(1,1) volatility model."""
    if not HAS_ARCH:
        return {"error": "arch not installed. Run: pip install arch"}

    try:
        returns = (np.log(series / series.shift(1)).dropna() * 100)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = arch_model(returns, vol="Garch", p=1, q=1, mean="constant")
            fitted = model.fit(disp="off")

        fc = fitted.forecast(horizon=forecast_horizon)
        vol_forecast = np.sqrt(fc.variance.values[-1, :])

        current_vol = float(np.sqrt(fitted.conditional_volatility.iloc[-1]))
        mean_vol = float(np.sqrt(fitted.conditional_volatility.mean()))
        forecast_vol = float(vol_forecast[-1])

        if current_vol > mean_vol * 1.2:
            vol_trend = "expanding"
        elif current_vol < mean_vol * 0.8:
            vol_trend = "compressing"
        else:
            vol_trend = "stable"

        return {
            "model": "GARCH(1,1)",
            "garch_current_vol": round(current_vol, 4),
            "garch_mean_vol": round(mean_vol, 4),
            "garch_forecast_vol": round(forecast_vol, 4),
            "vol_trend": vol_trend,
            "persistence": round(float(
                fitted.params.get("alpha[1]", 0) + fitted.params.get("beta[1]", 0)
            ), 4),
        }
    except Exception as e:
        return {"error": f"GARCH failed: {e}"}


def get_timeseries_forecast(symbol: str, interval: str = "1d", venue: str = "hl") -> dict:
    """Get time series forecast — stationarity test, ARIMA price forecast, GARCH volatility.

    Args:
        symbol: Asset symbol — BTC, ETH, GOLD, TSLA, AAPL
        interval: Candle interval — 1d recommended for time series
        venue: Data source — hl (Hyperliquid/YFinance), aster, tradfi
    """
    series = _get_close_series(symbol, interval=interval, venue=venue)
    if series is None:
        return {"error": f"Failed to get price data for {symbol}. Need at least 30 candles."}

    result = {
        "symbol": symbol.upper(),
        "interval": interval,
        "venue": venue,
        "data_points": len(series),
        "current_price": round(float(series.iloc[-1]), 2),
    }

    # Stationarity
    stationarity = test_stationarity(series)
    result["is_stationary"] = stationarity.get("is_stationary")
    result["adf_pvalue"] = stationarity.get("adf_pvalue")
    result["stationarity_interpretation"] = stationarity.get("interpretation", "")

    # ARIMA
    arima = fit_arima(series)
    if "error" not in arima:
        result["arima_forecast_5d"] = arima.get("forecast")
        result["arima_confidence_lower"] = arima.get("forecast_lower")
        result["arima_confidence_upper"] = arima.get("forecast_upper")
        result["arima_direction"] = arima.get("forecast_direction")
    else:
        result["arima_error"] = arima["error"]

    # GARCH
    garch = fit_garch(series)
    if "error" not in garch:
        result["garch_current_vol"] = garch.get("garch_current_vol")
        result["garch_forecast_vol"] = garch.get("garch_forecast_vol")
        result["vol_trend"] = garch.get("vol_trend")
    else:
        result["garch_error"] = garch["error"]

    # Build verdict
    parts = []
    if result.get("is_stationary") is False:
        parts.append("Price is trending (non-stationary)")
    elif result.get("is_stationary") is True:
        parts.append("Price is mean-reverting (stationary)")
    if result.get("arima_direction"):
        parts.append(f"ARIMA forecasts {result['arima_direction']}")
    if result.get("vol_trend"):
        parts.append(f"volatility is {result['vol_trend']}")
    result["verdict"] = ". ".join(parts) + "." if parts else "Insufficient data for verdict."

    return result
