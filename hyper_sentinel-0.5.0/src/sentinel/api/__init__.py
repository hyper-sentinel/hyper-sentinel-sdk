"""
Sentinel API Client — Thin REST wrapper for api.hyper-sentinel.com

  Soli Deo Gloria — To the Glory of God alone.

Usage:
    from sentinel.api import SentinelAPI

    client = SentinelAPI(api_key="sk-sentinel-xxx")
    btc = client.market.price("bitcoin")
    response = client.chat("analyze BTC outlook")
    order = client.trade.hl_order(coin="BTC", side="buy", size=0.01)
"""

from sentinel.api.client import SentinelAPI
from sentinel.api.errors import (
    SentinelAPIError,
    AuthenticationError,
    RateLimitError,
    InsufficientBalanceError,
)

__all__ = [
    "SentinelAPI",
    "SentinelAPIError",
    "AuthenticationError",
    "RateLimitError",
    "InsufficientBalanceError",
]
