"""
Sentinel API — Market Data Resource.

    client.market.price("bitcoin")
    client.market.stock("AAPL")
    client.market.dashboard()
    client.market.news("bitcoin")
    client.market.top_crypto(10)
    client.market.trending_tokens()
"""

from typing import Any, Dict, List, Optional


class MarketResource:
    """Market data endpoints — crypto, stocks, macro, news, social."""

    def __init__(self, http):
        self._http = http

    # ── Crypto (CoinGecko) ────────────────────────────────────

    def price(self, coin_id: str = "bitcoin") -> dict:
        """Get crypto price, market cap, 24h change.

        Args:
            coin_id: CoinGecko coin ID (e.g. "bitcoin", "ethereum", "solana")
        """
        return self._http.post("/api/v1/tools/get_crypto_price", {"coin_id": coin_id})

    def top_crypto(self, n: int = 10) -> dict:
        """Get top N cryptocurrencies by market cap."""
        return self._http.post("/api/v1/tools/get_crypto_top_n", {"n": n})

    def search_crypto(self, query: str) -> dict:
        """Search for a cryptocurrency by name or ticker."""
        return self._http.post("/api/v1/tools/search_crypto", {"query": query})

    # ── Stocks (YFinance) ─────────────────────────────────────

    def stock(self, symbol: str) -> dict:
        """Get stock price and fundamentals.

        Args:
            symbol: Ticker symbol (e.g. "AAPL", "TSLA", "NVDA")
        """
        return self._http.post("/api/v1/tools/stock_price", {"symbol": symbol})

    # ── EODHD Historical Data ─────────────────────────────────

    def history(self, symbol: str, period: str = "d", limit: int = 30) -> dict:
        """Get historical OHLCV data from EODHD.

        Args:
            symbol: EODHD symbol (e.g. "AAPL.US", "BTC-USD.CC")
            period: 'd' (daily), 'w' (weekly), 'm' (monthly)
            limit: Number of data points
        """
        return self._http.post("/api/v1/tools/get_eodhd_data", {
            "symbol": symbol, "period": period, "limit": limit
        })

    # ── Macro (FRED) ──────────────────────────────────────────

    def dashboard(self) -> dict:
        """Get macro economic dashboard — GDP, CPI, rates, VIX, unemployment."""
        return self._http.post("/api/v1/tools/macro_dashboard", {})

    def fred_series(self, series_id: str) -> dict:
        """Get a specific FRED data series.

        Args:
            series_id: FRED series ID (e.g. "GDP", "CPIAUCSL", "UNRATE")
        """
        return self._http.post("/api/v1/tools/get_fred_series", {"series_id": series_id})

    # ── News (Y2) ─────────────────────────────────────────────

    def news(self, topic: str = "crypto") -> dict:
        """Get news sentiment analysis for a topic."""
        return self._http.post("/api/v1/tools/get_news_sentiment", {"topic": topic})

    def news_recap(self, topic: str = "crypto") -> dict:
        """Get a news recap/summary for a topic."""
        return self._http.post("/api/v1/tools/get_news_recap", {"topic": topic})

    # ── Social (Elfa AI) ──────────────────────────────────────

    def trending_tokens(self) -> dict:
        """Get trending tokens from social media analysis."""
        return self._http.post("/api/v1/tools/get_trending_tokens", {})

    def social_mentions(self, query: str) -> dict:
        """Search social media mentions for a keyword."""
        return self._http.post("/api/v1/tools/search_mentions", {"query": query})

    # ── DexScreener ───────────────────────────────────────────

    def dex_search(self, query: str) -> dict:
        """Search for token pairs on DexScreener."""
        return self._http.post("/api/v1/tools/dex_search_pairs", {"query": query})

    def dex_profile(self, chain: str, address: str) -> dict:
        """Get token profile from DexScreener."""
        return self._http.post("/api/v1/tools/dex_token_profile", {
            "chain_id": chain, "token_address": address
        })

    # ── Technical Analysis ────────────────────────────────────

    def technical_analysis(self, symbol: str) -> dict:
        """Run technical analysis on a symbol (RSI, MACD, Bollinger, EMAs)."""
        return self._http.post("/api/v1/tools/run_ta", {"symbol": symbol})
