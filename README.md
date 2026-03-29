<div align="center">
<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/HYPER--SENTINEL-SDK-white?style=for-the-badge&labelColor=0d1117&color=0d1117">
  <img alt="Hyper-Sentinel SDK" src="https://img.shields.io/badge/HYPER--SENTINEL-SDK-black?style=for-the-badge">
</picture>

### Local-First AI Trading Agent + Python SDK

80+ tools · 12 scrapers · Zero-config · Sub-second queries

<br/>

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=pypi&color=3572A5)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat&logo=python&logoColor=white&color=3572A5)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/github/license/hyper-sentinel/hyper-sentinel-sdk?style=flat&color=3572A5)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=downloads&color=3572A5)](https://pypi.org/project/hyper-sentinel/)

[Website](https://hyper-sentinel.com) · [Documentation](https://hyper-sentinel.com/docs/) · [REST API Reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) · [PyPI](https://pypi.org/project/hyper-sentinel/)

<br/>
</div>

## Quick Start

```bash
pip install hyper-sentinel && sentinel-chat
```

That's it. On first run you'll be prompted for your AI provider API key (Anthropic, OpenAI, Google, or xAI). No email, no password, no account creation. **Your AI key is your identity.**

## What's New in v3.2.0

- **⚡ Fast Path** — Common queries like `price of btc` execute in <1 second with zero LLM calls
- **🔌 All Scrapers Local** — All 12 data sources (CoinGecko, Hyperliquid, FRED, Polymarket, etc.) execute locally — no gateway dependency
- **📊 Config-Aware Dashboard** — Real-time status shows which sources are configured and ready
- **🛡️ Anti-Hallucination** — System prompt hardened to prevent fabricated dates, stats, and metadata
- **🔧 Graceful Errors** — Ctrl+C returns to prompt, 10s connect timeouts prevent hangs

### AI Agent Chat

```
  ⚡ You → price of btc and xmr

  ╭─────────────────────── 🛡️ Sentinel ──╮
  │ Bitcoin (BTC): $66,565.00              │
  │   24h: -0.70%  ·  7d: -3.28%          │
  │   Market cap: $1,331,764,366,464       │
  │                                         │
  │ Monero (XMR): $330.89                  │
  │   24h: +0.18%  ·  7d: -6.13%          │
  │   Market cap: $6,118,626,878           │
  ╰──────────────── ⚡ instant · 0 LLM ───╯
```

**Fast Path queries** (zero compute, sub-1-second):
- `price of btc` / `btc price` / `how much is eth`
- `price of btc and xmr and sol` (multi-coin)
- `top 10 crypto` / `top 20 coins`

Everything else goes through your chosen LLM (Claude, GPT-4o, Gemini, Grok) with full tool access.

### Chat Commands

```
add                  # List available data sources & trading platforms
add ai               # Change LLM provider (Claude ↔ GPT ↔ Gemini ↔ Grok)
add hl               # Configure Hyperliquid perp futures
add polymarket       # Configure Polymarket prediction markets
add aster            # Configure Aster DEX futures
add fred             # Configure FRED economic data (GDP, CPI, rates)
add x                # Configure X/Twitter search & sentiment
add y2               # Configure Y2 Intelligence news
add elfa             # Configure Elfa AI social intelligence
add telegram         # Configure Telegram channel reader
add discord          # Configure Discord bot integration
tools                # List all tools the agent can call
status               # Show infrastructure dashboard
clear                # Reset conversation context
quit                 # Exit chat
```

### One-Shot Queries

```bash
sentinel ask "What are the top 5 cryptos by market cap?"
sentinel ask "Show me AAPL analyst recommendations"
sentinel ask "What's the current fed funds rate?"
```

### Python SDK

```python
from sentinel import SentinelClient

# Zero arguments — keys auto-loaded from ~/.sentinel/config
client = SentinelClient()

# Market data (local, instant)
btc = client.get_crypto_price("bitcoin")
top = client.get_crypto_top_n(10)
aapl = client.get_stock_price("AAPL")

# Perpetual trading (Hyperliquid — local)
client.place_hl_order(coin="ETH", side="buy", size=0.5, leverage=5)

# Prediction markets (Polymarket — local)
markets = client.get_polymarket_markets()

# Social intelligence (Elfa — needs key)
trending = client.get_trending_tokens()
news = client.get_news_sentiment("ethereum")

# AI chat (proxied through LLM — usage fees apply)
resp = client.chat("Analyze BTC market structure")
```

## Data Sources

All sources run **locally** via built-in scrapers. No gateway required.

| Source | Status | Tools | Config |
|:-------|:------:|:------|:-------|
| 🪙 **CoinGecko** | Always available | `get_crypto_price` `get_crypto_top` `search_crypto` | None needed |
| 📈 **YFinance** | Always available | `get_stock_quote` `get_stock_analyst` `get_stock_news` | None needed |
| 📊 **DexScreener** | Always available | `dexscreener_search` `dexscreener_trending` | None needed |
| 🏛️ **FRED** | Needs key | `get_fred_series` `search_fred` `get_economic_dashboard` | `add fred` |
| 📰 **Y2 Intelligence** | Needs key | `get_news_sentiment` `get_news_recap` `get_intelligence_reports` | `add y2` |
| 🔮 **Elfa AI** | Needs key | `get_trending_tokens` `get_top_mentions` `search_mentions` | `add elfa` |
| 🐦 **X (Twitter)** | Needs key | `search_x` | `add x` |
| ⚡ **Hyperliquid** | Needs wallet | `get_hl_positions` `place_hl_order` `get_hl_orderbook` + 7 more | `add hl` |
| 🌟 **Aster DEX** | Needs key | `aster_ticker` `aster_positions` `aster_balance` + 7 more | `add aster` |
| 🎲 **Polymarket** | Needs key | `get_polymarket_markets` `buy_polymarket` + 8 more | `add polymarket` |
| 💬 **Telegram** | Needs session | `tg_read_channel` `tg_search_messages` `tg_list_channels` | `add telegram` |
| 🎮 **Discord** | Needs token | `discord_read_channel` `discord_list_guilds` + 4 more | `add discord` |

## Authentication — Web4

**No email. No password. Your AI provider key is your identity.**

```python
# Option 1: Interactive setup (recommended)
$ sentinel-setup

# Option 2: Pass directly
client = SentinelClient(ai_key="sk-ant-xxx")

# Option 3: Use your Sentinel API key directly
client = SentinelClient(api_key="sk-sentinel-xxx")
```

Supported LLM providers:

| Provider | Key Prefix | Sign Up |
|:---------|:-----------|:--------|
| Anthropic (Claude) | `sk-ant-` | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | `sk-` | [platform.openai.com](https://platform.openai.com) |
| Google (Gemini) | `AIza` | [aistudio.google.com](https://aistudio.google.com) |
| xAI (Grok) | `xai-` | [console.x.ai](https://console.x.ai) |

## CLI Commands

```bash
# Getting started
sentinel-setup              # Full onboarding wizard
sentinel-chat               # Interactive AI agent
sentinel status             # Connection status dashboard
sentinel test               # Smoke test (auth + health + BTC price)

# Wallet management
sentinel wallet             # Dashboard — show wallets + balances
sentinel wallet connect     # Import private key (SOL or ETH)
sentinel wallet generate sol # Generate a new Solana wallet
sentinel wallet send        # Send crypto (with confirmation prompt)

# Add data sources & trading venues
sentinel add hl             # Hyperliquid DEX trading
sentinel add aster          # Aster DEX futures
sentinel add polymarket     # Polymarket prediction markets
sentinel add y2             # Y2 news intelligence
sentinel add x              # X (Twitter) API
sentinel add fred           # FRED economic data
sentinel add elfa           # Elfa AI social intel
sentinel add telegram       # Telegram client
sentinel add discord        # Discord bot

# Billing
sentinel billing            # View tier, usage, and fees
sentinel tools              # List all available tools
```

## Architecture

```
 sentinel-chat / sentinel ask / SentinelClient()
                    │
       ┌────────────┼────────────┐
       │            │            │
   Fast Path     Local       Gateway
   (regex)     Scrapers     (optional)
       │            │            │
   Instant     All 12 →    Sentinel Go API
   CoinGecko   CoinGecko    (Cloud Run)
   responses    YFinance         │
               DexScreener   Premium
               FRED          features
               Y2 Intel
               Elfa AI
               X/Twitter
               Hyperliquid
               Aster DEX
               Polymarket
               Telegram
               Discord
```

**Execution Priority:**
1. **Fast Path** — Regex-matched queries (price, top N) → instant, zero LLM
2. **Local Scrapers** — All tool calls execute locally via built-in scrapers
3. **Gateway** — Optional fallback for premium/cloud features

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

## Pricing

All tools are available on every tier. Upgrading reduces fees and increases rate limits.

| | Free | Pro | Enterprise |
|:--|:--:|:--:|:--:|
| **Price** | $0/mo | $100/mo | $1,000/mo |
| **LLM Markup** | 40% | 20% | 10% |
| **Maker Fee** | 0.10% | 0.06% | 0.02% |
| **Taker Fee** | 0.08% | 0.04% | 0.01% |
| **Rate Limit** | 300/min | 1,000/min | Unlimited |

## Links

- [hyper-sentinel.com](https://hyper-sentinel.com) — Website
- [hyper-sentinel.com/docs](https://hyper-sentinel.com/docs/) — SDK Documentation
- [REST API Reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) — Every endpoint documented
- [pypi.org/project/hyper-sentinel](https://pypi.org/project/hyper-sentinel/) — PyPI Package

## License

[AGPL-3.0](LICENSE) — © 2026 Sentinel Labs
