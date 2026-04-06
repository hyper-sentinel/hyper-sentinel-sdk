"""
Hyper-Sentinel v0.5.3 — The AI Trading SDK

Soli Deo Gloria — To the Glory of God alone.
© Sentinel Labs — https://hyper-sentinel.com

Usage:
    from hyper_sentinel import Sentinel

    client = Sentinel()  # auto-loads SENTINEL_API_KEY from env or ~/.sentinel/

    # Chat with AI (metered)
    print(client.chat("What's BTC at?"))

    # Market data
    btc = client.price("bitcoin")
    top = client.top_coins(10)

    # Trading (⚠️ real money)
    client.buy("BTC", 0.01)
    client.sell("ETH", 0.5, price=2000)
    positions = client.positions()

    # Any tool
    result = client.tool("get_fred_series", series_id="GDP")
"""

from typing import Optional, Union, Generator
from sentinel.api.client import SentinelAPI
from sentinel.api.errors import (
    SentinelAPIError,
    AuthenticationError,
)

__version__ = "0.5.10"


class Sentinel(SentinelAPI):
    """The Sentinel SDK — 62+ AI trading tools via one API key.

    Usage:
        client = Sentinel()
        client = Sentinel(api_key="sk-sentinel-xxx")

    Everything routes through api.hyper-sentinel.com.
    Every call is metered and billed per your tier.
    """

    # ── AI Chat ───────────────────────────────────────────────

    def chat(self, message: str, stream: bool = False, **kwargs) -> Union[str, Generator]:
        """Talk to the AI agent. It has access to all 62+ tools.

        Args:
            message: Your question, command, or analysis request
            stream: If True, yields text chunks for real-time output

        Returns:
            str response (or generator if stream=True)
        """
        response = self._chat_resource.send(message, stream=stream, **kwargs)
        if stream:
            return response
        return response.get("text", "")

    # ── Market Data ───────────────────────────────────────────

    def price(self, coin: str = "bitcoin") -> dict:
        """Get crypto price, market cap, 24h change."""
        return self.market.price(coin)

    def top_coins(self, n: int = 10) -> dict:
        """Get top N cryptocurrencies by market cap."""
        return self.market.top_crypto(n)

    def stock(self, symbol: str) -> dict:
        """Get stock/ETF price data."""
        return self.market.stock(symbol)

    def macro(self) -> dict:
        """Get macro dashboard — GDP, CPI, rates, VIX."""
        return self.market.dashboard()

    def news(self, topic: str = "crypto") -> dict:
        """Get news sentiment for a topic."""
        return self.market.news(topic)

    def trending(self) -> dict:
        """Get trending tokens from social analysis."""
        return self.market.trending_tokens()

    def orderbook(self, coin: str) -> dict:
        """Get Hyperliquid orderbook."""
        return self.trade.hl_orderbook(coin)

    # ── Trading ───────────────────────────────────────────────

    def buy(self, coin: str, size: float, price: float = None, **kwargs) -> dict:
        """Buy (market or limit). ⚠️ Real money.

        Args:
            coin: "BTC", "ETH", "SOL", etc.
            size: Amount in coin units
            price: Limit price (omit for market order)
        """
        order_type = "limit" if price else "market"
        return self.trade.hl_order(coin=coin, side="buy", size=size,
                                   price=price, order_type=order_type, **kwargs)

    def sell(self, coin: str, size: float, price: float = None, **kwargs) -> dict:
        """Sell (market or limit). ⚠️ Real money."""
        order_type = "limit" if price else "market"
        return self.trade.hl_order(coin=coin, side="sell", size=size,
                                   price=price, order_type=order_type, **kwargs)

    def positions(self) -> dict:
        """Get all open positions (Hyperliquid)."""
        return self.trade.hl_positions()

    def orders(self) -> dict:
        """Get open orders (Hyperliquid)."""
        return self.trade.hl_open_orders()

    # ── Generic Tool Call ─────────────────────────────────────

    def tool(self, name: str, **params) -> dict:
        """Call any of the 62+ tools by name.

        Args:
            name: Tool name (e.g. "get_fred_series", "search_x")
            **params: Tool parameters as keyword args
        """
        return self.tools.call(name, **params)


__all__ = [
    "Sentinel",
    "SentinelAPI",
    "SentinelAPIError",
    "AuthenticationError",
]
