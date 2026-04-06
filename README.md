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

**The terminal to command all markets.**

You already use Hyperliquid. You already check CoinGecko. You already scroll X for alpha. You already pull FRED data. Sentinel puts them all in one window — and lets you act on it.

One AI. Every exchange. Every signal. Execute.

<br/>

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=pypi&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat&logo=python&logoColor=white&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/github/license/hyper-sentinel/hyper-sentinel-sdk?style=flat&color=8b5cf6)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=downloads&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)

[Website](https://hyper-sentinel.com) · [API Docs](https://api.hyper-sentinel.com/docs) · [PyPI](https://pypi.org/project/hyper-sentinel/) · [GitHub](https://github.com/hyper-sentinel/hyper-sentinel-sdk)

</div>

---

## 1. Install

```bash
pip install hyper-sentinel
```

That's it. Three dependencies. Python 3.10+.

## 2. Launch

```bash
sentinel
```

First run takes 10 seconds. Paste an API key from any supported AI provider:

| Provider | Get a Key |
|:---------|:----------|
| Anthropic (Claude) | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | [platform.openai.com](https://platform.openai.com) |
| Google (Gemini) | [aistudio.google.com](https://aistudio.google.com) — free tier available |
| xAI (Grok) | [console.x.ai](https://console.x.ai) |

Your AI key is exchanged for a Sentinel API key. Both are saved locally to `~/.sentinel/`. You won't be asked again.

## 3. Configure

Sentinel boots with **live data already connected** — no setup required:

| Source | What You Get | Setup |
|--------|-------------|-------|
| **CoinGecko** | 10,000+ crypto prices, market caps, charts | Automatic |
| **Yahoo Finance** | Stocks, ETFs, options, earnings | Automatic |
| **FRED** | GDP, CPI, unemployment, Fed rate, VIX, yield curve | Automatic |

These work out of the box. Ask for any price, any macro indicator, any stock — it's already there.

Then connect the services you already use:

| Source | What It Unlocks | Key From |
|--------|----------------|----------|
| **Hyperliquid** | Trade perp futures, view positions, orderbooks | [app.hyperliquid.xyz](https://app.hyperliquid.xyz) |
| **Aster DEX** | Trade futures, set leverage, manage positions | [aster.finance](https://aster.finance) |
| **Polymarket** | Prediction markets, odds, positions | [polymarket.com](https://polymarket.com) |
| **X / Twitter** | Scrape tweets, sentiment analysis, trending topics | [developer.x.com](https://developer.x.com) |
| **Y2 Intelligence** | AI news recaps, sentiment scores, intel reports | [y2.finance](https://y2.finance) |
| **Elfa AI** | Trending tokens, social mentions, smart money signals | [elfa.ai](https://elfa.ai) |

The more you connect, the more powerful the agent becomes. But even with zero configuration, you have a macro + crypto + stock terminal that works right now.

## 4. Chat

This is the point. Type what you want. The AI agent has all your tools.

```
⚡ You → What's BTC at?
🛡️ Sentinel
  BTC $84,219 (+1.8%) · Vol $31.2B · MCap $1.67T
```

```
⚡ You → Pull GDP, unemployment, price of PLTR, and price of SOL
🛡️ Sentinel
  📊 Macro (FRED)
  GDP: $28.27T (Q4 2025, +2.4%)
  Unemployment: 4.1% (Feb 2026)

  📈 Stocks
  PLTR  $87.42  (+3.1%)  ·  Vol 48.2M

  🪙 Crypto
  SOL  $187.50  (+5.2%)  ·  MCap $88.4B
```

One prompt. Four data sources. One response.

```
⚡ You → Scrape X for BTC sentiment and pull the latest intel reports
🛡️ Sentinel
  🐦 X/Twitter — "BTC" (24h)
  Sentiment: Bullish (72%) · 12.4K mentions
  Top signal: @whale_alert massive BTC transfer to Coinbase

  📰 Intelligence (Y2)
  • "Bitcoin breaks $85K resistance amid ETF inflow surge"
  • "Fed holds rates — risk assets rally across the board"
```

```
⚡ You → Show my Hyperliquid positions
🛡️ Sentinel
  | Coin | Size  | Entry    | PnL      | Leverage |
  |------|-------|----------|----------|----------|
  | BTC  | 0.05  | $82,100  | +$105.95 | 10x      |
  | ETH  | 1.2   | $3,840   | -$12.40  | 5x       |
  | SOL  | 15.0  | $175.20  | +$184.50 | 3x       |
```

```
⚡ You → Buy 0.01 BTC on Hyperliquid at market
🛡️ Sentinel
  ⚠️ Confirm: BUY 0.01 BTC @ market on Hyperliquid?
  Notional: ~$842  ·  Venue: Hyperliquid  ·  Type: Market

⚡ You → Yes
🛡️ Sentinel
  ✅ Filled: 0.01 BTC @ $84,219  ·  Cost: $842.19
```

The AI handles the routing. You don't pick which tool to call — you just say what you want and it figures it out. Prices, macro data, sentiment, news, trades, positions — all from the same prompt.

---

## Python SDK

Use Sentinel programmatically in scripts, bots, or your own applications:

```python
from hyper_sentinel import Sentinel

client = Sentinel()  # auto-loads from ~/.sentinel/

# Chat — the AI agent with all 62+ tools
print(client.chat("What's the macro outlook?"))

# Market data
client.price("bitcoin")          # CoinGecko
client.stock("NVDA")             # Yahoo Finance
client.macro()                   # FRED dashboard

# Trading (⚠️ real money)
client.buy("BTC", 0.01)                    # market order
client.sell("ETH", 0.5, price=2000)        # limit order
client.positions()                          # open positions

# Any of the 62+ tools by name
client.tool("get_fred_series", series_id="GDP")
client.tool("search_x", query="BTC sentiment")
client.tool("get_news_sentiment", query="crypto")
```

## How It Works

```
Your terminal / Your code
         │
         ▼
  Sentinel SDK (3 deps: httpx, click, rich)
         │
         ▼
┌────────────────────────────────┐
│  Go API Gateway                │
│  Auth · Billing · Rate Limits  │
│  api.hyper-sentinel.com        │
└──────────────┬─────────────────┘
               │
┌──────────────▼─────────────────┐
│  Python Engine (Cloud Run)     │
│  62+ tools · AI agent          │
│  HL · Aster · Polymarket       │
│  CoinGecko · FRED · X · Y2    │
└────────────────────────────────┘
```

Every call is authenticated, metered, and routed through the gateway. The SDK is a thin REST client — all the heavy lifting happens server-side.

## Zero-Trust Architecture

| Key | Purpose | Storage |
|-----|---------|---------|
| **API Key** (`sk-sentinel-xxx`) | Authenticates all API calls | Server (hashed) |
| **Secret Key** (`sdg-vault-xxx`) | Encrypts your config vault | Client only — never sent |
| **AI Provider Key** | Forwarded to LLM provider | Never stored on our servers |

Your exchange keys are encrypted client-side with AES-256-GCM before they ever leave your machine. We can't read them. You hold the only decryption key.

## Pricing

No feature gating. Everyone gets full access to all 62+ tools. Subscriptions reduce your fees.

| Tier | Price | LLM Markup | Trade Fee | Rate Limit |
|------|-------|-----------|-----------|-----------| 
| **Free** | $0 | 40% | 0.10% / 0.07% | 300/min |
| **Pro** | $100/mo | 15% | 0.04% / 0.03% | 1,000/min |
| **Enterprise** | $1,000/mo | 5% | 0.02% / 0.01% | 5,000/min |

---

## Alternative Install Methods

**macOS (Homebrew + pipx)**
```bash
brew install pipx && pipx install hyper-sentinel
```

**macOS / Linux (venv)**
```bash
python3 -m venv ~/.sentinel-env && source ~/.sentinel-env/bin/activate && pip install hyper-sentinel
```

---

## Links

- **Website**: [hyper-sentinel.com](https://hyper-sentinel.com)
- **API Docs**: [api.hyper-sentinel.com/docs](https://api.hyper-sentinel.com/docs)
- **PyPI**: [pypi.org/project/hyper-sentinel](https://pypi.org/project/hyper-sentinel/)
- **GitHub**: [github.com/hyper-sentinel](https://github.com/hyper-sentinel)

## License

[AGPL-3.0](LICENSE) — © 2026 Sentinel Labs LLC

---

<div align="center">
<sub><i>Soli Deo Gloria</i> — To the Glory of God alone.</sub>
</div>
