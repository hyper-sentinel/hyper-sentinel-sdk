"""
Sentinel SDK — Upsonic Agent Swarm

Integrates Upsonic's Agent/Task/Team framework to provide multi-agent
coordination. Three specialized agents (Analyst, RiskManager, Trader)
work together in 'coordinate' mode, with all SDK scrapers available as tools.

Usage:
    from sentinel.swarm import build_swarm, swarm_chat
    team, agents = build_swarm()
    result = swarm_chat(team, "analyze BTC macro outlook")

CLI:
    sentinel-chat  # then type 'swarm' to enter multi-agent mode
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("sentinel.swarm")


# ══════════════════════════════════════════════════════════════════════
# Upsonic Tool Wrappers
# ══════════════════════════════════════════════════════════════════════
# Re-wrap SDK scrapers with @tool decorator for Upsonic agent consumption.

def _build_tools():
    """Build all Upsonic @tool wrapped functions from SDK scrapers."""
    try:
        from upsonic.tools import tool
    except ImportError:
        logger.warning("upsonic not installed — swarm tools unavailable")
        return [], [], [], [], [], [], [], [], []

    tools_crypto = []
    tools_macro = []
    tools_sentiment = []
    tools_trading_hl = []
    tools_trading_aster = []
    tools_trading_pm = []
    tools_social_tg = []
    tools_social_discord = []
    tools_stocks = []

    # ── Crypto (CoinGecko — always available) ────────────────
    try:
        from sentinel.scrapers.crypto import get_crypto_price, get_crypto_top_n, search_crypto

        @tool
        def crypto_price(coin_id: str) -> dict:
            """Get current price for a cryptocurrency from CoinGecko. Use 'bitcoin', 'ethereum', 'solana', etc."""
            return get_crypto_price(coin_id)

        @tool
        def crypto_top(n: int = 10) -> list:
            """Get top N cryptocurrencies by market cap from CoinGecko."""
            return get_crypto_top_n(n)

        @tool
        def crypto_search(query: str) -> list:
            """Search for a cryptocurrency by name or symbol on CoinGecko."""
            return search_crypto(query)

        tools_crypto = [crypto_price, crypto_top, crypto_search]
    except ImportError:
        pass

    # ── YFinance (stocks — always available) ──────────────────
    try:
        import yfinance as yf

        @tool
        def stock_price(symbol: str) -> dict:
            """Get current stock price, change, volume, and day range."""
            t = yf.Ticker(symbol)
            info = t.info
            return {
                "symbol": symbol.upper(),
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "change_pct": info.get("regularMarketChangePercent"),
                "volume": info.get("volume"),
                "day_high": info.get("dayHigh"),
                "day_low": info.get("dayLow"),
                "market_cap": info.get("marketCap"),
            }

        @tool
        def stock_analysis(symbol: str) -> dict:
            """Run comprehensive quantitative analysis on a stock — valuation, financials, technicals, risk, analyst targets."""
            t = yf.Ticker(symbol)
            info = t.info
            hist = t.history(period="1y")
            closes = hist["Close"].tolist() if not hist.empty else []
            # Compute MAs
            ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
            ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
            price = closes[-1] if closes else info.get("currentPrice")
            # Compute returns
            import math
            daily_returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))] if len(closes) > 1 else []
            avg_ret = sum(daily_returns) / len(daily_returns) if daily_returns else 0
            std_ret = (sum((r - avg_ret)**2 for r in daily_returns) / len(daily_returns))**0.5 if daily_returns else 0
            sharpe = (avg_ret / std_ret * math.sqrt(252)) if std_ret > 0 else None
            total_return = ((closes[-1] / closes[0]) - 1) * 100 if len(closes) > 1 else None
            result = {
                "symbol": symbol.upper(), "price": price,
                "market_cap": info.get("marketCap"), "pe_trailing": info.get("trailingPE"),
                "pe_forward": info.get("forwardPE"), "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"), "peg_ratio": info.get("pegRatio"),
                "ev_ebitda": info.get("enterpriseToEbitda"), "beta": info.get("beta"),
                "profit_margin": info.get("profitMargins"), "gross_margin": info.get("grossMargins"),
                "operating_margin": info.get("operatingMargins"), "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"), "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"), "total_cash": info.get("totalCash"),
                "total_debt": info.get("totalDebt"), "debt_to_equity": info.get("debtToEquity"),
                "free_cash_flow": info.get("freeCashflow"), "operating_cash_flow": info.get("operatingCashflow"),
                "ma_50": round(ma50, 2) if ma50 else None, "ma_200": round(ma200, 2) if ma200 else None,
                "price_vs_ma50": round((price / ma50 - 1) * 100, 2) if ma50 and price else None,
                "price_vs_ma200": round((price / ma200 - 1) * 100, 2) if ma200 and price else None,
                "target_high": info.get("targetHighPrice"), "target_mean": info.get("targetMeanPrice"),
                "target_low": info.get("targetLowPrice"), "recommendation": info.get("recommendationKey"),
                "analyst_count": info.get("numberOfAnalystOpinions"),
                "short_ratio": info.get("shortRatio"), "short_pct_float": info.get("shortPercentOfFloat"),
                "total_return_1y": round(total_return, 2) if total_return else None,
                "volatility_daily": round(std_ret * 100, 2) if std_ret else None,
                "sharpe_ratio": round(sharpe, 2) if sharpe else None,
                "1y_high": round(max(closes), 2) if closes else None,
                "1y_low": round(min(closes), 2) if closes else None,
            }
            return {k: v for k, v in result.items() if v is not None}

        @tool
        def analyst_recommendations(symbol: str) -> list:
            """Get analyst recommendations breakdown for a stock."""
            t = yf.Ticker(symbol)
            recs = t.recommendations
            if recs is not None and not recs.empty:
                return recs.tail(5).to_dict("records")
            return [{"info": "No recent recommendations"}]

        tools_stocks = [stock_price, stock_analysis, analyst_recommendations]
    except ImportError:
        pass

    # ── FRED (Macro) ─────────────────────────────────────────
    try:
        from sentinel.scrapers.fred import get_fred_series, get_economic_dashboard

        @tool
        def macro_dashboard() -> dict:
            """Get FRED macro dashboard: GDP, CPI, unemployment, fed funds rate, VIX, 10Y-2Y spread."""
            return get_economic_dashboard()

        @tool
        def fred_series(series_id: str) -> dict:
            """Get a specific FRED series. Common: FEDFUNDS, CPIAUCSL, GDP, UNRATE, T10Y2Y, VIXCLS."""
            return get_fred_series(series_id)

        tools_macro = [macro_dashboard, fred_series]
    except ImportError:
        pass

    # ── Y2 Intelligence ──────────────────────────────────────
    try:
        from sentinel.scrapers.y2 import get_news_sentiment, get_news_recap, get_intelligence_reports

        @tool
        def y2_sentiment(ticker: str = "BTC") -> dict:
            """Get Y2 Intelligence sentiment analysis for a ticker."""
            return get_news_sentiment(ticker)

        @tool
        def y2_recap(ticker: str = "BTC") -> dict:
            """Get Y2 Intelligence recap report for a ticker."""
            return get_news_recap(ticker)

        @tool
        def y2_reports() -> list:
            """Get latest Y2 Intelligence reports."""
            return get_intelligence_reports()

        tools_sentiment.extend([y2_sentiment, y2_recap, y2_reports])
    except ImportError:
        pass

    # ── Elfa AI ───────────────────────────────────────────────
    try:
        from sentinel.scrapers.elfa import (
            get_trending_tokens, get_top_mentions, search_mentions,
            get_trending_narratives, get_token_news,
        )

        @tool
        def elfa_trending() -> list:
            """Get trending tokens from Elfa AI social analysis."""
            return get_trending_tokens()

        @tool
        def elfa_mentions(query: str) -> dict:
            """Get social media mentions for a search query from Elfa AI."""
            return get_top_mentions(query)

        @tool
        def elfa_narratives() -> list:
            """Get trending crypto narratives from Elfa AI."""
            return get_trending_narratives()

        tools_sentiment.extend([elfa_trending, elfa_mentions, elfa_narratives])
    except ImportError:
        pass

    # ── X / Twitter ───────────────────────────────────────────
    try:
        from sentinel.scrapers.x import XScraper

        @tool
        def search_x(query: str, max_results: int = 10) -> list:
            """Search recent tweets on X (Twitter) for a query."""
            token = os.getenv("X_BEARER_TOKEN", "")
            if not token:
                return [{"error": "X_BEARER_TOKEN not set"}]
            return XScraper(token).search_tweets(query, max_results)

        tools_sentiment.append(search_x)
    except ImportError:
        pass

    # ── Hyperliquid ───────────────────────────────────────────
    try:
        from sentinel.scrapers.hyperliquid import (
            get_hl_account_info, get_hl_positions, get_hl_orderbook,
            get_hl_config, get_hl_open_orders,
            place_hl_order as _place, cancel_hl_order as _cancel,
            close_hl_position as _close,
        )

        @tool
        def hl_account() -> dict:
            """Get Hyperliquid account info: equity, margin, positions."""
            return get_hl_account_info()

        @tool
        def hl_positions() -> list:
            """Get all open Hyperliquid perpetual positions."""
            return get_hl_positions()

        @tool
        def hl_orderbook(symbol: str) -> dict:
            """Get Hyperliquid order book for a symbol (e.g. 'BTC')."""
            return get_hl_orderbook(symbol)

        @tool
        def hl_open_orders() -> list:
            """Get all open/pending Hyperliquid orders."""
            return get_hl_open_orders()

        @tool
        def hl_place_order(coin: str, side: str, size: float, price: float = 0, order_type: str = "market") -> dict:
            """Place a Hyperliquid perp order. side='buy'|'sell'. ⚠️ REAL TRADING."""
            return _place(coin=coin, side=side, size=size, price=price, order_type=order_type)

        @tool
        def hl_cancel_order(coin: str, oid: str) -> dict:
            """Cancel a Hyperliquid order by coin and order ID."""
            return _cancel(coin=coin, oid=oid)

        @tool
        def hl_close_position(coin: str) -> dict:
            """Close an entire Hyperliquid position at market price. ⚠️ REAL TRADING."""
            return _close(coin=coin)

        tools_trading_hl = [hl_account, hl_positions, hl_orderbook, hl_open_orders,
                           hl_place_order, hl_cancel_order, hl_close_position]
    except ImportError:
        pass

    # ── Aster DEX ─────────────────────────────────────────────
    try:
        from sentinel.scrapers.aster import (
            aster_ticker, aster_orderbook, aster_klines, aster_funding_rate,
            aster_balance, aster_positions, aster_place_order, aster_cancel_order,
            aster_set_leverage,
        )

        @tool
        def aster_market(symbol: str = "BTCUSDT") -> dict:
            """Get Aster DEX futures ticker data."""
            return aster_ticker(symbol)

        @tool
        def aster_book(symbol: str = "BTCUSDT", limit: int = 10) -> dict:
            """Get Aster DEX order book."""
            return aster_orderbook(symbol, limit)

        @tool
        def aster_candles(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 50) -> list:
            """Get Aster DEX candlestick data. Intervals: 1m, 5m, 15m, 1h, 4h, 1d."""
            return aster_klines(symbol, interval, limit)

        @tool
        def aster_funding(symbol: str = "BTCUSDT") -> dict:
            """Get current Aster DEX funding rate."""
            return aster_funding_rate(symbol)

        @tool
        def aster_get_positions() -> list:
            """Get Aster DEX open positions."""
            return aster_positions()

        @tool
        def aster_get_balance() -> dict:
            """Get Aster DEX account balance."""
            return aster_balance()

        @tool
        def aster_order(symbol: str, side: str, quantity: float = 0, order_type: str = "MARKET", price: float = 0) -> dict:
            """Place Aster DEX futures order. side='BUY'|'SELL'. ⚠️ REAL TRADING."""
            return aster_place_order(symbol=symbol, side=side, quantity=quantity, order_type=order_type, price=price if price else None)

        tools_trading_aster = [aster_market, aster_book, aster_candles, aster_funding,
                              aster_get_positions, aster_get_balance, aster_order]
    except ImportError:
        pass

    # ── Polymarket ────────────────────────────────────────────
    try:
        from sentinel.scrapers.polymarket import (
            search_polymarket, get_polymarket_markets, get_polymarket_orderbook,
            get_polymarket_price, get_polymarket_positions,
            buy_polymarket, sell_polymarket,
        )

        @tool
        def pm_search(query: str) -> list:
            """Search Polymarket prediction markets by query."""
            return search_polymarket(query)

        @tool
        def pm_markets() -> list:
            """Get active Polymarket prediction markets."""
            return get_polymarket_markets()

        @tool
        def pm_positions() -> list:
            """Get your open Polymarket positions."""
            return get_polymarket_positions()

        @tool
        def pm_buy(token_id: str, amount: float, price: float) -> dict:
            """Buy shares on Polymarket. ⚠️ REAL TRADING."""
            return buy_polymarket(token_id=token_id, amount=amount, price=price)

        tools_trading_pm = [pm_search, pm_markets, pm_positions, pm_buy]
    except ImportError:
        pass

    # ── Telegram ──────────────────────────────────────────────
    try:
        from sentinel.scrapers.telegram import tg_read_channel, tg_search_messages, tg_list_channels, tg_send_message

        @tool
        def telegram_read(channel: str, limit: int = 10) -> list:
            """Read recent messages from a Telegram channel."""
            return tg_read_channel(channel, limit)

        @tool
        def telegram_search(channel: str, query: str) -> list:
            """Search Telegram channel messages."""
            return tg_search_messages(channel, query)

        @tool
        def telegram_channels() -> list:
            """List your Telegram chats and channels."""
            return tg_list_channels()

        tools_social_tg = [telegram_read, telegram_search, telegram_channels]
    except ImportError:
        pass

    # ── Discord ───────────────────────────────────────────────
    try:
        from sentinel.scrapers.discord import (
            discord_read_channel, discord_search_messages,
            discord_list_guilds, discord_list_channels,
        )

        @tool
        def dc_read(channel_id: int, limit: int = 50) -> list:
            """Read recent messages from a Discord channel."""
            return discord_read_channel(channel_id, limit)

        @tool
        def dc_search(channel_id: int, query: str) -> list:
            """Search Discord channel messages."""
            return discord_search_messages(channel_id, query)

        @tool
        def dc_guilds() -> list:
            """List Discord servers the bot is in."""
            return discord_list_guilds()

        tools_social_discord = [dc_read, dc_search, dc_guilds]
    except ImportError:
        pass

    return (tools_crypto, tools_stocks, tools_macro, tools_sentiment,
            tools_trading_hl, tools_trading_aster, tools_trading_pm,
            tools_social_tg, tools_social_discord)


# ══════════════════════════════════════════════════════════════════════
# Agent Definitions
# ══════════════════════════════════════════════════════════════════════

def _detect_model() -> str:
    """Detect the LLM model string for Upsonic from env config."""
    provider = os.getenv("LLM_PROVIDER", "CLAUDE").upper()
    if provider in ("CLAUDE", "ANTHROPIC"):
        key = os.getenv("ANTHROPIC_API_KEY", "") or os.getenv("LLM_API_KEY", "")
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
        model = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
        return f"anthropic/{model}"
    elif provider in ("OPENAI", "GPT"):
        key = os.getenv("OPENAI_API_KEY", "") or os.getenv("LLM_API_KEY", "")
        if key:
            os.environ["OPENAI_API_KEY"] = key
        model = os.getenv("LLM_MODEL", "gpt-4o")
        return f"openai/{model}"
    elif provider in ("GOOGLE", "GEMINI"):
        key = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "") or os.getenv("LLM_API_KEY", "")
        if key:
            os.environ["GEMINI_API_KEY"] = key
        model = os.getenv("LLM_MODEL", "gemini-2.0-flash")
        return f"google/{model}"
    elif provider in ("XAI", "GROK"):
        key = os.getenv("XAI_API_KEY", "") or os.getenv("LLM_API_KEY", "")
        if key:
            os.environ["XAI_API_KEY"] = key
        model = os.getenv("LLM_MODEL", "grok-2")
        return f"xai/{model}"
    return "anthropic/claude-sonnet-4-20250514"


def _build_memory():
    """Build Upsonic SQLite memory for persistent agent context."""
    try:
        from upsonic.storage.memory.memory import Memory
        from upsonic.storage.providers.sqlite import SqliteStorage
        from pathlib import Path

        db_dir = Path.home() / ".sentinel"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(db_dir / "swarm_memory.db")

        storage = SqliteStorage("sessions", "profiles", db_path)
        memory = Memory(
            storage=storage,
            session_id="sentinel_swarm",
            user_id="sentinel",
            full_session_memory=True,
            summary_memory=True,
        )
        logger.info("Upsonic SQLite memory → %s", db_path)
        return memory
    except Exception as e:
        logger.warning("Upsonic memory unavailable: %s", e)
        return None


def build_swarm(mode: str = "coordinate"):
    """
    Build the Sentinel agent swarm.

    Returns:
        (team, {"analyst": agent, "risk": agent, "trader": agent})
        or (None, {}) if Upsonic is not installed.

    Modes:
        - "coordinate" — leader agent delegates to specialists (default)
        - "sequential" — agents run in fixed order
        - "parallel" — agents run simultaneously
    """
    try:
        from upsonic import Agent, Team
    except ImportError:
        logger.error("upsonic not installed. Run: pip install upsonic")
        return None, {}

    model = _detect_model()
    memory = _build_memory()

    # Build tool groups
    (tools_crypto, tools_stocks, tools_macro, tools_sentiment,
     tools_hl, tools_aster, tools_pm, tools_tg, tools_discord) = _build_tools()

    all_research_tools = tools_crypto + tools_stocks + tools_macro + tools_sentiment
    all_trading_tools = tools_hl + tools_aster + tools_pm
    all_social_tools = tools_tg + tools_discord

    # ── Analyst Agent ────────────────────────────────────
    analyst = Agent(
        name="Analyst",
        model=model,
        role="Market Research & Macro Analysis Specialist",
        goal="Research markets, analyze macro conditions, surface sentiment signals, and provide quantitative analysis",
        instructions=(
            "You are a quantitative analyst. Use tools to get REAL data — never fabricate. "
            "Use CoinGecko for crypto prices. YFinance for stocks (use stock_analysis for deep dives). "
            "FRED for macro (GDP, CPI, rates, VIX). Y2 + Elfa for sentiment. "
            "Be quantitative: cite specific numbers, percentages, changes. Flag anything unusual. "
            "Format numbers clearly: $87,421.32 not 87421.32."
        ),
        memory=memory,
        retry=2,
    )

    # ── Risk Manager Agent ───────────────────────────────
    risk_mgr = Agent(
        name="RiskManager",
        model=model,
        role="Portfolio Risk & Position Sizing Specialist",
        goal="Assess risk, size positions, protect capital, approve or reject trade proposals",
        instructions=(
            "You are a risk manager. Max 5% equity per trade. Flag if leverage >3x. "
            "Warn if one asset >30% of portfolio. Consider macro conditions for risk adjustments. "
            "You APPROVE or REJECT trade proposals. Calculate position sizes based on account equity. "
            "Check volatility (beta, daily vol) before sizing. Use stop-loss recommendations."
        ),
        memory=memory,
        retry=2,
    )

    # ── Trader Agent ─────────────────────────────────────
    trader = Agent(
        name="Trader",
        model=model,
        role="Trade Execution Specialist",
        goal="Execute trades precisely across Hyperliquid, Aster DEX, and Polymarket",
        instructions=(
            "ALWAYS confirm before executing trades. State exact order details: "
            "venue, direction, size, price. After execution, report fill price and order ID. "
            "For market data queries (orderbook, positions), act freely without confirmation. "
            "Use Hyperliquid for perp futures, Aster for altcoin futures, Polymarket for prediction markets."
        ),
        memory=memory,
        retry=2,
    )

    # Build team with coordinate mode (leader delegates)
    team = Team(
        agents=[analyst, risk_mgr, trader],
        mode=mode,
        model=model,
        memory=memory,
    )

    agents = {
        "analyst": analyst,
        "risk": risk_mgr,
        "trader": trader,
    }

    # Attach tool groups for task routing
    team._sentinel_tools = {
        "research": all_research_tools,
        "trading": all_trading_tools,
        "social": all_social_tools,
        "all": all_research_tools + all_trading_tools + all_social_tools,
    }

    logger.info(
        "Swarm ready — 3 agents · %s mode · %d tools · model: %s",
        mode, len(all_research_tools + all_trading_tools + all_social_tools), model,
    )
    return team, agents


# ══════════════════════════════════════════════════════════════════════
# Chat Interface
# ══════════════════════════════════════════════════════════════════════

def swarm_chat(team, message: str, tool_group: str = "all") -> str:
    """
    Send a message to the Sentinel swarm and get a coordinated response.

    Args:
        team: The Upsonic Team object from build_swarm()
        message: User's query
        tool_group: Which tools to attach — "research", "trading", "social", "all"

    Returns:
        Response string from the coordinated agents
    """
    if team is None:
        return "Swarm not initialized. Run: pip install upsonic"

    try:
        from upsonic import Task

        tools = getattr(team, "_sentinel_tools", {}).get(tool_group, [])
        task = Task(description=message, tools=tools)
        result = team.do([task])
        return str(result) if result else "No response from swarm."
    except Exception as e:
        logger.error("Swarm chat failed: %s", e)
        return f"Swarm error: {e}"


def swarm_status(team, agents: dict) -> dict:
    """Get swarm status for dashboard display."""
    if team is None:
        return {"status": "offline", "reason": "upsonic not installed"}

    return {
        "status": "online",
        "mode": getattr(team, "mode", "coordinate"),
        "model": _detect_model(),
        "agents": [
            {"name": "Analyst", "role": "Market Research & Macro", "status": "online", "subject": "sentinel.analyst"},
            {"name": "RiskManager", "role": "Portfolio Risk & Sizing", "status": "online", "subject": "sentinel.risk"},
            {"name": "Trader", "role": "Trade Execution", "status": "online", "subject": "sentinel.trader"},
        ],
        "tool_count": len(getattr(team, "_sentinel_tools", {}).get("all", [])),
    }
