"""
Sentinel API — Main Client.

    from sentinel.api import SentinelAPI

    # Option 1: Direct API key
    client = SentinelAPI(api_key="sk-sentinel-xxx")

    # Option 2: Auto-load from ~/.sentinel/api_key
    client = SentinelAPI()

    # Resources
    client.market.price("bitcoin")
    client.chat.send("analyze BTC")
    client.trade.hl_positions()
    client.billing.status()
    client.tools.list()
    client.tools.call("any_tool_name", param1="value")
"""

from typing import Generator, Optional, Union

from sentinel.api._http import HTTPClient, load_api_key, DEFAULT_BASE_URL
from sentinel.api.errors import AuthenticationError
from sentinel.api.resources.market import MarketResource
from sentinel.api.resources.chat import ChatResource
from sentinel.api.resources.trade import TradeResource
from sentinel.api.resources.billing import BillingResource
from sentinel.api.resources.tools import ToolsResource
from sentinel.api.resources.keys import KeysResource
from sentinel.api.resources.vault import VaultResource


class SentinelAPI:
    """Sentinel Labs API Client — your gateway to 52 tools, AI, and trading.

    All calls are routed through api.hyper-sentinel.com and metered
    against your account. Get your API key at hyper-sentinel.com.

    Usage:
        from sentinel.api import SentinelAPI

        client = SentinelAPI(api_key="sk-sentinel-xxx")

        # Market data
        btc = client.market.price("bitcoin")
        macro = client.market.dashboard()

        # AI chat (metered — billed per your tier)
        response = client.chat.send("analyze BTC macro outlook")
        print(response["text"])

        # Streaming
        for chunk in client.chat.send("deep dive NVDA", stream=True):
            print(chunk["text"], end="", flush=True)

        # Trading (⚠️ real money)
        positions = client.trade.hl_positions()
        order = client.trade.hl_order(coin="BTC", side="buy", size=0.01)

        # Billing
        status = client.billing.status()
        usage = client.billing.usage()

        # Any tool
        tools = client.tools.list()
        result = client.tools.call("get_fred_series", series_id="GDP")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize the Sentinel API client.

        Args:
            api_key: Your sk-sentinel-xxx key. If not provided,
                     loads from ~/.sentinel/api_key.
            base_url: API base URL (default: production)
            timeout: Request timeout in seconds
            max_retries: Number of retries on failure
        """
        # Resolve API key
        self._api_key = api_key or load_api_key()
        if not self._api_key:
            raise AuthenticationError(
                "No API key provided. Either:\n"
                "  1. Pass api_key='sk-sentinel-xxx' to SentinelAPI()\n"
                "  2. Run 'sentinel' CLI to authenticate\n"
                "  3. Sign up at hyper-sentinel.com to get a key"
            )

        # Create HTTP client
        self._http = HTTPClient(
            api_key=self._api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

        # Initialize resources
        self.market = MarketResource(self._http)
        self._chat_resource = ChatResource(self._http)
        self.trade = TradeResource(self._http)
        self.billing = BillingResource(self._http)
        self.tools = ToolsResource(self._http)
        self.keys = KeysResource(self._http)
        self.vault = VaultResource(self._http)

    # ── Convenience shortcuts ─────────────────────────────────

    def ping(self) -> dict:
        """Check API connectivity and get your account info."""
        return self._http.get("/")

    def health(self) -> dict:
        """Check API health status."""
        return self._http.get("/health")

    def docs(self) -> dict:
        """Get the OpenAPI 3.0 specification."""
        return self._http.get("/docs")

    @property
    def api_key(self) -> str:
        """Return the API key prefix (for display, never full key)."""
        if self._api_key and len(self._api_key) > 20:
            return self._api_key[:20] + "..."
        return self._api_key or ""

    # ── Context manager ───────────────────────────────────────

    def close(self):
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        return f"SentinelAPI(key={self.api_key})"
