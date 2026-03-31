<div align="center">
<br/>

```
██╗  ██╗██╗   ██╗██████╗ ███████╗██████╗
██║  ██║╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗
███████║ ╚████╔╝ ██████╔╝█████╗  ██████╔╝
██╔══██║  ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗
██║  ██║   ██║   ██║     ███████╗██║  ██║
╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝
```

# Hyper-Sentinel

**Quantitative AI Agent — Crypto, Equities & Macro**

10 data sources · 80+ tools · Multi-agent swarm · Sub-second queries

<br/>

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=pypi&color=00e5ff)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat&logo=python&logoColor=white&color=00e5ff)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/github/license/hyper-sentinel/hyper-sentinel-sdk?style=flat&color=00e5ff)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=downloads&color=00e5ff)](https://pypi.org/project/hyper-sentinel/)

[Website](https://hyper-sentinel.com) · [Docs](https://hyper-sentinel.com/docs/) · [PyPI](https://pypi.org/project/hyper-sentinel/)

</div>

---

## Quickstart

```bash
pip install hyper-sentinel
sentinel
```

Paste your LLM key. No email, no account, no cloud. **You're in.**

---

## What It Does

Sentinel is an autonomous AI agent that executes financial research and trades through natural language. Fast queries resolve instantly. Everything else routes through your chosen LLM with tool calling.

```
  ⚡ You → price of btc and eth

  ╭───────────────────────────── 🛡️ Sentinel ──╮
  │                                              │
  │  Bitcoin (BTC): $66,839.00                   │
  │    24h: -0.42%  ·  7d: +1.8%                │
  │                                              │
  │  Ethereum (ETH): $1,812.40                   │
  │    24h: +0.21%  ·  7d: -2.1%                │
  │                                              │
  ╰────────────────────── ⚡ instant · 0 LLM ───╯
```

| Query | Speed | How |
|:------|:------|:----|
| `price of btc` / `top 10 crypto` | **< 1s** | Fast Path — regex match, direct API, zero LLM |
| `analyze BTC and show AAPL recs` | **3–8s** | LLM agent calls tools, formats response |
| `run quant analysis on TSLA` | **10–20s** | Deep quant — valuation, technicals, risk, targets |

---

## Boot Sequence

When you launch `sentinel`, the system runs an animated boot sequence — authenticating your LLM, loading credentials, connecting exchanges, and deploying the MarketAgent:

```
  ✓ 🤖 Authenticating LLM — CLAUDE → claude-sonnet-4-20250514
  ✓ 🔑 Loading credentials — ~/.sentinel/config
  ✓ 🔧 Initializing tool registry — 80+ tools
  ✓ 📡 Bridging environment — 8 services
  ✓ 📊 Connecting data sources — CoinGecko · YFinance · DexScreener
  ✓ ⚡ Connecting exchanges — Hyperliquid · Aster · Polymarket
  ✓ 🛡️ Deploying MarketAgent — sentinel.market.data
```

---

## Data Sources

All sources execute **locally** via built-in scrapers. No gateway dependency.

| Source | What You Get | Setup |
|:-------|:-------------|:------|
| 🪙 **CoinGecko** | 10,000+ coins · prices · market data · trending | None — always on |
| 📈 **YFinance** | Stocks · ETFs · options · analyst recs · financials | None — always on |
| 📊 **DexScreener** | DEX pairs · trending tokens · new listings | None — always on |
| ⚡ **Hyperliquid** | Perps · positions · orders · balances · funding | `add hl` |
| 🌟 **Aster DEX** | Futures · positions · klines · leverage · orderbook | `add aster` |
| 🎲 **Polymarket** | Prediction markets · positions · buy/sell · odds | `add polymarket` |
| 🏛️ **FRED** | GDP · CPI · rates · 800K+ economic series | `add fred` |
| 📰 **Y2 Intelligence** | News sentiment · intelligence reports · recaps | `add y2` |
| 🔮 **Elfa AI** | Trending tokens · social mentions · sentiment | `add elfa` |
| 🐦 **X / Twitter** | Tweet search · accounts · trends | `add x` |

> 3 sources work instantly. The rest activate the moment you add a key — no restart required.

---

## Multi-Agent Swarm

Three specialized agents coordinate through the [Upsonic](https://github.com/Upsonic/Upsonic) framework:

| Agent | Role | Scope |
|:------|:-----|:------|
| 📊 **Analyst** | Market Research | Prices, technicals, macro data, sentiment |
| ⚠️ **RiskManager** | Portfolio Risk | Position sizing, leverage checks, trade approval |
| 💰 **Trader** | Execution | Hyperliquid, Aster DEX, Polymarket orders |

```bash
pip install 'hyper-sentinel[swarm]'
```

```
  ⚡ You → swarm

  🛡️  Sentinel Swarm — ONLINE

    📊 Analyst       ● ONLINE    sentinel.analyst
    ⚠️  RiskManager   ● ONLINE    sentinel.risk
    💰 Trader        ● ONLINE    sentinel.trader

  3 agents · Mode: COORDINATE · 80+ tools
```

---

## Python SDK

```python
from sentinel import SentinelClient

client = SentinelClient()  # keys from ~/.sentinel/config

# Crypto
btc = client.get_crypto_price("bitcoin")
top = client.get_crypto_top_n(10)

# Equities — deep quant
analysis = client.run_stock_analysis("TSLA")

# Perpetual futures (Hyperliquid)
positions = client.get_hl_positions()
client.place_hl_order(coin="ETH", side="buy", size=0.5)

# Prediction markets (Polymarket)
markets = client.get_polymarket_markets()
positions = client.get_polymarket_positions()

# Macro (FRED)
gdp = client.get_fred_series("GDP")
```

---

## LLM Providers

| Provider | Prefix | Link |
|:---------|:-------|:-----|
| Anthropic (Claude) | `sk-ant-` | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | `sk-` | [platform.openai.com](https://platform.openai.com) |
| Google (Gemini) | `AIza` | [aistudio.google.com](https://aistudio.google.com) |
| xAI (Grok) | `xai-` | [console.x.ai](https://console.x.ai) |

---

## Commands

```bash
# Terminal
sentinel                     # Launch agent (interactive chat)
sentinel ask "price of ETH"  # One-shot query
sentinel setup               # Onboarding wizard
sentinel status              # Infrastructure dashboard
sentinel tools               # List all tools

# Inside chat
add hl          Hyperliquid perps
add aster       Aster DEX futures
add polymarket  Prediction markets
swarm           Activate multi-agent mode
clear           Fresh dashboard + reset context
tools           List all 80+ tools
help            Show all commands
```

---

## Architecture

```
          sentinel / sentinel ask / SentinelClient
                         │
            ┌────────────┼────────────┐
            │            │            │
        Fast Path    12 Local      Upsonic
        (regex)      Scrapers      Swarm
            │            │            │
         < 1 sec     CoinGecko    3 Agents
         zero LLM    YFinance     Analyst
                     DexScreener  RiskManager
                     FRED · Y2    Trader
                     Elfa · X       │
                     HL · Aster   coordinate
                     PM · TG      mode
                     Discord
```

---

## Changelog

### v0.3.10 — Boot Sequence + Polymarket Full Integration
- **NEW**: Animated boot sequence with staged spinner initialization
- **NEW**: 5 Polymarket tools exposed (positions, buy, sell, price, orderbook)
- **NEW**: `sentinel` (no args) launches chat directly
- **FIX**: `clear` re-renders full banner + dashboard
- **FIX**: Post-install message — clean panel with launch CTA

### v0.3.8 — Aster Fix + Credential Sync
- **FIX**: Added `tenacity` to core dependencies (Aster scraper)
- **FIX**: Hyperliquid private key sync from production env
- **VERIFIED**: 7/7 integrations passing (CoinGecko, YFinance, HL, Aster, PM, DexScreener, CLOB)

### v0.3.4 — Multi-Agent Swarm
- **ADD**: Upsonic multi-agent swarm (Analyst, RiskManager, Trader)
- **ADD**: Dashboard shows swarm availability and agent roster

### v0.3.3 — Quant Analysis Engine
- **ADD**: `run_stock_analysis` — deep quantitative analysis

---

## Links

- [hyper-sentinel.com](https://hyper-sentinel.com) — Website
- [Documentation](https://hyper-sentinel.com/docs/) — Guides & API reference
- [PyPI](https://pypi.org/project/hyper-sentinel/) — Package
- [GitHub](https://github.com/hyper-sentinel/hyper-sentinel-sdk) — Source

## License

[AGPL-3.0](LICENSE) — © 2026 Sentinel Labs
