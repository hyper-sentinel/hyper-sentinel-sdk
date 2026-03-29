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
[dim]AI Agent · 80+ Tools · Gateway-Powered · Zero-Trust[/]
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

SYSTEM_PROMPT = """You are Sentinel, a production-grade AI trading agent with access to 80+ market intelligence tools.

CAPABILITIES:
- Real-time crypto prices (CoinGecko — 10,000+ coins)
- Stock data (YFinance — prices, analyst recs, financials, news)
- Economic data (FRED — GDP, CPI, unemployment, interest rates)
- DEX data (DexScreener — pairs, trending tokens, on-chain analytics)
- Social intelligence (X/Twitter search, Elfa AI trending, Y2 news)
- DEX trading (Hyperliquid perps, Aster futures, Polymarket predictions)
- On-chain swaps (Jupiter SOL, Uniswap ETH)
- Wallet management (generate, import, balance, send)

RULES:
- Always use tools to get REAL data. Never fabricate prices or statistics.
- Be concise and data-driven. Lead with numbers.
- When asked about multiple things, call multiple tools and synthesize ONE unified response.
- Format numbers clearly: $87,421.32 not 87421.32, 2.3% not 0.023.
- If a tool fails, say so honestly and suggest alternatives.
- For trading operations (placing orders, closing positions), confirm the action clearly.
- Keep responses focused — no unnecessary preamble.
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

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        return resp.json()
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

    try:
        resp = httpx.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        return resp.json()
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        return {"error": {"message": f"Cannot reach LLM API: {e}. Check your internet connection."}}
    except httpx.TimeoutException as e:
        return {"error": {"message": f"LLM API timed out: {e}"}}
    except Exception as e:
        return {"error": {"message": f"LLM call failed: {e}"}}


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
        if tool_name in ("get_stock_quote", "get_stock_analyst", "get_stock_news"):
            try:
                import yfinance as yf
            except ImportError:
                return json.dumps({"error": "yfinance not installed. Run: pip install yfinance"})

            ticker = args.get("ticker", args.get("symbol", "SPY")).upper()
            t = yf.Ticker(ticker)

            if tool_name == "get_stock_quote":
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
            elif tool_name == "get_stock_analyst":
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

    # Always-available sources
    ds.add_row("🪙 CoinGecko", "[green]● Always available[/]", "10,000+ crypto prices + top N + search")
    ds.add_row("📈 YFinance", "[green]● Always available[/]", "stocks + ETFs + analyst recs + news")
    ds.add_row("📊 DexScreener", "[green]● Always available[/]", "DEX pair data + trending + boosted tokens")

    # Gateway-dependent sources  — check if gateway is connected
    if gateway_ok:
        ds.add_row("🏛️ FRED", "[green]● Connected[/]", "GDP, CPI, rates, yield curve, VIX")
        ds.add_row("📰 Y2 Intelligence", "[green]● Connected[/]", "news sentiment + recaps + reports")
        ds.add_row("🔮 Elfa AI", "[green]● Connected[/]", "trending tokens + social mentions")
        ds.add_row("🐦 X (Twitter)", "[green]● Connected[/]", "tweets + trends + sentiment")
        ds.add_row("⚡ Hyperliquid", "[green]● Connected[/]", "perp futures + orders + positions")
        ds.add_row("🌟 Aster DEX", "[green]● Connected[/]", "futures + orderbook + klines + leverage")
        ds.add_row("🎲 Polymarket", "[green]● Connected[/]", "browse + bet + positions + orders")
        ds.add_row("💬 Telegram", "[green]● Connected[/]", "read channels + groups + monitor + send")
        ds.add_row("🎮 Discord", "[green]● Connected[/]", "read servers + channels + search + send")
    else:
        ds.add_row("🏛️ FRED", "[dim]○ Gateway pending[/]", "GDP, CPI, rates, yield curve, VIX")
        ds.add_row("📰 Y2 Intelligence", "[dim]○ Gateway pending[/]", "news sentiment + recaps + reports")
        ds.add_row("🔮 Elfa AI", "[dim]○ Gateway pending[/]", "trending tokens + social mentions")
        ds.add_row("🐦 X (Twitter)", "[dim]○ Gateway pending[/]", "tweets + trends + sentiment")
        ds.add_row("⚡ Hyperliquid", "[dim]○ Gateway pending[/]", "perp futures + orders + positions")
        ds.add_row("🌟 Aster DEX", "[dim]○ Gateway pending[/]", "futures + orderbook + klines + leverage")
        ds.add_row("🎲 Polymarket", "[dim]○ Gateway pending[/]", "browse + bet + positions + orders")
        ds.add_row("💬 Telegram", "[dim]○ Gateway pending[/]", "channels + groups + monitor")
        ds.add_row("🎮 Discord", "[dim]○ Gateway pending[/]", "servers + channels + search")

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

    console.print(agents)

    connected = 12 if gateway_ok else 3
    console.print(f"  [dim]{connected} data sources · Mode: [bold]SOLO (MarketAgent)[/][/]")
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
            console.print("  [bold cyan]Session[/]")
            console.print("  [s.cyan]clear[/]        [s.dim]Reset conversation context[/]")
            console.print("  [s.cyan]tools[/]        [s.dim]List all available tools[/]")
            console.print("  [s.cyan]status[/]       [s.dim]Show infrastructure dashboard[/]")
            console.print("  [s.cyan]quit[/]         [s.dim]Exit chat[/]")
            console.print()
            continue

        # ── Agent Tool-Use Loop ───────────────────────
        console.print()
        tool_calls_this_turn: list[str] = []
        t0 = time.time()

        def _on_tool(name: str, args: dict):
            nonlocal tool_calls_total, api_key, gateway_registered
            tool_calls_total += 1

            # Direct tools (CoinGecko, YFinance, DexScreener) skip gateway
            DIRECT_TOOLS = {
                "get_crypto_price", "get_crypto_top", "search_crypto",
                "get_stock_quote", "get_stock_analyst", "get_stock_news",
                "dexscreener_search", "dexscreener_trending",
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
