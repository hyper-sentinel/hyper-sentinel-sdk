<div align="center">
<br/>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/HYPER--SENTINEL-SDK-white?style=for-the-badge&labelColor=0d1117&color=0d1117">
  <img alt="Hyper-Sentinel SDK" src="https://img.shields.io/badge/HYPER--SENTINEL-SDK-black?style=for-the-badge">
</picture>

### Local-First AI Agent for Crypto, Equities & Macro

12 data sources · 65+ tools · Multi-agent swarm · Sub-second queries · One pip install

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

**With multi-agent swarm (Upsonic):**

```bash
pip install 'hyper-sentinel[swarm]' && sentinel-chat
```

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
| `run quant analysis on TSLA` | **10–20 seconds** | Deep quant engine — valuation, technicals, risk, analyst targets |

---

## Multi-Agent Swarm

Sentinel includes a **Upsonic-powered multi-agent swarm** for coordinated analysis and trading. Three specialized agents work together:

| Agent | Role | Capabilities |
|:------|:-----|:-------------|
| 📊 **Analyst** | Market Research & Macro | Crypto prices, stock analysis, FRED data, sentiment, news |
| ⚠️ **RiskManager** | Portfolio Risk & Sizing | Position limits, leverage checks, trade approval/rejection |
| 💰 **Trader** | Trade Execution | Hyperliquid, Aster DEX, Polymarket order placement |

```bash
# Install with swarm support
pip install 'hyper-sentinel[swarm]'
```

```
  ⚡ You → swarm

  🤖 Initializing Sentinel Swarm...

  🛡️  Sentinel Swarm — ONLINE

    Analyst          ● ONLINE    sentinel.analyst
    RiskManager      ● ONLINE    sentinel.risk
    Trader           ● ONLINE    sentinel.trader

  3 agents · Mode: COORDINATE · 42 tools · anthropic/claude-sonnet-4-20250514

  ⚡ You → analyze BTC macro outlook and assess trade risk

  ╭─────────────────────── 🛡️ Sentinel Swarm ────────────────────╮
  │  [Analyst researches → RiskManager evaluates → coordinated]   │
  ╰──────────────────────────────── 3 agents · coordinate · 14s ──╯
```

**Python API:**

```python
from sentinel.swarm import build_swarm, swarm_chat

team, agents = build_swarm(mode="coordinate")
result = swarm_chat(team, "analyze BTC macro outlook and assess trade risk")
```

---

## Data Sources

All 12 sources run **locally** via built-in scrapers. No gateway, no cloud dependency.

| Source | Tools | Setup |
|:-------|:------|:------|
| 🪙 **CoinGecko** | `get_crypto_price` · `get_crypto_top` · `search_crypto` | None — always available |
| 📈 **YFinance** | `get_stock_quote` · `run_stock_analysis` · `get_analyst_recs` | None — always available |
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

# Equities — deep quant analysis
aapl = client.get_stock_price("AAPL")
analysis = client.run_stock_analysis("TSLA")  # valuation + technicals + risk

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
swarm                Start multi-agent mode (Analyst + Risk + Trader)
swarm status         Show agent roster and status
solo                 Return to single-agent mode
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
   Fast Path    12 Local      Upsonic
   (regex)      Scrapers      Swarm
       │            │            │
    < 1 sec     CoinGecko    3 Agents
    zero LLM    YFinance     Analyst
                DexScreener  RiskManager
                FRED         Trader
                Y2 · Elfa      │
                X · HL       coordinate
                Aster · PM     mode
                TG · Discord
```

1. **Fast Path** → regex-matched price/top queries → instant
2. **Local Scrapers** → all tool calls execute locally via 12 built-in modules
3. **Swarm** → optional Upsonic multi-agent coordination (install with `[swarm]`)

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

## Changelog

### v0.3.5 — Config Bridge + Bug Fixes
- **FIX**: Bridge `~/.sentinel/config` credentials to env vars for all 14 scraper keys
- **FIX**: Aster secret and Polymarket funder env var mismatches

### v0.3.4 — Multi-Agent Swarm
- **ADD**: Upsonic multi-agent swarm (Analyst, RiskManager, Trader)
- **ADD**: `swarm`, `swarm status`, `solo` REPL commands
- **ADD**: Dashboard shows swarm availability and agent roster
- **ADD**: SQLite memory persistence for swarm sessions

### v0.3.3 — Quant Analysis Engine
- **ADD**: `run_stock_analysis` — deep quantitative analysis (valuation, technicals, risk, analyst targets)
- **UPGRADE**: System prompt with 11-section analysis formatting guide

### v0.3.2 — Stabilization
- **FIX**: Tool-naming mismatches between chat module and scrapers
- **ADD**: YFinance local-first stock data integration

---

## Links

- [hyper-sentinel.com](https://hyper-sentinel.com) — Website
- [Docs](https://hyper-sentinel.com/docs/) — Full documentation
- [API Reference](https://github.com/hyper-sentinel/docs/blob/main/rest-api/README.md) — Every endpoint
- [PyPI](https://pypi.org/project/hyper-sentinel/) — Package
- [Upsonic](https://github.com/Upsonic/Upsonic) — Multi-agent framework

## License

[AGPL-3.0](LICENSE) — © 2026 Sentinel Labs
