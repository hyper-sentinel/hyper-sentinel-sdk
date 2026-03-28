"""
Sentinel SDK v2.0 — Python client for the Sentinel API Gateway.

© Sentinel Labs — https://hyper-sentinel.com

Usage:
    from sentinel import SentinelClient

    # Register + authenticate
    client = SentinelClient()
    client.register(email="you@example.com", password="pass123", name="You")

    # Or login with existing account
    client = SentinelClient()
    client.login(email="you@example.com", password="pass123")

    # Market data (all tiers)
    btc = client.get_crypto_price("bitcoin")
    top = client.get_crypto_top_n(10)
    aapl = client.get_stock_price("AAPL")

    # AI chat (bring your own key)
    resp = client.chat("Analyze BTC market structure", ai_key="sk-ant-xxx")

    # Trading (all tiers — fees apply)
    client.place_hl_order(coin="ETH", side="buy", size=0.1)

    # Wallet management
    wallet = client.generate_wallet("sol")
    balance = client.get_wallet_balance(wallet["address"], "sol")

    # Upgrade for lower fees
    url = client.upgrade("pro")         # $100/mo — lower fees
    url = client.upgrade("enterprise")  # $1,000/mo — lowest fees
"""

import time
from typing import Any, Optional

import httpx

from sentinel.exceptions import (
    SentinelError,
    AuthError,
    ForbiddenError,
    RateLimitError,
    ToolNotFoundError,
)


class SentinelClient:
    """
    Python client for the Sentinel API Gateway.

    All 80+ tools are available as typed methods on every tier — Free, Pro, and
    Enterprise. There is no feature gating; upgrading reduces your fee rates.

    Each method calls POST /api/v1/tools/{tool_name} through the Go gateway
    with JWT authentication and API key metering.

    Args:
        api_key: Your Sentinel API key (sk-sentinel-xxx). Optional — generate via register().
        token: JWT token from register/login. Optional — set via register()/login().
        base_url: API base URL. Defaults to https://sentinel-api-281199879392.us-south1.run.app (production).
                  Set to http://localhost:8080 for local development.
        timeout: Request timeout in seconds. Defaults to 30.
        max_retries: Max retries on rate limit (429). Defaults to 3.
    """

    def __init__(
        self,
        api_key: str = "",
        token: str = "",
        base_url: str = "https://sentinel-api-281199879392.us-south1.run.app",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_id: str = ""
        self.tier: str = ""
        self._rate_limit_info: dict = {"limit": 0, "remaining": 0}
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._headers(),
        )

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    def _refresh_headers(self):
        """Update client headers after auth state changes."""
        self._client.headers.update(self._headers())

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def rate_limit(self) -> dict:
        """Last known rate limit info from response headers."""
        return self._rate_limit_info

    def __repr__(self) -> str:
        key_display = f"{self.api_key[:16]}..." if self.api_key else "none"
        return f"SentinelClient(url={self.base_url!r}, key={key_display!r}, tier={self.tier!r})"

    # ══════════════════════════════════════════════════════════
    # Core — call any tool by name
    # ══════════════════════════════════════════════════════════

    def call_tool(self, tool_name: str, **kwargs: Any) -> dict:
        """
        Call any tool by name. This is the generic method that all
        typed methods delegate to.

        Args:
            tool_name: Name of the tool (e.g., 'get_crypto_price')
            **kwargs: Tool parameters as keyword arguments

        Returns:
            dict with 'tool', 'data', and 'meta' keys

        Raises:
            AuthError: Invalid or missing API key (401)
            ForbiddenError: Access denied (403)
            RateLimitError: Rate limit exceeded (429)
            ToolNotFoundError: Tool doesn't exist (404)
            SentinelError: Any other API error
        """
        for attempt in range(self.max_retries + 1):
            response = self._client.post(
                f"/api/v1/tools/{tool_name}",
                json=kwargs,
            )

            # Track rate limit headers
            if "X-RateLimit-Limit" in response.headers:
                self._rate_limit_info = {
                    "limit": int(response.headers.get("X-RateLimit-Limit", 0)),
                    "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
                }

            if response.status_code == 200:
                return response.json()

            # Rate limited — retry with backoff
            if response.status_code == 429 and attempt < self.max_retries:
                wait = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait)
                continue

            # Error — raise appropriate exception
            self._raise_for_status(response, tool_name)

        # Should not reach here, but just in case
        self._raise_for_status(response, tool_name)

    def _raise_for_status(self, response: httpx.Response, tool_name: str):
        """Convert HTTP error responses to typed exceptions."""
        try:
            detail = response.json()
        except Exception:
            detail = {"error": response.text}

        msg = detail.get("error", detail.get("message", f"HTTP {response.status_code}"))

        if response.status_code == 401:
            raise AuthError(msg, status_code=401, detail=detail)
        elif response.status_code == 403:
            raise ForbiddenError(msg, status_code=403, detail=detail)
        elif response.status_code == 429:
            raise RateLimitError(msg, detail=detail)
        elif response.status_code == 404:
            raise ToolNotFoundError(msg, status_code=404, detail=detail)
        else:
            raise SentinelError(msg, status_code=response.status_code, detail=detail)

    # ══════════════════════════════════════════════════════════
    # Auth — Register, Login, API Key Management
    # ══════════════════════════════════════════════════════════

    def register(self, email: str, password: str, name: str = "") -> dict:
        """
        Register a new account. Sets token and user_id on the client.

        Returns:
            dict with user_id, email, tier, token
        """
        resp = self._client.post("/auth/register", json={
            "email": email, "password": password, "name": name,
        })
        if resp.status_code != 201:
            self._raise_for_status(resp, "register")
        data = resp.json()
        self.token = data["token"]
        self.user_id = data["user_id"]
        self.tier = data["tier"]
        self._refresh_headers()
        return data

    def login(self, email: str, password: str) -> dict:
        """
        Login to an existing account. Sets token and user_id on the client.

        Returns:
            dict with user_id, email, tier, token
        """
        resp = self._client.post("/auth/login", json={
            "email": email, "password": password,
        })
        if resp.status_code != 200:
            self._raise_for_status(resp, "login")
        data = resp.json()
        self.token = data["token"]
        self.user_id = data["user_id"]
        self.tier = data["tier"]
        self._refresh_headers()
        return data

    def generate_key(self, name: str = "default") -> dict:
        """
        Generate a new API key. Requires authentication.
        The key is returned ONCE — save it.

        Returns:
            dict with api_key, key_prefix, name, tier
        """
        resp = self._client.post("/auth/keys", json={"name": name})
        if resp.status_code != 201:
            self._raise_for_status(resp, "generate_key")
        data = resp.json()
        self.api_key = data["api_key"]
        self._refresh_headers()
        return data

    # ══════════════════════════════════════════════════════════
    # Billing — Stripe Checkout + Status
    # ══════════════════════════════════════════════════════════

    def upgrade(self, plan: str = "pro") -> str:
        """
        Create a Stripe Checkout session to upgrade your tier.
        Upgrading reduces your fee rates — everyone already has full access.

        Args:
            plan: 'pro' ($100/mo — 20% LLM, 0.06%/0.04% trades, 1K req/min)
                  'enterprise' ($1,000/mo — 10% LLM, 0.02%/0.01% trades, unlimited)

        Returns:
            Checkout URL — open in browser to complete payment.
        """
        resp = self._client.post(f"/api/v1/billing/subscribe?plan={plan}")
        if resp.status_code != 200:
            self._raise_for_status(resp, "upgrade")
        return resp.json()["checkout_url"]

    def checkout(self, plan: str = "pro") -> str:
        """Deprecated — use upgrade() instead."""
        return self.upgrade(plan)

    def upgrade_enterprise(self) -> str:
        """Shortcut for Enterprise ($1,000/mo) checkout — lowest fees."""
        return self.upgrade(plan="enterprise")

    def billing_status(self) -> dict:
        """
        Get your billing status, fee rates, usage, and upgrade options.

        Returns:
            dict with tier, subscription, your_fees (llm_markup, maker_fee, taker_fee),
            rate_limit_per_min, monthly_api_calls, platform_fees, upgrade paths
        """
        resp = self._client.get("/api/v1/billing/status")
        if resp.status_code != 200:
            self._raise_for_status(resp, "billing_status")
        return resp.json()

    def billing_usage(self) -> dict:
        """Get current billing period usage (tokens, fees, per-model breakdown)."""
        resp = self._client.get("/api/v1/billing/usage")
        if resp.status_code != 200:
            self._raise_for_status(resp, "billing_usage")
        return resp.json()

    def billing_history(self) -> dict:
        """Get past invoice history from Stripe."""
        resp = self._client.get("/api/v1/billing/history")
        if resp.status_code != 200:
            self._raise_for_status(resp, "billing_history")
        return resp.json()

    # ══════════════════════════════════════════════════════════
    # LLM Proxy — Chat with AI (metered via platform fee)
    # ══════════════════════════════════════════════════════════

    def chat(
        self,
        message: str,
        ai_key: str = "",
        model: str = "",
        provider: str = "",
        system: str = "",
        max_tokens: int = 0,
    ) -> dict:
        """
        Send a message to an LLM through the Sentinel proxy.
        Tokens are metered with a tier-based markup (Free: 40%, Pro: 20%, Enterprise: 10%).

        Args:
            message: Your message to the AI
            ai_key: Your AI provider API key (sk-ant-xxx, sk-xxx, AIza-xxx, xai-xxx)
            model: Model name (e.g., 'claude-sonnet-4-20250514', 'gpt-4o')
            provider: Override auto-detection ('anthropic', 'openai', 'google', 'xai')
            system: Optional system prompt
            max_tokens: Max response tokens (0 = gateway default of 4096)

        Returns:
            Provider response with sentinel_meta (token counts, fees)
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {"messages": messages}
        if model:
            payload["model"] = model
        if provider:
            payload["provider"] = provider
        if max_tokens > 0:
            payload["max_tokens"] = max_tokens

        # Send AI key via header (more secure — not logged in request body)
        extra_headers = {}
        if ai_key:
            extra_headers["X-AI-Key"] = ai_key

        resp = self._client.post("/api/v1/llm/chat", json=payload, headers=extra_headers)
        if resp.status_code != 200:
            self._raise_for_status(resp, "chat")
        return resp.json()

    def llm_usage(self) -> dict:
        """
        Get your LLM token usage for the current billing period.

        Returns:
            dict with monthly_tokens, monthly_fees, per-model breakdown
        """
        resp = self._client.get("/api/v1/llm/usage")
        if resp.status_code != 200:
            self._raise_for_status(resp, "llm_usage")
        return resp.json()

    # ══════════════════════════════════════════════════════════
    # Meta
    # ══════════════════════════════════════════════════════════

    def health(self) -> dict:
        """Check API health."""
        return self._client.get("/health").json()

    def api_info(self) -> dict:
        """Get API overview: version, tiers, revenue streams, endpoints, stats."""
        resp = self._client.get("/")
        if resp.status_code != 200:
            self._raise_for_status(resp, "api_info")
        return resp.json()

    def list_tools(self) -> list[dict]:
        """List all available tools with schemas."""
        resp = self._client.get("/api/v1/tools")
        if resp.status_code != 200:
            self._raise_for_status(resp, "list_tools")
        return resp.json()["tools"]

    def tool_info(self, tool_name: str) -> dict:
        """Get schema and info for a specific tool."""
        resp = self._client.get(f"/api/v1/tools/{tool_name}")
        if resp.status_code != 200:
            self._raise_for_status(resp, tool_name)
        return resp.json()

    # ══════════════════════════════════════════════════════════
    # Crypto (CoinGecko) — PUBLIC
    # ══════════════════════════════════════════════════════════

    def get_crypto_price(self, coin_id: str = "bitcoin") -> dict:
        """Get current price, market cap, and 24h change for a crypto."""
        return self.call_tool("get_crypto_price", coin_id=coin_id)["data"]

    def get_crypto_top_n(self, n: int = 10) -> list:
        """Get top N cryptocurrencies by market cap."""
        return self.call_tool("get_crypto_top_n", n=n)["data"]

    def search_crypto(self, query: str) -> list:
        """Search for cryptocurrencies by name or symbol."""
        return self.call_tool("search_crypto", query=query)["data"]

    # ══════════════════════════════════════════════════════════
    # FRED Macro — PUBLIC
    # ══════════════════════════════════════════════════════════

    def get_fred_series(self, series_id: str, limit: int = 10) -> dict:
        """Get a FRED economic data series (GDP, CPI, rates, etc.)."""
        return self.call_tool("get_fred_series", series_id=series_id, limit=limit)["data"]

    def search_fred(self, query: str) -> list:
        """Search FRED for economic data series."""
        return self.call_tool("search_fred", query=query)["data"]

    def get_economic_dashboard(self) -> dict:
        """Get a dashboard of key economic indicators."""
        return self.call_tool("get_economic_dashboard")["data"]

    # ══════════════════════════════════════════════════════════
    # Y2 Intelligence — PUBLIC
    # ══════════════════════════════════════════════════════════

    def get_news_sentiment(self, query: str = "crypto") -> dict:
        """Get news sentiment analysis for a topic."""
        return self.call_tool("get_news_sentiment", query=query)["data"]

    def get_news_recap(self) -> dict:
        """Get latest news recap."""
        return self.call_tool("get_news_recap")["data"]

    def get_intelligence_reports(self) -> list:
        """Get latest intelligence reports."""
        return self.call_tool("get_intelligence_reports")["data"]

    def get_report_detail(self, report_id: str) -> dict:
        """Get full detail for an intelligence report."""
        return self.call_tool("get_report_detail", report_id=report_id)["data"]

    # ══════════════════════════════════════════════════════════
    # Elfa AI — PUBLIC
    # ══════════════════════════════════════════════════════════

    def get_trending_tokens(self) -> list:
        """Get currently trending tokens from social data."""
        return self.call_tool("get_trending_tokens")["data"]

    def get_top_mentions(self) -> list:
        """Get tokens with the most social mentions."""
        return self.call_tool("get_top_mentions")["data"]

    def search_mentions(self, query: str) -> list:
        """Search social mentions for a token or topic."""
        return self.call_tool("search_mentions", query=query)["data"]

    def get_trending_narratives(self) -> list:
        """Get trending market narratives."""
        return self.call_tool("get_trending_narratives")["data"]

    def get_token_news(self, token: str) -> list:
        """Get news for a specific token."""
        return self.call_tool("get_token_news", token=token)["data"]

    # ══════════════════════════════════════════════════════════
    # X / Twitter — PUBLIC
    # ══════════════════════════════════════════════════════════

    def search_x(self, query: str, max_results: int = 10) -> list:
        """Search recent tweets on X (Twitter)."""
        return self.call_tool("search_x", query=query, max_results=max_results)["data"]

    # ══════════════════════════════════════════════════════════
    # Hyperliquid — PUBLIC (market data)
    # ══════════════════════════════════════════════════════════

    def get_hl_config(self) -> dict:
        """Get Hyperliquid exchange configuration."""
        return self.call_tool("get_hl_config")["data"]

    def get_hl_orderbook(self, coin: str = "ETH") -> dict:
        """Get Hyperliquid order book for a coin."""
        return self.call_tool("get_hl_orderbook", coin=coin)["data"]

    # ══════════════════════════════════════════════════════════
    # Hyperliquid — Trading (all tiers — maker/taker fees apply)
    # ══════════════════════════════════════════════════════════

    def get_hl_account_info(self) -> dict:
        """Get your Hyperliquid account info."""
        return self.call_tool("get_hl_account_info")["data"]

    def get_hl_positions(self) -> list:
        """Get your open Hyperliquid positions."""
        return self.call_tool("get_hl_positions")["data"]

    def get_hl_open_orders(self) -> list:
        """Get your open Hyperliquid orders."""
        return self.call_tool("get_hl_open_orders")["data"]

    def place_hl_order(
        self,
        coin: str,
        side: str,
        size: float,
        price: float = 0,
        order_type: str = "market",
        trigger_price: float = 0,
        reduce_only: bool = False,
    ) -> dict:
        """
        Place a Hyperliquid order.

        Args:
            coin: Coin symbol (e.g., 'ETH', 'BTC')
            side: 'buy' or 'sell'
            size: Position size in coins
            price: Limit price (0 = market order)
            order_type: 'market', 'limit', or 'trigger'
            trigger_price: Stop/take-profit trigger price (for trigger orders)
            reduce_only: If True, only reduces existing position
        """
        params = dict(coin=coin, side=side, size=size, price=price, order_type=order_type)
        if trigger_price > 0:
            params["trigger_price"] = trigger_price
        if reduce_only:
            params["reduce_only"] = reduce_only
        return self.call_tool("place_hl_order", **params)["data"]

    def cancel_hl_order(self, coin: str, order_id: str) -> dict:
        """Cancel a Hyperliquid order."""
        return self.call_tool("cancel_hl_order", coin=coin, order_id=order_id)["data"]

    def close_hl_position(self, coin: str) -> dict:
        """Close a Hyperliquid position."""
        return self.call_tool("close_hl_position", coin=coin)["data"]

    # ══════════════════════════════════════════════════════════
    # Aster DEX — PUBLIC (market data)
    # ══════════════════════════════════════════════════════════

    def aster_ping(self) -> dict:
        """Ping Aster DEX."""
        return self.call_tool("aster_ping")["data"]

    def aster_ticker(self, symbol: str = "ETHUSDT") -> dict:
        """Get Aster ticker data."""
        return self.call_tool("aster_ticker", symbol=symbol)["data"]

    def aster_orderbook(self, symbol: str = "ETHUSDT", limit: int = 20) -> dict:
        """Get Aster order book."""
        return self.call_tool("aster_orderbook", symbol=symbol, limit=limit)["data"]

    def aster_klines(self, symbol: str = "ETHUSDT", interval: str = "1h", limit: int = 100) -> list:
        """Get Aster kline/candlestick data."""
        return self.call_tool("aster_klines", symbol=symbol, interval=interval, limit=limit)["data"]

    def aster_funding_rate(self, symbol: str = "ETHUSDT") -> dict:
        """Get Aster funding rate."""
        return self.call_tool("aster_funding_rate", symbol=symbol)["data"]

    def aster_exchange_info(self) -> dict:
        """Get Aster exchange info."""
        return self.call_tool("aster_exchange_info")["data"]

    # ══════════════════════════════════════════════════════════
    # Aster DEX — Trading (all tiers — maker/taker fees apply)
    # ══════════════════════════════════════════════════════════

    def aster_diagnose(self) -> dict:
        """Diagnose Aster DEX connection."""
        return self.call_tool("aster_diagnose")["data"]

    def aster_balance(self) -> dict:
        """Get your Aster balance."""
        return self.call_tool("aster_balance")["data"]

    def aster_positions(self) -> list:
        """Get your Aster positions."""
        return self.call_tool("aster_positions")["data"]

    def aster_account_info(self) -> dict:
        """Get your Aster account info."""
        return self.call_tool("aster_account_info")["data"]

    def aster_place_order(
        self,
        symbol: str,
        side: str,
        quantity: float = 0,
        price: float = 0,
        order_type: str = "MARKET",
        usd_amount: float = 0,
    ) -> dict:
        """
        Place an Aster order.

        Prefer usd_amount over quantity — it avoids the qty-as-notional bug.
        Example: usd_amount=50 means $50 USD, not 50 contracts.

        Args:
            symbol: Trading pair (e.g., 'ETHUSDT')
            side: 'buy' or 'sell'
            quantity: Number of contracts (use usd_amount instead when possible)
            price: Limit price (0 = market order)
            order_type: 'MARKET' or 'LIMIT'
            usd_amount: USD amount to trade (preferred over quantity)
        """
        params = dict(symbol=symbol, side=side, order_type=order_type)
        if usd_amount > 0:
            params["usd_amount"] = usd_amount
        else:
            params["quantity"] = quantity
            if price > 0:
                params["price"] = price
        return self.call_tool("aster_place_order", **params)["data"]

    def aster_cancel_order(self, symbol: str, order_id: str) -> dict:
        """Cancel an Aster order."""
        return self.call_tool("aster_cancel_order", symbol=symbol, order_id=order_id)["data"]

    def aster_cancel_all_orders(self, symbol: str = "") -> dict:
        """Cancel all Aster orders."""
        return self.call_tool("aster_cancel_all_orders", symbol=symbol)["data"]

    def aster_open_orders(self, symbol: str = "") -> list:
        """Get your open Aster orders."""
        return self.call_tool("aster_open_orders", symbol=symbol)["data"]

    def aster_set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage for an Aster symbol."""
        return self.call_tool("aster_set_leverage", symbol=symbol, leverage=leverage)["data"]

    # ══════════════════════════════════════════════════════════
    # Polymarket — PUBLIC
    # ══════════════════════════════════════════════════════════

    def get_polymarket_markets(self, limit: int = 10) -> list:
        """Get active Polymarket prediction markets."""
        return self.call_tool("get_polymarket_markets", limit=limit)["data"]

    def search_polymarket(self, query: str) -> list:
        """Search Polymarket markets."""
        return self.call_tool("search_polymarket", query=query)["data"]

    def get_polymarket_orderbook(self, market_id: str) -> dict:
        """Get Polymarket order book."""
        return self.call_tool("get_polymarket_orderbook", market_id=market_id)["data"]

    def get_polymarket_price(self, market_id: str) -> dict:
        """Get current Polymarket price."""
        return self.call_tool("get_polymarket_price", market_id=market_id)["data"]

    # ══════════════════════════════════════════════════════════
    # Polymarket — Trading (all tiers — maker/taker fees apply)
    # ══════════════════════════════════════════════════════════

    def get_polymarket_positions(self) -> list:
        """Get your Polymarket positions."""
        return self.call_tool("get_polymarket_positions")["data"]

    def buy_polymarket(self, token_id: str, amount: float) -> dict:
        """Buy on Polymarket. Amount is in USDC."""
        return self.call_tool("buy_polymarket", token_id=token_id, amount=amount)["data"]

    def sell_polymarket(self, token_id: str, amount: float) -> dict:
        """Sell on Polymarket. Amount is in USDC."""
        return self.call_tool("sell_polymarket", token_id=token_id, amount=amount)["data"]

    def place_polymarket_limit(self, token_id: str, side: str, price: float, size: float) -> dict:
        """Place a Polymarket limit order."""
        return self.call_tool("place_polymarket_limit", token_id=token_id, side=side, price=price, size=size)["data"]

    def cancel_polymarket_order(self, order_id: str) -> dict:
        """Cancel a Polymarket order."""
        return self.call_tool("cancel_polymarket_order", order_id=order_id)["data"]

    def cancel_all_polymarket_orders(self) -> dict:
        """Cancel all Polymarket orders."""
        return self.call_tool("cancel_all_polymarket_orders")["data"]

    # ══════════════════════════════════════════════════════════
    # Telegram Client API — AUTHENTICATED
    # ══════════════════════════════════════════════════════════

    def tg_read_channel(self, channel: str, limit: int = 10) -> list:
        """Read recent messages from a Telegram channel."""
        return self.call_tool("tg_read_channel", channel=channel, limit=limit)["data"]

    def tg_search_messages(self, channel: str, query: str) -> list:
        """Search messages in a Telegram channel."""
        return self.call_tool("tg_search_messages", channel=channel, query=query)["data"]

    def tg_list_channels(self) -> list:
        """List your Telegram channels."""
        return self.call_tool("tg_list_channels")["data"]

    def tg_send_message(self, target: str, message: str) -> dict:
        """Send a Telegram message."""
        return self.call_tool("tg_send_message", target=target, message=message)["data"]

    # ══════════════════════════════════════════════════════════
    # Discord — AUTHENTICATED
    # ══════════════════════════════════════════════════════════

    def discord_read_channel(self, channel_id: int, limit: int = 50) -> list:
        """Read messages from a Discord channel."""
        return self.call_tool("discord_read_channel", channel_id=channel_id, limit=limit)["data"]

    def discord_search_messages(self, channel_id: int, query: str) -> list:
        """Search messages in a Discord channel."""
        return self.call_tool("discord_search_messages", channel_id=channel_id, query=query)["data"]

    def discord_list_guilds(self) -> list:
        """List your Discord servers."""
        return self.call_tool("discord_list_guilds")["data"]

    def discord_list_channels(self, guild_id: int = 0) -> list:
        """List channels in a Discord server."""
        return self.call_tool("discord_list_channels", guild_id=guild_id)["data"]

    def discord_send_message(self, channel_id: int, content: str) -> dict:
        """Send a Discord message."""
        return self.call_tool("discord_send_message", channel_id=channel_id, content=content)["data"]

    # ══════════════════════════════════════════════════════════
    # YFinance — Stocks, ETFs, Analyst Recs
    # ══════════════════════════════════════════════════════════

    def get_stock_price(self, symbol: str = "AAPL") -> dict:
        """Get current stock price, volume, and change."""
        return self.call_tool("get_stock_price", symbol=symbol)["data"]

    def get_stock_info(self, symbol: str = "AAPL") -> dict:
        """Get detailed stock info (market cap, P/E, sector, etc.)."""
        return self.call_tool("get_stock_info", symbol=symbol)["data"]

    def get_analyst_recs(self, symbol: str = "AAPL") -> dict:
        """Get analyst recommendations for a stock."""
        return self.call_tool("get_analyst_recs", symbol=symbol)["data"]

    def get_stock_news(self, symbol: str = "AAPL") -> list:
        """Get latest news for a stock."""
        return self.call_tool("get_stock_news", symbol=symbol)["data"]

    def get_stock_history(self, symbol: str = "AAPL", period: str = "1mo") -> list:
        """Get historical stock price data."""
        return self.call_tool("get_stock_history", symbol=symbol, period=period)["data"]

    # ══════════════════════════════════════════════════════════
    # Wallet Management — SOL + ETH (all tiers)
    # ══════════════════════════════════════════════════════════

    def generate_wallet(self, chain: str = "sol") -> dict:
        """Generate a new wallet keypair. Chain: 'sol' or 'eth'."""
        return self.call_tool("generate_wallet", chain=chain)["data"]

    def import_wallet(self, chain: str, private_key: str, label: str = "") -> dict:
        """Import an existing wallet from private key."""
        return self.call_tool("import_wallet", chain=chain, private_key=private_key, label=label)["data"]

    def list_wallets(self) -> dict:
        """List all configured wallets (SOL + ETH)."""
        return self.call_tool("list_wallets")["data"]

    def get_wallet_balance(self, address: str, chain: str = "sol") -> dict:
        """Get wallet balance. Chain: 'sol' or 'eth'."""
        return self.call_tool("get_wallet_balance", address=address, chain=chain)["data"]

    def send_crypto(self, to_address: str, amount: float, chain: str = "sol") -> dict:
        """Send crypto from active wallet. Chain: 'sol' or 'eth'."""
        return self.call_tool("send_crypto", to_address=to_address, amount=amount, chain=chain)["data"]

    # ══════════════════════════════════════════════════════════
    # Strategy & Algo (all tiers — enterprise gets lowest fees)
    # ══════════════════════════════════════════════════════════

    def get_strategy(self) -> dict:
        """Get current algo strategy configuration."""
        return self.call_tool("get_strategy")["data"]

    def set_strategy(
        self,
        algo: str = "sma",
        coin: str = "ETH",
        interval: str = "5m",
        trade_size: float = 20.0,
        leverage: int = 3,
        exchange: str = "hyperliquid",
    ) -> dict:
        """Set algo strategy parameters."""
        return self.call_tool(
            "set_strategy",
            algo=algo, coin=coin, interval=interval,
            trade_size=trade_size, leverage=leverage, exchange=exchange,
        )["data"]

    def list_algos(self) -> list:
        """List all available algo strategies."""
        return self.call_tool("list_algos")["data"]

    def start_strategy(self) -> dict:
        """Start the configured algo strategy."""
        return self.call_tool("start_strategy")["data"]

    def stop_strategy(self) -> dict:
        """Stop the currently running strategy."""
        return self.call_tool("stop_strategy")["data"]

    # ══════════════════════════════════════════════════════════
    # Trade Journal — Logging & Tax
    # ══════════════════════════════════════════════════════════

    def get_trade_journal(self, limit: int = 50) -> list:
        """Get your trade journal entries."""
        return self.call_tool("get_trade_journal", limit=limit)["data"]

    def get_trade_stats(self) -> dict:
        """Get trade performance statistics (P&L, win rate, etc.)."""
        return self.call_tool("get_trade_stats")["data"]

    # ══════════════════════════════════════════════════════════
    # TradingView — Webhook Alerts
    # ══════════════════════════════════════════════════════════

    def get_tv_alerts(self, limit: int = 20) -> list:
        """Get recent TradingView webhook alerts."""
        return self.call_tool("get_tv_alerts", limit=limit)["data"]

    # ══════════════════════════════════════════════════════════
    # Admin
    # ══════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════
    # USDC Billing — On-Chain Deposits (Solana USDC)
    # ══════════════════════════════════════════════════════════

    def usdc_balance(self) -> dict:
        """Get your USDC balance, cost per call, and calls remaining."""
        resp = self._client.get("/api/v1/billing/usdc/balance")
        if resp.status_code != 200:
            self._raise_for_status(resp, "usdc_balance")
        return resp.json()

    def usdc_deposit_address(self) -> dict:
        """Get the Solana USDC deposit address for funding your account."""
        resp = self._client.get("/api/v1/billing/usdc/deposit-address")
        if resp.status_code != 200:
            self._raise_for_status(resp, "usdc_deposit_address")
        return resp.json()

    def usdc_deposits(self) -> dict:
        """Get your USDC deposit history."""
        resp = self._client.get("/api/v1/billing/usdc/deposits")
        if resp.status_code != 200:
            self._raise_for_status(resp, "usdc_deposits")
        return resp.json()

    def usdc_register_wallet(self, sol_address: str) -> dict:
        """Register your SOL wallet address for USDC deposit matching."""
        resp = self._client.post("/api/v1/billing/usdc/register-wallet", json={"sol_address": sol_address})
        if resp.status_code != 200:
            self._raise_for_status(resp, "usdc_register_wallet")
        return resp.json()

    def usdc_check_deposits(self) -> dict:
        """Manually trigger a check for new USDC deposits."""
        resp = self._client.post("/api/v1/billing/usdc/check-deposits")
        if resp.status_code != 200:
            self._raise_for_status(resp, "usdc_check_deposits")
        return resp.json()

    # ══════════════════════════════════════════════════════════
    # Admin
    # ══════════════════════════════════════════════════════════

    def admin_stats(self) -> dict:
        """Get admin dashboard stats (total users, calls, revenue). Admin only."""
        resp = self._client.get("/admin/usage")
        if resp.status_code != 200:
            self._raise_for_status(resp, "admin_stats")
        return resp.json()

    # ══════════════════════════════════════════════════════════
    # DexScreener — DEX Pair Data & Trending
    # ══════════════════════════════════════════════════════════

    def dexscreener_search(self, query: str) -> list:
        """Search DEX pairs across all chains (token name, symbol, or CA)."""
        return self.call_tool("dexscreener_search", query=query)["data"]

    def dexscreener_token(self, token_address: str) -> list:
        """Get all DEX pairs for a token contract address."""
        return self.call_tool("dexscreener_token", token_address=token_address)["data"]

    def dexscreener_trending(self) -> list:
        """Get trending/boosted tokens on DexScreener."""
        return self.call_tool("dexscreener_trending")["data"]

    def dexscreener_pair(self, chain: str, pair_address: str) -> dict:
        """Get detailed pair info by chain and pair address."""
        return self.call_tool("dexscreener_pair", chain=chain, pair_address=pair_address)["data"]

    # ══════════════════════════════════════════════════════════
    # DEX Swaps — On-Chain (all tiers — Jupiter 0.50% referral fee applies)
    # ══════════════════════════════════════════════════════════

    def dex_buy_sol(self, contract_address: str, amount_sol: float, slippage: float = 0) -> dict:
        """Buy a token with SOL via Jupiter. Slippage in % (0 = backend default)."""
        params = dict(contract_address=contract_address, amount_sol=amount_sol)
        if slippage > 0:
            params["slippage"] = slippage
        return self.call_tool("dex_buy_sol", **params)["data"]

    def dex_buy_eth(self, contract_address: str, amount_eth: float, slippage: float = 0) -> dict:
        """Buy a token with ETH via Uniswap V2. Slippage in % (0 = backend default)."""
        params = dict(contract_address=contract_address, amount_eth=amount_eth)
        if slippage > 0:
            params["slippage"] = slippage
        return self.call_tool("dex_buy_eth", **params)["data"]

    def dex_sell_sol(self, contract_address: str, percentage: float = 100.0, slippage: float = 0) -> dict:
        """Sell a token for SOL via Jupiter. Slippage in % (0 = backend default)."""
        params = dict(contract_address=contract_address, percentage=percentage)
        if slippage > 0:
            params["slippage"] = slippage
        return self.call_tool("dex_sell_sol", **params)["data"]

    def dex_sell_eth(self, contract_address: str, percentage: float = 100.0, slippage: float = 0) -> dict:
        """Sell a token for ETH via Uniswap V2. Slippage in % (0 = backend default)."""
        params = dict(contract_address=contract_address, percentage=percentage)
        if slippage > 0:
            params["slippage"] = slippage
        return self.call_tool("dex_sell_eth", **params)["data"]

    def dex_price_sol(self, contract_address: str) -> dict:
        """Get token price on Solana via Jupiter."""
        return self.call_tool("dex_price_sol", contract_address=contract_address)["data"]

    def dex_price_eth(self, contract_address: str) -> dict:
        """Get token price on Ethereum via Uniswap V2."""
        return self.call_tool("dex_price_eth", contract_address=contract_address)["data"]

