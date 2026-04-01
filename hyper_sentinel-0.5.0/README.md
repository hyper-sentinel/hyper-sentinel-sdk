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

**The AI Trading SDK — 62+ tools · 3 venues · 1 API key**

Web4: AI agents + crypto infrastructure + zero-trust developer tooling

<br/>

[![PyPI](https://img.shields.io/pypi/v/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=pypi&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)
[![Python](https://img.shields.io/pypi/pyversions/hyper-sentinel?style=flat&logo=python&logoColor=white&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)
[![License](https://img.shields.io/github/license/hyper-sentinel/hyper-sentinel-sdk?style=flat&color=8b5cf6)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hyper-sentinel?style=flat&logo=pypi&logoColor=white&label=downloads&color=8b5cf6)](https://pypi.org/project/hyper-sentinel/)

[Console](https://console.hyper-sentinel.com) · [API Docs](https://api.hyper-sentinel.com/docs) · [PyPI](https://pypi.org/project/hyper-sentinel/) · [Website](https://hyper-sentinel.com)

</div>

---

## Install

```bash
pip install hyper-sentinel
```

## Get Your API Key

### Option 1: Developer Console (Web)

1. Visit [console.hyper-sentinel.com](https://console.hyper-sentinel.com)
2. Sign in with your AI provider key (Claude / GPT / Gemini / Grok)
3. Go to **API Keys** → **Create API Key**
4. Copy your `sk-sentinel-xxx` key

### Option 2: Terminal (SDK)

```bash
sentinel auth --provider claude --key sk-ant-api03-...
```

```
✓ Authenticated with Claude
✓ API Key:    sk-sentinel-abc123...
✓ Secret Key: sdg-vault-xyz789... (SAVE THIS — cannot be recovered)

Add to .env:
  SENTINEL_API_KEY=sk-sentinel-abc123...
```

---

## Quick Start

```python
from hyper_sentinel import Sentinel

# Initialize with your API key
client = Sentinel(api_key="sk-sentinel-xxx")

# Chat with AI + 62 tools
response = client.chat("What's the price of BTC?")
print(response)

# Call any tool directly
price = client.get_price("bitcoin")
top = client.get_top_coins(10)
macro = client.get_macro()

# Streaming responses
for token in client.chat("Analyze ETH outlook", stream=True):
    print(token, end="", flush=True)
```

## Trading

```python
# Hyperliquid
positions = client.get_positions()
client.place_order("BTC", "buy", 0.01)                     # market
client.place_order("ETH", "sell", 0.5, price=2000.0)        # limit
client.call("close_hl_position", coin="BTC")

# Aster DEX
client.call("aster_place_order", symbol="BTCUSDT", side="buy", size=0.01)
client.call("aster_set_leverage", symbol="BTCUSDT", leverage=5)

# Polymarket
markets = client.search_markets("election")
client.call("buy_polymarket", token_id="...", amount=10, price=0.65)
```

## Market Data

```python
# Crypto
client.get_price("ethereum")
client.get_top_coins(25)
client.call("get_crypto_chart", coin_id="bitcoin", days=30)
client.get_orderbook("BTC")

# Stocks & ETFs
client.call("get_stock_price", symbol="NVDA")

# Macro Economics
client.get_macro()                                    # GDP, CPI, Fed rate, VIX
client.call("get_fred_series", series_id="GDP")
```

## Intelligence

```python
# News & Sentiment
client.get_news()
client.call("get_news_sentiment", query="bitcoin")
client.call("get_intelligence_reports")

# Social
client.get_trending()
client.call("search_x", query="BTC")
client.call("get_top_mentions")
```

## Call Any Tool

```python
# Generic tool call — works with all 62+ tools
result = client.call("tool_name", param1="value", param2=123)

# List all available tools
tools = client.list_tools()
for tool in tools:
    print(f"{tool['name']}: {tool.get('description', '')}")
```

## Account & Billing

```python
# Check your usage
status = client.billing_status()
print(f"Tier: {status['tier']}, Calls: {status['monthly_api_calls']}")
```

---

## How It Works

```
pip install hyper-sentinel
         │
         ▼
  Your Code (Sentinel SDK)
  api_key = sk-sentinel-xxx
         │
         ▼
┌────────────────────────────┐
│  Go API Gateway            │
│  Auth · Billing · Metering │
│  api.hyper-sentinel.com    │
└────────────┬───────────────┘
             │
┌────────────▼───────────────┐
│  Python Engine (FastAPI)   │
│  62+ tools · 12 scrapers  │
│  HL · Aster · PM · FRED   │
└────────────────────────────┘
```

Every call is authenticated, metered, and billed through the gateway.

---

## Zero-Trust Architecture

| Key | Purpose | Storage |
|-----|---------|---------|
| **API Key** (`sk-sentinel-xxx`) | Authenticates API calls | Server (hashed) |
| **Secret Key** (`sdg-vault-xxx`) | Encrypts your config vault | Client only |
| **AI Provider Key** | Forwarded to LLM provider | Never stored |

Your AI provider keys are forwarded securely and never stored on our servers.

---

## Pricing

No feature gating. Everyone gets full access. Subscriptions reduce your fees.

| Tier | Price | LLM Markup | Trade Fee | Rate Limit |
|------|-------|-----------|-----------|-----------| 
| **Free** | $0 | 40% | 0.10% / 0.07% | 300/min |
| **Pro** | $100/mo | 15% | 0.04% / 0.03% | 1,000/min |
| **Enterprise** | $1,000/mo | 5% | 0.02% / 0.01% | 5,000/min |

---

## LLM Providers

| Provider | Prefix | Get a Key |
|:---------|:-------|:----------|
| Anthropic (Claude) | `sk-ant-` | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI (GPT) | `sk-` | [platform.openai.com](https://platform.openai.com) |
| Google (Gemini) | `AIza` | [aistudio.google.com](https://aistudio.google.com) |
| xAI (Grok) | `xai-` | [console.x.ai](https://console.x.ai) |

---

## Changelog

### v0.5.0 — Web4 Thin Client 🚀

- **BREAKING**: SDK is now a thin REST client — all calls go through `api.hyper-sentinel.com`
- **NEW**: `Sentinel(api_key="sk-sentinel-xxx")` — one-liner setup
- **NEW**: `sentinel auth` CLI — generate API keys from terminal
- **NEW**: `client.chat(message, stream=True)` — SSE streaming
- **NEW**: `client.call(tool, **params)` — call any of 62+ tools
- **NEW**: Secret recovery key for zero-trust config vault
- **REMOVED**: All heavy local dependencies (anthropic, openai, etc.)
- **DEPS**: `httpx`, `click`, `rich` — 3 total deps

### v0.4.1 — Stability Release

- SDK ↔ Gateway endpoint sync
- Bug fixes and documentation updates

### v0.3.16 — SaaS API Client

- `SentinelAPI` client with typed resources
- SSE streaming for LLM chat
- RFC 7807 error mapping

---

## Links

- **Console**: [console.hyper-sentinel.com](https://console.hyper-sentinel.com)
- **API Docs**: [api.hyper-sentinel.com/docs](https://api.hyper-sentinel.com/docs)
- **Website**: [hyper-sentinel.com](https://hyper-sentinel.com)
- **PyPI**: [pypi.org/project/hyper-sentinel](https://pypi.org/project/hyper-sentinel/)
- **GitHub**: [github.com/hyper-sentinel](https://github.com/hyper-sentinel)
- **Postman**: [Collection](https://github.com/hyper-sentinel/hyper-sentinel-go/blob/main/Sentinel_API.postman_collection.json)

## License

[AGPL-3.0](LICENSE) — © 2026 Sentinel Labs LLC

---

<div align="center">
<sub><i>Soli Deo Gloria</i> — To the Glory of God alone.</sub>
</div>
