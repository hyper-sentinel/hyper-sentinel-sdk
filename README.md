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

**AI trading terminal with 69 tools.** [See all tools →](TOOLS.md)

One terminal. Multi-LLM. Trade Hyperliquid & Aster — quant + market intel built in.

<br/>

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=pypi&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat&logo=python&logoColor=white&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/github/license/hyper-sentinel/hyper-sentinel-sdk?style=flat&color=8b5cf6)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=downloads&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)

[Website](https://hyper-sentinel.com) · [API Reference](https://api.hyper-sentinel.com/docs) · [PyPI](https://pypi.org/project/hyper-sentinel/)

</div>

---

## Install

**macOS / Linux**
```bash
pip3 install hyper-sentinel
```

**Windows (PowerShell)**
```powershell
pip install hyper-sentinel
```

> If `pip` isn't recognized on Windows, try `py -m pip install hyper-sentinel`

## Launch

```bash
sentinel
```

> **Windows**: Same command — `sentinel` — works after pip install.
> If it's not found, try `py -m sentinel.cli` or add your Python Scripts folder to PATH.

Paste an API key from any supported provider:

| Provider | Get a Key |
|:---------|:----------|
| Anthropic (Claude) | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | [platform.openai.com](https://platform.openai.com) |
| Google (Gemini) | [aistudio.google.com](https://aistudio.google.com) — free tier available |
| xAI (Grok) | [console.x.ai](https://console.x.ai) |

Your AI key is exchanged for a Sentinel API key. Both saved locally:
- **macOS / Linux**: `~/.sentinel/`
- **Windows**: `C:\Users\<you>\.sentinel\`

---

## What You Can Do

Type what you want. The AI agent calls the right tools automatically.

```
> What's BTC at?
BTC $84,219 (+1.8%) | Vol $31.2B | MCap $1.67T

> Show my Hyperliquid positions
| Coin | Size  | Entry    | PnL      | ROE    | Leverage |
|------|-------|----------|----------|--------|----------|
| BTC  | 0.7   | $70,711  | +$752    | +50.1% | 33x      |
| SOL  | 220   | $82.55   | +$169    | +18.6% | 20x      |

> Get GDP, unemployment, and fed rate
[calls get_fred_series x3 — real economic data]

> Search X for Mario Nawfal on Israel
[calls search_x — returns latest tweets]

> What's the Sharpe ratio on BTC?
Sharpe: 1.42 | Sortino: 1.87 | Max Drawdown: -18%
→ Good risk-adjusted returns. Sharpe > 1 suggests solid performance.

> Is ETH trending or random right now?
ARIMA forecasts up | Volatility compressing | Non-stationary (trending)
→ Price is trending, not mean-reverting. GARCH vol is compressing.

> What do the ML models say about SOL?
Trend: up (R²=0.72) | Regime: trending_up | Top signal: RSI
→ ML models lean bullish. Next candle prediction: up (64% confidence)

> What's the put/call ratio on AAPL?
P/C Ratio: 0.73 | IV: 28% | Sentiment: mildly bullish
→ Put/call below 1 suggests bullish positioning. IV is moderate.
```

## Pricing

Pay-as-you-go — **no subscription**. You only pay for what you use:

- **AI calls** are routed through the Sentinel gateway, which adds a small markup over the raw provider cost (40% on the free tier, lower on paid tiers).
- **Trades** carry a 0.01% on-chain builder fee, settled automatically with each order.

Bring your own LLM key; market data and quant tools are free.

## Data Sources (Always Available)

| Source | What |
|--------|------|
| CoinGecko | 10,000+ crypto prices, market caps, search |
| Yahoo Finance | Stocks, ETFs, analyst recs, options chains |
| FRED | GDP, CPI, unemployment, Fed rate, VIX, yield curve |
| DexScreener | DEX pairs, trending tokens, on-chain analytics |

## Quantitative Analysis (Built-In)

| Module | What |
|--------|------|
| Risk Metrics | Sharpe, Sortino, Calmar, VaR (3 methods), CVaR, max drawdown |
| Time Series | ARIMA forecast, GARCH volatility, ADF stationarity test |
| ML Signals | Linear regression trend, K-Means regime, Random Forest importance, logistic prediction |
| Options | Put/call ratio, implied volatility, ATM options, sentiment (stocks/ETFs only) |

## Trading Venues (Connect Your Keys)

| Venue | What |
|-------|------|
| Hyperliquid | Perp futures — crypto + TradFi (GOLD, TSLA, SP500) |
| Aster DEX | Perp futures with leverage |

Type `add hl` or `add aster` inside the terminal to connect.

## Intelligence Feeds (Connect Your Keys)

| Source | What |
|--------|------|
| X / Twitter | Tweet search, sentiment |
| Y2 Intelligence | News sentiment (GloriaAI), AI recaps, intelligence reports, audio narrations, monitoring profiles, OSINT feeds |
| Elfa AI | Trending tokens, social mentions |

Type `add x`, `add y2`, or `add elfa` inside the terminal to connect.

---

## Commands

| Command | What |
|---------|------|
| `status` | Connection health + account info |
| `tools` | List all 60 available tools |
| `model` | Pick your AI model (Fable, Opus, Sonnet, GPT, Gemini, Grok…) |
| `add` | Configure exchanges & data sources |
| `add ai` | Switch LLM provider / change your AI key |
| `help` | Show all commands |
| `quit` | Exit |
| Anything else | Chat with the AI — it has all the tools |

---

## Security

| Key | Purpose | Storage |
|-----|---------|---------|
| **API Key** (`sk-sentinel-xxx`) | Authenticates API calls | Server (hashed) |
| **Secret Key** (`sdg-vault-xxx`) | Encrypts your config vault | Client only — never sent |
| **AI Provider Key** | Forwarded to LLM provider | Never stored on our servers |

Your config vault is encrypted locally with Fernet (AES-128-CBC + HMAC-SHA256). Exchange keys never leave your machine in plaintext.

---

## Links

- **Website**: [hyper-sentinel.com](https://hyper-sentinel.com)
- **API Reference**: [api.hyper-sentinel.com/docs](https://api.hyper-sentinel.com/docs)
- **PyPI**: [pypi.org/project/hyper-sentinel](https://pypi.org/project/hyper-sentinel/)

## License

[AGPL-3.0](LICENSE) — 2026 Sentinel Labs LLC

---

<div align="center">
<sub><i>Soli Deo Gloria</i></sub>
</div>
