"""
Sentinel REST API Server — Local FastAPI with 69 tools.

Ported from the hyper-sentinel Python engine. Provides the same
POST /api/v1/tools/{tool_name} interface with auto-generated Swagger docs.

Usage:
    sentinel serve                # Start on localhost:8000
    sentinel serve --port 9000    # Custom port

Docs at: http://localhost:8000/docs
"""

import json
import logging
import os
import time
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger("sentinel.api")


# ============================================================================
# Rate Limiter (in-memory, per API key)
# ============================================================================

class RateLimiter:
    """Simple sliding-window rate limiter."""

    def __init__(self, max_per_minute: int = 60):
        self.max_per_minute = max_per_minute
        self._calls: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60
        self._calls[key] = [t for t in self._calls[key] if t > window_start]
        if len(self._calls[key]) >= self.max_per_minute:
            return False
        self._calls[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        window_start = now - 60
        recent = [t for t in self._calls[key] if t > window_start]
        return max(0, self.max_per_minute - len(recent))


# ============================================================================
# Build Tool Registry
# ============================================================================

def _build_registry():
    """Build the tool registry with all 69 tools."""
    from sentinel.tool_registry import ToolRegistry

    registry = ToolRegistry()

    # ── CoinGecko (3) — free, no key ──────────────────────────
    try:
        from sentinel.scrapers.crypto import get_crypto_price, get_crypto_top_n, search_crypto
        registry.register(get_crypto_price, get_crypto_top_n, search_crypto)
    except ImportError:
        logger.warning("CoinGecko scrapers unavailable")

    # ── Yahoo Finance (6) — free, no key ──────────────────────
    try:
        from sentinel.scrapers.yahoo import (
            get_stock_price, get_stock_info, get_stock_news,
            get_stock_history, get_analyst_recs, run_stock_analysis,
        )
        registry.register(get_stock_price, get_stock_info, get_stock_news,
                         get_stock_history, get_analyst_recs, run_stock_analysis)
    except ImportError:
        logger.warning("Yahoo Finance scrapers unavailable (pip install yfinance)")

    # ── FRED Macro (4) — free key ─────────────────────────────
    try:
        from sentinel.scrapers.fred import get_fred_series, search_fred, get_economic_dashboard, get_yield_curve
        registry.register(get_fred_series, search_fred, get_economic_dashboard, get_yield_curve)
    except ImportError:
        logger.warning("FRED scrapers unavailable")

    # ── Y2 Intelligence (7) ───────────────────────────────────
    try:
        from sentinel.scrapers.y2 import (
            get_news_sentiment, get_news_recap, get_intelligence_reports,
            get_report_detail, get_y2_feeds, get_report_audio, list_y2_profiles,
        )
        registry.register(get_news_sentiment, get_news_recap, get_intelligence_reports,
                         get_report_detail, get_y2_feeds, get_report_audio, list_y2_profiles)
    except ImportError:
        logger.warning("Y2 scrapers unavailable")

    # ── Elfa AI (5) ───────────────────────────────────────────
    try:
        from sentinel.scrapers.elfa import (
            get_trending_tokens, get_top_mentions, search_mentions,
            get_trending_narratives, get_token_news,
        )
        registry.register(get_trending_tokens, get_top_mentions, search_mentions,
                         get_trending_narratives, get_token_news)
    except ImportError:
        logger.warning("Elfa scrapers unavailable")

    # ── X / Twitter (1) ───────────────────────────────────────
    try:
        from sentinel.scrapers.x import XScraper
        def search_x(query: str, max_results: int = 10) -> list:
            """Search recent tweets on X (Twitter) for a query."""
            _x_token = os.getenv("X_BEARER_TOKEN", "").strip()
            if not _x_token:
                return [{"error": "X_BEARER_TOKEN not configured. Run: add x"}]
            return XScraper(_x_token).search_tweets(query, max_results)
        registry.register(search_x)
    except ImportError:
        logger.warning("X/Twitter scraper unavailable")

    # ── Hyperliquid (12) ──────────────────────────────────────
    try:
        from sentinel.scrapers.hyperliquid import (
            get_hl_config, get_hl_account_info, get_hl_positions,
            get_hl_orderbook, get_hl_open_orders, get_hl_tradfi_assets,
            get_hl_tradfi_price, place_hl_order, cancel_hl_order,
            close_hl_position, set_hl_leverage, approve_hl_builder_fee,
        )
        registry.register(
            get_hl_config, get_hl_account_info, get_hl_positions,
            get_hl_orderbook, get_hl_open_orders, get_hl_tradfi_assets,
            get_hl_tradfi_price, place_hl_order, cancel_hl_order,
            close_hl_position, set_hl_leverage, approve_hl_builder_fee,
        )
    except ImportError:
        logger.warning("Hyperliquid scrapers unavailable")

    # ── Aster DEX (15) ────────────────────────────────────────
    try:
        from sentinel.scrapers.aster import (
            aster_ticker, aster_klines, aster_positions,
            aster_orderbook, aster_funding_rate, aster_exchange_info,
            aster_balance, aster_account_info, aster_open_orders,
            aster_place_order, aster_cancel_order, aster_cancel_all_orders,
            aster_set_leverage, aster_diagnose, aster_ping,
        )
        registry.register(
            aster_ticker, aster_klines, aster_positions,
            aster_orderbook, aster_funding_rate, aster_exchange_info,
            aster_balance, aster_account_info, aster_open_orders,
            aster_place_order, aster_cancel_order, aster_cancel_all_orders,
            aster_set_leverage, aster_diagnose, aster_ping,
        )
    except ImportError:
        logger.warning("Aster scrapers unavailable")

    # ── DexScreener (4) — free, no key ────────────────────────
    try:
        from sentinel.scrapers.dexscreener_v2 import (
            dexscreener_search, dexscreener_pair,
            dexscreener_token_lookup, dexscreener_trending,
        )
        registry.register(dexscreener_search, dexscreener_pair,
                         dexscreener_token_lookup, dexscreener_trending)
    except ImportError:
        logger.warning("DexScreener v2 scrapers unavailable")

    # ── TA / Quant Engine (9) ─────────────────────────────────
    try:
        from sentinel.scrapers.ta import get_ta_indicators, get_ta_signal, get_klines
        registry.register(get_ta_indicators, get_ta_signal, get_klines)
    except ImportError:
        logger.warning("TA engine unavailable")

    try:
        from sentinel.scrapers.risk import get_risk_metrics
        registry.register(get_risk_metrics)
    except ImportError:
        pass

    try:
        from sentinel.scrapers.ml_signals import get_ml_signals
        registry.register(get_ml_signals)
    except ImportError:
        pass

    try:
        from sentinel.scrapers.timeseries import get_timeseries_forecast
        registry.register(get_timeseries_forecast)
    except ImportError:
        pass

    try:
        from sentinel.scrapers.portfolio import get_portfolio_risk, get_portfolio_summary
        registry.register(get_portfolio_risk, get_portfolio_summary)
    except ImportError:
        pass

    try:
        from sentinel.scrapers.options import get_options_analysis, get_options_expirations, get_options_chain
        registry.register(get_options_analysis, get_options_expirations, get_options_chain)
    except ImportError:
        pass

    # ── Usage Tracking (1) ────────────────────────────────────
    try:
        from sentinel.scrapers.usage import get_usage_summary
        registry.register(get_usage_summary)
    except ImportError:
        pass

    # ── Polymarket — shelved ──────────────────────────────────
    # ── Telegram — shelved ────────────────────────────────────
    # ── Discord — shelved ─────────────────────────────────────
    # ── Strategy — shelved (in-house algos, not production) ───

    return registry


# ── Public tools — no API key required ────────────────────────
PUBLIC_TOOLS = {
    # CoinGecko (3)
    "get_crypto_price", "get_crypto_top_n", "search_crypto",
    # Yahoo Finance (6)
    "get_stock_price", "get_stock_info", "get_stock_news",
    "get_stock_history", "get_analyst_recs", "run_stock_analysis",
    # FRED (4)
    "get_fred_series", "search_fred", "get_economic_dashboard", "get_yield_curve",
    # Y2 Intelligence — read-only (5 of 7, reports + feeds)
    "get_news_sentiment", "get_news_recap", "get_intelligence_reports",
    "get_report_detail", "get_y2_feeds", "get_report_audio", "list_y2_profiles",
    # Elfa (5)
    "get_trending_tokens", "get_top_mentions", "search_mentions",
    "get_trending_narratives", "get_token_news",
    # X (1)
    "search_x",
    # DexScreener (4)
    "dexscreener_search", "dexscreener_pair",
    "dexscreener_token_lookup", "dexscreener_trending",
    # HL — read-only (5 of 12)
    "get_hl_positions", "get_hl_account_info", "get_hl_orderbook",
    "get_hl_tradfi_assets", "get_hl_tradfi_price",
    # Aster — read-only (8 of 15)
    "aster_ping", "aster_ticker", "aster_orderbook", "aster_klines",
    "aster_funding_rate", "aster_exchange_info", "aster_positions",
    "aster_balance",
    # TA/Quant (9)
    "get_ta_indicators", "get_ta_signal", "get_klines",
    "get_risk_metrics", "get_ml_signals", "get_timeseries_forecast",
    "get_portfolio_risk", "get_portfolio_summary",
    "get_options_analysis", "get_options_expirations", "get_options_chain",
    # Usage (1)
    "get_usage_summary",
}


# ============================================================================
# Create FastAPI App
# ============================================================================

def create_app():
    """Create the Sentinel REST API FastAPI app."""
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    registry = _build_registry()
    rate_limiter = RateLimiter(max_per_minute=int(os.getenv("API_RATE_LIMIT", "60")))
    _start_time = time.time()

    # API keys
    _raw_keys = os.getenv("API_KEYS", "").strip()
    valid_keys = set(k.strip() for k in _raw_keys.split(",") if k.strip()) if _raw_keys else set()

    app = FastAPI(
        title="🛡️ Sentinel API",
        description=(
            "REST API for Hyper-Sentinel — 60+ crypto trading, intelligence, and analysis tools.\n\n"
            "**Public tools** (no auth): crypto prices, social sentiment, news, macro data.\n\n"
            "**Auth-required tools** (X-API-Key header): DEX trading, account balances, order management."
        ),
        version="0.9.1",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def _global_handler(request: Request, exc: Exception):
        logger.error(f"API error: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": "Internal server error"})

    def _uptime() -> str:
        elapsed = int(time.time() - _start_time)
        h, r = divmod(elapsed, 3600)
        m, s = divmod(r, 60)
        return f"{h}h {m}m {s}s" if h else f"{m}m {s}s" if m else f"{s}s"

    # ── Routes ────────────────────────────────────────────────

    @app.get("/", tags=["Meta"])
    async def root():
        return {
            "name": "Sentinel API",
            "version": "0.9.1",
            "engine": "fastapi",
            "tools": registry.tool_count,
            "public_tools": len([t for t in registry.tool_names if t in PUBLIC_TOOLS]),
            "docs": "/docs",
        }

    @app.get("/health", tags=["Meta"])
    async def health():
        return {
            "status": "ok",
            "tools": registry.tool_count,
            "uptime": _uptime(),
        }

    @app.get("/api/v1/tools", tags=["Tools"])
    async def list_tools():
        tools = []
        for spec in registry.specs():
            tools.append({
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["parameters"],
                "auth_required": spec["name"] not in PUBLIC_TOOLS,
            })
        return {"count": len(tools), "tools": tools}

    @app.get("/api/v1/tools/{tool_name}", tags=["Tools"])
    async def tool_info(tool_name: str):
        for spec in registry.specs():
            if spec["name"] == tool_name:
                return {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": spec["parameters"],
                    "auth_required": spec["name"] not in PUBLIC_TOOLS,
                }
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    @app.post("/api/v1/tools/{tool_name}", tags=["Tools"])
    async def call_tool(tool_name: str, request: Request):
        if tool_name not in registry.tool_names:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        # Auth check
        api_key = request.headers.get("X-API-Key")
        if tool_name not in PUBLIC_TOOLS:
            if valid_keys and (not api_key or api_key not in valid_keys):
                raise HTTPException(status_code=401, detail="Unauthorized — X-API-Key required")

        # Rate limit
        key = api_key or (request.client.host if request.client else "anon")
        if not rate_limiter.check(key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        # Parse body
        try:
            body = await request.json()
        except Exception:
            body = {}

        # Execute
        result_str = registry.execute(tool_name, body)
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            result = {"raw": result_str}

        return {
            "tool": tool_name,
            "result": result,
            "meta": {"rate_limit_remaining": rate_limiter.remaining(key)},
        }

    return app


# ============================================================================
# Run Server
# ============================================================================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the Sentinel API server."""
    import uvicorn
    from rich.console import Console

    console = Console()
    console.print()
    console.print("  [bold cyan]🛡️  Sentinel API Server[/]")
    console.print(f"  [dim]http://{host}:{port}/docs — Swagger UI[/]")
    console.print(f"  [dim]http://{host}:{port}/health — Health check[/]")
    console.print()

    uvicorn.run(
        "sentinel.server:create_app",
        factory=True,
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )
