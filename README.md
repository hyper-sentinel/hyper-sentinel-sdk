<div align="center">
<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/HYPER--SENTINEL-SDK-white?style=for-the-badge&labelColor=0d1117&color=0d1117">
  <img alt="Hyper-Sentinel SDK" src="https://img.shields.io/badge/HYPER--SENTINEL-SDK-black?style=for-the-badge">
</picture>

### Python SDK for the Sentinel API Gateway

80+ tools for crypto trading, AI, market intelligence & autonomous strategies

<br/>

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=pypi&color=3572A5)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat&logo=python&logoColor=white&color=3572A5)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/github/license/hyper-sentinel/hyper-sentinel-sdk?style=flat&color=3572A5)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=downloads&color=3572A5)](https://pypi.org/project/hyper-sentinel/)

[Website](https://hyper-sentinel.com) · [Documentation](https://hyper-sentinel.com/docs/) · [REST API Reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) · [PyPI](https://pypi.org/project/hyper-sentinel/)

<br/>
</div>

## Install

```bash
pip install hyper-sentinel
```

or with [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv add hyper-sentinel
```

## Quick Start

```python
from sentinel import SentinelClient

client = SentinelClient()
client.register(email="you@example.com", password="secure123", name="Your Name")

# Generate a persistent API key
key = client.generate_key(name="my-bot")
# → sk-sentinel-xxx (save this!)

# Market data
btc = client.get_crypto_price("bitcoin")
top = client.get_crypto_top_n(10)
aapl = client.get_stock_price("AAPL")

# AI chat (bring your own key)
resp = client.chat("Analyze BTC market structure", ai_key="sk-ant-xxx")

# Perpetual trading
client.place_hl_order(coin="ETH", side="buy", size=0.5, leverage=5)

# DEX swaps
client.dex_buy_sol(contract_address="So1...", amount_sol=0.5, slippage=5.0)

# Social intelligence
trending = client.get_trending_tokens()
news = client.get_news_sentiment("ethereum")
```

## Authentication

```python
# New account
client = SentinelClient()
client.register(email="you@mail.com", password="pass", name="You")

# Existing account
client = SentinelClient()
client.login(email="you@mail.com", password="pass")

# API key (recommended for bots)
client = SentinelClient(api_key="sk-sentinel-xxx")
```

## What's Included

| Category | Tools | Description |
|:---------|:------|:------------|
| **Crypto** | `get_crypto_price` `get_crypto_top_n` `search_crypto` | CoinGecko market data |
| **Equities** | `get_stock_price` `get_stock_info` `get_analyst_recs` `get_stock_news` `get_stock_history` | yfinance quotes & analysis |
| **Macro** | `get_fred_series` `search_fred` `get_economic_dashboard` | FRED economic data |
| **News** | `get_news_sentiment` `get_news_recap` `get_intelligence_reports` | Sentiment & analysis |
| **Social** | `get_trending_tokens` `get_top_mentions` `search_mentions` `get_trending_narratives` | Elfa AI social intelligence |
| **X / Twitter** | `search_x` | Real-time social search |
| **DexScreener** | `dexscreener_search` `dexscreener_trending` `dexscreener_token` `dexscreener_pair` | DEX pair analytics |
| **Hyperliquid** | `place_hl_order` `get_hl_positions` `get_hl_orderbook` `cancel_hl_order` `close_hl_position` | Perpetual futures |
| **Aster DEX** | `aster_place_order` `aster_positions` `aster_ticker` `aster_klines` `aster_balance` | Perpetual futures |
| **DEX Swaps** | `dex_buy_sol` `dex_sell_sol` `dex_buy_eth` `dex_sell_eth` `dex_price_sol` `dex_price_eth` | On-chain trading |
| **AI Chat** | `chat` `llm_usage` | Claude, GPT-4o, Gemini, Grok |
| **Algo** | `set_strategy` `start_strategy` `stop_strategy` `list_algos` | Automated strategies |
| **Wallets** | `generate_wallet` `import_wallet` `list_wallets` `get_wallet_balance` `send_crypto` | Multi-chain wallets |
| **Telegram** | `tg_get_updates` `tg_send_message` | Messaging integration |
| **Discord** | `discord_read_channel` `discord_send_message` `discord_list_guilds` | Server integration |
| **Polymarket** | `get_polymarket_events` `search_polymarket` | Prediction markets |
| **Journal** | `get_trade_journal` `get_trade_stats` | Trade history & analytics |
| **Billing** | `billing_status` `billing_usage` `upgrade` | Tier management |

> Every tool is available on every tier. See the [full API reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) for parameters and response formats.

## Pricing

All tools are available on every tier. Upgrading reduces per-call fees.

| | Free | Pro | Enterprise |
|:--|:--:|:--:|:--:|
| **Monthly** | $0 | $100 | $1,000 |
| **LLM Markup** | 3× | 2× | 1.2× |
| **Trade Fee** | 0.05% | 0.03% | 0.01% |
| **Data Fee** | $0.001/call | $0.0005/call | Free |
| **Rate Limit** | 100/min | 500/min | Unlimited |

```python
url = client.upgrade("pro")           # Returns Stripe checkout URL
url = client.upgrade("enterprise")
```

## Error Handling

```python
from sentinel.exceptions import SentinelError, AuthError, RateLimitError, ToolNotFoundError

try:
    client.place_hl_order(coin="ETH", side="buy", size=0.1)
except RateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except AuthError:
    print("Invalid credentials")
```

## Architecture

```
Your App → hyper-sentinel (Python SDK)
               │ HTTPS
         Sentinel Go Gateway (Cloud Run)
               │ gRPC / HTTP
         Python Engine (FastAPI)
               │
     ┌─────────┼──────────┐
   Trading   Data       AI
   ────────  ────────   ────────
   Hyperliquid  CoinGecko   Claude
   Aster DEX    yfinance    GPT-4o
   Jupiter      FRED        Gemini
   Uniswap      Elfa AI     Grok
```

## Links

- [hyper-sentinel.com](https://hyper-sentinel.com) — Website
- [hyper-sentinel.com/docs](https://hyper-sentinel.com/docs/) — SDK Documentation
- [REST API Reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) — Every endpoint documented
- [pypi.org/project/hyper-sentinel](https://pypi.org/project/hyper-sentinel/) — PyPI Package

## License

[AGPL-3.0](LICENSE) — © 2026 Sentinel Labs
