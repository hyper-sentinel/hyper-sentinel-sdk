# Hyper-Sentinel SDK

Python SDK for the Sentinel API — 80+ tools for crypto trading, market intelligence, and AI analysis.

> **Install:** `pip install hyper-sentinel` or `uv add hyper-sentinel`

## Key Points

- **Full access on free tier** — trading, LLM, data, wallets, everything
- **Revenue from fees, not paywalls** — upgrade to Pro/Enterprise for lower rates
- **4 trading venues** — HyperLiquid, Aster DEX, Polymarket, Jupiter
- **17 AI models** — Claude, GPT-4o, Gemini, Grok (bring your own key)

## Install

```bash
# pip (Mac / Windows PowerShell / Linux)
pip install hyper-sentinel

# uv (recommended)
uv add hyper-sentinel
```

## Quick Start

```python
from sentinel import SentinelClient

client = SentinelClient()

# Register (first time)
client.register(email="you@example.com", password="pass123", name="Your Name")

# Generate an API key (save this!)
key = client.generate_key(name="my-key")
print(f"API Key: {key['api_key']}")

# Market data
btc = client.get_crypto_price("bitcoin")
print(f"BTC: ${btc['price']:,.2f}")

# AI chat (bring your own key)
resp = client.chat(
    "Analyze BTC market structure",
    ai_key="sk-ant-your-anthropic-key",
)

# Trading (all tiers — fees apply)
client.place_hl_order(coin="ETH", side="buy", size=0.1)

# DEX Trading — on-chain swaps
client.dex_buy_sol(contract_address="CA_ADDRESS", amount_sol=0.5)

# Check billing
print(client.billing_status())

# Upgrade to lower your fees
url = client.upgrade("pro")          # $100/mo
url = client.upgrade("enterprise")   # $1,000/mo
```

## Returning Users

```python
client = SentinelClient()
client.login(email="you@example.com", password="pass123")
```

## Tiers (Fee-Discount Model)

| | **Free** | **Pro** ($100/mo) | **Enterprise** ($1K/mo) |
|---|---|---|---|
| Access | Everything | Everything | Everything |
| LLM markup | 40% | 20% | 10% |
| Trade maker fee | 0.10% | 0.06% | 0.02% |
| Trade taker fee | 0.07% | 0.04% | 0.01% |
| Rate limit | 300/min | 1,000/min | Unlimited |
| Monthly limit | None | None | None |

Pro pays for itself at ~$10K/day trading volume.

## Available Tools (80+)

| Category | Examples | Tier |
|----------|---------|------|
| Crypto | `get_crypto_price`, `get_crypto_top_n`, `search_crypto` | All |
| Macro | `get_fred_series`, `get_economic_dashboard` | All |
| News | `get_news_sentiment`, `get_intelligence_reports` | All |
| Social | `get_trending_tokens`, `get_top_mentions`, `get_trending_narratives` | All |
| X / Twitter | `search_x` | All |
| DexScreener | `dexscreener_search`, `dexscreener_trending`, `dexscreener_token` | All |
| Stocks | `get_stock_price`, `get_stock_info`, `get_analyst_recs` | All |
| Hyperliquid | `get_hl_orderbook`, `place_hl_order`, `get_hl_positions` | All |
| Aster DEX | `aster_ticker`, `aster_place_order`, `aster_positions` | All |
| Polymarket | `search_polymarket`, `buy_polymarket`, `get_polymarket_positions` | All |
| DEX Swaps | `dex_buy_sol`, `dex_buy_eth`, `dex_sell_sol`, `dex_sell_eth` | All |
| Wallets | `generate_wallet`, `import_wallet`, `get_wallet_balance`, `send_crypto` | All |
| Telegram | `tg_read_channel`, `tg_send_message` | All |
| Discord | `discord_read_channel`, `discord_send_message` | All |
| AI Chat | `chat` (Anthropic, OpenAI, Google, xAI) | All |
| Algos | `list_algos`, `set_strategy`, `start_strategy` | All |
| Trade Journal | `get_trade_journal`, `get_trade_stats` | All |
| TradingView | `get_tv_alerts` | All |

## Error Handling

```python
from sentinel import SentinelClient, AuthError, RateLimitError

try:
    client.place_hl_order(coin="ETH", side="buy", size=0.1)
except RateLimitError as e:
    print(f"Rate limited — {e.remaining} left of {e.limit_per_min}/min ({e.tier} tier)")
    print(f"Retry after {e.retry_after}s")
```

## Architecture

```
Your App -> sentinel-sdk (Python)
               | HTTPS
          Sentinel Go Gateway (Cloud Run)
               | gRPC/HTTP
          Python Engine (FastAPI) — tools, LLM, algo execution
```

## License

AGPL-3.0 — Sentinel Labs
