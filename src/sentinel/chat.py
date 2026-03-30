"""
Sentinel Chat — Interactive AI Agent with Tool-Use Loop.

The brain that turns the SDK from a REST client into an AI agent.
Sends user questions to an LLM with tool schemas; when the LLM requests
tool calls, executes them on the Go gateway and feeds results back.

Supports: Anthropic (Claude), OpenAI (GPT), xAI (Grok), Google (Gemini).

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

GATEWAY_URL = "https://sentinel-api-4gqwf3cjxa-uc.a.run.app"

SENTINEL_DIR = Path.home() / ".sentinel"
CONFIG_FILE = SENTINEL_DIR / "config"


# ══════════════════════════════════════════════════════════════
# Banner
# ══════════════════════════════════════════════════════════════

BANNER = """
[bold cyan]██╗  ██╗██╗   ██╗██████╗ ███████╗██████╗[/]
[bold cyan]██║  ██║╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗[/]
[bold cyan]███████║ ╚████╔╝ ██████╔╝█████╗  ██████╔╝[/]
[bold cyan]██╔══██║  ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗[/]
[bold cyan]██║  ██║   ██║   ██║     ███████╗██║  ██║[/]
[bold cyan]╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝[/]

[bold white]S E N T I N E L[/]
[dim]AI Agent · 65+ Tools · Local-First · Zero-Config[/]
"""


# ══════════════════════════════════════════════════════════════
# Config Helpers
# ══════════════════════════════════════════════════════════════

KEY_PREFIXES = {
    "sk-ant-":  ("anthropic", "CLAUDE",  "Anthropic (Claude)",  "🟣"),
    "sk-proj-": ("openai",    "OPENAI",  "OpenAI (GPT)",        "🟢"),
    "sk-":      ("openai",    "OPENAI",  "OpenAI (GPT)",        "🟢"),
    "AIza":     ("google",    "GEMINI",  "Google (Gemini)",     "🔵"),
    "xai-":     ("xai",       "GROK",    "xAI (Grok)",          "⚫"),
}


def _detect_provider(key: str):
    """Detect LLM provider from API key prefix."""
    for prefix, info in KEY_PREFIXES.items():
        if key.startswith(prefix):
            return info  # (provider_id, short_label, full_label, emoji)
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
    """Lazy-register with gateway using AI key."""
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/auth/ai-key",
            json={"ai_key": ai_key},
            timeout=30.0,
        )
        if resp.status_code in (200, 201):
            return resp.json()
    except Exception:
        pass
    return {}


# ══════════════════════════════════════════════════════════════
# System Prompt
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are Sentinel, a production-grade AI trading agent built by the Hyper-Sentinel project.
Version: 0.3.4 | Build: March 2026 | Platform: hyper-sentinel SDK (PyPI)

CAPABILITIES:
- Real-time crypto prices (CoinGecko — 10,000+ coins)
- Stock data (YFinance — prices, analyst recs, financials, news, full quant analysis)
- Economic data (FRED — GDP, CPI, unemployment, interest rates)
- DEX data (DexScreener — pairs, trending tokens, on-chain analytics)
- Social intelligence (X/Twitter search, Elfa AI trending, Y2 news)
- DEX trading (Hyperliquid perps, Aster futures, Polymarket predictions)
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
For quant analysis, ALWAYS use the run_stock_analysis tool to get comprehensive data in a single call.
"""

# ══════════════════════════════════════════════════════════════
# Default Models per Provider
# ══════════════════════════════════════════════════════════════

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "xai": "grok-2",
    "google": "gemini-2.0-flash",
}

PROVIDER_ENDPOINTS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/chat/completions",
    "xai": "https://api.x.ai/v1/chat/completions",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
}


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
                "limit": {"type": "integer", "description": "Number of recent observations", "default": 10},
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
        "description": "Get a snapshot of key economic indicators: GDP, CPI, unemployment, fed funds rate, 10yr yield.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # ── News & Sentiment ──────────────────────────────────────
    {
        "name": "get_news_sentiment",
        "description": "Get news sentiment analysis for a topic or asset.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Topic to analyze (e.g. 'crypto', 'bitcoin', 'AI stocks')"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_news_recap",
        "description": "Get an AI-generated recap of today's top market news.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # ── DexScreener ───────────────────────────────────────────
    {
        "name": "dexscreener_search",
        "description": "Search for DEX trading pairs by token name or symbol.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Token name or symbol to search"}},
            "required": ["query"],
        },
    },
    {
        "name": "dexscreener_trending",
        "description": "Get trending tokens across all DEXes (hot memecoins, new listings, etc).",
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

    # ── Hyperliquid ───────────────────────────────────────────
    {
        "name": "get_hl_positions",
        "description": "Get current open positions on Hyperliquid DEX.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_hl_orderbook",
        "description": "Get the order book for a Hyperliquid trading pair.",
        "parameters": {
            "type": "object",
            "properties": {"coin": {"type": "string", "description": "Trading pair symbol (e.g. ETH, BTC, SOL)"}},
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
        "description": "Place a trade on Hyperliquid. Supports market and limit orders.",
        "parameters": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "Trading pair (e.g. ETH, BTC)"},
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
        "description": "Close an open Hyperliquid position for a specific coin.",
        "parameters": {
            "type": "object",
            "properties": {"coin": {"type": "string", "description": "Position to close (e.g. ETH, BTC)"}},
            "required": ["coin"],
        },
    },

    # ── Polymarket ────────────────────────────────────────────
    {
        "name": "search_polymarket",
        "description": "Search Polymarket prediction markets by topic.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search topic (e.g. 'Trump', 'Fed rate', 'Bitcoin 100k')"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_polymarket_markets",
        "description": "Get active Polymarket prediction markets with current odds.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Number of markets", "default": 10}},
            "required": [],
        },
    },

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

    # ── Telegram ──────────────────────────────────────────────
    {
        "name": "tg_read_channel",
        "description": "Read messages from a Telegram channel.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel username or ID"},
                "limit": {"type": "integer", "description": "Number of messages", "default": 10},
            },
            "required": ["channel"],
        },
    },
    {
        "name": "tg_list_channels",
        "description": "List available Telegram channels.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # ── Discord ───────────────────────────────────────────────
    {
        "name": "discord_list_guilds",
        "description": "List connected Discord servers/guilds.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "discord_read_channel",
        "description": "Read messages from a Discord channel.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "integer", "description": "Discord channel ID"},
                "limit": {"type": "integer", "description": "Number of messages", "default": 50},
            },
            "required": ["channel_id"],
        },
    },

    # ── Wallets / DEX Swaps ───────────────────────────────────
    {
        "name": "list_wallets",
        "description": "List configured wallets across chains (SOL, ETH).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "dex_buy_sol",
        "description": "Buy a token on Solana via Jupiter aggregator.",
        "parameters": {
            "type": "object",
            "properties": {
                "contract_address": {"type": "string", "description": "Token contract address on Solana"},
                "amount_sol": {"type": "number", "description": "Amount of SOL to spend"},
                "slippage": {"type": "number", "description": "Max slippage %", "default": 0},
            },
            "required": ["contract_address", "amount_sol"],
        },
    },
    {
        "name": "dex_buy_eth",
        "description": "Buy a token on Ethereum via Uniswap.",
        "parameters": {
            "type": "object",
            "properties": {
                "contract_address": {"type": "string", "description": "Token contract address on Ethereum"},
                "amount_eth": {"type": "number", "description": "Amount of ETH to spend"},
                "slippage": {"type": "number", "description": "Max slippage %", "default": 0},
            },
            "required": ["contract_address", "amount_eth"],
        },
    },
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

def _call_anthropic(ai_key: str, model: str, messages: list, tools: list) -> dict:
    """Call Anthropic Messages API with tool support."""
    headers = {
        "x-api-key": ai_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": messages,
        "system": SYSTEM_PROMPT,
    }
    if tools:
        payload["tools"] = _tools_for_anthropic(tools)

    import time as _time
    last_err = ""
    for attempt in range(3):
        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(120.0, connect=10.0),
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
                return resp.json()
            except (ValueError, Exception):
                if attempt < 2:
                    _time.sleep(1.5 * (attempt + 1))
                    continue
                return {"error": {"message": f"Anthropic returned empty response after 3 retries."}}
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            return {"error": {"message": f"Cannot reach Anthropic API: {e}. Check your internet connection."}}
        except httpx.TimeoutException as e:
            return {"error": {"message": f"Anthropic API timed out: {e}"}}
        except Exception as e:
            return {"error": {"message": f"LLM call failed: {e}"}}


def _call_openai_compat(
    ai_key: str,
    model: str,
    messages: list,
    tools: list,
    endpoint: str,
) -> dict:
    """Call OpenAI-compatible API (OpenAI, xAI, Google) with tool support."""
    headers = {
        "Authorization": f"Bearer {ai_key}",
        "Content-Type": "application/json",
    }
    all_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": all_messages,
    }
    if tools:
        payload["tools"] = _tools_for_openai(tools)

    import time as _time
    for attempt in range(3):
        try:
            resp = httpx.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
            if resp.status_code in (403, 429, 500, 502, 503, 529) and attempt < 2:
                _time.sleep(1.5 * (attempt + 1))
                continue
            try:
                return resp.json()
            except (ValueError, Exception):
                if attempt < 2:
                    _time.sleep(1.5 * (attempt + 1))
                    continue
                return {"error": {"message": f"LLM API returned HTTP {resp.status_code} with invalid response after 3 retries."}}
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            return {"error": {"message": f"Cannot reach LLM API: {e}. Check your internet connection."}}
        except httpx.TimeoutException as e:
            return {"error": {"message": f"LLM API timed out: {e}"}}
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
        if tool_name == "get_crypto_price":
            symbol = args.get("symbol", "").lower()
            # CoinGecko simple price API
            r = httpx.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": symbol, "vs_currencies": "usd", "include_24hr_change": "true",
                         "include_market_cap": "true", "include_24hr_vol": "true"},
                timeout=10.0,
            )
            data = r.json()
            if not data or symbol not in data:
                # Try search first
                sr = httpx.get(f"https://api.coingecko.com/api/v3/search?query={symbol}", timeout=10.0)
                coins = sr.json().get("coins", [])
                if coins:
                    coin_id = coins[0]["id"]
                    r = httpx.get(
                        "https://api.coingecko.com/api/v3/simple/price",
                        params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true",
                                 "include_market_cap": "true", "include_24hr_vol": "true"},
                        timeout=10.0,
                    )
                    data = r.json()
                    symbol = coin_id
            if symbol in data:
                info = data[symbol]
                return json.dumps({
                    "symbol": symbol,
                    "price_usd": info.get("usd"),
                    "change_24h_pct": info.get("usd_24h_change"),
                    "market_cap_usd": info.get("usd_market_cap"),
                    "volume_24h_usd": info.get("usd_24h_vol"),
                    "source": "coingecko",
                })
            return json.dumps({"error": f"Token '{symbol}' not found on CoinGecko"})

        if tool_name == "get_crypto_top":
            n = args.get("n", 10)
            r = httpx.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": n, "page": 1},
                timeout=10.0,
            )
            coins = [{"rank": c["market_cap_rank"], "name": c["name"], "symbol": c["symbol"],
                       "price": c["current_price"], "change_24h": c.get("price_change_percentage_24h"),
                       "market_cap": c["market_cap"]} for c in r.json()]
            return json.dumps({"top_coins": coins, "source": "coingecko"})

        if tool_name == "search_crypto":
            query = args.get("query", "")
            r = httpx.get(f"https://api.coingecko.com/api/v3/search?query={query}", timeout=10.0)
            coins = [{"id": c["id"], "name": c["name"], "symbol": c["symbol"],
                       "market_cap_rank": c.get("market_cap_rank")} for c in r.json().get("coins", [])[:10]]
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
            pairs = r.json().get("pairs", [])[:5]
            results = [{"name": p.get("baseToken", {}).get("name"), "symbol": p.get("baseToken", {}).get("symbol"),
                         "price": p.get("priceUsd"), "chain": p.get("chainId"),
                         "dex": p.get("dexId"), "volume_24h": p.get("volume", {}).get("h24")} for p in pairs]
            return json.dumps({"pairs": results, "source": "dexscreener"})

        if tool_name == "dexscreener_trending":
            r = httpx.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=10.0)
            tokens = r.json()[:10] if isinstance(r.json(), list) else []
            results = [{"symbol": t.get("tokenAddress", "")[:8], "chain": t.get("chainId"),
                         "url": t.get("url")} for t in tokens]
            return json.dumps({"trending": results, "source": "dexscreener"})

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
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except ImportError:
                return json.dumps({"error": "hyperliquid-python-sdk not installed. Run: pip install hyperliquid-python-sdk eth-account"})
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── FRED (needs API key from config) ──────────────────────
        if tool_name in ("get_fred_series", "search_fred", "get_economic_dashboard"):
            try:
                from sentinel.scrapers import fred
                if tool_name == "get_fred_series":
                    return json.dumps(fred.get_fred_series(**args))
                elif tool_name == "search_fred":
                    return json.dumps(fred.search_fred(**args))
                elif tool_name == "get_economic_dashboard":
                    return json.dumps(fred.get_economic_dashboard())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Y2 Intelligence (needs API key) ───────────────────────
        if tool_name in ("get_news_sentiment", "get_news_recap", "get_intelligence_reports", "get_report_detail"):
            try:
                from sentinel.scrapers import y2
                dispatch = {
                    "get_news_sentiment": lambda: y2.get_news_sentiment(**args),
                    "get_news_recap": lambda: y2.get_news_recap(**args),
                    "get_intelligence_reports": lambda: y2.get_intelligence_reports(**args),
                    "get_report_detail": lambda: y2.get_report_detail(**args),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Elfa AI (needs API key) ───────────────────────────────
        if tool_name in ("get_trending_tokens", "get_top_mentions", "search_mentions",
                         "get_trending_narratives", "get_token_news"):
            try:
                from sentinel.scrapers import elfa
                dispatch = {
                    "get_trending_tokens": lambda: elfa.get_trending_tokens(**args),
                    "get_top_mentions": lambda: elfa.get_top_mentions(**args),
                    "search_mentions": lambda: elfa.search_mentions(**args),
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
                    "aster_ticker": lambda: aster.aster_ticker(**args),
                    "aster_orderbook": lambda: aster.aster_orderbook(**args),
                    "aster_klines": lambda: aster.aster_klines(**args),
                    "aster_funding_rate": lambda: aster.aster_funding_rate(**args),
                    "aster_exchange_info": lambda: aster.aster_exchange_info(**args),
                    "aster_balance": lambda: aster.aster_balance(),
                    "aster_positions": lambda: aster.aster_positions(**args),
                    "aster_config": lambda: aster.aster_config(),
                    "aster_diagnose": lambda: aster.aster_diagnose(),
                    "aster_ping": lambda: aster.aster_ping(),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Polymarket (needs private key) ────────────────────────
        if tool_name.startswith("polymarket_") or tool_name.startswith("get_polymarket_") or \
           tool_name in ("buy_polymarket", "sell_polymarket", "search_polymarket",
                         "place_polymarket_limit", "cancel_polymarket_order", "cancel_all_polymarket_orders"):
            try:
                from sentinel.scrapers import polymarket as pm
                dispatch = {
                    "get_polymarket_markets": lambda: pm.get_polymarket_markets(**args),
                    "search_polymarket": lambda: pm.search_polymarket(**args),
                    "get_polymarket_orderbook": lambda: pm.get_polymarket_orderbook(**args),
                    "get_polymarket_price": lambda: pm.get_polymarket_price(**args),
                    "get_polymarket_positions": lambda: pm.get_polymarket_positions(),
                    "buy_polymarket": lambda: pm.buy_polymarket(**args),
                    "sell_polymarket": lambda: pm.sell_polymarket(**args),
                    "place_polymarket_limit": lambda: pm.place_polymarket_limit(**args),
                    "cancel_polymarket_order": lambda: pm.cancel_polymarket_order(**args),
                    "cancel_all_polymarket_orders": lambda: pm.cancel_all_polymarket_orders(),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Telegram (needs session) ──────────────────────────────
        if tool_name.startswith("tg_"):
            try:
                from sentinel.scrapers import telegram as tg
                dispatch = {
                    "tg_read_channel": lambda: tg.tg_read_channel(**args),
                    "tg_search_messages": lambda: tg.tg_search_messages(**args),
                    "tg_list_channels": lambda: tg.tg_list_channels(**args),
                    "tg_send_message": lambda: tg.tg_send_message(**args),
                    "tg_get_config": lambda: tg.tg_get_config(),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

        # ── Discord (needs bot token) ─────────────────────────────
        if tool_name.startswith("discord_"):
            try:
                from sentinel.scrapers import discord as dc
                dispatch = {
                    "discord_read_channel": lambda: dc.discord_read_channel(**args),
                    "discord_search_messages": lambda: dc.discord_search_messages(**args),
                    "discord_list_guilds": lambda: dc.discord_list_guilds(),
                    "discord_list_channels": lambda: dc.discord_list_channels(**args),
                    "discord_send_message": lambda: dc.discord_send_message(**args),
                    "discord_get_config": lambda: dc.discord_get_config(),
                }
                if tool_name in dispatch:
                    return json.dumps(dispatch[tool_name]())
            except Exception as e:
                return json.dumps({"error": str(e), "tool": tool_name})

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
# Dashboard — Mirrors main.py's _print_status()
# ══════════════════════════════════════════════════════════════

def _print_dashboard(config: dict, gateway_ok: bool):
    """Print the full Infrastructure + Data Sources + Agents dashboard."""
    provider = config.get("ai_provider", "anthropic")
    ai_key = config.get("ai_key", "")
    detected = _detect_provider(ai_key) if ai_key else None
    model = DEFAULT_MODELS.get(provider, "claude-sonnet-4-20250514")

    # ── LLM confirmation line (matches Python folder) ─────────
    if detected:
        provider_id, short_label, full_label, emoji = detected
        console.print(f"  [green]✓ LLM: {short_label} → {provider_id}/{model}[/]")
    else:
        console.print(f"  [s.error]✗ LLM: No API key configured[/]")

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
        tier = config.get("tier", "free").capitalize()
        infra.add_row("🌐 Gateway", f"[green]● Connected[/]", f"{tier} tier · Cloud Run")
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

    pm_ok = config.get("polymarket_key") or os.environ.get("POLYMARKET_PRIVATE_KEY", "")
    ds.add_row("🎲 Polymarket",
               "[green]● Ready[/]" if pm_ok else "[yellow]○ Needs config[/]",
               "browse + bet + positions + orders" + ("" if pm_ok else " · [dim]add polymarket[/]"))

    tg_ok = config.get("tg_api_id") or os.environ.get("TELEGRAM_API_ID", "")
    ds.add_row("💬 Telegram",
               "[green]● Ready[/]" if tg_ok else "[yellow]○ Needs config[/]",
               "read channels + groups + monitor + send" + ("" if tg_ok else " · [dim]add telegram[/]"))

    dc_ok = config.get("discord_token") or os.environ.get("DISCORD_BOT_TOKEN", "")
    ds.add_row("🎮 Discord",
               "[green]● Ready[/]" if dc_ok else "[yellow]○ Needs config[/]",
               "read servers + channels + search + send" + ("" if dc_ok else " · [dim]add discord[/]"))

    console.print(ds)

    # ── Agents Panel ──────────────────────────────────────────
    agents = Table(
        title="[bold cyan]🛡️  Agents[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    agents.add_column("Agent", style="bold white", min_width=18)
    agents.add_column("Status", min_width=16)
    agents.add_column("Subject", style="dim")

    agents.add_row("📊 MarketAgent", "[green]● ONLINE[/]", "sentinel.market.data")

    # Check for Upsonic swarm availability
    try:
        import upsonic  # noqa: F401
        agents.add_row("📊 Analyst", "[dim]○ Ready[/]", "[dim]sentinel.analyst · type 'swarm'[/]")
        agents.add_row("⚠️  RiskManager", "[dim]○ Ready[/]", "[dim]sentinel.risk[/]")
        agents.add_row("💰 Trader", "[dim]○ Ready[/]", "[dim]sentinel.trader[/]")
        _swarm_available = True
    except ImportError:
        _swarm_available = False

    console.print(agents)

    # Count connected sources
    connected = 3  # CoinGecko + YFinance + DexScreener always
    for k in ("fred_api_key", "y2_api_key", "elfa_api_key", "x_bearer_token"):
        if config.get(k) or os.environ.get(k, ""):
            connected += 1
    if hl_ok: connected += 1
    if aster_ok: connected += 1
    if pm_ok: connected += 1
    if tg_ok: connected += 1
    if dc_ok: connected += 1
    if _swarm_available:
        console.print(f"  [dim]{connected} data sources · Mode: [bold]SOLO (MarketAgent)[/] · Swarm: [green]available[/] · type [bold]'swarm'[/] to activate[/]")
    else:
        console.print(f"  [dim]{connected} data sources · Mode: [bold]SOLO (MarketAgent)[/] · Swarm: [yellow]pip install 'hyper-sentinel[swarm]'[/][/]")
    console.print()
    console.print("  Type a question, or [bold]'help'[/] for commands.")
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
    provider = config.get("ai_provider", "anthropic")

    if not ai_key:
        console.print("  [s.error]✗ No AI key configured[/] — run [bold]sentinel-setup[/] first.\n")
        return

    # ── Banner + Dashboard (instant — no blocking calls) ──
    console.print(BANNER)

    gateway_ok = bool(api_key)

    # ── Bridge config → env vars for scrapers ─────────
    # Scrapers read os.getenv(), but user keys are stored in ~/.sentinel/config.
    # Bridge them so all scrapers see the credentials.
    _CONFIG_TO_ENV = {
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
    for config_key, env_key in _CONFIG_TO_ENV.items():
        val = config.get(config_key, "")
        if val and not os.environ.get(env_key):
            os.environ[env_key] = str(val)

    _print_dashboard(config, gateway_ok)

    # ── Session state ─────────────────────────────────
    history: list[dict] = []
    tools = TOOL_SCHEMAS  # always provide schemas — lazy-register on first call
    model_name = DEFAULT_MODELS.get(provider, "claude-sonnet-4-20250514")
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
            console.print("  [s.dim]Context cleared — new session started.[/]\n")
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

        if cmd == "status":
            config = _load_config()  # refresh
            _print_dashboard(config, gateway_ok)
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
                    console.print("  [s.dim]  sk-xxx      → OpenAI (GPT)[/]")
                    console.print("  [s.dim]  AIza-xxx    → Google (Gemini)[/]")
                    console.print("  [s.dim]  xai-xxx     → xAI (Grok)[/]")
                    console.print()
                    console.print("[s.cyan.bold]  🔑 API Key →[/] ", end="")
                    new_key = input().strip()
                    if new_key:
                        detected = _detect_provider(new_key)
                        if detected:
                            new_provider, new_model_default, provider_label = detected
                            ai_key = new_key
                            provider = new_provider
                            model_name = DEFAULT_MODELS.get(new_provider, new_model_default)
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
            else:
                # Show available services
                console.print()
                console.print("  [bold cyan]AI Provider[/]")
                console.print(f"  [s.cyan]add ai[/]            [s.dim]Change LLM provider (current: {provider.upper()})[/]")
                console.print()
                console.print("  [bold cyan]Trading & Prediction Markets[/]")
                console.print("  [s.cyan]add hl[/]            [s.dim]Hyperliquid perp futures[/]")
                console.print("  [s.cyan]add polymarket[/]    [s.dim]Prediction markets[/]")
                console.print("  [s.cyan]add aster[/]         [s.dim]Aster DEX futures[/]")
                console.print()
                console.print("  [bold cyan]Data Sources[/]")
                console.print("  [s.cyan]add fred[/]          [s.dim]FRED economic data (GDP, CPI, rates)[/]")
                console.print("  [s.cyan]add x[/]             [s.dim]X/Twitter search & sentiment[/]")
                console.print("  [s.cyan]add y2[/]            [s.dim]Y2 Intelligence news[/]")
                console.print("  [s.cyan]add elfa[/]          [s.dim]Elfa AI social intelligence[/]")
                console.print("  [s.cyan]add eodhd[/]         [s.dim]EODHD historical market data[/]")
                console.print("  [s.cyan]add telegram[/]      [s.dim]Telegram channel reader[/]")
                console.print("  [s.cyan]add discord[/]       [s.dim]Discord bot integration[/]")
                console.print()
            continue

        if cmd in ("help", "?"):
            console.print()
            console.print("  [bold cyan]Chat[/]")
            console.print("  [s.dim]Just type a question — the AI agent will call tools and respond.[/]")
            console.print()
            console.print("  [bold cyan]Configure[/]")
            console.print("  [s.cyan]add[/]          [s.dim]List available data sources & trading platforms[/]")
            console.print("  [s.cyan]add hl[/]       [s.dim]Configure Hyperliquid trading[/]")
            console.print("  [s.cyan]add fred[/]     [s.dim]Configure FRED economic data[/]")
            console.print("  [s.cyan]add x[/]        [s.dim]Configure X/Twitter search[/]")
            console.print()
            console.print("  [bold cyan]Multi-Agent Swarm[/]")
            console.print("  [s.cyan]swarm[/]        [s.dim]Start Upsonic multi-agent mode (Analyst + Risk + Trader)[/]")
            console.print("  [s.cyan]swarm status[/] [s.dim]Show swarm agent status[/]")
            console.print("  [s.cyan]solo[/]         [s.dim]Return to single-agent mode[/]")
            console.print()
            console.print("  [bold cyan]Session[/]")
            console.print("  [s.cyan]clear[/]        [s.dim]Reset conversation context[/]")
            console.print("  [s.cyan]tools[/]        [s.dim]List all available tools[/]")
            console.print("  [s.cyan]status[/]       [s.dim]Show infrastructure dashboard[/]")
            console.print("  [s.cyan]quit[/]         [s.dim]Exit chat[/]")
            console.print()
            continue

        # ── Swarm Commands ──────────────────────────────────────
        if cmd == "swarm" or cmd == "swarm start":
            console.print()
            console.print("  [bold cyan]🤖 Initializing Sentinel Swarm...[/]")
            try:
                from sentinel.swarm import build_swarm, swarm_status as _swarm_status
                _swarm_team, _swarm_agents = build_swarm()
                if _swarm_team:
                    status = _swarm_status(_swarm_team, _swarm_agents)
                    console.print()
                    console.print("  [bold green]🛡️  Sentinel Swarm — ONLINE[/]")
                    console.print()
                    for ag in status.get("agents", []):
                        console.print(f"    [s.cyan]{ag['name']:<16}[/] [green]● ONLINE[/]    [s.dim]{ag['subject']}[/]")
                    console.print()
                    console.print(f"  [s.dim]{len(status.get('agents', []))} agents · Mode: {status.get('mode', 'coordinate').upper()} · {status.get('tool_count', 0)} tools · {status.get('model', 'unknown')}[/]")
                    console.print()
                    console.print("  [s.dim]Swarm mode active. All queries will be routed through the agent team.[/]")
                    console.print("  [s.dim]Type 'solo' to return to single-agent mode.[/]")
                    console.print()
                else:
                    console.print("  [s.error]✗ Swarm init failed — check logs[/]")
                    _swarm_team = None
                    _swarm_agents = {}
            except ImportError:
                console.print("  [s.error]✗ upsonic not installed[/]")
                console.print("  [s.dim]Install with: pip install 'hyper-sentinel[swarm]'[/]")
                console.print()
                _swarm_team = None
                _swarm_agents = {}
            continue

        if cmd == "swarm status":
            try:
                if '_swarm_team' in dir() and _swarm_team:
                    from sentinel.swarm import swarm_status as _swarm_status
                    status = _swarm_status(_swarm_team, _swarm_agents)
                    console.print()
                    console.print("  [bold green]🛡️  Sentinel Swarm — ONLINE[/]")
                    for ag in status.get("agents", []):
                        console.print(f"    [s.cyan]{ag['name']:<16}[/] [green]● ONLINE[/]    [s.dim]{ag['subject']}[/]")
                    console.print(f"  [s.dim]{len(status.get('agents', []))} agents · Mode: {status.get('mode', 'coordinate').upper()}[/]")
                    console.print()
                else:
                    console.print("  [s.dim]Swarm not active. Type 'swarm' to start.[/]")
                    console.print()
            except Exception:
                console.print("  [s.dim]Swarm not active. Type 'swarm' to start.[/]")
                console.print()
            continue

        if cmd == "solo":
            _swarm_team = None
            _swarm_agents = {}
            console.print("  [s.dim]Returned to single-agent mode.[/]\n")
            continue

        # ── Swarm Mode Intercept ───────────────────────────────
        # If swarm is active, route through Upsonic Team instead of direct LLM
        _swarm_active = '_swarm_team' in dir() and locals().get('_swarm_team') is not None
        if _swarm_active:
            console.print()
            console.print("  [bold s.cyan]⏳ Swarm processing...[/]")
            t0 = time.time()
            try:
                from sentinel.swarm import swarm_chat
                swarm_result = swarm_chat(_swarm_team, user_input)
                elapsed = time.time() - t0
                console.print(Panel(
                    swarm_result,
                    title="[bold]🛡️ Sentinel Swarm[/]",
                    border_style="#007a8a",
                    box=box.ROUNDED,
                    subtitle=f"[s.dim]3 agents · coordinate · {elapsed:.1f}s[/]",
                    subtitle_align="right",
                    padding=(1, 3),
                ))
                console.print()
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": [{"type": "text", "text": swarm_result}]})
                save_message(session_id, "user", user_input)
                save_message(session_id, "assistant", swarm_result)
                if not session_titled:
                    update_session_title(session_id, user_input[:80])
                    session_titled = True
            except Exception as e:
                console.print(f"  [s.error]Swarm error: {e}[/]")
                console.print("  [s.dim]Falling back to single-agent mode...[/]")
                _swarm_team = None
                _swarm_agents = {}
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
            DIRECT_TOOLS = {
                # CoinGecko
                "get_crypto_price", "get_crypto_top", "search_crypto",
                # YFinance
                "get_stock_price", "get_stock_info", "get_analyst_recs", "get_stock_news", "get_stock_history", "run_stock_analysis",
                # DexScreener
                "dexscreener_search", "dexscreener_trending",
                # Hyperliquid
                "get_hl_positions", "get_hl_account_info", "get_hl_open_orders",
                "get_hl_orderbook", "get_hl_config", "place_hl_order",
                "close_hl_position", "cancel_hl_order", "set_hl_leverage",
                "approve_hl_builder_fee",
                # FRED
                "get_fred_series", "search_fred", "get_economic_dashboard",
                # Y2 Intelligence
                "get_news_sentiment", "get_news_recap", "get_intelligence_reports", "get_report_detail",
                # Elfa AI
                "get_trending_tokens", "get_top_mentions", "search_mentions",
                "get_trending_narratives", "get_token_news",
                # Aster DEX
                "aster_ticker", "aster_orderbook", "aster_klines", "aster_funding_rate",
                "aster_exchange_info", "aster_balance", "aster_positions",
                "aster_config", "aster_diagnose", "aster_ping",
                # Polymarket
                "get_polymarket_markets", "search_polymarket", "get_polymarket_orderbook",
                "get_polymarket_price", "get_polymarket_positions", "buy_polymarket",
                "sell_polymarket", "place_polymarket_limit", "cancel_polymarket_order",
                "cancel_all_polymarket_orders",
                # Telegram
                "tg_read_channel", "tg_search_messages", "tg_list_channels",
                "tg_send_message", "tg_get_config",
                # Discord
                "discord_read_channel", "discord_search_messages", "discord_list_guilds",
                "discord_list_channels", "discord_send_message", "discord_get_config",
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
                    llm_resp = _call_anthropic(ai_key, model_name, history, tools)
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
                while stop_reason == "tool_use" and iteration < 15:
                    iteration += 1
                    tool_uses = [b for b in content if b.get("type") == "tool_use"]
                    thinking = [b["text"] for b in content if b.get("type") == "text" and b.get("text", "").strip()]
                    if thinking:
                        console.print(f"  [s.dim]{' '.join(thinking)}[/]")

                    # Execute tools
                    tool_results = []
                    for tu in tool_uses:
                        _on_tool(tu["name"], tu.get("input", {}))
                        result = _execute_tool(api_key, tu["name"], tu.get("input", {}))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": result,
                        })

                    history.append({"role": "user", "content": tool_results})

                    # Next LLM call
                    console.print("  [s.cyan]⏳ Sentinel analyzing...[/]")
                    llm_resp = _call_anthropic(ai_key, model_name, history, tools)

                    if "error" in llm_resp:
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
                while finish_reason == "tool_calls" and message.get("tool_calls") and iteration < 15:
                    iteration += 1
                    history.append({
                        "role": "assistant",
                        "content": message.get("content"),
                        "tool_calls": message["tool_calls"],
                    })
                    for tc in message["tool_calls"]:
                        func = tc.get("function", {})
                        name = func.get("name", "?")
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}
                        _on_tool(name, args)
                        result = _execute_tool(api_key, name, args)
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        })

                    console.print("  [s.cyan]⏳ Sentinel analyzing...[/]")
                    endpoint = PROVIDER_ENDPOINTS.get(provider, PROVIDER_ENDPOINTS["openai"])
                    llm_resp = _call_openai_compat(ai_key, model_name, history, tools, endpoint)

                    if "error" in llm_resp:
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

            # ── Display Response Panel ────────────────
            elapsed = time.time() - t0
            rich_text = _md_to_rich(response_text)

            n_tools = len(tool_calls_this_turn)
            footer = f"[s.dim]{n_tools} tool{'s' if n_tools != 1 else ''} · {elapsed:.1f}s[/]"

            console.print(Panel(
                rich_text,
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
    model = DEFAULT_MODELS.get(provider, "claude-sonnet-4-20250514")

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
