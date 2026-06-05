"""
Sentinel ML Signals — Machine learning analysis for any asset.

Regression trend, regime detection (K-Means), feature importance (Random Forest),
and up/down prediction (Logistic Regression). All from kline data.

Usage:
    from sentinel.scrapers.ml_signals import get_ml_signals
    result = get_ml_signals("BTC", "1d", "hl")
"""

import logging
import warnings
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("sentinel.ml_signals")

try:
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.cluster import KMeans
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def _build_feature_df(symbol: str, interval: str = "1d", venue: str = "hl",
                      limit: int = 200) -> Optional[pd.DataFrame]:
    """Build a feature matrix from kline data + TA indicators."""
    try:
        from sentinel.scrapers.ta import klines_to_df
    except ImportError:
        return None

    df = klines_to_df(symbol, interval=interval, limit=limit, venue=venue)
    if df is None or len(df) < 50:
        return None

    # Build features
    df["returns"] = np.log(df["close"] / df["close"].shift(1))
    df["sma_9"] = df["close"].rolling(9).mean()
    df["sma_21"] = df["close"].rolling(21).mean()
    df["ema_12"] = df["close"].ewm(span=12).mean()
    df["rsi_14"] = _compute_rsi(df["close"], 14)
    df["volume_sma"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma"]
    df["bb_mid"] = df["close"].rolling(20).mean()
    df["bb_std"] = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    # MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    # Target: next candle direction (1 = up, 0 = down)
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)

    return df.dropna()


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Simple RSI computation."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _get_feature_cols() -> list:
    """Feature columns for ML models."""
    return ["returns", "rsi_14", "macd", "macd_histogram", "bb_width",
            "volume_ratio", "sma_9", "ema_12"]


def regression_trend(df: pd.DataFrame) -> dict:
    """Linear regression on recent prices — trend direction + strength."""
    X = np.arange(len(df)).reshape(-1, 1)
    y = df["close"].values

    model = LinearRegression()
    model.fit(X, y)

    r2 = model.score(X, y)
    slope = float(model.coef_[0])
    direction = "up" if slope > 0 else "down"

    return {
        "trend_direction": direction,
        "trend_strength_r2": round(r2, 4),
        "slope_per_candle": round(slope, 4),
    }


def regime_detection(df: pd.DataFrame) -> dict:
    """K-Means clustering on returns — detect market regime."""
    features = df[["returns", "bb_width", "volume_ratio"]].dropna()
    if len(features) < 10:
        return {"error": "Not enough data for regime detection"}

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kmeans = KMeans(n_clusters=3, n_init=10, random_state=42)
        labels = kmeans.fit_predict(X_scaled)

    # Map clusters by mean return
    cluster_returns = {}
    for i in range(3):
        mask = labels == i
        cluster_returns[i] = features["returns"].values[mask].mean()

    sorted_clusters = sorted(cluster_returns.items(), key=lambda x: x[1])
    regime_map = {
        sorted_clusters[0][0]: "trending_down",
        sorted_clusters[1][0]: "sideways",
        sorted_clusters[2][0]: "trending_up",
    }

    current_label = labels[-1]
    return {
        "current_regime": regime_map[current_label],
        "regime_distribution": {
            regime_map[i]: int((labels == i).sum()) for i in range(3)
        },
    }


def feature_importance(df: pd.DataFrame) -> dict:
    """Random Forest feature importance — which indicators matter most."""
    feature_cols = _get_feature_cols()
    available = [c for c in feature_cols if c in df.columns]

    X = df[available].dropna()
    y = df.loc[X.index, "target"]

    if len(X) < 20:
        return {"error": "Not enough data for feature importance"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
        rf.fit(X, y)

    importances = dict(zip(available, rf.feature_importances_))
    sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)

    return {
        "top_features": [f[0] for f in sorted_features[:5]],
        "feature_scores": {f[0]: round(f[1], 4) for f in sorted_features},
    }


def predict_direction(df: pd.DataFrame) -> dict:
    """Logistic Regression — predict next candle direction."""
    feature_cols = _get_feature_cols()
    available = [c for c in feature_cols if c in df.columns]

    X = df[available].dropna()
    y = df.loc[X.index, "target"]

    if len(X) < 30:
        return {"error": "Not enough data for prediction"}

    # Train on all but last, predict last
    X_train, X_test = X.iloc[:-1], X.iloc[-1:]
    y_train = y.iloc[:-1]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lr = LogisticRegression(random_state=42, max_iter=1000)
        lr.fit(X_train_scaled, y_train)

    prediction = lr.predict(X_test_scaled)[0]
    proba = lr.predict_proba(X_test_scaled)[0]
    confidence = float(max(proba))

    return {
        "next_candle_prediction": "up" if prediction == 1 else "down",
        "prediction_confidence": round(confidence, 4),
    }


def get_ml_signals(symbol: str, interval: str = "1d", venue: str = "hl") -> dict:
    """Get ML-based trading signals — trend, regime, feature importance, prediction.

    Args:
        symbol: Asset symbol — BTC, ETH, GOLD, TSLA, AAPL
        interval: Candle interval — 1d recommended for ML signals
        venue: Data source — hl (Hyperliquid/YFinance), aster, tradfi
    """
    if not HAS_SKLEARN:
        return {"error": "scikit-learn not installed. Run: pip install scikit-learn"}

    df = _build_feature_df(symbol, interval=interval, venue=venue)
    if df is None:
        return {"error": f"Failed to build feature matrix for {symbol}. Need at least 50 candles."}

    result = {
        "symbol": symbol.upper(),
        "interval": interval,
        "venue": venue,
        "data_points": len(df),
    }

    # Regression trend
    trend = regression_trend(df)
    result["trend_direction"] = trend.get("trend_direction")
    result["trend_strength_r2"] = trend.get("trend_strength_r2")

    # Regime
    regime = regime_detection(df)
    result["current_regime"] = regime.get("current_regime")

    # Feature importance
    fi = feature_importance(df)
    result["top_features"] = fi.get("top_features", [])

    # Prediction
    pred = predict_direction(df)
    result["next_candle_prediction"] = pred.get("next_candle_prediction")
    result["prediction_confidence"] = pred.get("prediction_confidence")

    # Verdict
    parts = []
    if result.get("trend_direction"):
        r2 = result.get("trend_strength_r2", 0)
        strength = "strong" if r2 > 0.7 else "moderate" if r2 > 0.4 else "weak"
        parts.append(f"ML models show a {strength} {result['trend_direction']}trend (R²={r2})")
    if result.get("current_regime"):
        parts.append(f"regime is {result['current_regime'].replace('_', ' ')}")
    if result.get("top_features"):
        parts.append(f"{result['top_features'][0]} is the strongest signal right now")
    result["verdict"] = ". ".join(parts) + "." if parts else "Insufficient data for ML analysis."

    return result
