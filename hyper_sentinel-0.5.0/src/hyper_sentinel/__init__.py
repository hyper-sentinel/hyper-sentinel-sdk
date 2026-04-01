"""
hyper_sentinel — Convenience alias for the sentinel package.

    from hyper_sentinel import Sentinel

    client = Sentinel(api_key="sk-sentinel-xxx")
    result = client.chat("What's the price of BTC?")
    price = client.call("get_crypto_price", coin_id="bitcoin")

This module re-exports everything from the sentinel package so both
`from sentinel import Sentinel` and `from hyper_sentinel import Sentinel` work.
"""

from sentinel import (  # noqa: F401
    Sentinel,
    SentinelAPI,
    SentinelAPIError,
    AuthenticationError,
    __version__,
)

__all__ = [
    "Sentinel",
    "SentinelAPI",
    "SentinelAPIError",
    "AuthenticationError",
    "__version__",
]
