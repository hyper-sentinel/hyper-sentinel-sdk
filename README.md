<div align="center">

# Hyper-Sentinel SDK

**Python SDK for the Sentinel API Gateway**

80+ tools for crypto trading, AI chat, market intelligence, and autonomous strategies.

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat-square&color=00ff4c&labelColor=010a03)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat-square&color=b4ff00&labelColor=010a03)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/badge/license-AGPL--3.0-39ff14?style=flat-square&labelColor=010a03)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-hyper--sentinel.com-00ff4c?style=flat-square&labelColor=010a03)](https://hyper-sentinel.com/docs/)

[Website](https://hyper-sentinel.com) · [Docs](https://hyper-sentinel.com/docs/) · [REST API](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) · [PyPI](https://pypi.org/project/hyper-sentinel/)

</div>

---

## Install

```bash
pip install hyper-sentinel
```

```bash
uv add hyper-sentinel
```

> Requires **Python 3.10+**

---

## Quick Start

```python
from sentinel import SentinelClient

# Create account + authenticate
client = SentinelClient()
client.register(email="you@example.com", password="secure123", name="Your Name")

# Generate a persistent API key (save this!)
key = client.generate_key(name="my-bot")
# → sk-sentinel-xxx

# ─── Market Data ───────────────────────────
btc = client.get_crypto_price("bitcoin")
top = client.get_crypto_top_n(10)
aapl = client.get_stock_price("AAPL")
macro = client.get_economic_dashboard()

# ─── AI Chat (bring your own key) ─────────
resp = client.chat(
    "Analyze BTC market structure",
    ai_key="sk-ant-xxx",       # Anthropic, OpenAI, Google, xAI
    model="claude-sonnet-4-20250514",
)

# ─── Perpetual Trading ────────────────────
client.place_hl_order(coin="ETH", side="buy", size=0.5, leverage=5)
client.get_hl_positions()
client.close_hl_position("ETH")

# ─── DEX Swaps ────────────────────────────
client.dex_buy_sol(contract_address="So1...", amount_sol=0.5, slippage=5.0)
client.dex_price_sol("So1...")

# ─── Intelligence ─────────────────────────
trending = client.get_trending_tokens()
news = client.get_news_sentiment("ethereum")
tweets = client.search_x("BTC", max_results=20)
```

---

## Authentication

```python
# Option 1: Register (new account)
client = SentinelClient()
client.register(email="you@mail.com", password="pass", name="You")

# Option 2: Login (existing account)
client = SentinelClient()
client.login(email="you@mail.com", password="pass")

# Option 3: API Key (recommended for bots & scripts)
client = SentinelClient(api_key="sk-sentinel-xxx")
```

---

## Features

<table>
<tr>
<td width="50%">

### 📈 Market Data
- **Crypto** — CoinGecko prices, top N, search
- **Equities** — yfinance quotes, analyst ratings, news
- **Macro** — FRED series, economic dashboard
- **DexScreener** — trending pairs, token lookup

</td>
<td width="50%">

### 🤖 AI Chat
- **Multi-LLM** — Claude, GPT-4o, Gemini, Grok
- **Bring your own key** — no markup lock-in
- **Tier-based pricing** — lower fees as you scale
- **Token metering** — transparent cost tracking

</td>
</tr>
<tr>
<td>

### ⚡ Trading
- **Hyperliquid** — perps, leverage, order management
- **Aster DEX** — perpetual futures on Aster
- **DEX Swaps** — Solana (Jupiter) & Ethereum (Uniswap)
- **Algo Trading** — configure & run strategies

</td>
<td>

### 🔍 Intelligence
- **Elfa AI** — trending tokens, social narratives
- **News** — sentiment analysis, market recaps
- **X / Twitter** — real-time social search
- **Polymarket** — prediction market data

</td>
</tr>
<tr>
<td>

### 💬 Messaging
- **Telegram** — read channels, send messages
- **Discord** — guilds, channels, search, send
- **TradingView** — webhook alert ingestion

</td>
<td>

### 👛 Wallets & Billing
- **Multi-chain** — generate/import Sol, Eth, BTC wallets
- **Send crypto** — transfer from managed wallets
- **USDC billing** — deposit, check balances
- **Stripe** — subscription management

</td>
</tr>
</table>

---

## All Methods (80+)

<details>
<summary><strong>Market Data — Crypto</strong></summary>

| Method | Description |
|--------|-------------|
| `get_crypto_price(coin_id)` | Live price, market cap, 24h change |
| `get_crypto_top_n(n)` | Top N by market cap |
| `search_crypto(query)` | Search by name or symbol |

</details>

<details>
<summary><strong>Market Data — Equities</strong></summary>

| Method | Description |
|--------|-------------|
| `get_stock_price(symbol)` | Current price and metrics |
| `get_stock_info(symbol)` | Company fundamentals |
| `get_analyst_recs(symbol)` | Analyst consensus |
| `get_stock_news(symbol)` | Ticker news |
| `get_stock_history(symbol, period)` | OHLCV history |

</details>

<details>
<summary><strong>Market Data — Macro (FRED)</strong></summary>

| Method | Description |
|--------|-------------|
| `get_fred_series(series_id, limit)` | FRED time series |
| `search_fred(query)` | Search economic indicators |
| `get_economic_dashboard()` | GDP, CPI, rates dashboard |

</details>

<details>
<summary><strong>News & Intelligence</strong></summary>

| Method | Description |
|--------|-------------|
| `get_news_sentiment(query)` | Sentiment-analyzed news |
| `get_news_recap()` | Market recap |
| `get_intelligence_reports()` | Curated reports |
| `get_report_detail(report_id)` | Full report |

</details>

<details>
<summary><strong>Social Intelligence (Elfa AI)</strong></summary>

| Method | Description |
|--------|-------------|
| `get_trending_tokens()` | Trending by social volume |
| `get_top_mentions()` | Most mentioned tokens |
| `search_mentions(query)` | Search social mentions |
| `get_trending_narratives()` | Emerging narratives |
| `get_token_news(token)` | Token-specific news + social |

</details>

<details>
<summary><strong>X / Twitter</strong></summary>

| Method | Description |
|--------|-------------|
| `search_x(query, max_results)` | Search X for recent posts |

</details>

<details>
<summary><strong>DexScreener</strong></summary>

| Method | Description |
|--------|-------------|
| `dexscreener_search(query)` | Search token pairs |
| `dexscreener_token(address)` | Pairs for a token |
| `dexscreener_trending()` | Trending pairs |
| `dexscreener_pair(chain, pair)` | Detailed pair data |

</details>

<details>
<summary><strong>Trading — Hyperliquid</strong></summary>

| Method | Description |
|--------|-------------|
| `get_hl_config()` | Exchange configuration |
| `get_hl_orderbook(coin)` | Level-2 order book |
| `get_hl_account_info()` | Account equity & margin |
| `get_hl_positions()` | Open positions with P&L |
| `get_hl_open_orders()` | Pending orders |
| `place_hl_order(coin, side, size, ...)` | Place orders |
| `cancel_hl_order(coin, order_id)` | Cancel order |
| `close_hl_position(coin)` | Market close |

</details>

<details>
<summary><strong>Trading — Aster DEX</strong></summary>

| Method | Description |
|--------|-------------|
| `aster_ping()` | Connectivity test |
| `aster_ticker(symbol)` | 24h ticker |
| `aster_orderbook(symbol, limit)` | Order book |
| `aster_klines(symbol, interval, limit)` | Candlestick data |
| `aster_funding_rate(symbol)` | Funding rate |
| `aster_exchange_info()` | Symbols & rules |
| `aster_diagnose()` | API diagnostics |
| `aster_balance()` | Account balances |
| `aster_positions()` | Open positions |
| `aster_account_info()` | Account details |
| `aster_place_order(...)` | Place orders |

</details>

<details>
<summary><strong>Trading — DEX Swaps</strong></summary>

| Method | Description |
|--------|-------------|
| `dex_buy_sol(address, amount, slippage)` | Buy with SOL |
| `dex_sell_sol(address, pct, slippage)` | Sell for SOL |
| `dex_buy_eth(address, amount, slippage)` | Buy with ETH |
| `dex_sell_eth(address, pct, slippage)` | Sell for ETH |
| `dex_price_sol(address)` | Solana token price |
| `dex_price_eth(address)` | Ethereum token price |

</details>

<details>
<summary><strong>Algo Trading</strong></summary>

| Method | Description |
|--------|-------------|
| `get_strategy()` | Active strategy config |
| `set_strategy(name, params, ...)` | Configure strategy |
| `list_algos()` | Available strategies |
| `start_strategy()` | Start |
| `stop_strategy()` | Stop |

</details>

<details>
<summary><strong>Wallets</strong></summary>

| Method | Description |
|--------|-------------|
| `generate_wallet(chain)` | Generate (sol/eth/btc) |
| `import_wallet(chain, key, label)` | Import existing |
| `list_wallets()` | All managed wallets |
| `get_wallet_balance(address, chain)` | Check balances |
| `send_crypto(to, amount, chain)` | Send crypto |

</details>

<details>
<summary><strong>Telegram</strong></summary>

| Method | Description |
|--------|-------------|
| `tg_get_updates(limit)` | Poll messages |
| `tg_send_message(target, message)` | Send message |

</details>

<details>
<summary><strong>Discord</strong></summary>

| Method | Description |
|--------|-------------|
| `discord_read_channel(channel_id, limit)` | Read messages |
| `discord_search_messages(channel_id, query)` | Search |
| `discord_list_guilds()` | List servers |
| `discord_list_channels(guild_id)` | List channels |
| `discord_send_message(channel_id, content)` | Send message |

</details>

<details>
<summary><strong>AI Chat</strong></summary>

| Method | Description |
|--------|-------------|
| `chat(message, ai_key, model, provider)` | Multi-LLM chat |
| `llm_usage()` | Token usage & costs |

</details>

<details>
<summary><strong>Billing & System</strong></summary>

| Method | Description |
|--------|-------------|
| `billing_status()` | Tier, subscription, fees |
| `billing_usage()` | Current period usage |
| `billing_history()` | Past invoices |
| `upgrade(plan)` | Stripe checkout |
| `health()` | API health check |
| `list_tools()` | All available tools |
| `tool_info(name)` | Tool schema |
| `call_tool(name, **kwargs)` | Generic tool caller |

</details>

---

## Pricing

All tools available on every tier. Upgrading reduces fees.

| | **Free** | **Pro** ($100/mo) | **Enterprise** ($1K/mo) |
|:--|:--:|:--:|:--:|
| Access | ✅ Everything | ✅ Everything | ✅ Everything |
| LLM Markup | 3× | 2× | 1.2× |
| Trade Fee | 0.05% | 0.03% | 0.01% |
| Data Fee | $0.001/call | $0.0005/call | Free |
| Rate Limit | 100/min | 500/min | Unlimited |

```python
url = client.upgrade("pro")           # Returns Stripe checkout URL
url = client.upgrade("enterprise")
```

---

## Error Handling

```python
from sentinel.exceptions import (
    SentinelError,      # Base — catch-all
    AuthError,          # 401
    ForbiddenError,     # 403
    RateLimitError,     # 429 (auto-retried 3×)
    ToolNotFoundError,  # 404
)

try:
    client.place_hl_order(coin="ETH", side="buy", size=0.1)
except RateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except AuthError:
    print("Invalid credentials")
```

---

## Architecture

```
Your App ──→ hyper-sentinel (Python SDK)
                    │ HTTPS
             Sentinel Go Gateway (Cloud Run)
                    │ gRPC / HTTP
             Python Engine (FastAPI)
                    │
        ┌───────────┼────────────┐
    Hyperliquid   CoinGecko   Anthropic
    Aster DEX     yfinance     OpenAI
    Jupiter       FRED        Gemini
    Uniswap       Elfa AI      xAI
```

---

## Links

| Resource | URL |
|----------|-----|
| 🌐 Website | [hyper-sentinel.com](https://hyper-sentinel.com) |
| 📖 Docs | [hyper-sentinel.com/docs](https://hyper-sentinel.com/docs/) |
| 📡 REST API | [github.com/hyper-sentinel/docs](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) |
| 📦 PyPI | [pypi.org/project/hyper-sentinel](https://pypi.org/project/hyper-sentinel/) |

---

## License

[AGPL-3.0](LICENSE) — © 2026 Sentinel Labs
