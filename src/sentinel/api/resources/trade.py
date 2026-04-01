"""
Sentinel API — Trade Resource.

    # Hyperliquid
    order = client.trade.hl_order(coin="BTC", side="buy", size=0.01)
    positions = client.trade.hl_positions()

    # Aster DEX
    order = client.trade.aster_order(symbol="BTCUSDT", side="buy", size=0.01)

    # Polymarket
    bet = client.trade.pm_buy(token_id="...", amount=10, price=0.65)
"""

from typing import Optional


class TradeResource:
    """Trading across Hyperliquid, Aster DEX, and Polymarket."""

    def __init__(self, http):
        self._http = http

    # ── Hyperliquid ───────────────────────────────────────────

    def hl_positions(self) -> dict:
        """Get all Hyperliquid positions."""
        return self._http.post("/api/v1/tools/hl_positions", {})

    def hl_account(self) -> dict:
        """Get Hyperliquid account info — equity, margin, P&L."""
        return self._http.post("/api/v1/tools/hl_account", {})

    def hl_orderbook(self, coin: str) -> dict:
        """Get Hyperliquid orderbook for a coin."""
        return self._http.post("/api/v1/tools/hl_orderbook", {"coin": coin})

    def hl_open_orders(self) -> dict:
        """Get Hyperliquid open orders."""
        return self._http.post("/api/v1/tools/hl_open_orders", {})

    def hl_order(
        self,
        coin: str,
        side: str,
        size: float,
        price: float = None,
        order_type: str = "market",
        leverage: int = None,
    ) -> dict:
        """Place an order on Hyperliquid.

        ⚠️ REAL MONEY — use with caution.

        Args:
            coin: Ticker (e.g. "BTC", "ETH", "SOL")
            side: "buy" or "sell"
            size: Position size in coin units
            price: Limit price (required for limit orders)
            order_type: "market" or "limit"
            leverage: Leverage multiplier (optional)
        """
        payload = {
            "coin": coin,
            "side": side,
            "size": size,
            "order_type": order_type,
        }
        if price is not None:
            payload["price"] = price
        if leverage is not None:
            payload["leverage"] = leverage
        return self._http.post("/api/v1/tools/hl_place_order", payload)

    def hl_config(self) -> dict:
        """Get Hyperliquid perpetuals configuration."""
        return self._http.post("/api/v1/tools/hl_config", {})

    # ── Aster DEX ─────────────────────────────────────────────

    def aster_ticker(self, symbol: str = "BTCUSDT") -> dict:
        """Get Aster DEX ticker data."""
        return self._http.post("/api/v1/tools/aster_ticker", {"symbol": symbol})

    def aster_orderbook(self, symbol: str = "BTCUSDT") -> dict:
        """Get Aster DEX orderbook."""
        return self._http.post("/api/v1/tools/aster_orderbook", {"symbol": symbol})

    def aster_positions(self) -> dict:
        """Get all Aster DEX positions."""
        return self._http.post("/api/v1/tools/aster_positions", {})

    def aster_balance(self) -> dict:
        """Get Aster DEX account balance."""
        return self._http.post("/api/v1/tools/aster_balance", {})

    def aster_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float = None,
        order_type: str = "MARKET",
        leverage: int = None,
    ) -> dict:
        """Place an order on Aster DEX.

        ⚠️ REAL MONEY — use with caution.
        """
        payload = {
            "symbol": symbol,
            "side": side.upper(),
            "quantity": size,
            "order_type": order_type,
        }
        if price is not None:
            payload["price"] = price
        if leverage is not None:
            payload["leverage"] = leverage
        return self._http.post("/api/v1/tools/aster_place_order", payload)

    def aster_cancel(self, symbol: str, order_id: str) -> dict:
        """Cancel an Aster DEX order."""
        return self._http.post("/api/v1/tools/aster_cancel_order", {
            "symbol": symbol, "order_id": order_id
        })

    def aster_open_orders(self, symbol: str = None) -> dict:
        """Get Aster DEX open orders."""
        payload = {"symbol": symbol} if symbol else {}
        return self._http.post("/api/v1/tools/aster_open_orders", payload)

    def aster_set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage on Aster DEX."""
        return self._http.post("/api/v1/tools/aster_set_leverage", {
            "symbol": symbol, "leverage": leverage
        })

    def aster_diagnose(self) -> dict:
        """Run Aster DEX connection diagnostics."""
        return self._http.post("/api/v1/tools/aster_diagnose", {})

    # ── Polymarket ────────────────────────────────────────────

    def pm_markets(self) -> dict:
        """Get active Polymarket prediction markets."""
        return self._http.post("/api/v1/tools/pm_markets", {})

    def pm_search(self, query: str) -> dict:
        """Search Polymarket for a topic."""
        return self._http.post("/api/v1/tools/pm_search", {"query": query})

    def pm_price(self, token_id: str) -> dict:
        """Get Polymarket token price."""
        return self._http.post("/api/v1/tools/pm_price", {"token_id": token_id})

    def pm_positions(self) -> dict:
        """Get your Polymarket positions."""
        return self._http.post("/api/v1/tools/pm_positions", {})

    def pm_buy(self, token_id: str, amount: float, price: float) -> dict:
        """Buy on Polymarket. ⚠️ REAL MONEY."""
        return self._http.post("/api/v1/tools/pm_buy", {
            "token_id": token_id, "amount": amount, "price": price
        })

    def pm_sell(self, token_id: str, amount: float, price: float) -> dict:
        """Sell on Polymarket. ⚠️ REAL MONEY."""
        return self._http.post("/api/v1/tools/pm_sell", {
            "token_id": token_id, "amount": amount, "price": price
        })

    def pm_orderbook(self, token_id: str) -> dict:
        """Get Polymarket orderbook for a token."""
        return self._http.post("/api/v1/tools/pm_orderbook", {"token_id": token_id})
