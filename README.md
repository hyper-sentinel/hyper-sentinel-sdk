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

## Quick Start

```bash
# One-time setup — paste your AI key, configure wallets
sentinel-setup
```

```python
from sentinel import SentinelClient

# After setup, zero arguments needed — keys auto-loaded from ~/.sentinel/config
client = SentinelClient()

# Market data
btc = client.get_crypto_price("bitcoin")
top = client.get_crypto_top_n(10)
aapl = client.get_stock_price("AAPL")

# AI chat (proxied through Sentinel — usage fees apply)
resp = client.chat("Analyze BTC market structure")

# Perpetual trading (Hyperliquid)
client.place_hl_order(coin="ETH", side="buy", size=0.5, leverage=5)

# DEX swaps (Solana / Ethereum)
client.dex_buy_sol(contract_address="So1...", amount_sol=0.5, slippage=5.0)

# Social intelligence
trending = client.get_trending_tokens()
news = client.get_news_sentiment("ethereum")
```

## Authentication — Web4

**No email. No password. Your AI provider key is your identity.**

```python
# Option 1: Interactive setup (recommended)
# Run once — saves to ~/.sentinel/config
$ sentinel-setup

# Option 2: Pass directly
client = SentinelClient(ai_key="sk-ant-xxx")

# Option 3: Use your Sentinel API key directly
client = SentinelClient(api_key="sk-sentinel-xxx")
```

Supported providers:

| Provider | Key Prefix | Sign Up |
|:---------|:-----------|:--------|
| Anthropic (Claude) | `sk-ant-` | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | `sk-` | [platform.openai.com](https://platform.openai.com) |
| Google (Gemini) | `AIza` | [aistudio.google.com](https://aistudio.google.com) |
| xAI (Grok) | `xai-` | [console.x.ai](https://console.x.ai) |

### How It Works

1. You provide your AI provider key (e.g. `sk-ant-xxx`)
2. Sentinel hashes it → creates a deterministic account (no email needed)
3. You get a `sk-sentinel-xxx` key — cached locally to `~/.sentinel/config`
4. All API calls use your Sentinel key — your AI key is never sent again

## CLI Commands

```bash
# Getting started
sentinel-setup              # Full onboarding wizard (AI key + wallets)
sentinel status             # Connection status dashboard
sentinel test               # Smoke test (auth + health + BTC price)
sentinel help               # Full categorized command reference

# Wallet management (Phantom-style)
sentinel wallet             # Dashboard — show wallets + balances
sentinel wallet connect     # Import private key (SOL or ETH)
sentinel wallet generate sol # Generate a new Solana wallet
sentinel wallet send        # Send crypto (with confirmation prompt)
sentinel wallet receive     # Show deposit addresses

# Add data sources & trading venues
sentinel add                # Show all available integrations
sentinel add hl             # Hyperliquid DEX trading
sentinel add aster          # Aster DEX futures
sentinel add polymarket     # Polymarket prediction markets
sentinel add y2             # Y2 news intelligence
sentinel add x              # X (Twitter) API
sentinel add fred           # FRED economic data
sentinel add elfa           # Elfa AI social intel
sentinel add telegram       # Telegram Client
sentinel add discord        # Discord bot
sentinel add tv             # TradingView webhooks

# Billing & upgrade
sentinel billing            # View tier, usage, and fees
sentinel upgrade            # Upgrade to Pro ($100/mo)
sentinel upgrade enterprise # Upgrade to Enterprise ($1,000/mo)
sentinel tools              # List all 80+ available tools
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
| **Billing** | `usdc_balance` `usdc_deposit_address` `usdc_check_deposits` | USDC balance & usage |

> Every tool is available on every tier. See the [full API reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) for parameters and response formats.

## Pricing

All 80+ tools are available on every tier. Upgrading reduces fees and increases rate limits.

| | Free | Pro | Enterprise |
|:--|:--:|:--:|:--:|
| **Price** | $0/mo | $100/mo | $1,000/mo |
| **LLM Markup** | 40% | 20% | 10% |
| **Maker Fee** | 0.10% | 0.06% | 0.02% |
| **Taker Fee** | 0.08% | 0.04% | 0.01% |
| **Rate Limit** | 300/min | 1,000/min | Unlimited |

```python
# Check billing status
status = client.billing_status()

# Upgrade via CLI
# sentinel upgrade pro
# sentinel upgrade enterprise

# Or check your USDC balance
balance = client.usdc_balance()
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
