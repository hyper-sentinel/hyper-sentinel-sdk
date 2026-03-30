<div align="center">
<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/HYPER--SENTINEL-SDK-white?style=for-the-badge&labelColor=0d1117&color=0d1117">
  <img alt="Hyper-Sentinel SDK" src="https://img.shields.io/badge/HYPER--SENTINEL-SDK-black?style=for-the-badge">
</picture>

### Local-First AI Agent for Crypto, Equities & Macro

12 data sources · 65+ tools · Sub-second queries · One pip install

<br/>

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=pypi&color=3572A5)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat&logo=python&logoColor=white&color=3572A5)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/github/license/hyper-sentinel/hyper-sentinel-sdk?style=flat&color=3572A5)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=downloads&color=3572A5)](https://pypi.org/project/hyper-sentinel/)

[Website](https://hyper-sentinel.com) · [Docs](https://hyper-sentinel.com/docs/) · [API Reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) · [PyPI](https://pypi.org/project/hyper-sentinel/)

<br/>
</div>

---

## Install

```bash
pip install hyper-sentinel && sentinel-chat
```

Paste your LLM key on first run. No email, no account. You're in.

---

## How It Works

Sentinel is an AI agent that calls tools to answer your questions. Common queries hit a **fast path** and return instantly. Everything else goes through your chosen LLM.

```
  ⚡ You → price of btc and xmr

  ╭─────────────────────── 🛡️ Sentinel ──────────────────────────╮
  │                                                                │
  │  Bitcoin (BTC): $66,565.00                                     │
  │    24h: -0.70%  ·  7d: -3.28%  ·  Market cap: $1.3T           │
  │                                                                │
  │  Monero (XMR): $330.89                                         │
  │    24h: +0.18%  ·  7d: -6.13%  ·  Market cap: $6.1B           │
  │                                                                │
  ╰────────────────────────────────────── ⚡ instant · 0 LLM ─────╯
```

| Query Type | Speed | How |
|:-----------|:------|:----|
| `price of btc` / `top 10 crypto` | **< 1 second** | Fast Path — regex match, direct API call, zero LLM |
| `analyze BTC structure and AAPL recs` | **3–8 seconds** | LLM agent calls tools, formats response |

---

## Data Sources

All 12 sources run **locally** via built-in scrapers. No gateway, no cloud dependency.

| Source | Tools | Setup |
|:-------|:------|:------|
| 🪙 **CoinGecko** | `get_crypto_price` · `get_crypto_top` · `search_crypto` | None — always available |
| 📈 **YFinance** | `get_stock_quote` · `get_stock_analyst` · `get_stock_news` | None — always available |
| 📊 **DexScreener** | `dexscreener_search` · `dexscreener_trending` | None — always available |
| 🏛️ **FRED** | `get_fred_series` · `search_fred` · `get_economic_dashboard` | `add fred` |
| 📰 **Y2 Intelligence** | `get_news_sentiment` · `get_news_recap` · `get_intelligence_reports` | `add y2` |
| 🔮 **Elfa AI** | `get_trending_tokens` · `get_top_mentions` · `search_mentions` | `add elfa` |
| 🐦 **X / Twitter** | `search_x` | `add x` |
| ⚡ **Hyperliquid** | `get_hl_positions` · `place_hl_order` · `get_hl_orderbook` + 7 more | `add hl` |
| 🌟 **Aster DEX** | `aster_ticker` · `aster_positions` · `aster_balance` + 7 more | `add aster` |
| 🎲 **Polymarket** | `get_polymarket_markets` · `buy_polymarket` + 8 more | `add polymarket` |
| 💬 **Telegram** | `tg_read_channel` · `tg_search_messages` · `tg_list_channels` | `add telegram` |
| 🎮 **Discord** | `discord_read_channel` · `discord_list_guilds` + 4 more | `add discord` |

> 3 sources work out of the box. The rest activate the moment you add a key — no restart needed.

---

## Python SDK

```python
from sentinel import SentinelClient

client = SentinelClient()  # keys loaded from ~/.sentinel/config

# Crypto (instant)
btc = client.get_crypto_price("bitcoin")
top = client.get_crypto_top_n(10)

# Equities (instant)
aapl = client.get_stock_price("AAPL")

# Perpetual futures (Hyperliquid)
positions = client.get_hl_positions()
client.place_hl_order(coin="ETH", side="buy", size=0.5)

# Prediction markets (Polymarket)
markets = client.get_polymarket_markets()

# Macro data (FRED)
gdp = client.get_fred_series("GDP")

# AI chat — uses your LLM
resp = client.chat("What's the best DeFi play right now?")
```

---

## Authentication

Add your LLM API key. That's it.

```bash
sentinel-chat          # prompts on first run
sentinel-setup         # or run the setup wizard
```

```python
client = SentinelClient(ai_key="sk-ant-xxx")  # or pass directly
```

| Provider | Prefix | Get a key |
|:---------|:-------|:----------|
| Anthropic (Claude) | `sk-ant-` | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | `sk-` | [platform.openai.com](https://platform.openai.com) |
| Google (Gemini) | `AIza` | [aistudio.google.com](https://aistudio.google.com) |
| xAI (Grok) | `xai-` | [console.x.ai](https://console.x.ai) |

---

## Commands

### Chat (inside `sentinel-chat`)

```
add                  List all data sources you can configure
add hl               Hyperliquid perp futures
add polymarket       Polymarket prediction markets
add aster            Aster DEX futures
add fred             FRED economic data
add x                X / Twitter
add y2               Y2 Intelligence news
add elfa             Elfa AI social intel
add telegram         Telegram channels
add discord          Discord bot
add ai               Switch LLM provider
tools                List all 65+ tools
status               Infrastructure dashboard
clear                Reset context
quit                 Exit
```

### Terminal

```bash
sentinel-chat                    # Interactive agent
sentinel-setup                   # Onboarding wizard
sentinel ask "price of ETH"      # One-shot query
sentinel status                  # Dashboard
sentinel wallet                  # Manage wallets
sentinel tools                   # List all tools
```

---

## Architecture

```
 sentinel-chat / sentinel ask / SentinelClient
                    │
       ┌────────────┼────────────┐
       │            │            │
   Fast Path    12 Local      Gateway
   (regex)      Scrapers     (optional)
       │            │            │
    < 1 sec     CoinGecko     Go API
    zero LLM    YFinance     Cloud Run
                DexScreener
                FRED
                Y2 · Elfa · X
                Hyperliquid
                Aster · Polymarket
                Telegram · Discord
```

1. **Fast Path** → regex-matched price/top queries → instant
2. **Local Scrapers** → all tool calls execute locally
3. **Gateway** → optional, for premium cloud features

---

## Error Handling

```python
from sentinel.exceptions import SentinelError, AuthError, RateLimitError

try:
    client.place_hl_order(coin="ETH", side="buy", size=0.1)
except RateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except AuthError:
    print("Invalid credentials")
```

---

## Links

- [hyper-sentinel.com](https://hyper-sentinel.com) — Website
- [Docs](https://hyper-sentinel.com/docs/) — Full documentation
- [API Reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) — Every endpoint
- [PyPI](https://pypi.org/project/hyper-sentinel/) — Package

## License

[AGPL-3.0](LICENSE) — © 2026 Sentinel Labs
