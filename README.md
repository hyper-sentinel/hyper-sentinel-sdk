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

**AI trading terminal with 62+ tools.**

One command. Every exchange. Every signal.

<br/>

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=pypi&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat&logo=python&logoColor=white&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/github/license/hyper-sentinel/hyper-sentinel-sdk?style=flat&color=8b5cf6)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=downloads&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)

[Website](https://hyper-sentinel.com) · [API Reference](https://api.hyper-sentinel.com/docs) · [PyPI](https://pypi.org/project/hyper-sentinel/)

</div>

---

## Install

```bash
pip install hyper-sentinel
```

## Launch

```bash
sentinel
```

Paste an API key from any supported provider:

| Provider | Get a Key |
|:---------|:----------|
| Anthropic (Claude) | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | [platform.openai.com](https://platform.openai.com) |
| Google (Gemini) | [aistudio.google.com](https://aistudio.google.com) — free tier available |
| xAI (Grok) | [console.x.ai](https://console.x.ai) |

Your AI key is exchanged for a Sentinel API key. Both saved locally to `~/.sentinel/`.

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
```

## Data Sources (Always Available)

| Source | What |
|--------|------|
| CoinGecko | 10,000+ crypto prices, market caps, search |
| Yahoo Finance | Stocks, ETFs, analyst recs, full quant analysis |
| FRED | GDP, CPI, unemployment, Fed rate, VIX, yield curve |
| DexScreener | DEX pairs, trending tokens, on-chain analytics |

## Trading Venues (Connect Your Keys)

| Venue | What |
|-------|------|
| Hyperliquid | Perp futures — crypto + TradFi (GOLD, TSLA, SP500) |
| Aster DEX | Perp futures with leverage |
| Polymarket | Prediction markets |

Type `add hl`, `add aster`, or `add polymarket` inside the terminal to connect.

## Intelligence Feeds (Connect Your Keys)

| Source | What |
|--------|------|
| X / Twitter | Tweet search, sentiment |
| Y2 Intelligence | AI news recaps, sentiment scores |
| Elfa AI | Trending tokens, social mentions |
| EODHD | Historical market data |

Type `add x`, `add y2`, `add elfa`, or `add eodhd` inside the terminal to connect.

---

## Commands

| Command | What |
|---------|------|
| `status` | Connection health + account info |
| `tools` | List all 62+ available tools |
| `add` | Configure exchanges & data sources |
| `add ai` | Swap your LLM provider |
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

Exchange keys are encrypted client-side with AES-256-GCM before leaving your machine.

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
