"""
Sentinel SDK v2.0 — Python client for the Sentinel API.

© Sentinel Labs — https://hyper-sentinel.com

Full access on every tier — upgrade for lower fees.

Usage:
    from sentinel import SentinelClient

    client = SentinelClient(api_key="sk-sent-xxx")
    btc = client.get_crypto_price("bitcoin")
"""

from sentinel.client import SentinelClient
from sentinel.exceptions import (
    SentinelError,
    AuthError,
    ForbiddenError,
    RateLimitError,
    ToolNotFoundError,
)

__version__ = "2.0.0"
__all__ = [
    "SentinelClient",
    "SentinelError",
    "AuthError",
    "ForbiddenError",
    "RateLimitError",
    "ToolNotFoundError",
]
