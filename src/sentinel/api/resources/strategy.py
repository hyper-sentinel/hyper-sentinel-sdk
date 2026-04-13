"""
Sentinel API — Strategy Resource.

    client.strategy.status()
    client.strategy.start()
    client.strategy.stop()
    client.strategy.config(algo="macd", symbol="ETH", leverage=5)
    client.strategy.set_algo("bb", params={"period": 20})
    client.strategy.list_algos()
    client.strategy.algo_info("sma")
"""

from typing import Any, Dict, Optional


class StrategyResource:
    """Strategy management — start/stop, configure, switch algos."""

    def __init__(self, http):
        self._http = http

    def status(self) -> dict:
        """Get current strategy status — mode, algo, symbol, venue, config."""
        return self._http.get("/api/v1/strategy/status")

    def start(self) -> dict:
        """Start the trading strategy with the current configuration."""
        return self._http.post("/api/v1/strategy/start", {})

    def stop(self) -> dict:
        """Stop the running strategy."""
        return self._http.post("/api/v1/strategy/stop", {})

    def config(
        self,
        algo: Optional[str] = None,
        symbol: Optional[str] = None,
        venue: Optional[str] = None,
        interval: Optional[str] = None,
        trade_usd: Optional[float] = None,
        leverage: Optional[int] = None,
    ) -> dict:
        """Update strategy configuration.

        Args:
            algo: Algorithm name (e.g. "sma", "bb", "macd", "rsi_ict")
            symbol: Trading symbol (e.g. "ETH", "SOL", "BTC")
            venue: Trading venue ("hl" or "aster")
            interval: Candle interval (e.g. "1m", "5m", "15m")
            trade_usd: Trade size in USD
            leverage: Leverage multiplier
        """
        body = {}
        if algo is not None:
            body["algo"] = algo
        if symbol is not None:
            body["symbol"] = symbol
        if venue is not None:
            body["venue"] = venue
        if interval is not None:
            body["interval"] = interval
        if trade_usd is not None:
            body["trade_usd"] = trade_usd
        if leverage is not None:
            body["leverage"] = leverage
        return self._http.post("/api/v1/strategy/config", body)

    def set_algo(self, name: str, params: Optional[Dict[str, Any]] = None) -> dict:
        """Switch the active algorithm.

        Args:
            name: Algorithm name (e.g. "sma", "bb", "macd")
            params: Optional algorithm-specific parameters
        """
        body: Dict[str, Any] = {"algo": name}
        if params is not None:
            body["params"] = params
        return self._http.post("/api/v1/strategy/algo", body)

    def list_algos(self) -> dict:
        """List all available trading algorithms."""
        return self._http.get("/api/v1/algos")

    def algo_info(self, name: str) -> dict:
        """Get detailed info about a specific algorithm.

        Args:
            name: Algorithm name (e.g. "sma", "bb", "macd")
        """
        return self._http.get(f"/api/v1/algos/{name}")
