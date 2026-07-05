"""
Sentinel Chat — Interactive AI Agent with Tool-Use Loop.

The brain that turns the SDK from a REST client into an AI agent.
Sends user questions to an LLM with tool schemas; when the LLM requests
tool calls, executes them on the Go gateway and feeds results back.

Supports: Anthropic (Claude), OpenAI (GPT), xAI (Grok), Google (Gemini),
         DeepSeek, Zhipu AI (GLM), Minimax, Moonshot (Kimi).

Usage:
    sentinel chat          # interactive REPL
    sentinel-chat          # standalone entry point
    sentinel ask "..."     # one-shot question
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

# ── Theme (same retro 80s cyan palette as cli.py) ────────────
SENTINEL_THEME = Theme({
    "s.cyan": "#00e5ff",
    "s.cyan.bold": "bold #00e5ff",
    "s.green": "#4cff99",
    "s.gold": "bold #ffaa00",
    "s.magenta": "bold #ff44ff",
    "s.dim": "dim #b0d4db",
    "s.border": "#007a8a",
    "s.error": "bold #ff4444",
    "s.yellow": "bold #ffaa00",
})

console = Console(theme=SENTINEL_THEME)

GATEWAY_URL = "https://api.hyper-sentinel.com"

SENTINEL_DIR = Path.home() / ".sentinel"
CONFIG_FILE = SENTINEL_DIR / "config"


# ══════════════════════════════════════════════════════════════
# Banner
# ══════════════════════════════════════════════════════════════

def _make_banner() -> str:
    """Build the startup banner with live version + tool count."""
    from sentinel import __version__
    n_tools = len(TOOL_SCHEMAS)
    return f"""
[bold cyan]██╗  ██╗██╗   ██╗██████╗ ███████╗██████╗[/]
[bold cyan]██║  ██║╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗[/]
[bold cyan]███████║ ╚████╔╝ ██████╔╝█████╗  ██████╔╝[/]
[bold cyan]██╔══██║  ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗[/]
[bold cyan]██║  ██║   ██║   ██║     ███████╗██║  ██║[/]
[bold cyan]╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝[/]

[bold white]S E N T I N E L[/]
[dim]Quantitative AI Agent · {n_tools} Tools · Local-First · v{__version__}[/]
"""


# ══════════════════════════════════════════════════════════════
# Config Helpers
# ══════════════════════════════════════════════════════════════

# Unambiguous key prefixes — checked first, no probing needed.
KEY_PREFIXES = {
    "sk-ant-":  ("anthropic", "CLAUDE",  "Anthropic (Claude)",  "🟣"),
    "sk-proj-": ("openai",    "OPENAI",  "OpenAI (GPT)",        "🟢"),
    "AIza":     ("google",    "GEMINI",  "Google (Gemini)",     "🔵"),
    "xai-":     ("xai",       "GROK",    "xAI (Grok)",          "⚫"),
}

# GLM keys have a unique format: 32-char hex DOT 16-char alnum.
_GLM_KEY_RE = re.compile(r'^[a-f0-9]{32}\.[A-Za-z0-9]{16}$')

# Labels for providers whose keys share the sk- prefix (ambiguous).
_SK_PROVIDER_LABELS = {
    "openai":   ("openai",   "OPENAI",   "OpenAI (GPT)",       "🟢"),
    "deepseek": ("deepseek", "DEEPSEEK", "DeepSeek",           "🟠"),
    "minimax":  ("minimax",  "MINIMAX",  "Minimax",            "🟡"),
    "moonshot": ("moonshot", "MOONSHOT", "Moonshot (Kimi)",    "🟤"),
}


def _probe_sk_provider(key: str) -> str:
    """Resolve ambiguous sk- keys by probing each provider's /models endpoint.

    Fires a lightweight GET against each candidate; the first non-401 wins.
    Result is cached in config so the probe only runs once per key.
    """
    config = _load_config()
    cached = config.get("provider_override")
    if cached:
        return cached

    candidates = [
        ("openai",   "https://api.openai.com/v1/models"),
        ("deepseek", "https://api.deepseek.com/models"),
        ("minimax",  "https://api.minimax.io/v1/models"),
        ("moonshot", "https://api.moonshot.ai/v1/models"),
    ]
    for provider_id, url in candidates:
        try:
            resp = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=3)
            if resp.status_code != 401:
                config["provider_override"] = provider_id
                _save_config(config)
                return provider_id
        except Exception:
            continue
    return "openai"  # safe fallback


def _detect_provider(key: str):
    """Detect LLM provider from API key prefix.

    Detection order:
    1. GLM unique pattern ([hex32].[alnum16]) — no collision possible.
    2. Unambiguous prefixes (sk-ant-, sk-proj-, AIza, xai-).
    3. Generic sk- → silent endpoint probe (cached after first run).
    """
    # 1. GLM unique key format
    if _GLM_KEY_RE.match(key):
        return ("zhipu", "GLM", "Zhipu AI (GLM)", "🔴")

    # 2. Unambiguous prefixes
    for prefix, info in KEY_PREFIXES.items():
        if key.startswith(prefix):
            return info

    # 3. Ambiguous sk- → probe
    if key.startswith("sk-"):
        provider_id = _probe_sk_provider(key)
        return _SK_PROVIDER_LABELS.get(provider_id, _SK_PROVIDER_LABELS["openai"])

    return None


def _load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_config(config: dict):
    SENTINEL_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass


def _register_with_gateway(ai_key: str) -> dict:
    """Lazy-register with gateway using AI key.

    v0.9.2: also persists the returned sentinel key to ~/.sentinel/api_key so
    _gateway_llm_request() (which calls load_api_key()) sends X-API-Key on every
    /api/v1/llm/chat call.  Without this, BYO-key users went out as anonymous and
    were never counted by the FreeQuotaGate.
    """
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/auth/ai-key",
            json={"ai_key": ai_key},
            timeout=30.0,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            sentinel_key = data.get("api_key", "")
            if sentinel_key:
                try:
                    from sentinel.api._http import save_api_key
                    save_api_key(sentinel_key)
                except Exception:
                    pass
            return data
    except Exception:
        pass
    return {}


# ══════════════════════════════════════════════════════════════
# System Prompt
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are Sentinel, a production-grade AI trading agent built by the Hyper-Sentinel project.
Version: 0.9.4 | Build: June 2026 | Platform: hyper-sentinel SDK (PyPI)

CAPABILITIES:
- Real-time crypto prices (CoinGecko — 10,000+ coins)
- Stock data (YFinance — prices, analyst recs, financials, news)
- Quantitative engine (TA indicators, risk metrics, ML signals, time series forecasts, options analysis)
- Economic data (FRED — GDP, CPI, unemployment, interest rates)
- DEX data (DexScreener — pairs, trending tokens, on-chain analytics)
- Social intelligence (X/Twitter search, Elfa AI trending, Y2 news)
- DEX trading (Hyperliquid perps, Aster futures)
- On-chain swaps (Jupiter SOL, Uniswap ETH)
- Wallet management (generate, import, balance, send)

RULES:
- Always use tools to get REAL data. Never fabricate prices, dates, statistics, or metadata.
- Do NOT invent version numbers, dates, uptime percentages, or system status details — use only what you know from this prompt.
- Be concise and data-driven. Lead with numbers.
- When asked about multiple things, call multiple tools and synthesize ONE unified response.
- Format numbers clearly: $87,421.32 not 87421.32, 2.3% not 0.023.
- If a tool fails, say so honestly and suggest alternatives.
- For trading operations (placing orders, closing positions), confirm the action clearly.
- Keep responses focused — no unnecessary preamble. Don't dump system status unless asked.

ANALYSIS FORMATTING:
When performing stock/crypto analysis or "quant analysis", produce a COMPREHENSIVE report with these sections:
1. 📊 CURRENT PRICE & MARKET DATA — price, change, day range, market cap
2. 📈 VALUATION METRICS — P/E (trailing & forward), P/B, P/S, PEG, EV/EBITDA. Flag extremes with ⚠️
3. 💰 FINANCIAL HEALTH — margins (profit, gross, operating, EBITDA), ROE, ROA, growth rates, balance sheet (cash, debt, ratios), cash flow
4. 📊 TECHNICAL ANALYSIS — 50-day & 200-day MA, price vs MA %, trend direction, volume vs average
5. 🎯 ANALYST SENTIMENT — recommendation breakdown, price targets (high/mean/median/low), implied upside
6. ⚠️ RISK FACTORS — beta, overall risk score, short interest, governance risk
7. 📉 FUNDAMENTAL CONCERNS — bullet list of negatives
8. ✅ POSITIVE FACTORS — bullet list of positives
9. 🎯 QUANTITATIVE SUMMARY — score out of 10 with breakdown (valuation, financial health, growth, technical, momentum, risk-adjusted)
10. 💡 TRADING PERSPECTIVE — key support/resistance levels, momentum signals
11. 🎪 FINAL VERDICT — BULLISH/NEUTRAL/BEARISH with reasoning and entry point recommendations

Use section dividers (────) between each section. Use emoji indicators: 🔴 bad, 🟡 mixed, 🟢 good, ⚠️ warning.
For quant analysis, use MULTIPLE tools together for a comprehensive report:
- run_stock_analysis — valuation, fundamentals, balance sheet, analyst targets (YFinance)
- get_ta_indicators — RSI, MACD, Bollinger Bands, SMA/EMA crossovers (internal TA engine)
- get_risk_metrics — Sharpe ratio, Sortino, VaR, CVaR, max drawdown (internal risk engine)
- get_ml_signals — regression trend, K-Means regime detection, RF feature importance, logistic prediction (internal ML engine)
- get_options_analysis — put/call ratio, implied volatility, ATM options, sentiment (nearest expiry quick-look)
- get_options_expirations — list all expiry dates including LEAPS for any stock/ETF (call FIRST before get_options_chain)
- get_options_chain — full options chain for ANY expiry with Greeks (delta/gamma/theta/vega/rho). For LEAPS: call get_options_expirations first, then get_options_chain with the expiry date and near_money=5.
- get_timeseries_forecast — ARIMA forecast, GARCH volatility, stationarity test (internal timeseries engine)
Call them in parallel. For stocks, set venue="tradfi". For crypto, use venue="hl".
For options queries: call get_options_expirations to discover valid dates, then get_options_chain with the exact date. Always use near_money=5 or near_money=10 to avoid dumping too many contracts.
"""

# ══════════════════════════════════════════════════════════════
# Default Models per Provider
# ══════════════════════════════════════════════════════════════

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",   # current; Opus 4.8 / Fable 5 available via fallbacks
    "openai": "gpt-5.5",
    "xai": "grok-4.3",
    "google": "gemini-3.5-flash",
    # ── Chinese / open-source providers ──
    "deepseek": "deepseek-v4-pro",
    "zhipu":    "glm-5.2",
    "minimax":  "minimax-m3",
    "moonshot": "kimi-k2.7-code",
}

PROVIDER_ENDPOINTS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/chat/completions",
    "xai": "https://api.x.ai/v1/chat/completions",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    # ── Chinese / open-source providers ──
    "deepseek": "https://api.deepseek.com/chat/completions",
    "zhipu":    "https://api.z.ai/api/paas/v4/chat/completions",
    "minimax":  "https://api.minimax.io/v1/chat/completions",
    "moonshot": "https://api.moonshot.ai/v1/chat/completions",
}

# ── Model Catalog ─────────────────────────────────────────────
# Single source of truth: drives the `model` picker (per provider, in display
# order) and the fallback chains (derived below). label + desc show in the picker.
MODEL_CATALOG = {
    "anthropic": [
        {"id": "claude-sonnet-4-6", "label": "Sonnet 4.6", "desc": "balanced · $3/$15"},
        {"id": "claude-opus-4-8",   "label": "Opus 4.8",   "desc": "most capable · $5/$25"},
        {"id": "claude-fable-5",    "label": "Fable 5",    "desc": "most powerful · $10/$50"},
        {"id": "claude-haiku-4-5",  "label": "Haiku 4.5",  "desc": "fastest · $1/$5"},
    ],
    "openai": [
        {"id": "gpt-5.5",      "label": "GPT-5.5",      "desc": "flagship"},
        {"id": "gpt-5.4",      "label": "GPT-5.4",      "desc": "previous flagship"},
        {"id": "gpt-5.4-mini", "label": "GPT-5.4 mini", "desc": "fast / cheap"},
    ],
    "google": [
        {"id": "gemini-3.5-flash",      "label": "Gemini 3.5 Flash",      "desc": "most intelligent, efficient"},
        {"id": "gemini-3.1-pro",        "label": "Gemini 3.1 Pro",        "desc": "flagship reasoning"},
        {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite", "desc": "budget, high-volume"},
    ],
    "xai": [
        {"id": "grok-4.3",      "label": "Grok 4.3",      "desc": "flagship · $1.25/$2.50"},
        {"id": "grok-4.1-fast", "label": "Grok 4.1 Fast", "desc": "fast / cheap"},
    ],
    # ── Chinese / open-source providers ──
    "deepseek": [
        {"id": "deepseek-v4-pro",   "label": "DeepSeek V4 Pro",   "desc": "1.6T · strongest open-source"},
        {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash", "desc": "284B · fast / cheap"},
    ],
    "zhipu": [
        {"id": "glm-5.2", "label": "GLM 5.2", "desc": "1M context · Zhipu AI"},
    ],
    "minimax": [
        {"id": "minimax-m3", "label": "Minimax M3", "desc": "agentic · reasoning"},
    ],
    "moonshot": [
        {"id": "kimi-k2.7-code", "label": "Kimi K2.7", "desc": "code + agentic · Moonshot AI"},
    ],
}

# Fallback chains, derived from the catalog so the two never drift. The caller tries
# the chosen model first, then these in order — always lands on a valid model.
MODEL_FALLBACKS = {p: [m["id"] for m in models] for p, models in MODEL_CATALOG.items()}


def _resolve_model(config: dict, provider: str) -> str:
    """Model to use: a saved per-user override (`config["model"]`) if it's valid for
    this provider, otherwise the provider's default."""
    saved = config.get("model")
    if saved and any(m["id"] == saved for m in MODEL_CATALOG.get(provider, [])):
        return saved
    return DEFAULT_MODELS.get(provider, "claude-sonnet-4-6")


# Maximum wall-clock seconds the agent tool-use loop may run per prompt.
# Raised from 60s (v0.8.8) to match the gateway's 150s proxy timeout.
RESPONSE_TIME_LIMIT_S = 150

# ══════════════════════════════════════════════════════════════
# Tool Schema Definitions (curated from SentinelClient methods)
# ══════════════════════════════════════════════════════════════

TOOL_SCHEMAS = [
    # ── Crypto ────────────────────────────────────────────────
    {
        "name": "get_crypto_price",
        "description": "Get current price, market cap, 24h change for a cryptocurrency. Use CoinGecko IDs (bitcoin, ethereum, solana, etc).",
        "parameters": {
            "type": "object",
            "properties": {"coin_id": {"type": "string", "description": "CoinGecko coin ID (e.g. bitcoin, ethereum, solana, dogecoin)"}},
            "required": ["coin_id"],
        },
    },
    {
        "name": "get_crypto_top_n",
        "description": "Get top N cryptocurrencies by market cap with prices and 24h changes.",
        "parameters": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "Number of top coins (default 10)", "default": 10}},
            "required": [],
        },
    },
    {
        "name": "search_crypto",
        "description": "Search for a cryptocurrency by name or symbol.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query (e.g. 'chainlink', 'LINK')"}},
            "required": ["query"],
        },
    },

    # ── Stocks (YFinance) ─────────────────────────────────────
    {
        "name": "get_stock_price",
        "description": "Get current stock price, volume, day range for a ticker symbol.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Stock ticker (e.g. AAPL, TSLA, NVDA, SPY)"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "get_stock_info",
        "description": "Get detailed company info — market cap, P/E ratio, sector, description, financials.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Stock ticker symbol"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "get_analyst_recs",
        "description": "Get analyst recommendations (buy/hold/sell) and price targets for a stock.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Stock ticker symbol"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "get_stock_news",
        "description": "Get latest news articles for a stock ticker.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Stock ticker symbol"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "get_stock_history",
        "description": "Get historical price data for a stock. Useful for calculating Sharpe ratio, returns, volatility.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol"},
                "period": {"type": "string", "description": "Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max", "default": "1mo"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "run_stock_analysis",
        "description": "Run comprehensive quantitative analysis on a stock — valuation, financials, technicals (50/200 MA), risk metrics, analyst targets, short interest, balance sheet, and growth. Use this for deep analysis requests.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol (e.g. TSLA, AAPL, NVDA)"},
            },
            "required": ["symbol"],
        },
    },

    # ── Economic Data (FRED) ──────────────────────────────────
    {
        "name": "get_fred_series",
        "description": "Get FRED economic data series. Common IDs: GDP, CPIAUCSL (CPI), UNRATE (unemployment), FEDFUNDS (fed rate), DGS10 (10yr yield).",
        "parameters": {
            "type": "object",
            "properties": {
                "series_id": {"type": "string", "description": "FRED series ID (e.g. GDP, CPIAUCSL, UNRATE, FEDFUNDS)"},
                "period": {"type": "string", "description": "Lookback period — 3m, 6m, 1y, 2y, 5y, 10y. Default: 1y"},
                "limit": {"type": "integer", "description": "Number of recent observations to return", "default": 10},
            },
            "required": ["series_id"],
        },
    },
    {
        "name": "search_fred",
        "description": "Search FRED for economic data series by keyword.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search term (e.g. 'inflation', 'housing starts')"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_economic_dashboard",
        "description": "Get a snapshot of key economic indicators: GDP, CPI, unemployment, fed funds rate, 10yr yield. Includes YoY% change for CPI, GDP, M2, and payrolls.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_yield_curve",
        "description": "Get the full US Treasury yield curve — 3M through 30Y yields, key spreads (10Y-2Y, 10Y-3M, 30Y-2Y), and inversion status (normal/inverted/flat). One-call macro snapshot.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # ── News & Sentiment ──────────────────────────────────────
    {
        "name": "get_news_sentiment",
        "description": "Get news sentiment analysis for a topic or asset using Y2 Intelligence. Requires Y2_API_KEY.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Topic or comma-separated topics to analyze (e.g. 'bitcoin', 'bitcoin,ethereum', 'AI stocks', 'macro')"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_news_recap",
        "description": "Get an AI-generated recap of today's top market news.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # ── DexScreener (free, no key) ─────────────────────────────
    {
        "name": "dexscreener_search",
        "description": "Search for DEX trading pairs by token name, symbol, or contract address across all chains and DEXes. Returns price, volume, liquidity, market cap. No API key needed. Example queries: 'PEPE', 'SOL/USDC', or a contract address.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Token name, symbol, pair name, or contract address to search"}},
            "required": ["query"],
        },
    },
    {
        "name": "dexscreener_token_lookup",
        "description": "Look up all DEX pairs for a specific token by its contract address. Optionally filter by chain. Returns price, liquidity, volume, market cap for each pair. No API key needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "token_address": {"type": "string", "description": "Token contract address (e.g. 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v' for USDC on Solana)"},
                "chain": {"type": "string", "description": "Optional chain filter: solana, ethereum, bsc, base, arbitrum, polygon, avalanche", "default": ""},
            },
            "required": ["token_address"],
        },
    },
    {
        "name": "dexscreener_trending",
        "description": "Get the hottest trending/boosted tokens across all DEXes right now. Shows memecoins, new launches, and promoted tokens with active boosts. No API key needed.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "dexscreener_pair",
        "description": "Get detailed pair info (price, liquidity, volume, market cap, 24h change) by chain and pair address. No API key needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "description": "Blockchain: solana, ethereum, bsc, base, arbitrum, polygon, avalanche"},
                "pair_address": {"type": "string", "description": "The DEX pair contract address"},
            },
            "required": ["chain", "pair_address"],
        },
    },

    {
        "name": "get_intelligence_reports",
        "description": "List AI-generated intelligence reports from Y2. Reports are deep-dive briefs on monitored topics. Returns report IDs for use with get_report_detail.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of reports to return (1-20, default 10)", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "get_report_detail",
        "description": "Get the full content of a specific Y2 intelligence report — AI-written brief, source citations, metadata.",
        "parameters": {
            "type": "object",
            "properties": {
                "report_id": {"type": "string", "description": "Report ID from get_intelligence_reports"},
            },
            "required": ["report_id"],
        },
    },
    {
        "name": "get_y2_feeds",
        "description": "List all available Y2 news feed topics with descriptions. Shows the 19 topics Y2 can monitor.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_report_audio",
        "description": "Get audio narration URL for a Y2 intelligence report.",
        "parameters": {
            "type": "object",
            "properties": {
                "report_id": {"type": "string", "description": "Report ID"},
            },
            "required": ["report_id"],
        },
    },
    {
        "name": "list_y2_profiles",
        "description": "List your Y2 monitoring profiles — what topics you are tracking and delivery schedule. Read-only.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # ── Social (X/Twitter) ────────────────────────────────────
    {
        "name": "search_x",
        "description": "Search X (Twitter) for tweets matching a query. Returns recent tweets with text, author, engagement.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'from:MarioNawfal', 'bitcoin', '#crypto')"},
                "max_results": {"type": "integer", "description": "Max tweets to return (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },

    # ── Elfa AI (Social Intelligence) ─────────────────────────
    {
        "name": "get_trending_tokens",
        "description": "Get trending tokens from Elfa AI social intelligence — tokens with rising social mentions.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_mentions",
        "description": "Search social media mentions for a token or topic across platforms.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Token or topic to search mentions for"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_trending_narratives",
        "description": "Get trending narratives and topics in crypto from social intelligence.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    {
        "name": "get_top_mentions",
        "description": "Get top social media mentions for a token/ticker from Elfa AI.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Token ticker (e.g. BTC, ETH, SOL)"},
                "time_window": {"type": "string", "description": "Time window: 1h, 6h, 24h, 7d", "default": "24h"},
                "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_token_news",
        "description": "Get news mentions for a specific token from social media via Elfa AI.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Token ticker (e.g. BTC, ETH)"},
                "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
            "required": ["ticker"],
        },
    },

    # ── Hyperliquid (crypto + TradFi perps) ─────────────────────
    {
        "name": "get_hl_positions",
        "description": "Get current open positions on Hyperliquid DEX (crypto and TradFi).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_hl_orderbook",
        "description": "Get the order book for a Hyperliquid trading pair — supports crypto (BTC, ETH) and TradFi (GOLD, SILVER, OIL, TSLA, SP500).",
        "parameters": {
            "type": "object",
            "properties": {"coin": {"type": "string", "description": "Trading pair — crypto (ETH, BTC, SOL) or TradFi (GOLD, SILVER, OIL, TSLA, SP500, NVDA)"}},
            "required": ["coin"],
        },
    },
    {
        "name": "get_hl_account_info",
        "description": "Get Hyperliquid account info — balances, margin, equity.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "place_hl_order",
        "description": "Place a trade on Hyperliquid — supports crypto (BTC, ETH, SOL) AND TradFi (GOLD, SILVER, OIL, TSLA, SP500, NVDA). Market and limit orders.",
        "parameters": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "Trading pair — crypto (ETH, BTC) or TradFi (GOLD, SILVER, OIL, TSLA, SP500, NVDA)"},
                "side": {"type": "string", "description": "'buy' (long) or 'sell' (short)"},
                "size": {"type": "number", "description": "Order size in contracts"},
                "price": {"type": "number", "description": "Limit price (0 for market order)", "default": 0},
                "order_type": {"type": "string", "description": "'market' or 'limit'", "default": "market"},
            },
            "required": ["coin", "side", "size"],
        },
    },
    {
        "name": "close_hl_position",
        "description": "Close an open Hyperliquid position — supports crypto and TradFi.",
        "parameters": {
            "type": "object",
            "properties": {"coin": {"type": "string", "description": "Position to close — crypto (ETH, BTC) or TradFi (GOLD, TSLA, SP500)"}},
            "required": ["coin"],
        },
    },
    {
        "name": "get_hl_tradfi_assets",
        "description": "List all available TradFi / commodity / stock perps on Hyperliquid — GOLD, SILVER, OIL, TSLA, NVDA, SP500, and 50+ more with live prices and max leverage.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_hl_tradfi_price",
        "description": "Get current price, spread, and funding for a TradFi asset on Hyperliquid — GOLD, SILVER, OIL, TSLA, SP500, NVDA, etc.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Asset symbol — GOLD, SILVER, OIL, TSLA, SP500, NVDA, AAPL, etc."}},
            "required": ["symbol"],
        },
    },

    {
        "name": "get_hl_config",
        "description": "Show current Hyperliquid configuration status — wallet, network, connected.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_hl_open_orders",
        "description": "Get all open/pending orders on Hyperliquid.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "cancel_hl_order",
        "description": "Cancel an open order on Hyperliquid.",
        "parameters": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "Trading pair (e.g. ETH, BTC)"},
                "oid": {"type": "integer", "description": "Order ID to cancel"},
            },
            "required": ["coin", "oid"],
        },
    },
    {
        "name": "set_hl_leverage",
        "description": "Set leverage for a coin on Hyperliquid.",
        "parameters": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "Trading pair"},
                "leverage": {"type": "integer", "description": "Leverage multiplier"},
                "is_cross": {"type": "boolean", "description": "True for cross margin, False for isolated", "default": True},
            },
            "required": ["coin", "leverage"],
        },
    },
    {
        "name": "approve_hl_builder_fee",
        "description": "Approve the builder fee for Hyperliquid trading (one-time per account).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # ── Technical Analysis ────────────────────────────────────
    {
        "name": "get_ta_indicators",
        "description": "Get full TA indicators for any asset — SMA(9/21), EMA(12/26), RSI(14), MACD, Bollinger Bands. Works for crypto (BTC, ETH), TradFi (GOLD, TSLA), or Aster DEX (BTCUSDT). Supports intervals: 1m, 5m, 15m, 1h, 4h, 1d.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Asset symbol — BTC, ETH, GOLD, TSLA, BTCUSDT"},
                "interval": {"type": "string", "description": "Candle interval — 1m, 5m, 15m, 1h, 4h, 1d. Default: 5m"},
                "venue": {"type": "string", "description": "Data source — hl (Hyperliquid), aster (Aster DEX), tradfi (TradFi). Default: hl"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_ta_signal",
        "description": "Get SMA crossover signal + RSI for any asset. Returns bullish/bearish/neutral + overbought/oversold. Quick signal check for trading decisions.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Asset symbol — BTC, ETH, GOLD, TSLA"},
                "interval": {"type": "string", "description": "Candle interval — 5m, 15m, 1h, 4h, 1d. Default: 5m"},
                "venue": {"type": "string", "description": "Data source — hl, aster, tradfi. Default: hl"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_klines",
        "description": "Get raw OHLCV candlestick data for any asset. Returns open, high, low, close, volume for each candle period.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Asset symbol — BTC, ETH, GOLD, TSLA, BTCUSDT"},
                "interval": {"type": "string", "description": "Candle interval — 1m, 5m, 15m, 1h, 4h, 1d. Default: 5m"},
                "limit": {"type": "integer", "description": "Number of candles. Default: 50"},
                "venue": {"type": "string", "description": "Data source — hl, aster, tradfi. Default: hl"}
            },
            "required": ["symbol"],
        },
    },

    # ── Quantitative Analysis ────────────────────────────────
    {
        "name": "get_risk_metrics",
        "description": "Get risk metrics for any asset — Sharpe ratio, Sortino ratio, Calmar ratio, VaR (Value at Risk, 3 methods), CVaR, max drawdown. Tells you if the return is worth the risk. Use for any risk assessment question.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Asset symbol — BTC, ETH, GOLD, TSLA, AAPL"},
                "interval": {"type": "string", "description": "Candle interval — 1d recommended. Default: 1d"},
                "venue": {"type": "string", "description": "Data source — hl, aster, tradfi. Default: hl"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_timeseries_forecast",
        "description": "Get time series forecast — ARIMA price prediction, GARCH volatility forecast, stationarity test. Tells you if price is trending or mean-reverting, and forecasts next 5 periods.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Asset symbol — BTC, ETH, GOLD, TSLA, AAPL"},
                "interval": {"type": "string", "description": "Candle interval — 1d recommended. Default: 1d"},
                "venue": {"type": "string", "description": "Data source — hl, aster, tradfi. Default: hl"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_ml_signals",
        "description": "Get ML-based trading signals — linear regression trend, K-Means regime detection (trending up/sideways/down), Random Forest feature importance, logistic regression up/down prediction with confidence score.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Asset symbol — BTC, ETH, GOLD, TSLA, AAPL"},
                "interval": {"type": "string", "description": "Candle interval — 1d recommended. Default: 1d"},
                "venue": {"type": "string", "description": "Data source — hl, aster, tradfi. Default: hl"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_options_analysis",
        "description": "Get options analysis for a stock or ETF — put/call ratio, implied volatility, ATM options, most active contracts, and sentiment (bullish/bearish/neutral). Only works for stocks and ETFs, not crypto. Uses nearest expiry only — for specific dates or LEAPS, use get_options_chain instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock/ETF ticker — AAPL, TSLA, SPY, QQQ, MSFT"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_options_expirations",
        "description": "List all available options expiration dates for a stock/ETF, including LEAPS (>1yr out). Use this FIRST to discover valid expiry dates before calling get_options_chain. Returns dates only, no chain data.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock/ETF ticker — AAPL, TSLA, SPY, LULU, GLD, TLT"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_options_chain",
        "description": "Get the full options chain for a specific expiry — calls/puts with strike, bid/ask, volume, OI, IV, and computed Greeks (delta, gamma, theta, vega, rho). Supports LEAPS. Use get_options_expirations first to find valid dates.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock/ETF ticker — AAPL, TSLA, SPY, LULU, GLD"},
                "expiry": {"type": "string", "description": "Expiration date YYYY-MM-DD from get_options_expirations. Omit for nearest."},
                "option_type": {"type": "string", "description": "Filter: 'calls', 'puts', or 'both' (default: both)"},
                "min_strike": {"type": "number", "description": "Minimum strike price filter"},
                "max_strike": {"type": "number", "description": "Maximum strike price filter"},
                "near_money": {"type": "integer", "description": "Show N strikes above + below ATM (e.g. 5 = ~10 contracts). Recommended to keep output focused."},
            },
            "required": ["symbol"],
        },
    },

    # ── Portfolio ─────────────────────────────────────────────

    {
        "name": "get_portfolio_summary",
        "description": "Get a unified portfolio summary across all connected trading venues (Hyperliquid, Aster). Shows total equity, per-venue breakdowns, all open positions, and unrealized PnL.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_portfolio_risk",
        "description": "Analyze portfolio risk: position concentration, effective leverage, venue allocation, and risk level (LOW/MEDIUM/HIGH). Requires at least one connected venue.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # ── Usage / Revenue ──────────────────────────────────────
    {
        "name": "get_usage_summary",
        "description": "Get LLM usage summary with token counts, costs, and profit. Period can be 'today', 'week', 'month', or 'all'.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Time period: today, week, month, or all. Default: today"}
            },
            "required": [],
        },
    },

    # ── Polymarket (HIDDEN — not production-tested yet) ──────
    # Uncomment to re-enable. Scraper code lives in scrapers/polymarket.py
    # {
    #     "name": "search_polymarket",
    #     ...
    # },
    # ... (7 tools hidden: search_polymarket, get_polymarket_markets,
    #      get_polymarket_positions, buy_polymarket, sell_polymarket,
    #      get_polymarket_price, get_polymarket_orderbook)

    # ── Aster DEX ─────────────────────────────────────────────
    {
        "name": "aster_ticker",
        "description": "Get current price/ticker info from Aster DEX for a futures pair.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Trading pair (e.g. BTCUSDT, ETHUSDT)"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "aster_positions",
        "description": "Get current open positions on Aster DEX.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "aster_klines",
        "description": "Get candlestick/kline data from Aster DEX.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g. ETHUSDT)"},
                "interval": {"type": "string", "description": "Candle interval: 1m, 5m, 15m, 1h, 4h, 1d", "default": "1h"},
                "limit": {"type": "integer", "description": "Number of candles", "default": 100},
            },
            "required": ["symbol"],
        },
    },

    {
        "name": "aster_orderbook",
        "description": "Get live orderbook (bids/asks) from Aster DEX.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g. BTCUSDT)"},
                "limit": {"type": "integer", "description": "Depth levels (default 10)", "default": 10},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "aster_funding_rate",
        "description": "Get current funding rate and mark price from Aster DEX.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (optional — all pairs if omitted)"},
            },
            "required": [],
        },
    },
    {
        "name": "aster_exchange_info",
        "description": "Get exchange info from Aster DEX — trading pairs, contract specs, tick sizes.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Specific pair (optional — all pairs if omitted)"},
            },
            "required": [],
        },
    },
    {
        "name": "aster_balance",
        "description": "Get account balance on Aster DEX futures.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "aster_account_info",
        "description": "Get full account info from Aster DEX — assets, positions, margins.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "aster_open_orders",
        "description": "Get all open/pending orders on Aster DEX.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (optional — all pairs if omitted)"},
            },
            "required": [],
        },
    },
    {
        "name": "aster_place_order",
        "description": "Place an order on Aster DEX futures. Supports market, limit, stop-market, and stop-limit.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g. ETHUSDT)"},
                "side": {"type": "string", "description": "BUY or SELL"},
                "order_type": {"type": "string", "description": "MARKET, LIMIT, STOP_MARKET, STOP", "default": "MARKET"},
                "quantity": {"type": "number", "description": "Order quantity in base asset", "default": 0},
                "price": {"type": "number", "description": "Limit price (required for LIMIT/STOP orders)"},
                "stop_price": {"type": "number", "description": "Trigger price for stop orders"},
                "time_in_force": {"type": "string", "description": "GTC, IOC, FOK", "default": "GTC"},
                "reduce_only": {"type": "boolean", "description": "Close-only order", "default": False},
                "usd_amount": {"type": "number", "description": "Order size in USD (alternative to quantity)"},
            },
            "required": ["symbol", "side"],
        },
    },
    {
        "name": "aster_cancel_order",
        "description": "Cancel an open order on Aster DEX.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair"},
                "order_id": {"type": "integer", "description": "Order ID to cancel (latest if omitted)"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "aster_cancel_all_orders",
        "description": "Cancel all open orders for a symbol on Aster DEX.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "aster_set_leverage",
        "description": "Set leverage for a symbol on Aster DEX (1-125x).",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair"},
                "leverage": {"type": "integer", "description": "Leverage multiplier (1-125)"},
            },
            "required": ["symbol", "leverage"],
        },
    },
    {
        "name": "aster_diagnose",
        "description": "Run comprehensive diagnostics on Aster DEX connection — API key status, connectivity, account access.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "aster_ping",
        "description": "Check Aster DEX API connectivity and latency.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    # v0.9.5: three Aster tools added
    {
        "name": "aster_place_order_confirmed",
        "description": "Place an order on Aster DEX and poll until fill confirmation (FILLED, CANCELED, TIMEOUT). For market orders, confirms execution. For limit orders, waits up to timeout_seconds.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g., 'BTC', 'ETH')"},
                "side": {"type": "string", "description": "'BUY' or 'SELL'"},
                "order_type": {"type": "string", "description": "'MARKET' or 'LIMIT'", "default": "MARKET"},
                "quantity": {"type": "number", "description": "Contract quantity (or USD amount — auto-detected)"},
                "price": {"type": "number", "description": "Limit price (required for LIMIT orders)"},
                "usd_amount": {"type": "number", "description": "Explicit USD amount (preferred over quantity)"},
                "timeout_seconds": {"type": "number", "description": "Max seconds to wait for confirmation", "default": 15},
            },
            "required": ["symbol", "side"],
        },
    },
    {
        "name": "aster_countdown_cancel",
        "description": "Dead man's switch — auto-cancel all Aster orders for a symbol if not refreshed within countdown_ms. Call periodically (e.g., every 20s for a 30s timer). Set countdown_ms=0 to disable.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g., 'BTC')"},
                "countdown_ms": {"type": "integer", "description": "Milliseconds until auto-cancel. 0 to disable.", "default": 30000},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "aster_place_trailing_stop",
        "description": "Place a trailing stop market order on Aster futures. The stop follows the price at a fixed percentage distance.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g., 'BTC')"},
                "side": {"type": "string", "description": "'SELL' for long positions, 'BUY' for short positions", "default": "SELL"},
                "quantity": {"type": "number", "description": "Contract size"},
                "callback_rate": {"type": "number", "description": "Trail distance as percentage (1.0 = 1% trail)", "default": 1.0},
                "activation_price": {"type": "number", "description": "Optional price at which trailing starts"},
                "usd_amount": {"type": "number", "description": "Explicit USD amount for auto-conversion"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "aster_order_history",
        "description": "Get recent order history for a symbol on Aster DEX.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g., 'BTC')"},
                "limit": {"type": "integer", "description": "Number of orders to return", "default": 20},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "aster_trade_history",
        "description": "Get recent trade fills for a symbol on Aster DEX.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g., 'BTC')"},
                "limit": {"type": "integer", "description": "Number of trades to return", "default": 20},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "aster_set_margin_mode",
        "description": "Set margin mode for a symbol on Aster DEX — ISOLATED or CROSSED.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair (e.g., 'BTC')"},
                "margin_type": {"type": "string", "description": "'ISOLATED' or 'CROSSED'", "default": "CROSSED"},
            },
            "required": ["symbol"],
        },
    },

    # {
    #     "name": "tg_read_channel",
    #     "description": "Read messages from a Telegram channel.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "channel": {"type": "string", "description": "Channel username or ID"},
    #             "limit": {"type": "integer", "description": "Number of messages", "default": 10},
    #         },
    #         "required": ["channel"],
    #     },
    # },
    # {
    #     "name": "tg_list_channels",
    #     "description": "List available Telegram channels.",
    #     "parameters": {"type": "object", "properties": {}, "required": []},
    # },

    # ── Discord — shelved ─────────────────────────────────────
    # {
    #     "name": "discord_list_guilds",
    #     "description": "List connected Discord servers/guilds.",
    #     "parameters": {"type": "object", "properties": {}, "required": []},
    # },
    # {
    #     "name": "discord_read_channel",
    #     "description": "Read messages from a Discord channel.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "channel_id": {"type": "integer", "description": "Discord channel ID"},
    #             "limit": {"type": "integer", "description": "Number of messages", "default": 50},
    #         },
    #         "required": ["channel_id"],
    #     },
    # },

    # ── Strategy / Algo Trading — shelved (in-house algos, not production) ──
    # {
    #     "name": "strategy_status",
    #     "description": "Get current algo trading strategy status.",
    #     "parameters": {"type": "object", "properties": {}, "required": []},
    # },
    # {
    #     "name": "strategy_start",
    #     "description": "Start the algo trading strategy.",
    #     "parameters": {"type": "object", "properties": {}, "required": []},
    # },
    # {
    #     "name": "strategy_stop",
    #     "description": "Stop the algo trading strategy.",
    #     "parameters": {"type": "object", "properties": {}, "required": []},
    # },
    # {
    #     "name": "strategy_set_algo",
    #     "description": "Set the active trading algorithm.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "algo": {"type": "string", "description": "Algorithm name"},
    #             "params": {"type": "object", "description": "Optional algo-specific parameters"},
    #         },
    #         "required": ["algo"],
    #     },
    # },
    # {
    #     "name": "list_algos",
    #     "description": "List all available trading algorithms.",
    #     "parameters": {"type": "object", "properties": {}, "required": []},
    # },

    # ── Wallets / DEX Swaps — removed (not a product feature) ──
]


# ══════════════════════════════════════════════════════════════
# Tool Format Converters

# ══════════════════════════════════════════════════════════════

def _tools_for_anthropic(tools: list[dict]) -> list[dict]:
    """Convert tool schemas to Anthropic format."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in tools
    ]


def _tools_for_openai(tools: list[dict]) -> list[dict]:
    """Convert tool schemas to OpenAI/xAI/Gemini format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in tools
    ]


# ══════════════════════════════════════════════════════════════
# LLM API Callers
# ══════════════════════════════════════════════════════════════

def _track_llm_usage(resp_data: dict, provider: str, model: str):
    """Log LLM usage to the local usage tracker (non-blocking, best-effort)."""
    try:
        from sentinel.scrapers import usage
        inp = out = 0
        if provider == "anthropic":
            u = resp_data.get("usage", {})
            inp, out = u.get("input_tokens", 0), u.get("output_tokens", 0)
        elif provider in ("openai", "xai", "deepseek", "minimax", "moonshot", "zhipu"):
            u = resp_data.get("usage", {})
            inp, out = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        elif provider == "google":
            # Try OpenAI-compat format first (used via /v1beta/openai/ endpoint)
            u = resp_data.get("usage", {})
            inp, out = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
            # Fallback to native Gemini format
            if not inp and not out:
                u = resp_data.get("usageMetadata", {})
                inp, out = u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)
        if inp or out:
            usage.log_usage(provider, model, inp, out)
    except Exception:
        pass  # Usage tracking is best-effort — never block the user

def _call_anthropic(ai_key: str, model: str, messages: list, tools: list) -> dict:
    """Call Anthropic Messages API with tool support and model fallback."""
    fallbacks = MODEL_FALLBACKS.get("anthropic", [])
    # Build model list: requested model first, then fallbacks (deduped)
    models_to_try = [model] + [m for m in fallbacks if m != model]

    for model_attempt in models_to_try:
        result = _call_anthropic_single(ai_key, model_attempt, messages, tools)
        # Check for model-specific errors that warrant a fallback
        if "error" in result:
            err_msg = str(result.get("error", ""))
            if isinstance(result.get("error"), dict):
                err_msg = result["error"].get("message", "") + " " + result["error"].get("type", "")
            err_lower = err_msg.lower()
            # Model deprecated, not found, or invalid — try next
            if any(k in err_lower for k in ("not_found", "model_not_found", "deprecated",
                                             "invalid_model", "does not exist", "not available",
                                             "model not found", "retired")):
                if model_attempt != models_to_try[-1]:
                    next_model = models_to_try[models_to_try.index(model_attempt) + 1]
                    console.print(f"  [yellow]⚠ Model '{model_attempt}' unavailable — falling back to '{next_model}'[/]")
                    continue
        return result
    return result  # Return last error if all fallbacks exhausted


def _provider_from_endpoint(endpoint: str) -> str:
    """Resolve a provider endpoint URL to its provider ID."""
    # Build reverse lookup from PROVIDER_ENDPOINTS (skip anthropic — different path)
    for prov, url in PROVIDER_ENDPOINTS.items():
        if prov == "anthropic":
            continue
        # Match on the domain portion of the URL
        domain = url.split("//")[1].split("/")[0] if "//" in url else ""
        if domain and domain in endpoint:
            return prov
    return "openai"  # safe fallback


def _gateway_llm_request(provider: str, ai_key: str, model: str, messages: list, tools: list):
    """Build (url, headers, body) for a gateway-routed LLM call.

    Routes through the Sentinel gateway (POST /api/v1/llm/chat) instead of hitting the
    provider directly — so every call is metered + marked up (the 20% revenue rail). The
    gateway proxies to the real provider with the user's BYOK key, extracts the
    role:"system" message itself, and forwards `tools` (provider-native shape) unchanged.
    """
    from sentinel.api._http import load_api_key
    sentinel_key = load_api_key() or ""
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "ai_key": ai_key,
        "provider": provider,
    }
    if tools:
        body["tools"] = _tools_for_anthropic(tools) if provider == "anthropic" else _tools_for_openai(tools)
    headers = {"Content-Type": "application/json"}
    if sentinel_key:
        headers["X-API-Key"] = sentinel_key
    # v0.9.3: also send the AI key as a header so the gateway's X-AI-Key identity path resolves the
    # user even if no Sentinel key was saved (e.g. Windows file-save failed). Belt-and-suspenders — the
    # gateway forwards the provider key from the body, so this is purely for auth/identity.
    if ai_key:
        headers["X-AI-Key"] = ai_key
    return f"{GATEWAY_URL}/api/v1/llm/chat", headers, body


def _call_anthropic_single(ai_key: str, model: str, messages: list, tools: list) -> dict:
    """Call Anthropic via the Sentinel gateway — single model attempt."""
    url, headers, payload = _gateway_llm_request("anthropic", ai_key, model, messages, tools)

    import time as _time
    last_err = ""
    for attempt in range(3):
        try:
            resp = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(120.0, connect=15.0),
            )
            if resp.status_code in (403, 429, 500, 502, 503, 529) and attempt < 2:
                last_err = f"HTTP {resp.status_code}"
                _time.sleep(1.5 * (attempt + 1))
                continue
            # Non-200: try to parse JSON error, otherwise show body snippet
            if resp.status_code != 200:
                try:
                    return resp.json()  # Anthropic returns JSON errors
                except (ValueError, Exception):
                    body_snippet = resp.text[:200].replace('\n', ' ').strip()
                    return {"error": {"message": f"Anthropic HTTP {resp.status_code}: {body_snippet}"}}
            try:
                data = resp.json()
                _track_llm_usage(data, "anthropic", model)
                return data
            except (ValueError, Exception):
                if attempt < 2:
                    _time.sleep(1.5 * (attempt + 1))
                    continue
                return {"error": {"message": f"Anthropic returned empty response after 3 retries."}}
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            if attempt < 2:
                _time.sleep(2 * (attempt + 1))
                continue
            return {"error": {"message": f"Cannot reach Anthropic API: {e}. Check your internet connection."}}
        except httpx.TimeoutException as e:
            if attempt < 2:
                console.print(f"  [yellow]⚠ Anthropic timeout (attempt {attempt + 1}/3) — retrying...[/]")
                _time.sleep(2 * (attempt + 1))
                continue
            return {"error": {"message": f"Anthropic API timed out after 3 attempts. Try a simpler query or check your connection."}}
        except Exception as e:
            return {"error": {"message": f"LLM call failed: {e}"}}


def _call_anthropic_streamed(ai_key: str, model: str, messages: list, tools: list) -> dict:
    """Stream an Anthropic call through the gateway (SSE), showing a transient live
    preview of the text as it generates (a rolling tail that auto-clears on exit).
    The agent loop then renders the final answer in the themed Panel — so we get the
    streaming feel AND the cohesive box.

    Reconstructs the same {content, stop_reason} dict the loop expects (text + tool_use
    blocks), so tool-calling still works. Falls back to non-streaming on any failure.
    """
    from rich.live import Live
    from rich.text import Text

    url, headers, body = _gateway_llm_request("anthropic", ai_key, model, messages, tools)
    text_parts: list[str] = []
    tool_blocks: list[dict] = []
    stop_reason = "end_turn"
    streamed_any = False

    def _preview() -> Text:
        # Show only the last ~12 lines so a long response never overflows the screen.
        tail = "\n".join("".join(text_parts).splitlines()[-12:])
        return Text("  " + tail.replace("\n", "\n  "), style="#6b8e8e")

    try:
        with httpx.stream(
            "POST", url + "?stream=true", headers=headers, json=body,
            timeout=httpx.Timeout(180.0, connect=15.0),
        ) as resp:
            if resp.status_code != 200:
                resp.read()
                return _call_anthropic(ai_key, model, messages, tools)
            with Live(console=console, refresh_per_second=12, transient=True) as live:
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except (ValueError, Exception):
                        continue
                    if ev.get("type") == "tool_use":
                        tool_blocks.append({
                            "type": "tool_use",
                            "id": ev.get("id"),
                            "name": ev.get("name"),
                            "input": ev.get("input", {}),
                        })
                    elif ev.get("done"):
                        stop_reason = ev.get("stop_reason", "end_turn")
                        _track_llm_usage({"usage": ev.get("usage", {})}, "anthropic", model)
                        break
                    else:
                        t = ev.get("text", "")
                        if t:
                            text_parts.append(t)
                            streamed_any = True
                            live.update(_preview())
    except Exception:
        # If nothing streamed yet, fall back cleanly to non-streaming.
        if not streamed_any and not tool_blocks:
            return _call_anthropic(ai_key, model, messages, tools)
        # Otherwise keep whatever streamed so far.

    content: list[dict] = []
    text = "".join(text_parts)
    if text:
        content.append({"type": "text", "text": text})
    content.extend(tool_blocks)
    return {"content": content, "stop_reason": stop_reason, "_streamed": True}


def _call_openai_compat(
    ai_key: str,
    model: str,
    messages: list,
    tools: list,
    endpoint: str,
) -> dict:
    """Call OpenAI-compatible API with tool support and model fallback."""
    # Detect provider for fallback chain
    _prov = _provider_from_endpoint(endpoint)

    fallbacks = MODEL_FALLBACKS.get(_prov, [])
    models_to_try = [model] + [m for m in fallbacks if m != model]

    for model_attempt in models_to_try:
        result = _call_openai_compat_single(ai_key, model_attempt, messages, tools, endpoint)
        # Check for model-specific errors that warrant a fallback
        if "error" in result:
            err_msg = str(result.get("error", ""))
            if isinstance(result.get("error"), dict):
                err_msg = result["error"].get("message", "") + " " + result["error"].get("type", "") + " " + result["error"].get("code", "")
            err_lower = err_msg.lower()
            if any(k in err_lower for k in ("model_not_found", "not_found", "deprecated",
                                             "invalid_model", "does not exist", "not available",
                                             "model not found", "retired", "decommissioned")):
                if model_attempt != models_to_try[-1]:
                    next_model = models_to_try[models_to_try.index(model_attempt) + 1]
                    console.print(f"  [yellow]⚠ Model '{model_attempt}' unavailable — falling back to '{next_model}'[/]")
                    continue
        return result
    return result


def _call_openai_compat_single(
    ai_key: str,
    model: str,
    messages: list,
    tools: list,
    endpoint: str,
) -> dict:
    """Call OpenAI-compatible API — single model attempt."""
    # Derive provider from the endpoint, then route via the gateway.
    _prov = _provider_from_endpoint(endpoint)
    url, headers, payload = _gateway_llm_request(_prov, ai_key, model, messages, tools)

    import time as _time
    for attempt in range(3):
        try:
            resp = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(120.0, connect=15.0),
            )
            if resp.status_code in (403, 429, 500, 502, 503, 529) and attempt < 2:
                _time.sleep(1.5 * (attempt + 1))
                continue
            try:
                data = resp.json()
                # Detect provider from endpoint for tracking
                _prov = _provider_from_endpoint(endpoint)
                _track_llm_usage(data, _prov, model)
                return data
            except (ValueError, Exception):
                if attempt < 2:
                    _time.sleep(1.5 * (attempt + 1))
                    continue
                return {"error": {"message": f"LLM API returned HTTP {resp.status_code} with invalid response after 3 retries."}}
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            if attempt < 2:
                _time.sleep(2 * (attempt + 1))
                continue
            return {"error": {"message": f"Cannot reach LLM API: {e}. Check your internet connection."}}
        except httpx.TimeoutException as e:
            if attempt < 2:
                console.print(f"  [yellow]⚠ LLM timeout (attempt {attempt + 1}/3) — retrying...[/]")
                _time.sleep(2 * (attempt + 1))
                continue
            return {"error": {"message": f"LLM API timed out after 3 attempts. Try a simpler query or check your connection."}}
        except Exception as e:
            return {"error": {"message": f"LLM call failed: {e}"}}


# ══════════════════════════════════════════════════════════════
# Fast Path — zero LLM compute for known queries
# ══════════════════════════════════════════════════════════════

import re

# Common symbol mapping for fast path
_FAST_SYMBOLS = {
    "btc": "bitcoin", "bitcoin": "bitcoin",
    "eth": "ethereum", "ethereum": "ethereum",
    "sol": "solana", "solana": "solana",
    "xmr": "monero", "monero": "monero",
    "doge": "dogecoin", "dogecoin": "dogecoin",
    "xrp": "ripple", "ripple": "ripple",
    "ada": "cardano", "cardano": "cardano",
    "dot": "polkadot", "polkadot": "polkadot",
    "avax": "avalanche-2", "avalanche": "avalanche-2",
    "matic": "matic-network", "polygon": "matic-network",
    "link": "chainlink", "chainlink": "chainlink",
    "bnb": "binancecoin", "binance": "binancecoin",
    "uni": "uniswap", "uniswap": "uniswap",
    "atom": "cosmos", "cosmos": "cosmos",
    "near": "near", "arb": "arbitrum", "arbitrum": "arbitrum",
    "op": "optimism", "sui": "sui", "apt": "aptos",
    "pepe": "pepe", "shib": "shiba-inu",
    "ltc": "litecoin", "litecoin": "litecoin",
    "hype": "hyperliquid", "hyperliquid": "hyperliquid",
    "fartcoin": "fartcoin", "fart": "fartcoin",
}

# Patterns for fast path matching
_PRICE_PATTERNS = [
    # "price of btc" / "price of btc and eth"
    re.compile(r"(?:what(?:'s| is| are)?\s+(?:the\s+)?)?price(?:s)?\s+(?:of\s+)?(.+)", re.I),
    # "btc price" / "eth price"
    re.compile(r"^(\w+)\s+price$", re.I),
    # "how much is btc"
    re.compile(r"how\s+much\s+(?:is|are|does)\s+(.+?)(?:\s+(?:worth|cost|trading))?$", re.I),
]

_TOP_PATTERN = re.compile(r"(?:top|best|biggest)\s+(\d+)?\s*(?:crypto|coins?|tokens?)?", re.I)


def _fast_path(user_input: str) -> str | None:
    """Intercept common queries and handle locally without LLM.

    Returns formatted text if fast path matches, None otherwise.
    """
    text = user_input.strip().lower()

    # ── Price queries ──────────────────────────────────────
    for pat in _PRICE_PATTERNS:
        m = pat.match(text)
        if m:
            raw = m.group(1).strip()
            # Split on "and", ",", "&", spaces
            parts = re.split(r"\s+and\s+|\s*,\s*|\s*&\s*|\s+", raw)
            coins = []
            for p in parts:
                p = p.strip().lower().rstrip("?.,!")
                if p in _FAST_SYMBOLS:
                    coins.append(_FAST_SYMBOLS[p])
                elif len(p) >= 2:
                    coins.append(p)  # Try raw as CoinGecko ID

            if not coins:
                return None

            return _fetch_and_format_prices(coins)

    # ── Top N ──────────────────────────────────────────────
    m = _TOP_PATTERN.match(text)
    if m:
        n = int(m.group(1) or 10)
        return _fetch_and_format_top(min(n, 25))

    return None


def _fetch_and_format_prices(coin_ids: list[str]) -> str | None:
    """Fetch prices from CoinGecko and format as rich text."""
    try:
        from sentinel.scrapers.crypto import get_crypto_price
    except ImportError:
        # Fallback to inline httpx
        try:
            import httpx
            results = []
            for cid in coin_ids:
                resp = httpx.get(
                    f"https://api.coingecko.com/api/v3/coins/{cid}",
                    params={"localization": "false", "tickers": "false",
                            "community_data": "false", "developer_data": "false"},
                    timeout=10.0,
                    headers={"User-Agent": "Sentinel/1.0"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    md = data.get("market_data", {})
                    results.append({
                        "name": data.get("name", cid),
                        "symbol": data.get("symbol", "").upper(),
                        "current_price": md.get("current_price", {}).get("usd"),
                        "price_change_pct_24h": md.get("price_change_percentage_24h"),
                        "price_change_pct_7d": md.get("price_change_percentage_7d"),
                        "market_cap_rank": md.get("market_cap_rank"),
                        "market_cap": md.get("market_cap", {}).get("usd"),
                    })
            if not results:
                return None
            return _format_price_results(results)
        except Exception:
            return None

    results = []
    for cid in coin_ids:
        try:
            data = get_crypto_price(cid)
            if data and "error" not in data:
                results.append(data)
        except Exception:
            pass

    if not results:
        return None

    return _format_price_results(results)


def _format_price_results(results: list[dict]) -> str:
    """Format price data as rich text."""
    lines = []
    for r in results:
        name = r.get("name", "?")
        symbol = r.get("symbol", "").upper()
        price = r.get("current_price")
        change_24h = r.get("price_change_pct_24h")
        change_7d = r.get("price_change_pct_7d")
        rank = r.get("market_cap_rank")
        mcap = r.get("market_cap")

        # Format price
        if price and price >= 1:
            price_str = f"${price:,.2f}"
        elif price:
            price_str = f"${price:.6f}"
        else:
            price_str = "N/A"

        # Format changes
        def _fmt_change(val):
            if val is None:
                return "[dim]N/A[/dim]"
            color = "green" if val >= 0 else "red"
            return f"[{color}]{val:+.2f}%[/{color}]"

        lines.append(f"[bold cyan]{name}[/bold cyan] ({symbol}): [bold]{price_str}[/bold]")
        lines.append(f"  24h: {_fmt_change(change_24h)}  ·  7d: {_fmt_change(change_7d)}  ·  Rank #{rank or '?'}")
        if mcap:
            lines.append(f"  Market cap: ${mcap:,.0f}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _fetch_and_format_top(n: int) -> str | None:
    """Fetch top N crypto and format."""
    try:
        from sentinel.scrapers.crypto import get_crypto_top_n
        data = get_crypto_top_n(n)
    except ImportError:
        try:
            import httpx
            resp = httpx.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={"vs_currency": "usd", "order": "market_cap_desc",
                        "per_page": n, "page": 1, "sparkline": "false"},
                timeout=10.0,
                headers={"User-Agent": "Sentinel/1.0"},
            )
            data = resp.json() if resp.status_code == 200 else None
        except Exception:
            return None
    except Exception:
        return None

    if not data:
        return None

    lines = [f"[bold]Top {len(data)} Cryptocurrencies by Market Cap[/bold]\n"]
    for c in data:
        rank = c.get("rank") or c.get("market_cap_rank", "?")
        sym = (c.get("symbol") or "").upper()
        name = c.get("name", "?")
        price = c.get("current_price")
        change = c.get("price_change_pct_24h") or c.get("price_change_percentage_24h")

        price_str = f"${price:,.2f}" if price and price >= 1 else f"${price:.6f}" if price else "N/A"
        color = "green" if change and change >= 0 else "red"
        change_str = f"[{color}]{change:+.2f}%[/{color}]" if change is not None else "[dim]N/A[/dim]"

        lines.append(f"  #{rank:<3} [bold]{sym:<6}[/bold] {name:<15} {price_str:<12} {change_str}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# Tool Smoke Test / Diagnose
# ══════════════════════════════════════════════════════════════

def _run_tool_smoke_test(api_key: str) -> None:
    """Run a smoke test across all 69 tool categories and report pass/fail.

    v0.9.2: expanded from 4 probes to full category coverage.
    - Keyless tools: always tested (CoinGecko, YFinance, DexScreener, Aster public, TA/quant/options)
    - Key-gated tools: tested when key present, explicitly skipped+labeled when absent
    Categories map to all 69 TOOL_SCHEMAS entries.
    """
    import os

    # ── Always-on probes (no API key required) ────────────────────
    always_probes = [
        # CoinGecko (3 tools)
        ("get_crypto_price",        {"coin_id": "bitcoin"},                            "CoinGecko · price (bitcoin)"),
        ("get_crypto_top_n",        {"n": 5},                                          "CoinGecko · top 5"),
        ("search_crypto",           {"query": "ethereum"},                             "CoinGecko · search"),
        # YFinance (6 tools)
        ("get_stock_price",         {"symbol": "AAPL"},                               "YFinance · stock price"),
        ("get_stock_info",          {"symbol": "AAPL"},                               "YFinance · stock info"),
        ("get_stock_history",       {"symbol": "AAPL", "period": "1mo"},              "YFinance · stock history"),
        ("get_analyst_recs",        {"symbol": "AAPL"},                               "YFinance · analyst recs"),
        ("get_stock_news",          {"symbol": "AAPL"},                               "YFinance · stock news"),
        ("run_stock_analysis",      {"symbol": "AAPL"},                               "YFinance · full analysis"),
        # DexScreener (4 tools)
        ("dexscreener_search",      {"query": "PEPE"},                                "DexScreener · search"),
        ("dexscreener_trending",    {},                                                "DexScreener · trending"),
        ("dexscreener_token_lookup",{"token_address": "So11111111111111111111111111111111111111112"}, "DexScreener · token lookup (SOL)"),
        # Aster DEX public (no key needed)
        ("aster_ping",              {},                                                "Aster · ping"),
        ("aster_exchange_info",     {},                                                "Aster · exchange info"),
        ("aster_ticker",            {"symbol": "BTCUSDT"},                            "Aster · ticker BTC"),
        ("aster_funding_rate",      {},                                                "Aster · funding rate"),
        # TA / Quant (local compute — use tradfi/YFinance venue to avoid HL auth)
        ("get_ta_indicators",       {"symbol": "AAPL", "interval": "1d", "venue": "tradfi"},  "TA · indicators AAPL"),
        ("get_ta_signal",           {"symbol": "AAPL", "interval": "1d", "venue": "tradfi"},  "TA · signal AAPL"),
        ("get_risk_metrics",        {"symbol": "AAPL", "interval": "1d", "venue": "tradfi"},  "Quant · risk metrics AAPL"),
        ("get_ml_signals",          {"symbol": "AAPL", "interval": "1d", "venue": "tradfi"},  "Quant · ML signals AAPL"),
        ("get_timeseries_forecast", {"symbol": "AAPL", "interval": "1d", "venue": "tradfi"},  "Quant · timeseries AAPL"),
        # Options (YFinance, no key)
        ("get_options_expirations", {"symbol": "AAPL"},                               "Options · expirations AAPL"),
        ("get_options_analysis",    {"symbol": "AAPL"},                               "Options · analysis AAPL"),
        # Portfolio + usage (local, no key)
        ("get_portfolio_summary",   {},                                                "Portfolio · summary"),
        ("get_usage_summary",       {"period": "today"},                              "Usage · today"),
    ]

    # ── Key-gated probes — skipped (labeled) when key absent ─────
    keyed_probes = [
        # FRED
        ("FRED_API_KEY",        "get_fred_series",       {"series_id": "CPIAUCSL", "limit": 3},  "FRED · CPI series"),
        ("FRED_API_KEY",        "search_fred",           {"query": "unemployment"},               "FRED · search"),
        ("FRED_API_KEY",        "get_economic_dashboard",{},                                      "FRED · macro dashboard"),
        ("FRED_API_KEY",        "get_yield_curve",       {},                                      "FRED · yield curve"),
        # Y2
        ("Y2_API_KEY",          "get_news_sentiment",    {"query": "bitcoin"},                    "Y2 · news sentiment"),
        ("Y2_API_KEY",          "get_news_recap",        {},                                      "Y2 · news recap"),
        ("Y2_API_KEY",          "get_intelligence_reports", {"limit": 3},                         "Y2 · intelligence reports"),
        ("Y2_API_KEY",          "get_y2_feeds",          {},                                      "Y2 · feeds"),
        ("Y2_API_KEY",          "list_y2_profiles",      {},                                      "Y2 · profiles"),
        # Elfa
        ("ELFA_API_KEY",        "get_trending_tokens",   {},                                      "Elfa · trending tokens"),
        ("ELFA_API_KEY",        "search_mentions",       {"query": "bitcoin"},                    "Elfa · search mentions"),
        ("ELFA_API_KEY",        "get_trending_narratives", {},                                    "Elfa · narratives"),
        ("ELFA_API_KEY",        "get_top_mentions",      {"ticker": "BTC"},                       "Elfa · top mentions BTC"),
        ("ELFA_API_KEY",        "get_token_news",        {"ticker": "BTC"},                       "Elfa · token news BTC"),
        # X / Twitter
        ("X_BEARER_TOKEN",      "search_x",              {"query": "bitcoin", "max_results": 5},  "X · search"),
        # Hyperliquid
        ("HYPERLIQUID_WALLET_ADDRESS", "get_hl_config",  {},                                      "HL · config"),
        ("HYPERLIQUID_WALLET_ADDRESS", "get_hl_tradfi_assets", {},                                "HL · TradFi assets"),
        ("HYPERLIQUID_WALLET_ADDRESS", "get_hl_positions", {},                                    "HL · positions"),
        ("HYPERLIQUID_WALLET_ADDRESS", "get_hl_account_info", {},                                 "HL · account info"),
        # Aster (authenticated)
        ("ASTER_API_KEY",       "aster_balance",         {},                                      "Aster · balance"),
        ("ASTER_API_KEY",       "aster_positions",       {},                                      "Aster · positions"),
        ("ASTER_API_KEY",       "aster_open_orders",     {},                                      "Aster · open orders"),
        ("ASTER_API_KEY",       "aster_diagnose",        {},                                      "Aster · diagnose"),
        ("ASTER_API_KEY",       "aster_account_info",    {},                                      "Aster · account info"),
    ]

    console.print()
    console.print("  [bold cyan]Tool Smoke Test[/] [dim]— all-69 category sweep...[/]")
    console.print()

    passed, failed, skipped = 0, 0, 0
    results = []

    def _probe(tool_name: str, args: dict, desc: str):
        nonlocal passed, failed
        try:
            raw = _execute_direct(tool_name, args)
            if raw is None:
                raw = _execute_tool(api_key, tool_name, args)
            parsed = json.loads(raw) if raw else {}
            if isinstance(parsed, dict) and "error" in parsed:
                results.append(("FAIL", desc, str(parsed["error"])[:80]))
                failed += 1
            elif isinstance(parsed, list) and parsed and isinstance(parsed[0], dict) and "error" in parsed[0]:
                results.append(("FAIL", desc, str(parsed[0]["error"])[:80]))
                failed += 1
            else:
                results.append(("PASS", desc, ""))
                passed += 1
        except Exception as e:
            results.append(("FAIL", desc, str(e)[:80]))
            failed += 1

    # Always-on
    for tool_name, args, desc in always_probes:
        _probe(tool_name, args, desc)

    # Key-gated
    for env_key, tool_name, args, desc in keyed_probes:
        if os.getenv(env_key):
            _probe(tool_name, args, desc)
        else:
            results.append(("SKIP", desc, f"{env_key} not set"))
            skipped += 1

    # Print results grouped by status
    for status, desc, detail in results:
        if status == "PASS":
            console.print(f"  [green]✓[/] {desc}")
        elif status == "FAIL":
            console.print(f"  [red]✗[/] [bold]{desc}[/] [dim]— {detail}[/]")
        else:
            console.print(f"  [dim]—[/] {desc} [dim](skipped: {detail})[/]")

    total_run = passed + failed
    color = "green" if failed == 0 else ("yellow" if failed < total_run / 2 else "red")
    console.print()
    console.print(
        f"  [{color}]{passed}/{total_run} passed[/]"
        f"  [dim]{skipped} skipped (keys absent)[/]"
        f"  [dim]· Run 'tools' for the full 69-tool list[/]"
    )
    console.print()


# ══════════════════════════════════════════════════════════════
# Tool Execution via Gateway
# ══════════════════════════════════════════════════════════════

def _execute_tool(api_key: str, tool_name: str, tool_args: dict) -> str:
    """Execute a tool. Free tools run directly; others go through gateway."""

    # ── Direct execution for free/public tools ────────────────
    direct = _execute_direct(tool_name, tool_args)
    if direct is not None:
        return direct

    # ── Gateway execution for everything else ─────────────────
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/api/v1/tools/{tool_name}",
            json=tool_args,
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.text
        return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:200]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _execute_direct(tool_name: str, args: dict) -> str | None:
    """Execute free tools directly without gateway. Returns None if not a direct tool."""
    try:
        # ── CoinGecko (free, no key) ──────────────────────────
        # v0.9.2: route through scrapers/crypto.py so retry/backoff/cache/demo-key
        # apply uniformly.  Previously this path made raw httpx calls with no retry.
        if tool_name == "get_crypto_price":
            from sentinel.scrapers.crypto import get_crypto_price as _cgprice, SYMBOL_TO_ID
            # Tool schema uses coin_id; fallback to symbol for compatibility
            symbol = args.get("coin_id", args.get("symbol", "")).lower().strip()
            coin_id = SYMBOL_TO_ID.get(symbol, symbol)
            result = _cgprice(coin_id)
            if "error" in result:
                # Try interpreting symbol as a literal CoinGecko ID
                if coin_id != symbol:
                    result2 = _cgprice(symbol)
                    if "error" not in result2:
                        result = result2
            # Normalize output shape to what the LLM expects
            if "error" not in result:
                return json.dumps({
                    "symbol": result.get("symbol", coin_id.upper()),
                    "price_usd": result.get("current_price"),
                    "change_24h_pct": result.get("price_change_pct_24h"),
                    "market_cap_usd": result.get("market_cap"),
                    "volume_24h_usd": result.get("total_volume_24h"),
                    "source": "coingecko",
                })
            return json.dumps(result)

        if tool_name in ("get_crypto_top", "get_crypto_top_n"):
            from sentinel.scrapers.crypto import get_crypto_top_n as _cgtop
            n = args.get("n", 10)
            coins_data = _cgtop(n)
            coins = [{"rank": c.get("rank"), "name": c.get("name"), "symbol": c.get("symbol"),
                       "price": c.get("current_price"), "change_24h": c.get("price_change_pct_24h"),
                       "market_cap": c.get("market_cap")} for c in coins_data if "error" not in c]
            return json.dumps({"top_coins": coins, "source": "coingecko"})

        if tool_name == "search_crypto":
            from sentinel.scrapers.crypto import search_crypto as _cgsearch
            query = args.get("query", "")
            coins = _cgsearch(query)
            return json.dumps({"results": coins, "source": "coingecko"})

        # ── YFinance (free, no key) ───────────────────────────
        if tool_name in ("get_stock_price", "get_stock_info", "get_analyst_recs", "get_stock_news", "get_stock_history", "run_stock_analysis"):
            try:
                import yfinance as yf
            except ImportError:
                return json.dumps({"error": "yfinance not installed. Run: pip install yfinance"})

            ticker = args.get("ticker", args.get("symbol", "SPY")).upper()
            t = yf.Ticker(ticker)

            if tool_name == "get_stock_price":
                info = t.info
                return json.dumps({
                    "ticker": ticker,
                    "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                    "change_pct": info.get("regularMarketChangePercent"),
                    "market_cap": info.get("marketCap"),
                    "volume": info.get("volume"),
                    "name": info.get("shortName"),
                    "pe_ratio": info.get("trailingPE"),
                    "52w_high": info.get("fiftyTwoWeekHigh"),
                    "52w_low": info.get("fiftyTwoWeekLow"),
                    "source": "yfinance",
                })
            elif tool_name == "get_stock_info":
                info = t.info
                return json.dumps({
                    "ticker": ticker,
                    "name": info.get("shortName"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "market_cap": info.get("marketCap"),
                    "pe_ratio": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "dividend_yield": info.get("dividendYield"),
                    "52w_high": info.get("fiftyTwoWeekHigh"),
                    "52w_low": info.get("fiftyTwoWeekLow"),
                    "description": (info.get("longBusinessSummary") or "")[:300],
                    "source": "yfinance",
                })
            elif tool_name == "get_analyst_recs":
                recs = t.recommendations
                if recs is not None and len(recs) > 0:
                    recent = recs.tail(5).to_dict(orient="records")
                    return json.dumps({"ticker": ticker, "recommendations": recent, "source": "yfinance"})
                return json.dumps({"ticker": ticker, "recommendations": [], "source": "yfinance"})
            elif tool_name == "get_stock_news":
                news = t.news or []
                items = [{"title": n.get("title"), "publisher": n.get("publisher"),
                          "link": n.get("link")} for n in news[:5]]
                return json.dumps({"ticker": ticker, "news": items, "source": "yfinance"})
            elif tool_name == "get_stock_history":
                period = args.get("period", "1mo")
                hist = t.history(period=period)
                if hist.empty:
                    return json.dumps({"error": f"No history for {ticker}"})
                closes = hist["Close"].tolist()
                returns = [(closes[i] - closes[i-1])/closes[i-1] for i in range(1, len(closes))]
                avg_return = sum(returns)/len(returns) if returns else 0
                volatility = (sum((r - avg_return)**2 for r in returns) / len(returns))**0.5 if returns else 0
                sharpe = (avg_return / volatility * (252**0.5)) if volatility > 0 else 0
                return json.dumps({
                    "ticker": ticker,
                    "period": period,
                    "current_price": float(closes[-1]),
                    "period_return_pct": round((closes[-1]/closes[0] - 1) * 100, 2),
                    "daily_avg_return_pct": round(avg_return * 100, 4),
                    "daily_volatility_pct": round(volatility * 100, 4),
                    "annualized_sharpe": round(sharpe, 2),
                    "high": round(max(closes), 2),
                    "low": round(min(closes), 2),
                    "data_points": len(closes),
                    "source": "yfinance",
                })
            elif tool_name == "run_stock_analysis":
                info = t.info
                # Pull 1Y history for technicals
                hist = t.history(period="1y")
                closes_1y = hist["Close"].tolist() if not hist.empty else []
                # 1mo for short-term
                hist_1m = t.history(period="1mo")
                closes_1m = hist_1m["Close"].tolist() if not hist_1m.empty else []

                # Compute returns & volatility
                if len(closes_1y) > 1:
                    returns = [(closes_1y[i] - closes_1y[i-1])/closes_1y[i-1] for i in range(1, len(closes_1y))]
                    avg_ret = sum(returns)/len(returns)
                    vol = (sum((r - avg_ret)**2 for r in returns)/len(returns))**0.5
                    sharpe = (avg_ret / vol * (252**0.5)) if vol > 0 else 0
                else:
                    avg_ret, vol, sharpe = 0, 0, 0

                # Moving averages
                ma50 = sum(closes_1y[-50:])/50 if len(closes_1y) >= 50 else None
                ma200 = sum(closes_1y[-200:])/200 if len(closes_1y) >= 200 else None
                price = info.get("currentPrice") or info.get("regularMarketPrice") or (closes_1y[-1] if closes_1y else None)

                # Analyst targets
                recs = t.recommendations
                rec_summary = {}
                if recs is not None and len(recs) > 0:
                    latest = recs.tail(1).to_dict(orient="records")
                    if latest:
                        rec_summary = latest[0]

                result = {
                    "ticker": ticker,
                    "name": info.get("shortName"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    # ── Price ──
                    "current_price": price,
                    "previous_close": info.get("previousClose"),
                    "day_high": info.get("dayHigh"),
                    "day_low": info.get("dayLow"),
                    "52w_high": info.get("fiftyTwoWeekHigh"),
                    "52w_low": info.get("fiftyTwoWeekLow"),
                    "change_pct": info.get("regularMarketChangePercent"),
                    # ── Valuation ──
                    "market_cap": info.get("marketCap"),
                    "pe_trailing": info.get("trailingPE"),
                    "pe_forward": info.get("forwardPE"),
                    "peg_ratio": info.get("pegRatio"),
                    "price_to_book": info.get("priceToBook"),
                    "price_to_sales": info.get("priceToSalesTrailing12Months"),
                    "enterprise_value": info.get("enterpriseValue"),
                    "ev_to_ebitda": info.get("enterpriseToEbitda"),
                    # ── Financials ──
                    "revenue": info.get("totalRevenue"),
                    "revenue_growth": info.get("revenueGrowth"),
                    "earnings_growth": info.get("earningsGrowth"),
                    "profit_margin": info.get("profitMargins"),
                    "gross_margin": info.get("grossMargins"),
                    "operating_margin": info.get("operatingMargins"),
                    "ebitda_margin": info.get("ebitdaMargins"),
                    "roe": info.get("returnOnEquity"),
                    "roa": info.get("returnOnAssets"),
                    "eps_trailing": info.get("trailingEps"),
                    "eps_forward": info.get("forwardEps"),
                    # ── Balance Sheet ──
                    "total_cash": info.get("totalCash"),
                    "total_debt": info.get("totalDebt"),
                    "debt_to_equity": info.get("debtToEquity"),
                    "current_ratio": info.get("currentRatio"),
                    "quick_ratio": info.get("quickRatio"),
                    "operating_cash_flow": info.get("operatingCashflow"),
                    "free_cash_flow": info.get("freeCashflow"),
                    # ── Technicals ──
                    "ma_50": round(ma50, 2) if ma50 else None,
                    "ma_200": round(ma200, 2) if ma200 else None,
                    "price_vs_ma50_pct": round((price/ma50 - 1) * 100, 2) if ma50 and price else None,
                    "price_vs_ma200_pct": round((price/ma200 - 1) * 100, 2) if ma200 and price else None,
                    "avg_volume": info.get("averageVolume"),
                    "volume": info.get("volume"),
                    # ── Risk ──
                    "beta": info.get("beta"),
                    "overall_risk": info.get("overallRisk"),
                    "audit_risk": info.get("auditRisk"),
                    "board_risk": info.get("boardRisk"),
                    "compensation_risk": info.get("compensationRisk"),
                    "shareholder_rights_risk": info.get("shareHolderRightsRisk"),
                    "short_pct_of_float": info.get("shortPercentOfFloat"),
                    "short_ratio": info.get("shortRatio"),
                    "shares_short": info.get("sharesShort"),
                    # ── Analyst Targets ──
                    "target_high": info.get("targetHighPrice"),
                    "target_mean": info.get("targetMeanPrice"),
                    "target_median": info.get("targetMedianPrice"),
                    "target_low": info.get("targetLowPrice"),
                    "recommendation_key": info.get("recommendationKey"),
                    "number_of_analysts": info.get("numberOfAnalystOpinions"),
                    "analyst_recommendations": rec_summary,
                    # ── Quant Metrics ──
                    "1y_return_pct": round((closes_1y[-1]/closes_1y[0] - 1) * 100, 2) if len(closes_1y) > 1 else None,
                    "daily_volatility_pct": round(vol * 100, 4) if vol else None,
                    "annualized_sharpe": round(sharpe, 2) if sharpe else None,
                    "1y_high": round(max(closes_1y), 2) if closes_1y else None,
                    "1y_low": round(min(closes_1y), 2) if closes_1y else None,
                    # ── Dividend ──
                    "dividend_yield": info.get("dividendYield"),
                    "dividend_rate": info.get("dividendRate"),
                    "payout_ratio": info.get("payoutRatio"),
                    "source": "yfinance",
                }
                # Remove None values to keep response clean
                result = {k: v for k, v in result.items() if v is not None}
                return json.dumps(result)

        # ── DexScreener (free, no key) ────────────────────────
        if tool_name == "dexscreener_search":
            query = args.get("query", "")
            r = httpx.get(f"https://api.dexscreener.com/latest/dex/search?q={query}", timeout=10.0)
            pairs = r.json().get("pairs", [])[:8]
            results = [{
                "name": p.get("baseToken", {}).get("name"),
                "symbol": p.get("baseToken", {}).get("symbol"),
                "price_usd": p.get("priceUsd"),
                "chain": p.get("chainId"),
                "dex": p.get("dexId"),
                "volume_24h": p.get("volume", {}).get("h24"),
                "liquidity_usd": p.get("liquidity", {}).get("usd"),
                "market_cap": p.get("marketCap"),
                "price_change_24h": p.get("priceChange", {}).get("h24"),
                "url": p.get("url"),
            } for p in pairs]
            return json.dumps({"pairs": results, "source": "dexscreener"})

        if tool_name == "dexscreener_token_lookup":
            token_address = args.get("token_address", "")
            chain = args.get("chain", "")
            if chain:
                r = httpx.get(f"https://api.dexscreener.com/token-pairs/v1/{chain}/{token_address}", timeout=10.0)
            else:
                r = httpx.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}", timeout=10.0)
            data = r.json()
            pairs_raw = data if isinstance(data, list) else data.get("pairs", [])
            pairs = pairs_raw[:8]
            results = [{
                "name": p.get("baseToken", {}).get("name"),
                "symbol": p.get("baseToken", {}).get("symbol"),
                "price_usd": p.get("priceUsd"),
                "chain": p.get("chainId"),
                "dex": p.get("dexId"),
                "volume_24h": p.get("volume", {}).get("h24"),
                "liquidity_usd": p.get("liquidity", {}).get("usd"),
                "market_cap": p.get("marketCap"),
                "price_change_24h": p.get("priceChange", {}).get("h24"),
                "url": p.get("url"),
            } for p in pairs]
            return json.dumps({"token": token_address, "chain": chain or "all", "pairs": results, "source": "dexscreener"})

        if tool_name == "dexscreener_trending":
            r = httpx.get("https://api.dexscreener.com/token-boosts/top/v1", timeout=10.0)
            tokens = r.json()[:12] if isinstance(r.json(), list) else []
            results = [{
                "chain": t.get("chainId"),
                "token_address": t.get("tokenAddress"),
                "boost_amount": t.get("totalAmount"),
                "description": t.get("description", ""),
                "url": t.get("url"),
            } for t in tokens]
            return json.dumps({"trending": results, "source": "dexscreener"})

        if tool_name == "dexscreener_pair":
            chain = args.get("chain", "")
            pair_address = args.get("pair_address", "")
            r = httpx.get(f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}", timeout=10.0)
            data = r.json()
            pairs = data.get("pairs", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            if not pairs:
                return json.dumps({"error": f"Pair not found: {chain}/{pair_address}"})
            p = pairs[0]
            result = {
                "name": p.get("baseToken", {}).get("name"),
                "symbol": f"{p.get('baseToken', {}).get('symbol')}/{p.get('quoteToken', {}).get('symbol')}",
                "price_usd": p.get("priceUsd"),
                "chain": p.get("chainId"),
                "dex": p.get("dexId"),
                "volume_24h": p.get("volume", {}).get("h24"),
                "liquidity_usd": p.get("liquidity", {}).get("usd"),
                "market_cap": p.get("marketCap"),
                "fdv": p.get("fdv"),
                "price_change_5m": p.get("priceChange", {}).get("m5"),
                "price_change_1h": p.get("priceChange", {}).get("h1"),
                "price_change_24h": p.get("priceChange", {}).get("h24"),
                "url": p.get("url"),
                "source": "dexscreener",
            }
            return json.dumps(result)


        # ── Hyperliquid (local scraper, needs wallet config) ─────
        if tool_name.startswith("get_hl_") or tool_name.startswith("place_hl_") or \
           tool_name in ("close_hl_position", "cancel_hl_order", "set_hl_leverage", "approve_hl_builder_fee"):
            try:
                from sentinel.scrapers import hyperliquid as hl
                dispatch = {
                    "get_hl_positions": lambda: hl.get_hl_positions(),
                    "get_hl_account_info": lambda: hl.get_hl_account_info(),
                    "get_hl_open_orders": lambda: hl.get_hl_open_orders(),
                    "get_hl_orderbook": lambda: hl.get_hl_orderbook(**args),
                    "get_hl_config": lambda: hl.get_hl_config(),
                    "place_hl_order": lambda: hl.place_hl_order(**args),
                    "close_hl_position": lambda: hl.close_hl_position(**args),
                    "cancel_hl_order": lambda: hl.cancel_hl_order(**args),
                    "set_hl_leverage": lambda: hl.set_hl_leverage(**args),
                    "approve_hl_builder_fee": lambda: hl.approve_hl_builder_fee(),
                    "get_hl_tradfi_assets": lambda: hl.get_hl_tradfi_assets(),
                    "get_hl_tradfi_price": lambda: hl.get_hl_tradfi_price(**args),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except ImportError:
                return json.dumps({"error": "hyperliquid-python-sdk not installed. Run: pip install hyperliquid-python-sdk eth-account"})
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Technical Analysis (local, uses YFinance/Aster klines) ─
        if tool_name in ("get_ta_indicators", "get_ta_signal", "get_klines"):
            try:
                from sentinel.scrapers import ta as ta_engine
                if tool_name == "get_ta_indicators":
                    result = ta_engine.compute_indicators(
                        args.get("symbol", "BTC"),
                        interval=args.get("interval", "5m"),
                        venue=args.get("venue", "hl"),
                    )
                elif tool_name == "get_ta_signal":
                    result = ta_engine.get_ta_summary(
                        args.get("symbol", "BTC"),
                        interval=args.get("interval", "5m"),
                        venue=args.get("venue", "hl"),
                    )
                elif tool_name == "get_klines":
                    df = ta_engine.klines_to_df(
                        args.get("symbol", "BTC"),
                        interval=args.get("interval", "5m"),
                        limit=args.get("limit", 50),
                        venue=args.get("venue", "hl"),
                    )
                    if df is not None:
                        records = df.tail(args.get("limit", 50)).reset_index().to_dict("records")
                        # Convert timestamps to strings
                        for r in records:
                            for k, v in r.items():
                                if hasattr(v, 'isoformat'):
                                    r[k] = v.isoformat()
                        result = {"symbol": args.get("symbol", "BTC"), "candles": len(records), "data": records}
                    else:
                        result = {"error": f"No kline data for {args.get('symbol', 'BTC')}"}
                return json.dumps(result)
            except ImportError as e:
                return json.dumps({"error": f"TA dependencies missing: {e}. Run: pip install pandas yfinance"})
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Quantitative Analysis (local, uses klines from ta.py) ──
        if tool_name in ("get_risk_metrics", "get_timeseries_forecast", "get_ml_signals",
                        "get_options_analysis", "get_options_expirations", "get_options_chain"):
            try:
                if tool_name == "get_risk_metrics":
                    from sentinel.scrapers.risk import get_risk_metrics
                    result = get_risk_metrics(
                        args.get("symbol", "BTC"),
                        interval=args.get("interval", "1d"),
                        venue=args.get("venue", "hl"),
                    )
                elif tool_name == "get_timeseries_forecast":
                    from sentinel.scrapers.timeseries import get_timeseries_forecast
                    result = get_timeseries_forecast(
                        args.get("symbol", "BTC"),
                        interval=args.get("interval", "1d"),
                        venue=args.get("venue", "hl"),
                    )
                elif tool_name == "get_ml_signals":
                    from sentinel.scrapers.ml_signals import get_ml_signals
                    result = get_ml_signals(
                        args.get("symbol", "BTC"),
                        interval=args.get("interval", "1d"),
                        venue=args.get("venue", "hl"),
                    )
                elif tool_name == "get_options_analysis":
                    from sentinel.scrapers.options import get_options_analysis
                    result = get_options_analysis(args.get("symbol", "AAPL"))
                elif tool_name == "get_options_expirations":
                    from sentinel.scrapers.options import get_options_expirations
                    result = get_options_expirations(args.get("symbol", "AAPL"))
                elif tool_name == "get_options_chain":
                    from sentinel.scrapers.options import get_options_chain
                    result = get_options_chain(
                        symbol=args.get("symbol", "AAPL"),
                        expiry=args.get("expiry"),
                        option_type=args.get("option_type", "both"),
                        min_strike=args.get("min_strike"),
                        max_strike=args.get("max_strike"),
                        near_money=args.get("near_money"),
                    )
                return json.dumps(result)
            except ImportError as e:
                return json.dumps({"error": f"Quant dependencies missing: {e}. Run: pip install statsmodels arch scikit-learn"})
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Portfolio Tracker ──────────────────────────────────────
        if tool_name in ("get_portfolio_summary", "get_portfolio_risk"):
            try:
                from sentinel.scrapers import portfolio
                if tool_name == "get_portfolio_summary":
                    return json.dumps(portfolio.get_portfolio_summary())
                elif tool_name == "get_portfolio_risk":
                    return json.dumps(portfolio.get_portfolio_risk())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Usage Tracker ──────────────────────────────────────────
        if tool_name == "get_usage_summary":
            try:
                from sentinel.scrapers import usage
                period = args.get("period", "today")
                return json.dumps(usage.get_usage_summary(period))
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── FRED (needs API key from config) ──────────────────────
        if tool_name in ("get_fred_series", "search_fred", "get_economic_dashboard", "get_yield_curve"):
            try:
                from sentinel.scrapers import fred
                if tool_name == "get_fred_series":
                    return json.dumps(fred.get_fred_series(**args))
                elif tool_name == "search_fred":
                    return json.dumps(fred.search_fred(**args))
                elif tool_name == "get_economic_dashboard":
                    return json.dumps(fred.get_economic_dashboard())
                elif tool_name == "get_yield_curve":
                    return json.dumps(fred.get_yield_curve())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Y2 Intelligence (needs API key) ───────────────────────
        if tool_name in ("get_news_sentiment", "get_news_recap", "get_intelligence_reports",
                         "get_report_detail", "get_y2_feeds", "get_report_audio", "list_y2_profiles"):
            try:
                from sentinel.scrapers import y2
                # v0.9.2: TOOL_SCHEMA exposes "query=" but y2.get_news_sentiment() takes
                # "topics=".  Map here so the schema mismatch doesn't crash end users.
                def _news_sentiment_call():
                    _args = dict(args)
                    if "query" in _args and "topics" not in _args:
                        _args["topics"] = _args.pop("query")
                    return y2.get_news_sentiment(**_args)
                dispatch = {
                    "get_news_sentiment": _news_sentiment_call,
                    "get_news_recap": lambda: y2.get_news_recap(**args),
                    "get_intelligence_reports": lambda: y2.get_intelligence_reports(**args),
                    "get_report_detail": lambda: y2.get_report_detail(**args),
                    # v0.9.2: three Y2 tools were in TOOL_SCHEMAS but not dispatched locally;
                    # they would silently fall through to the gateway even though they need
                    # the user's local Y2_API_KEY.
                    "get_y2_feeds": lambda: y2.get_y2_feeds(),
                    "get_report_audio": lambda: y2.get_report_audio(**args),
                    "list_y2_profiles": lambda: y2.list_y2_profiles(),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── X / Twitter (needs X_BEARER_TOKEN) ────────────────────
        if tool_name == "search_x":
            try:
                import os as _os
                from sentinel.scrapers.x import XScraper
                token = _os.getenv("X_BEARER_TOKEN", "").strip()
                if not token:
                    return json.dumps({
                        "error": "X_BEARER_TOKEN not set. Add it with 'sentinel add x' or "
                                 "set X_BEARER_TOKEN in your environment.",
                        "tool": "search_x",
                    })
                query = args.get("query", "")
                max_results = args.get("max_results", 10)
                result = XScraper(token).search_tweets(query, max_results)
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Elfa AI (needs API key) ───────────────────────────────
        if tool_name in ("get_trending_tokens", "get_top_mentions", "search_mentions",
                         "get_trending_narratives", "get_token_news"):
            try:
                from sentinel.scrapers import elfa
                # v0.9.2: TOOL_SCHEMA exposes "query=" for search_mentions but
                # elfa.search_mentions() takes "keywords=".  Map here so the schema
                # mismatch doesn't produce a TypeError on every LLM call.
                def _search_mentions_call():
                    _args = dict(args)
                    if "query" in _args and "keywords" not in _args:
                        _args["keywords"] = _args.pop("query")
                    return elfa.search_mentions(**_args)
                dispatch = {
                    "get_trending_tokens": lambda: elfa.get_trending_tokens(**args),
                    "get_top_mentions": lambda: elfa.get_top_mentions(**args),
                    "search_mentions": _search_mentions_call,
                    "get_trending_narratives": lambda: elfa.get_trending_narratives(**args),
                    "get_token_news": lambda: elfa.get_token_news(**args),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Aster DEX (needs API key + secret) ────────────────────
        if tool_name.startswith("aster_"):
            try:
                from sentinel.scrapers import aster
                dispatch = {
                    # ── Public / read-only ──
                    "aster_ticker": lambda: aster.aster_ticker(**args),
                    "aster_orderbook": lambda: aster.aster_orderbook(**args),
                    "aster_klines": lambda: aster.aster_klines(**args),
                    "aster_funding_rate": lambda: aster.aster_funding_rate(**args),
                    "aster_exchange_info": lambda: aster.aster_exchange_info(**args),
                    "aster_ping": lambda: aster.aster_ping(),
                    # ── Authenticated read ──
                    "aster_balance": lambda: aster.aster_balance(),
                    "aster_positions": lambda: aster.aster_positions(**args),
                    "aster_config": lambda: aster.aster_config(),
                    "aster_diagnose": lambda: aster.aster_diagnose(),
                    # v0.9.2: six Aster tools were in TOOL_SCHEMAS but missing from this
                    # dispatch dict — they fell through to the gateway even though they
                    # require the user's local ASTER_API_KEY/SECRET and would always fail
                    # at the gateway (no user credentials there).
                    "aster_account_info": lambda: aster.aster_account_info(),
                    "aster_open_orders": lambda: aster.aster_open_orders(**args),
                    # ── Trading ──
                    "aster_place_order": lambda: aster.aster_place_order(**args),
                    "aster_cancel_order": lambda: aster.aster_cancel_order(**args),
                    "aster_cancel_all_orders": lambda: aster.aster_cancel_all_orders(**args),
                    "aster_set_leverage": lambda: aster.aster_set_leverage(**args),
                    # v0.9.5: three Aster tools existed in aster.py but were missing from
                    # this dispatch dict — the LLM agent could never call them.
                    "aster_place_order_confirmed": lambda: aster.aster_place_order_confirmed(**args),
                    "aster_countdown_cancel": lambda: aster.aster_countdown_cancel(**args),
                    "aster_place_trailing_stop": lambda: aster.aster_place_trailing_stop(**args),
                    "aster_order_history": lambda: aster.aster_order_history(**args),
                    "aster_trade_history": lambda: aster.aster_trade_history(**args),
                    "aster_set_margin_mode": lambda: aster.aster_set_margin_mode(**args),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Polymarket — shelved until v0.7.7 (tools tested in sentinel-sdk-test) ──
        # if tool_name.startswith("polymarket_") or tool_name.startswith("get_polymarket_") or \
        #    tool_name in ("buy_polymarket", "sell_polymarket", "search_polymarket",
        #                  "place_polymarket_limit", "cancel_polymarket_order", "cancel_all_polymarket_orders"):
        #     try:
        #         from sentinel.scrapers import polymarket as pm
        #         dispatch = {
        #             "get_polymarket_markets": lambda: pm.get_polymarket_markets(**args),
        #             "search_polymarket": lambda: pm.search_polymarket(**args),
        #             "get_polymarket_orderbook": lambda: pm.get_polymarket_orderbook(**args),
        #             "get_polymarket_price": lambda: pm.get_polymarket_price(**args),
        #             "get_polymarket_positions": lambda: pm.get_polymarket_positions(),
        #             "buy_polymarket": lambda: pm.buy_polymarket(**args),
        #             "sell_polymarket": lambda: pm.sell_polymarket(**args),
        #             "place_polymarket_limit": lambda: pm.place_polymarket_limit(**args),
        #             "cancel_polymarket_order": lambda: pm.cancel_polymarket_order(**args),
        #             "cancel_all_polymarket_orders": lambda: pm.cancel_all_polymarket_orders(),
        #         }
        #         if tool_name in dispatch:
        #             return json.dumps(dispatch[tool_name]())
        #     except Exception as e:
        #         return json.dumps({"error": str(e), "tool": tool_name})

        # ── Telegram / Discord — shelved (ghost code removed in v0.9.2) ──────────
        # telegram.py and discord.py import from automation.* which is a mono-repo
        # module not shipped in the SDK pip package.  The schemas were already removed
        # from TOOL_SCHEMAS so the LLM cannot call these.  The dispatch blocks have
        # been removed to prevent confusing ImportError messages if somehow called.

    except Exception as e:
        return json.dumps({"error": str(e), "tool": tool_name})

    return None  # Not a direct tool — fall through to gateway


# ══════════════════════════════════════════════════════════════
# Markdown → Rich Converter
# ══════════════════════════════════════════════════════════════

def _md_to_rich(text: str) -> str:
    """Convert markdown formatting to Rich markup for terminal display."""
    text = re.sub(r'^---+$', '[dim]' + '─' * 60 + '[/dim]', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'[bold]\1[/bold]', text)
    text = re.sub(r'^### (.+)$', r'[bold green]\1[/bold green]', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'[bold cyan]\1[/bold cyan]', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'[bold white]\1[/bold white]', text, flags=re.MULTILINE)
    text = re.sub(r'^- ', '  • ', text, flags=re.MULTILINE)
    text = re.sub(r'`([^`]+)`', r'[bold cyan]\1[/bold cyan]', text)
    return text


# ══════════════════════════════════════════════════════════════
# 402 Quota / Payment Handler
# ══════════════════════════════════════════════════════════════

def _handle_402(resp_dict: dict) -> bool:
    """Detect a gateway 402 response and render an amber info panel.

    Returns True if the response was a 402 (caller should ``continue`` the REPL
    loop); False if it was a different kind of error and the caller should handle
    it normally.

    Gateway 402 shapes:
    - ``error == "quota_exceeded"``  → free-tier weekly prompt cap hit
    - ``error == "payment_failed"``  → card on file was declined
    """
    err_code = resp_dict.get("error")
    if err_code not in ("quota_exceeded", "payment_failed"):
        return False

    prompt_limit = resp_dict.get("prompt_limit", 10)
    resets_at = resp_dict.get("resets_at", "")

    # Humanize the reset date: ISO 8601 → "Tue, Jun 24 · 6d".
    reset_str = ""
    if resets_at:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
            days = max(0, (dt - datetime.now(timezone.utc)).days)
            reset_str = dt.strftime("%a, %b ") + str(dt.day) + (f" · {days}d" if days else " · today")
        except Exception:
            reset_str = resets_at[:10]

    if err_code == "quota_exceeded":
        lines = [f"You've used all [bold]{prompt_limit}[/] free prompts this week."]
        if reset_str:
            lines.append(f"[s.dim]Resets {reset_str}[/]")
        lines += [
            "",
            "Add a payment method for [bold]unlimited[/] access —",
            "pay-as-you-go, flat 20%, no subscription.",
            "",
            "[bold]→ Type  [cyan]upgrade[/]  to add a card[/]",
        ]
        title = "[bold yellow]⚡ Free limit reached[/]"
        border = "yellow"
    else:  # payment_failed
        lines = [
            "[bold]Your payment method failed.[/]",
            "Update your card to keep going:",
            "",
            "[bold]→ Type  [cyan]upgrade[/]  to update payment[/]",
        ]
        title = "[bold red]Payment failed[/]"
        border = "red"

    console.print(Panel(
        "\n".join(lines),
        title=title,
        title_align="left",
        border_style=border,
        box=box.ROUNDED,
        padding=(1, 3),
    ))
    console.print()
    return True


def _do_upgrade(api_key: str = "") -> None:
    """Fetch the real Stripe upgrade link from the gateway and open it in the browser.

    Calls POST /api/v1/billing/subscribe (authenticated). The gateway returns a Stripe
    Payment Link (buy.stripe.com/...) with the user's client_reference_id attached; after
    the user adds a card on Stripe's hosted page, the checkout.session.completed webhook
    flips them to unlimited. No website pages involved — Stripe hosts the whole flow.
    """
    import webbrowser
    from sentinel.api._http import load_api_key
    key = load_api_key() or api_key
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/api/v1/billing/subscribe",
            headers={"X-API-Key": key} if key else {},
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        if resp.status_code == 200:
            url = resp.json().get("checkout_url", "")
            if url:
                console.print(Panel(
                    "Opening Stripe checkout in your browser…\n\n"
                    f"If it doesn't open, paste this link:\n[bold cyan]{url}[/]\n\n"
                    "[s.dim]Add a card → unlimited prompts, pay-as-you-go at a flat 20%. "
                    "No subscription, cancel anytime.[/]",
                    title="[bold]⚡ Upgrade[/]", title_align="left",
                    border_style="#5fd7ff", box=box.ROUNDED, padding=(1, 3),
                ))
                console.print()
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                return
            console.print("  [s.error]No checkout link returned by the gateway.[/]\n")
            return
        console.print(f"  [s.error]Couldn't start checkout (HTTP {resp.status_code}). Try again shortly.[/]\n")
    except Exception as e:
        console.print(f"  [s.error]Upgrade failed: {e}[/]\n")


def _fetch_billing_status(api_key: str = "") -> dict:
    """Fetch the full billing/status dict (payment_status, prompts_used, prompt_limit, ...).

    CRITICAL (v0.8.9 Bug B fix): authenticate with the SAME key the LLM call uses —
    load_api_key() reads ~/.sentinel/api_key, which is the credential _gateway_llm_request
    sends on /api/v1/llm/chat. The free-tier gate counts prompts under THAT user, so the
    meter must read THAT user too. (The chat config's "sentinel_api_key" can be a different
    key → a different user → the 0/10 bug.) Returns {} on any error.
    """
    from sentinel.api._http import load_api_key
    key = load_api_key() or api_key
    if not key:
        return {}
    try:
        resp = httpx.get(
            f"{GATEWAY_URL}/api/v1/billing/status",
            headers={"X-API-Key": key},
            timeout=httpx.Timeout(8.0, connect=5.0),
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


# ══════════════════════════════════════════════════════════════
# Dashboard — Mirrors main.py's _print_status()
# ══════════════════════════════════════════════════════════════

def _print_dashboard(config: dict, gateway_ok: bool):
    """Print the full Infrastructure + Data Sources + Agents dashboard."""
    provider = config.get("ai_provider", "anthropic")
    ai_key = config.get("ai_key", "")
    detected = _detect_provider(ai_key) if ai_key else None
    model = _resolve_model(config, provider)

    # Refresh live billing/quota for the line tied under the LLM line (boot + on `clear`).
    if gateway_ok:
        config["billing_status"] = _fetch_billing_status(config.get("sentinel_api_key", ""))

    # ── LLM confirmation line (matches Python folder) ─────────
    if detected:
        provider_id, short_label, full_label, emoji = detected
        console.print(f"  [green]✓ LLM: {short_label} → {provider_id}/{model}[/]")
    else:
        console.print(f"  [s.error]✗ LLM: No API key configured[/]")

    # ── Billing/quota line — tied directly under the LLM line (per sentinel_example.md) ──
    billing = config.get("billing_status", {})
    if billing.get("payment_status") == "active":
        console.print("  [green]✓[/] [dim]Pay-as-you-go · Unlimited[/]")
    elif billing.get("prompts_used") is not None:
        _limit = int(billing.get("prompt_limit", 10))
        _remaining = max(0, _limit - int(billing.get("prompts_used", 0)))
        _color = "green" if _remaining > 3 else ("yellow" if _remaining > 0 else "red")
        console.print(f"  [{_color}]✓[/] [dim]Free tier · {_remaining}/{_limit} prompts left this week[/]")

    # ── Infrastructure Panel ──────────────────────────────────
    infra = Table(
        title="[bold cyan]📡 Infrastructure[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    infra.add_column("Component", style="bold white", min_width=18)
    infra.add_column("Status", min_width=20)
    infra.add_column("Details", style="dim")

    # LLM
    if detected:
        infra.add_row("🤖 LLM", f"[green]● {detected[1]}[/]", "Ready")
    else:
        infra.add_row("🤖 LLM", "[red]✗ No API key[/]", "Run sentinel-setup")

    # Gateway
    if gateway_ok:
        billing = config.get("billing_status", {})
        payment_status = billing.get("payment_status", config.get("payment_status", "free"))
        if payment_status in ("free", "") or payment_status is None:
            prompts_used = billing.get("prompts_used")
            prompt_limit = int(billing.get("prompt_limit", 10))
            if prompts_used is not None:
                # Match the under-LLM line: show REMAINING with the same green→yellow→red coloring.
                remaining = max(0, prompt_limit - int(prompts_used))
                color = "green" if remaining > 3 else ("yellow" if remaining > 0 else "red")
                detail = f"Free tier · [{color}]{remaining}/{prompt_limit}[/] prompts left · Cloud Run"
            else:
                detail = "Free tier · Cloud Run"
        else:
            detail = "Pay-as-you-go · Unlimited · Cloud Run"
        infra.add_row("🌐 Gateway", f"[green]● Connected[/]", detail)
    else:
        infra.add_row("🌐 Gateway", "[dim]○ Pending[/]", "Auto-connects on first query")

    # Tools
    infra.add_row("🔧 Tools", f"[green]● {len(TOOL_SCHEMAS)} tools loaded[/]", "Crypto · Stocks · Macro · Social · Trading")

    # Config
    infra.add_row("🔑 Config", f"[green]● ~/.sentinel/config[/]", "Zero-trust auth")

    console.print()
    console.print(infra)

    # ── Data Sources Panel ────────────────────────────────────
    ds = Table(
        title="[bold cyan]📊 Data Sources[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    ds.add_column("Source", style="bold white", min_width=18)
    ds.add_column("Status", min_width=20)
    ds.add_column("Details", style="dim")

    # Always-available sources (no key needed)
    ds.add_row("🪙 CoinGecko", "[green]● Always available[/]", "10,000+ crypto prices + top N + search")
    ds.add_row("📈 YFinance", "[green]● Always available[/]", "stocks + ETFs + analyst recs + news")
    ds.add_row("📊 DexScreener", "[green]● Always available[/]", "DEX pair data + trending + boosted tokens")

    # Config-dependent sources — check if user configured keys
    def _key_status(key_name: str, label: str, detail: str, add_cmd: str):
        """Show green if key is configured, yellow if needs setup."""
        val = config.get(key_name, os.environ.get(key_name, ""))
        if val:
            ds.add_row(label, "[green]● Ready[/]", detail)
        else:
            ds.add_row(label, "[yellow]○ Needs key[/]", f"{detail} · [dim]add {add_cmd}[/]")

    _key_status("fred_api_key", "🏛️ FRED", "GDP, CPI, rates, yield curve, VIX", "fred")
    _key_status("y2_api_key", "📰 Y2 Intelligence", "news sentiment + recaps + reports", "y2")
    _key_status("elfa_api_key", "🔮 Elfa AI", "trending tokens + social mentions", "elfa")
    _key_status("x_bearer_token", "🐦 X (Twitter)", "tweets + trends + sentiment", "x")

    # Exchange status — check wallet/key config
    hl_ok = config.get("hyperliquid_wallet") or os.environ.get("HYPERLIQUID_WALLET_ADDRESS", "")
    ds.add_row("⚡ Hyperliquid",
               "[green]● Ready[/]" if hl_ok else "[yellow]○ Needs config[/]",
               "perp futures + orders + positions" + ("" if hl_ok else " · [dim]add hl[/]"))

    aster_ok = config.get("aster_api_key") or os.environ.get("ASTER_API_KEY", "")
    ds.add_row("🌟 Aster DEX",
               "[green]● Ready[/]" if aster_ok else "[yellow]○ Needs config[/]",
               "futures + orderbook + klines + leverage" + ("" if aster_ok else " · [dim]add aster[/]"))

    # Polymarket — shelved, coming in v0.7.7
    # pm_ok = config.get("polymarket_key") or os.environ.get("POLYMARKET_PRIVATE_KEY", "")
    # ds.add_row("🎲 Polymarket",
    #            "[green]● Ready[/]" if pm_ok else "[yellow]○ Needs config[/]",
    #            "browse + bet + positions + orders" + ("" if pm_ok else " · [dim]add polymarket[/]"))
    # Telegram + Discord: archived — re-enable when tested
    # tg_ok = config.get("tg_api_id") or os.environ.get("TELEGRAM_API_ID", "")
    # dc_ok = config.get("discord_token") or os.environ.get("DISCORD_BOT_TOKEN", "")

    console.print(ds)

    # Count connected sources
    connected = 3  # CoinGecko + YFinance + DexScreener always
    for k in ("fred_api_key", "y2_api_key", "elfa_api_key", "x_bearer_token"):
        if config.get(k) or os.environ.get(k, ""):
            connected += 1
    if hl_ok: connected += 1
    if aster_ok: connected += 1
    # if pm_ok: connected += 1  # Polymarket shelved
    # tg/dc archived — uncomment when re-enabled
    # if tg_ok: connected += 1
    # if dc_ok: connected += 1
    console.print(f"  [dim]{connected} data sources connected[/]")
    console.print()
    console.print("  Type a question · [bold]model[/] to switch AI model · [bold]'help'[/] for commands.")
    console.print()


# ══════════════════════════════════════════════════════════════
# First-Run Setup (prompt for AI key if missing)
# ══════════════════════════════════════════════════════════════

def _first_run_setup() -> dict:
    """If no AI key is configured, prompt for one (like main.py does)."""
    config = _load_config()

    if config.get("ai_key"):
        return config

    console.print()
    console.print("  [bold]First-time setup[/] — paste your AI provider API key.")
    console.print("  [s.dim]Supports: Anthropic (sk-ant-...), OpenAI (sk-...), Google (AIza...), xAI (xai-...)[/]")
    console.print()

    while True:
        try:
            key = console.input("  [s.cyan.bold]🔑 API Key →[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [bold]Goodbye![/]\n")
            sys.exit(0)

        if not key:
            continue

        detected = _detect_provider(key)
        if not detected:
            console.print("  [s.error]✗ Unrecognized key prefix.[/] Try again.\n")
            continue

        provider_id, short_label, full_label, emoji = detected
        config["ai_key"] = key
        config["ai_provider"] = provider_id
        _save_config(config)
        # Also save to dedicated file so ChatResource.load_ai_key() finds it
        from sentinel.api._http import save_ai_key
        save_ai_key(key)
        console.print(f"  [green]✓ {emoji} {full_label} detected — saved to ~/.sentinel/config[/]\n")
        break

    # Try gateway registration
    with console.status("[s.cyan]  Registering with gateway...[/]", spinner="dots"):
        result = _register_with_gateway(config["ai_key"])
    if result.get("api_key"):
        config["sentinel_api_key"] = result["api_key"]
        config["tier"] = result.get("tier", "free")
        _save_config(config)
        console.print("  [green]✓ Gateway connected[/]")
    else:
        console.print("  [s.dim]○ Gateway offline — will retry on next launch[/]")

    return config


# ══════════════════════════════════════════════════════════════
# Config → Environment Bridge
# ══════════════════════════════════════════════════════════════

_CONFIG_TO_ENV_MAP = {
    "hyperliquid_wallet": "HYPERLIQUID_WALLET_ADDRESS",
    "hyperliquid_key": "HYPERLIQUID_PRIVATE_KEY",
    "aster_api_key": "ASTER_API_KEY",
    "aster_api_secret": "ASTER_API_SECRET",
    "polymarket_key": "POLYMARKET_PRIVATE_KEY",
    "polymarket_funder": "POLYMARKET_FUNDER",
    "fred_api_key": "FRED_API_KEY",
    "y2_api_key": "Y2_API_KEY",
    "elfa_api_key": "ELFA_API_KEY",
    "x_bearer_token": "X_BEARER_TOKEN",
    "tg_api_id": "TELEGRAM_API_ID",
    "tg_api_hash": "TELEGRAM_API_HASH",
    "discord_token": "DISCORD_BOT_TOKEN",
    "eodhd_api_key": "EODHD_API_KEY",
}


def _bridge_config_to_env(config: dict):
    """Bridge ~/.sentinel/config keys → os.environ so tools can find them.

    Called on boot AND after every `add <service>` so that tools configured
    mid-session work immediately without restarting sentinel.
    """
    for config_key, env_key in _CONFIG_TO_ENV_MAP.items():
        val = config.get(config_key, "")
        if val:
            os.environ[env_key] = str(val)


# ══════════════════════════════════════════════════════════════
# Interactive Chat REPL
# ══════════════════════════════════════════════════════════════

def run_chat(config: dict):
    """
    Launch the interactive AI agent chat.

    Provides a full-screen REPL similar to `uv run main.py` in the Python folder,
    but powered by the Go gateway for tool execution.
    """
    ai_key = config.get("ai_key", "")
    api_key = config.get("sentinel_api_key", "")

    # v0.8.9 Bug B fix — UNIFY IDENTITY. The LLM call + free-tier gate authenticate with
    # load_api_key() (~/.sentinel/api_key); the chat config's key can be a *different* key →
    # a different gateway user → the "0/10 forever" bug. Make the chat config + tool calls use
    # the SAME canonical key so every gateway call (LLM, tools, billing) resolves to ONE user.
    try:
        from sentinel.api._http import load_api_key
        _canonical = load_api_key()
        if _canonical and _canonical != api_key:
            api_key = _canonical
            config["sentinel_api_key"] = _canonical
            _save_config(config)
    except Exception:
        pass
    provider = config.get("ai_provider", "anthropic")

    # Fallback: check ~/.sentinel/ai_key flat file (cli.py saves here)
    if not ai_key:
        try:
            from sentinel.api._http import load_ai_key
            ai_key = load_ai_key() or ""
            if ai_key:
                # Sync back to JSON config so this fallback isn't needed next time
                config["ai_key"] = ai_key
                detected = _detect_provider(ai_key)
                if detected:
                    provider = detected[0]
                    config["ai_provider"] = provider
                _save_config(config)
        except Exception:
            pass

    if not ai_key:
        console.print("  [s.error]✗ No AI key configured[/] — run [bold]sentinel[/] to set up.\n")
        return

    # v0.9.4 IDENTITY FIX — ALWAYS register the current ai_key with the gateway at launch, idempotently.
    # (0.9.3 only registered "if not api_key", but upgraded users carry a STALE sentinel_api_key in
    # ~/.sentinel/config from an old/ephemeral-DB session — so the guard skipped, the stale key didn't
    # resolve, and every call fell through to "anonymous": counter stuck at 10/10, usage unbilled.)
    # /auth/ai-key is idempotent (creates-or-returns the account + its canonical Sentinel key for this
    # ai_key), so re-registering a valid key is a no-op and a stale key gets replaced with the right one.
    # The returned key is persisted to ~/.sentinel/api_key, which _gateway_llm_request() and
    # _fetch_billing_status() read for the X-API-Key header.
    if ai_key:
        result = _register_with_gateway(ai_key)
        new_key = result.get("api_key", "")
        if not new_key:
            try:
                from sentinel.api._http import load_api_key as _lk
                new_key = _lk() or ""
            except Exception:
                new_key = ""
        if new_key:
            api_key = new_key
            config["sentinel_api_key"] = new_key
            _save_config(config)

    # ── Animated Boot Sequence ─────────────────────────────────
    console.print(_make_banner())

    gateway_ok = bool(api_key)

    # Bridge config → env on boot
    _bridge_config_to_env(config)

    # ── Staged boot with spinners ─────────────────────────────
    from rich.live import Live
    from rich.text import Text
    import time as _time

    detected = _detect_provider(ai_key) if ai_key else None
    provider_label = detected[1] if detected else "UNKNOWN"

    boot_stages = [
        ("🤖", "Authenticating LLM", f"{provider_label} → {_resolve_model(config, provider)}", 0.3),
        ("🔑", "Loading credentials", f"~/.sentinel/config", 0.2),
        ("🔧", "Initializing tool registry", f"{len(TOOL_SCHEMAS)} tools", 0.25),
        ("📡", "Bridging environment", f"{sum(1 for k in _CONFIG_TO_ENV_MAP if config.get(k))} services", 0.15),
        ("📊", "Connecting data sources", "CoinGecko · YFinance · DexScreener", 0.2),
    ]

    # Count exchange connections
    exchanges = []
    if config.get("hyperliquid_wallet"): exchanges.append("Hyperliquid")
    if config.get("aster_api_key"): exchanges.append("Aster")
    # if config.get("polymarket_key"): exchanges.append("Polymarket")  # archived
    if exchanges:
        boot_stages.append(("⚡", "Connecting exchanges", " · ".join(exchanges), 0.25))

    # Social feeds
    socials = []
    if config.get("x_bearer_token"): socials.append("X")
    if config.get("y2_api_key"): socials.append("Y2")
    if config.get("tg_api_id"): socials.append("Telegram")
    if config.get("discord_token"): socials.append("Discord")
    if socials:
        boot_stages.append(("🐦", "Connecting social feeds", " · ".join(socials), 0.15))

    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    with Live(console=console, refresh_per_second=15, transient=True) as live:
        completed = []
        for i, (icon, label, detail, duration) in enumerate(boot_stages):
            # Animate spinner for this stage
            frames = int(duration / 0.067)  # ~15fps
            for f in range(max(frames, 3)):
                lines = []
                # Show completed stages
                for ci, cl, cd in completed:
                    lines.append(f"  [green]✓[/] {ci} [bold]{cl}[/] [dim]— {cd}[/]")
                # Show current stage with spinner
                spin = spinner_frames[f % len(spinner_frames)]
                lines.append(f"  [cyan]{spin}[/] {icon} [bold]{label}[/] [dim]— {detail}[/]")
                live.update(Text.from_markup("\n".join(lines)))
                _time.sleep(0.067)

            # Do the actual work for this stage
            if "Bridging" in label:
                _bridge_config_to_env(config)

            completed.append((icon, label, detail))

        # Final render — all green
        final_lines = []
        for ci, cl, cd in completed:
            final_lines.append(f"  [green]✓[/] {ci} [bold]{cl}[/] [dim]— {cd}[/]")
        live.update(Text.from_markup("\n".join(final_lines)))
        _time.sleep(0.15)

    # Print final boot summary (persists after Live clears)
    console.print()
    for ci, cl, cd in completed:
        console.print(f"  [green]✓[/] {ci} [bold]{cl}[/] [dim]— {cd}[/]")
    console.print()

    _print_dashboard(config, gateway_ok)

    # ── Session state ─────────────────────────────────
    history: list[dict] = []
    tools = TOOL_SCHEMAS  # always provide schemas — lazy-register on first call
    model_name = _resolve_model(config, provider)
    tool_calls_total = 0
    start_session = time.time()
    gateway_registered = gateway_ok  # track if we've registered

    # ── Session memory ────────────────────────────────
    from sentinel.memory import create_session, save_message, update_session_title, update_session_stats
    session_id = create_session(provider, model_name)
    session_titled = False

    # ── REPL ──────────────────────────────────────────
    while True:
        try:
            console.print("[s.cyan.bold]  ⚡ You →[/] ", end="")
            user_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n\n  [bold]Goodbye![/]\n")
            break

        if not user_input:
            continue

        cmd = user_input.lower().strip()

        # ── Built-in commands ─────────────────────────
        if cmd in ("quit", "exit", "q"):
            elapsed = time.time() - start_session
            update_session_stats(session_id, tool_calls_total)
            console.print(f"\n  [s.dim]{tool_calls_total} tool calls · {len(history)} messages · {elapsed:.0f}s · session {session_id}[/]")
            console.print("  [bold]Goodbye![/]\n")
            break

        if cmd == "clear":
            history = []
            tool_calls_total = 0
            session_id = create_session(provider, model_name)
            session_titled = False
            console.clear()
            console.print(_make_banner())
            _print_dashboard(config, gateway_ok)
            console.print()
            continue

        if cmd in ("sessions", "history"):
            from sentinel.memory import list_sessions
            sessions = list_sessions(10)
            if not sessions:
                console.print("  [s.dim]No saved sessions yet.[/]\n")
            else:
                console.print()
                console.print("  [bold cyan]📋 Recent Sessions[/]")
                for s in sessions:
                    ts = datetime.fromtimestamp(s['updated_at']).strftime('%b %d %H:%M')
                    active = " [green]← active[/]" if s['id'] == session_id else ""
                    console.print(f"  [s.cyan]{s['id']}[/]  {ts}  [dim]{s['message_count']} msgs · {s['tool_calls']} tools[/]  {s['title']}{active}")
                console.print()
            continue

        if cmd == "tools":
            console.print()
            for t in TOOL_SCHEMAS:
                console.print(f"  [s.cyan]{t['name']:<30}[/] [s.dim]{t['description'][:65]}[/]")
            console.print()
            continue

        if cmd in ("tools diagnose", "diagnose"):
            _run_tool_smoke_test(api_key)
            continue

        if cmd == "status":
            config = _load_config()  # refresh
            _print_dashboard(config, gateway_ok)
            continue

        if cmd in ("approve-builder", "approve builder", "approve_builder") or cmd.startswith("approve-builder ") or cmd.startswith("approve builder "):
            # Check if user specified a venue
            venue = "hl"  # default
            if "aster" in cmd.lower():
                venue = "aster"

            if venue == "aster":
                from sentinel.cli import _approve_aster_builder_fee_step
                _approve_aster_builder_fee_step(config)
                continue

            # ── Hyperliquid (default) ──
            try:
                from sentinel.scrapers.hyperliquid import _check_builder_fee_status
                status = _check_builder_fee_status()
                if status.get("approved"):
                    console.print("\n  [green]✓ Builder fee already approved![/]\n")
                    continue
            except Exception:
                pass

            APPROVAL_URL = "https://api.hyper-sentinel.com/approve-builder"
            console.print(Panel(
                "Opening builder fee approval in your browser…\n\n"
                "Connect your wallet (MetaMask/Ledger) and click Approve.\n"
                f"[dim]If it doesn't open, paste this link:[/]\n[bold cyan]{APPROVAL_URL}[/]",
                title="[bold]⚡ Builder Fee[/]", title_align="left",
                border_style="#5fd7ff", box=box.ROUNDED, padding=(1, 3),
            ))
            console.print()
            try:
                import webbrowser
                webbrowser.open(APPROVAL_URL)
            except Exception:
                pass

            from sentinel.cli import _poll_builder_approval
            if _poll_builder_approval(timeout=120):
                config["builder_fee_approved"] = True
                _save_config(config)
                console.print("  [green]✓ All future trades include builder fee.[/]\n")
            else:
                console.print("  [dim]→ Run 'approve-builder' anytime to retry.[/]\n")
            continue

        if cmd in ("upgrade", "subscribe", "billing"):
            _do_upgrade(api_key)
            continue

        if cmd == "model" or cmd.startswith("model "):
            catalog = MODEL_CATALOG.get(provider, [])
            parts = user_input.split(None, 1)
            # Direct shortcut: `model <name>`
            if len(parts) > 1 and parts[1].strip():
                model_name = parts[1].strip()
                config["model"] = model_name
                _save_config(config)
                console.print(f"\n  [green]✓ Model set to[/] [bold]{model_name}[/] [s.dim](saved as default)[/]\n")
                continue
            if not catalog:
                console.print(f"\n  [s.dim]No model list for {provider}.[/]\n")
                continue
            # Interactive picker
            console.print()
            console.print(f"  [bold cyan]🤖 Select model[/] [s.dim]— {provider.upper()} (current: {model_name})[/]")
            for i, m in enumerate(catalog, 1):
                mark = "[green]✓[/]" if m["id"] == model_name else " "
                console.print(f"  [s.cyan]{i}.[/] [bold]{m['label']:<16}[/] {mark} [s.dim]{m['desc']}[/]")
            console.print('  [s.dim]Number → set as default · "N s" → this session only · Enter → cancel[/]')
            console.print("[s.cyan.bold]  model →[/] ", end="")
            try:
                sel = input().strip()
            except (EOFError, KeyboardInterrupt):
                sel = ""
            if not sel:
                console.print("  [s.dim]Cancelled.[/]\n")
                continue
            session_only = sel.lower().endswith(" s")
            num = sel[:-1].strip() if session_only else sel
            try:
                idx = int(num)
                if not (1 <= idx <= len(catalog)):
                    raise ValueError
            except ValueError:
                console.print("  [s.error]✗ Invalid selection[/]\n")
                continue
            model_name = catalog[idx - 1]["id"]
            if session_only:
                console.print(f"  [green]✓[/] Using [bold]{model_name}[/] [s.dim]for this session only[/]\n")
            else:
                config["model"] = model_name
                _save_config(config)
                console.print(f"  [green]✓[/] Default set to [bold]{model_name}[/] [s.dim](saved)[/]\n")
            continue

        if cmd.startswith("add"):
            parts = cmd.split(None, 1)
            if len(parts) > 1:
                service = parts[1].strip()

                # Special: reconfigure LLM API key
                if service == "ai":
                    console.print()
                    console.print("  [bold cyan]🤖 Reconfigure AI Provider[/]")
                    console.print(f"  [s.dim]Current: {provider.upper()} → {model_name}[/]")
                    console.print()
                    console.print("  [s.dim]Paste a new API key (or press Enter to keep current):[/]")
                    console.print("  [s.dim]  sk-ant-xxx  → Anthropic (Claude)[/]")
                    console.print("  [s.dim]  sk-proj-xxx → OpenAI (GPT)[/]")
                    console.print("  [s.dim]  AIza-xxx    → Google (Gemini)[/]")
                    console.print("  [s.dim]  xai-xxx     → xAI (Grok)[/]")
                    console.print("  [s.dim]  sk-xxx      → DeepSeek / Minimax / Moonshot (auto-detected)[/]")
                    console.print("  [s.dim]  hex.alnum   → Zhipu AI (GLM)[/]")
                    console.print()
                    console.print("[s.cyan.bold]  🔑 API Key →[/] ", end="")
                    new_key = input().strip()
                    if new_key:
                        detected = _detect_provider(new_key)
                        if detected:
                            new_provider, provider_label = detected[0], detected[2]
                            ai_key = new_key
                            provider = new_provider
                            # New provider → drop any saved model override, use its default
                            config.pop("model", None)
                            model_name = DEFAULT_MODELS.get(new_provider, "claude-sonnet-4-6")
                            config["ai_key"] = ai_key
                            config["ai_provider"] = provider
                            # Reset gateway key so it re-registers with new AI key
                            config.pop("sentinel_api_key", None)
                            api_key = ""
                            gateway_registered = False
                            _save_config(config)
                            console.print(f"  [green]✓ Switched to {provider_label}[/] → {model_name}")
                        else:
                            console.print("  [s.error]✗ Unrecognized key format[/] — key not changed")
                    else:
                        console.print(f"  [s.dim]Keeping {provider.upper()}[/]")
                    console.print()
                    continue

                from sentinel.cli import _add_service
                _add_service(service)
                config = _load_config()  # refresh after add
                _bridge_config_to_env(config)  # re-bridge so tools work immediately
            else:
                # Show available services
                console.print()
                console.print("  [bold cyan]AI Provider[/]")
                console.print(f"  [s.cyan]add ai[/]            [s.dim]Change LLM provider (current: {provider.upper()})[/]")
                console.print()
                console.print("  [bold cyan]Trading & Prediction Markets[/]")
                console.print("  [s.cyan]add hl[/]            [s.dim]Hyperliquid perp futures[/]")
                # console.print("  [s.cyan]add polymarket[/]    [s.dim]Prediction markets[/]")  # archived
                console.print("  [s.cyan]add aster[/]         [s.dim]Aster DEX futures[/]")
                console.print()
                console.print("  [bold cyan]Data Sources[/]")
                console.print("  [s.cyan]add fred[/]          [s.dim]FRED economic data (GDP, CPI, rates)[/]")
                console.print("  [s.cyan]add x[/]             [s.dim]X/Twitter search & sentiment[/]")
                console.print("  [s.cyan]add y2[/]            [s.dim]Y2 Intelligence news[/]")
                console.print("  [s.cyan]add elfa[/]          [s.dim]Elfa AI social intelligence[/]")
                console.print("  [s.cyan]add eodhd[/]         [s.dim]EODHD historical market data[/]")
                console.print()
            continue

        if cmd in ("help", "?"):
            console.print()
            console.print("  [bold cyan]Chat[/]")
            console.print("  [s.dim]Just type a question — the AI agent will call tools and respond.[/]")
            console.print()
            console.print("  [bold cyan]Configure[/]")
            console.print("  [s.cyan]model[/]        [s.dim]Pick the AI model (e.g. Fable, Opus, Sonnet)[/]")
            console.print("  [s.cyan]add ai[/]       [s.dim]Switch LLM provider / change your AI key[/]")
            console.print("  [s.cyan]add[/]          [s.dim]List available data sources & trading platforms[/]")
            console.print("  [s.cyan]add hl[/]       [s.dim]Configure Hyperliquid trading[/]")
            console.print("  [s.cyan]add fred[/]     [s.dim]Configure FRED economic data[/]")
            console.print("  [s.cyan]add x[/]        [s.dim]Configure X/Twitter search[/]")
            console.print("  [s.cyan]approve-builder[/] [s.dim]Approve HL builder fee (one-time)[/]")
            console.print("  [s.cyan]approve-builder aster[/] [s.dim]Approve Aster builder fee[/]")
            console.print()
            console.print("  [bold cyan]Session[/]")
            console.print("  [s.cyan]clear[/]        [s.dim]Reset conversation context[/]")
            console.print("  [s.cyan]tools[/]        [s.dim]List all available tools[/]")
            console.print("  [s.cyan]status[/]       [s.dim]Show infrastructure dashboard[/]")
            console.print("  [s.cyan]quit[/]         [s.dim]Exit chat[/]")
            console.print()
            continue

        fast_result = _fast_path(user_input)
        if fast_result is not None:
            t0 = time.time()
            console.print()
            elapsed = time.time() - t0
            console.print(Panel(
                fast_result,
                title="[bold]🛡️ Sentinel[/]",
                border_style="#007a8a",
                box=box.ROUNDED,
                subtitle=f"[s.dim]⚡ instant · 0 LLM calls[/]",
                subtitle_align="right",
                padding=(1, 3),
            ))
            console.print()
            # Save to history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": [{"type": "text", "text": fast_result}]})
            save_message(session_id, "user", user_input)
            save_message(session_id, "assistant", fast_result)
            if not session_titled:
                update_session_title(session_id, user_input[:80])
                session_titled = True
            continue

        # ── Agent Tool-Use Loop ───────────────────────
        console.print()
        tool_calls_this_turn: list[str] = []
        t0 = time.time()

        def _on_tool(name: str, args: dict):
            nonlocal tool_calls_total, api_key, gateway_registered
            tool_calls_total += 1

            # Direct tools — ALL scrapers run locally, no gateway needed
            # v0.9.2 DIRECT_TOOLS — every tool in TOOL_SCHEMAS that runs on the user's
            # machine (all 69 schema tools + the get_crypto_top alias).
            # Ghost tg_*/discord_* entries removed; missing tools added.
            DIRECT_TOOLS = {
                # CoinGecko (free, no key)
                "get_crypto_price", "get_crypto_top", "get_crypto_top_n", "search_crypto",
                # YFinance (free, no key)
                "get_stock_price", "get_stock_info", "get_analyst_recs", "get_stock_news", "get_stock_history", "run_stock_analysis",
                # DexScreener (free, no key)
                "dexscreener_search", "dexscreener_token_lookup", "dexscreener_trending", "dexscreener_pair",
                # Hyperliquid (needs wallet; read-only works with HYPERLIQUID_WALLET_ADDRESS)
                "get_hl_positions", "get_hl_account_info", "get_hl_open_orders",
                "get_hl_orderbook", "get_hl_config", "place_hl_order",
                "close_hl_position", "cancel_hl_order", "set_hl_leverage",
                "approve_hl_builder_fee", "get_hl_tradfi_assets", "get_hl_tradfi_price",
                # Technical Analysis (local compute, uses HL/Aster/YFinance data)
                "get_ta_indicators", "get_ta_signal", "get_klines",
                # Quantitative Analysis (local compute)
                "get_risk_metrics", "get_timeseries_forecast", "get_ml_signals",
                "get_options_analysis", "get_options_expirations", "get_options_chain",
                # Portfolio (local aggregation of HL+Aster)
                "get_portfolio_summary", "get_portfolio_risk",
                # FRED (needs FRED_API_KEY)
                "get_fred_series", "search_fred", "get_economic_dashboard", "get_yield_curve",
                # Y2 Intelligence (needs Y2_API_KEY) — v0.9.2: added missing 3 tools
                "get_news_sentiment", "get_news_recap", "get_intelligence_reports", "get_report_detail",
                "get_y2_feeds", "get_report_audio", "list_y2_profiles",
                # X / Twitter (needs X_BEARER_TOKEN) — v0.9.2: added missing dispatch
                "search_x",
                # Elfa AI (needs ELFA_API_KEY)
                "get_trending_tokens", "get_top_mentions", "search_mentions",
                "get_trending_narratives", "get_token_news",
                # Aster DEX (public endpoints need no key; trading needs ASTER_API_KEY+SECRET)
                # v0.9.2: added 6 missing tools that were in TOOL_SCHEMAS but fell through to gateway
                "aster_ticker", "aster_orderbook", "aster_klines", "aster_funding_rate",
                "aster_exchange_info", "aster_balance", "aster_positions",
                "aster_config", "aster_diagnose", "aster_ping",
                "aster_account_info", "aster_open_orders",
                "aster_place_order", "aster_cancel_order", "aster_cancel_all_orders", "aster_set_leverage",
                # Polymarket — archived
                # "get_polymarket_markets", "search_polymarket", "get_polymarket_orderbook",
                # "get_polymarket_price", "get_polymarket_positions", "buy_polymarket",
                # "sell_polymarket", "place_polymarket_limit", "cancel_polymarket_order",
                # "cancel_all_polymarket_orders",
                # Usage / Revenue
                "get_usage_summary",
                # Note: Telegram (tg_*) and Discord (discord_*) tools were removed in v0.9.2.
                # They imported from automation.* which is not shipped in the SDK package.
            }

            # Lazy gateway registration — only for gateway-dependent tools
            if name not in DIRECT_TOOLS and not gateway_registered and not api_key:
                console.print("  [s.dim]⚙ Connecting to gateway...[/]")
                result = _register_with_gateway(ai_key)
                if result.get("api_key"):
                    api_key = result["api_key"]
                    config["sentinel_api_key"] = api_key
                    config["tier"] = result.get("tier", "free")
                    _save_config(config)
                    gateway_registered = True
                    console.print("  [green]✓ Gateway connected[/]")

            arg_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
            console.print(f"  [s.dim]⚙ {name}[/]([s.cyan]{arg_str}[/])")
            tool_calls_this_turn.append(name)

        try:
            # Add user message
            history.append({"role": "user", "content": user_input})
            save_message(session_id, "user", user_input)

            # Auto-title from first user message
            if not session_titled:
                update_session_title(session_id, user_input[:80])
                session_titled = True

            response_text = None

            # First LLM call
            console.print("  [s.cyan]⏳ Sentinel thinking...[/]")
            try:
                if provider == "anthropic":
                    llm_resp = _call_anthropic_streamed(ai_key, model_name, history, tools)
                else:
                    endpoint = PROVIDER_ENDPOINTS.get(provider, PROVIDER_ENDPOINTS["openai"])
                    llm_resp = _call_openai_compat(ai_key, model_name, history, tools, endpoint)
            except KeyboardInterrupt:
                console.print("\n  [s.dim]Cancelled.[/]\n")
                if history and history[-1].get("role") == "user":
                    history.pop()
                continue

            # ── Process Anthropic response ────────────
            if provider == "anthropic":
                if "error" in llm_resp:
                    if _handle_402(llm_resp):
                        if history and history[-1].get("role") == "user":
                            history.pop()
                        continue
                    err = llm_resp["error"]
                    if isinstance(err, dict):
                        err = err.get("message", str(err))
                    console.print(Panel(f"[s.error]⚠ LLM Error[/]\n[s.dim]{err}[/]",
                                        border_style="#662222", box=box.ROUNDED))
                    console.print()
                    if history and history[-1].get("role") == "user":
                        history.pop()
                    continue

                content = llm_resp.get("content", [])
                stop_reason = llm_resp.get("stop_reason", "end_turn")
                history.append({"role": "assistant", "content": content})

                # Tool-use iteration loop
                iteration = 0
                failed_tools: dict = {}
                while stop_reason == "tool_use" and iteration < 15:
                    if time.time() - t0 > RESPONSE_TIME_LIMIT_S:
                        response_text = "⚠ Response time limit reached. Try a simpler query."
                        break
                    iteration += 1
                    tool_uses = [b for b in content if b.get("type") == "tool_use"]
                    thinking = [b["text"] for b in content if b.get("type") == "text" and b.get("text", "").strip()]
                    if thinking:
                        console.print(f"  [s.dim]{' '.join(thinking)}[/]")

                    # Execute tools
                    tool_results = []
                    for tu in tool_uses:
                        _on_tool(tu["name"], tu.get("input", {}))
                        tool_name = tu["name"]
                        if failed_tools.get(tool_name, 0) >= 2:
                            result = json.dumps({"error": f"{tool_name} is temporarily unavailable after repeated failures"})
                        else:
                            result = _execute_tool(api_key, tool_name, tu.get("input", {}))
                            if isinstance(result, str) and "error" in result.lower():
                                failed_tools[tool_name] = failed_tools.get(tool_name, 0) + 1
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": result,
                        })

                    history.append({"role": "user", "content": tool_results})

                    # Next LLM call
                    console.print("  [s.cyan]⏳ Sentinel analyzing...[/]")
                    llm_resp = _call_anthropic_streamed(ai_key, model_name, history, tools)

                    if "error" in llm_resp:
                        if _handle_402(llm_resp):
                            response_text = ""
                            break
                        err = llm_resp["error"]
                        if isinstance(err, dict):
                            err = err.get("message", str(err))
                        response_text = f"⚠ LLM Error: {err}"
                        break

                    content = llm_resp.get("content", [])
                    stop_reason = llm_resp.get("stop_reason", "end_turn")
                    history.append({"role": "assistant", "content": content})

                # Extract final text
                if response_text is None:
                    response_text = "\n".join(
                        b["text"] for b in content if b.get("type") == "text"
                    ) or "(no response)"

            # ── Process OpenAI-compatible response ────
            else:
                if "error" in llm_resp:
                    if _handle_402(llm_resp):
                        if history and history[-1].get("role") == "user":
                            history.pop()
                        continue
                    err = llm_resp["error"]
                    if isinstance(err, dict):
                        err = err.get("message", str(err))
                    console.print(Panel(f"[s.error]⚠ LLM Error[/]\n[s.dim]{err}[/]",
                                        border_style="#662222", box=box.ROUNDED))
                    console.print()
                    if history and history[-1].get("role") == "user":
                        history.pop()
                    continue

                choice = llm_resp.get("choices", [{}])[0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "stop")

                # Tool-use iteration loop
                iteration = 0
                failed_tools: dict = {}
                while finish_reason == "tool_calls" and message.get("tool_calls") and iteration < 15:
                    if time.time() - t0 > RESPONSE_TIME_LIMIT_S:
                        response_text = "⚠ Response time limit reached. Try a simpler query."
                        break
                    iteration += 1
                    assistant_entry = {
                        "role": "assistant",
                        "content": message.get("content"),
                        "tool_calls": message["tool_calls"],
                    }
                    # Preserve reasoning fields for Chinese providers (DeepSeek, Kimi, Minimax).
                    # These providers require reasoning context in subsequent turns or they 400.
                    if message.get("reasoning_content"):
                        assistant_entry["reasoning_content"] = message["reasoning_content"]
                    if message.get("reasoning_details"):
                        assistant_entry["reasoning_details"] = message["reasoning_details"]
                    history.append(assistant_entry)
                    for tc in message["tool_calls"]:
                        func = tc.get("function", {})
                        name = func.get("name", "?")
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}
                        _on_tool(name, args)
                        if failed_tools.get(name, 0) >= 2:
                            result = json.dumps({"error": f"{name} is temporarily unavailable after repeated failures"})
                        else:
                            result = _execute_tool(api_key, name, args)
                            if isinstance(result, str) and "error" in result.lower():
                                failed_tools[name] = failed_tools.get(name, 0) + 1
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        })

                    console.print("  [s.cyan]⏳ Sentinel analyzing...[/]")
                    endpoint = PROVIDER_ENDPOINTS.get(provider, PROVIDER_ENDPOINTS["openai"])
                    llm_resp = _call_openai_compat(ai_key, model_name, history, tools, endpoint)

                    if "error" in llm_resp:
                        if _handle_402(llm_resp):
                            response_text = ""
                            break
                        err = llm_resp["error"]
                        if isinstance(err, dict):
                            err = err.get("message", str(err))
                        response_text = f"⚠ LLM Error: {err}"
                        break

                    choice = llm_resp.get("choices", [{}])[0]
                    message = choice.get("message", {})
                    finish_reason = choice.get("finish_reason", "stop")

                if response_text is None:
                    response_text = message.get("content", "(no response)")
                    history.append({"role": "assistant", "content": response_text})

            # ── Display Response ──────────────────────
            elapsed = time.time() - t0
            n_tools = len(tool_calls_this_turn)
            footer = f"[s.dim]{n_tools} tool{'s' if n_tools != 1 else ''} · {elapsed:.1f}s[/]"

            # response_text == "" means _handle_402 already showed its panel; skip.
            if response_text:
                # Same themed box for every provider (Claude streams a live preview first,
                # which clears; gpt/grok/gemini render straight into the box).
                console.print(Panel(
                    _md_to_rich(response_text),
                    title="[bold cyan]🛡️ Sentinel[/]",
                    subtitle=footer,
                    title_align="right",
                    subtitle_align="right",
                    border_style="#2a6e6e",
                    box=box.ROUNDED,
                    padding=(1, 3),
                    expand=True,
                ))
                console.print()

            # v0.9.2: refresh billing status after each turn and show live counter.
            # This makes the counter visibly decrement so users know they're being counted,
            # and ensures the 402 paywall renders on the very turn the limit is hit.
            if gateway_ok and response_text != "":
                try:
                    billing = _fetch_billing_status(api_key)
                    if billing:
                        config["billing_status"] = billing
                        _ps = billing.get("payment_status", "free")
                        if _ps not in ("active",):
                            _pu = int(billing.get("prompts_used", 0))
                            _pl = int(billing.get("prompt_limit", 10))
                            _rem = max(0, _pl - _pu)
                            _col = "green" if _rem > 3 else ("yellow" if _rem > 0 else "red")
                            console.print(f"  [dim]Quota: [{_col}]{_rem}/{_pl}[/] free prompts remaining[/]")
                except Exception:
                    pass

        except Exception as e:
            console.print(Panel(
                f"[s.error]✗ Error[/]\n[s.dim]{e}[/]",
                title="⚠️ Error", title_align="right",
                border_style="#662222", box=box.ROUNDED,
            ))
            console.print()
            if history and history[-1].get("role") == "user":
                history.pop()


def run_ask(config: dict, question: str):
    """One-shot question — run agent loop and print response."""
    ai_key = config.get("ai_key", "")
    api_key = config.get("sentinel_api_key", "")
    provider = config.get("ai_provider", "anthropic")
    model = _resolve_model(config, provider)

    if not ai_key:
        console.print("  [s.error]✗ No AI key[/] — run [bold]sentinel-setup[/] first.\n")
        return

    if not api_key:
        result = _register_with_gateway(ai_key)
        api_key = result.get("api_key", "")

    tools = TOOL_SCHEMAS if api_key else []
    history: list[dict] = []
    history.append({"role": "user", "content": question})

    def on_tool_call(name, args):
        arg_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
        console.print(f"  [s.dim]⚙ {name}({arg_str})[/]")

    console.print()
    t0 = time.time()

    # Simplified loop for one-shot
    response_text = None
    for iteration in range(15):
        console.print("  [s.cyan]⏳ Sentinel thinking...[/]")
        if provider == "anthropic":
            llm_resp = _call_anthropic(ai_key, model, history, tools)
        else:
            endpoint = PROVIDER_ENDPOINTS.get(provider, PROVIDER_ENDPOINTS["openai"])
            llm_resp = _call_openai_compat(ai_key, model, history, tools, endpoint)

        if "error" in llm_resp:
            if _handle_402(llm_resp):
                response_text = ""
                break
            err = llm_resp["error"]
            if isinstance(err, dict):
                err = err.get("message", str(err))
            response_text = f"⚠ LLM Error: {err}"
            break

        if provider == "anthropic":
            content = llm_resp.get("content", [])
            stop_reason = llm_resp.get("stop_reason", "end_turn")
            history.append({"role": "assistant", "content": content})

            if stop_reason == "tool_use":
                tool_results = []
                for tu in [b for b in content if b.get("type") == "tool_use"]:
                    on_tool_call(tu["name"], tu.get("input", {}))
                    result = _execute_tool(api_key, tu["name"], tu.get("input", {}))
                    tool_results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": result})
                history.append({"role": "user", "content": tool_results})
                continue
            else:
                response_text = "\n".join(b["text"] for b in content if b.get("type") == "text") or "(no response)"
                break
        else:
            choice = llm_resp.get("choices", [{}])[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "stop")

            if finish_reason == "tool_calls" and message.get("tool_calls"):
                history.append({"role": "assistant", "content": message.get("content"), "tool_calls": message["tool_calls"]})
                for tc in message["tool_calls"]:
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    on_tool_call(func.get("name", "?"), args)
                    result = _execute_tool(api_key, func.get("name", "?"), args)
                    history.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                continue
            else:
                response_text = message.get("content", "(no response)")
                break

    if response_text is None:
        response_text = "⚠ Max iterations reached."

    elapsed = time.time() - t0
    # response_text == "" means _handle_402 already rendered its panel.
    if response_text:
        console.print(Panel(
            _md_to_rich(response_text),
            title="[bold cyan]🛡️ Sentinel[/]",
            subtitle=f"[s.dim]{elapsed:.1f}s[/]",
            title_align="right", subtitle_align="right",
            border_style="#2a6e6e", box=box.ROUNDED,
            padding=(1, 3), expand=True,
        ))
        console.print()


# ══════════════════════════════════════════════════════════════
# Entry Points
# ══════════════════════════════════════════════════════════════

def _entry_chat():
    """Standalone entry point for `sentinel-chat` command."""
    config = _first_run_setup()
    run_chat(config)
