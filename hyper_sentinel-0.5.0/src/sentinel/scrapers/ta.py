"""
Sentinel TA Engine — Technical Analysis for Trading Strategies

Ported from hyper-sentinel/core/ta_engine.py.
Computes SMA, EMA, RSI, MACD, Bollinger Bands, and crossover detection
across all venues (Aster, Hyperliquid, TradFi).

Usage:
    from sentinel.scrapers.ta import compute_sma, compute_indicators, detect_crossover, get_ta_summary
    df = compute_sma("BTCUSDT", fast=9, slow=21, interval="5m")
    signal = detect_crossover(df)  # "bullish", "bearish", or None
"""

import logging
from typing import Optional

import pandas as pd

try:
    import pandas_ta as pta
except ImportError:
    pta = None

logger = logging.getLogger("sentinel.ta")


# ══════════════════════════════════════════════════════════════════════
# Kline Fetchers — venue-aware (aster / hl / tradfi)
# ══════════════════════════════════════════════════════════════════════

def klines_to_df(
    symbol: str,
    interval: str = "5m",
    limit: int = 100,
    venue: str = "hl",
) -> Optional[pd.DataFrame]:
    """
    Fetch klines (OHLCV candles) and return as a pandas DataFrame.

    Args:
        symbol: Trading pair — e.g. "BTC", "ETHUSDT", "GOLD"
        interval: Candle interval — 1m, 5m, 15m, 1h, 4h, 1d
        limit: Number of candles
        venue: "hl" (YFinance), "aster" (Aster DEX klines), "tradfi" (YFinance for TradFi)

    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    if venue == "aster":
        return _klines_aster(symbol, interval, limit)
    else:
        # Both "hl" and "tradfi" use YFinance
        return _klines_yfinance(symbol, interval, limit)


def _klines_aster(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    """Fetch klines from Aster DEX."""
    try:
        from sentinel.scrapers.aster import aster_klines
    except ImportError:
        logger.error("Aster scraper not available")
        return None

    raw = aster_klines(symbol, interval=interval, limit=limit)

    if isinstance(raw, dict) and raw.get("error"):
        logger.error(f"Klines fetch failed for {symbol}: {raw['error']}")
        return None

    if not raw or len(raw) < 2:
        logger.warning(f"Insufficient kline data for {symbol}: got {len(raw) if raw else 0} candles")
        return None

    df = pd.DataFrame(raw)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def _klines_yfinance(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    """
    Fetch klines via YFinance — used for Hyperliquid and TradFi.

    Maps coin names (ETH, BTC, GOLD) to YFinance tickers (ETH-USD, BTC-USD, GC=F).
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed — needed for klines. Run: pip install yfinance")
        return None

    # Map to YFinance ticker
    yf_symbol = _map_to_yfinance(symbol)

    # Map interval string to (yfinance_interval, period)
    interval_map = {
        "1m": ("1m", "1d"),
        "3m": ("5m", "5d"),     # YF doesn't have 3m
        "5m": ("5m", "5d"),
        "15m": ("15m", "60d"),
        "30m": ("30m", "60d"),
        "1h": ("1h", "730d"),
        "4h": ("1h", "730d"),   # YF doesn't have 4h → use 1h
        "1d": ("1d", "2y"),
        "D": ("1d", "2y"),
        "1w": ("1wk", "5y"),
        "W": ("1wk", "5y"),
    }
    yf_interval, yf_period = interval_map.get(interval, ("5m", "5d"))

    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=yf_period, interval=yf_interval)

        if df.empty:
            logger.warning(f"No YFinance data for {yf_symbol}")
            return None

        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].tail(limit)

        logger.debug(f"YFinance klines for {yf_symbol}: {len(df)} candles ({yf_interval})")
        return df

    except Exception as e:
        logger.error(f"YFinance klines error for {yf_symbol}: {e}")
        return None


# ── YFinance symbol mapping ──────────────────────────────────────

# TradFi assets mapped to their YFinance contract symbols
_TRADFI_YF_MAP = {
    "GOLD": "GC=F", "XAU": "GC=F",
    "SILVER": "SI=F", "XAG": "SI=F",
    "OIL": "CL=F", "WTI": "CL=F", "CL": "CL=F", "CRUDEOIL": "CL=F",
    "BRENT": "BZ=F", "BRENTOIL": "BZ=F",
    "COPPER": "HG=F",
    "NATGAS": "NG=F", "NATURALGAS": "NG=F",
    "PLATINUM": "PL=F",
    "PALLADIUM": "PA=F",
    "CORN": "ZC=F",
    "SP500": "^GSPC", "SPX": "^GSPC", "S&P500": "^GSPC",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
    "JP225": "^N225", "NIKKEI": "^N225",
    "EURUSD": "EURUSD=X", "EUR": "EURUSD=X",
    "USDJPY": "JPY=X", "JPY": "JPY=X",
}


def _map_to_yfinance(symbol: str) -> str:
    """Map a Sentinel symbol to a YFinance ticker."""
    clean = symbol.upper().replace("XYZ:", "").strip()

    # Check TradFi map
    if clean in _TRADFI_YF_MAP:
        return _TRADFI_YF_MAP[clean]

    # Crypto: append -USD if needed
    if not clean.endswith("-USD") and not clean.endswith("USDT"):
        return f"{clean}-USD"

    return clean


# ══════════════════════════════════════════════════════════════════════
# Indicators
# ══════════════════════════════════════════════════════════════════════

def compute_sma(
    symbol: str,
    fast: int = 9,
    slow: int = 21,
    interval: str = "5m",
    limit: int = 100,
    venue: str = "hl",
) -> Optional[pd.DataFrame]:
    """
    Compute fast and slow SMA for a symbol.

    Returns DataFrame with columns: close, sma_fast, sma_slow, crossover.
    crossover: 1 = bullish cross (fast above slow), -1 = bearish, 0 = no cross.
    """
    df = klines_to_df(symbol, interval=interval, limit=limit, venue=venue)
    if df is None:
        return None

    if pta:
        df["sma_fast"] = pta.sma(df["close"], length=fast)
        df["sma_slow"] = pta.sma(df["close"], length=slow)
    else:
        df["sma_fast"] = df["close"].rolling(window=fast).mean()
        df["sma_slow"] = df["close"].rolling(window=slow).mean()

    # Detect crossover
    df["cross_diff"] = df["sma_fast"] - df["sma_slow"]
    df["cross_prev"] = df["cross_diff"].shift(1)
    df["crossover"] = 0
    df.loc[(df["cross_diff"] > 0) & (df["cross_prev"] <= 0), "crossover"] = 1   # bullish
    df.loc[(df["cross_diff"] < 0) & (df["cross_prev"] >= 0), "crossover"] = -1  # bearish

    return df


def compute_indicators(
    symbol: str,
    interval: str = "5m",
    limit: int = 100,
    venue: str = "hl",
) -> Optional[dict]:
    """
    Compute a full suite of technical indicators.

    Returns dict with latest values for: SMA(9), SMA(21), EMA(12), EMA(26),
    RSI(14), MACD, Bollinger Bands, and the current price.
    """
    df = klines_to_df(symbol, interval=interval, limit=limit, venue=venue)
    if df is None:
        return None

    result = {
        "symbol": symbol.upper(),
        "interval": interval,
        "venue": venue,
        "price": float(df["close"].iloc[-1]),
        "candles": len(df),
    }

    if pta:
        # SMAs
        sma9 = pta.sma(df["close"], length=9)
        sma21 = pta.sma(df["close"], length=21)
        result["sma_9"] = float(sma9.iloc[-1]) if sma9 is not None and not sma9.empty else None
        result["sma_21"] = float(sma21.iloc[-1]) if sma21 is not None and not sma21.empty else None

        # EMAs
        ema12 = pta.ema(df["close"], length=12)
        ema26 = pta.ema(df["close"], length=26)
        result["ema_12"] = float(ema12.iloc[-1]) if ema12 is not None and not ema12.empty else None
        result["ema_26"] = float(ema26.iloc[-1]) if ema26 is not None and not ema26.empty else None

        # RSI
        rsi = pta.rsi(df["close"], length=14)
        result["rsi_14"] = float(rsi.iloc[-1]) if rsi is not None and not rsi.empty else None

        # MACD
        macd = pta.macd(df["close"])
        if macd is not None and not macd.empty:
            result["macd"] = float(macd.iloc[-1, 0])
            result["macd_signal"] = float(macd.iloc[-1, 1])
            result["macd_histogram"] = float(macd.iloc[-1, 2])

        # Bollinger Bands
        bbands = pta.bbands(df["close"], length=20)
        if bbands is not None and not bbands.empty:
            result["bb_upper"] = float(bbands.iloc[-1, 0])
            result["bb_mid"] = float(bbands.iloc[-1, 1])
            result["bb_lower"] = float(bbands.iloc[-1, 2])
    else:
        # Minimal fallback without pandas-ta
        result["sma_9"] = float(df["close"].rolling(9).mean().iloc[-1])
        result["sma_21"] = float(df["close"].rolling(21).mean().iloc[-1])
        result["rsi_14"] = None
        result["note"] = "pandas-ta not installed — only SMA available. Run: pip install pandas-ta"

    return result


def detect_crossover(df: Optional[pd.DataFrame]) -> Optional[str]:
    """
    Check the most recent candle for a crossover signal.

    Returns:
        "bullish"  — fast SMA just crossed ABOVE slow SMA
        "bearish"  — fast SMA just crossed BELOW slow SMA
        None       — no crossover on the latest candle
    """
    if df is None or "crossover" not in df.columns:
        return None

    latest = df["crossover"].iloc[-1]
    if latest == 1:
        return "bullish"
    elif latest == -1:
        return "bearish"
    return None


def get_ta_summary(symbol: str, interval: str = "5m", venue: str = "hl") -> dict:
    """
    One-call summary: all indicators + crossover signal.
    Designed to be used as an agent tool.

    Args:
        symbol: Any asset — BTC, ETH, GOLD, TSLA, BTCUSDT
        interval: Candle interval — 1m, 5m, 15m, 1h, 4h, 1d
        venue: "hl" (Hyperliquid/YFinance), "aster" (Aster DEX), "tradfi" (TradFi/YFinance)
    """
    indicators = compute_indicators(symbol, interval=interval, venue=venue)
    if not indicators:
        return {"error": f"Failed to compute TA for {symbol}"}

    sma_df = compute_sma(symbol, interval=interval, venue=venue)
    signal = detect_crossover(sma_df)

    indicators["sma_crossover_signal"] = signal or "neutral"

    # Human-readable RSI signal
    rsi = indicators.get("rsi_14")
    if rsi:
        if rsi > 70:
            indicators["rsi_signal"] = "overbought"
        elif rsi < 30:
            indicators["rsi_signal"] = "oversold"
        else:
            indicators["rsi_signal"] = "neutral"

    return indicators
"""
    Module ported from hyper-sentinel/core/ta_engine.py for Sentinel SDK 0.4.0.
    Adapted imports: sentinel.scrapers.aster, YFinance for HL/TradFi.
"""
