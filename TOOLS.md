# Sentinel Tool Reference

> **75 tools** across 10 categories. Updated for v0.9.8.
>
> Tools are called automatically by the AI agent based on your natural language input.
> Some tools require API keys — type `add` in the terminal to configure.

---

## 📊 Market Data — Crypto (CoinGecko)

*Free — no API key needed*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `get_crypto_price` | Current price, market cap, 24h change for a cryptocurrency | `"what's BTC at?"` |
| `get_crypto_top_n` | Top N cryptos by market cap | `"show me top 10 cryptos"` |
| `search_crypto` | Search for a crypto by name or symbol | `"find the solana token"` |

---

## 📈 Market Data — Stocks (Yahoo Finance)

*Free — no API key needed*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `get_stock_price` | Current price, volume, day range | `"what's NVDA trading at?"` |
| `get_stock_info` | Company details — market cap, P/E, sector, description | `"tell me about Apple's financials"` |
| `get_analyst_recs` | Analyst buy/hold/sell ratings and price targets | `"what do analysts say about TSLA?"` |
| `get_stock_news` | Latest news articles for a ticker | `"get me NVDA news"` |
| `get_stock_history` | Historical prices — calculates returns, volatility | `"show me AAPL's last 3 months"` |
| `run_stock_analysis` | Full quantitative analysis — valuation, technicals, risk | `"run full analysis on MSFT"` |

---

## 🏦 Macro Economics (FRED)

*Free — optional API key for higher rate limits (`add fred`)*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `get_fred_series` | Any FRED data series (GDP, CPI, UNRATE, FEDFUNDS, etc.) | `"what's the current fed funds rate?"` |
| `search_fred` | Search FRED by keyword | `"search fred for housing starts"` |
| `get_economic_dashboard` | Snapshot: GDP, CPI, unemployment, fed rate, 10yr yield (with YoY%) | `"give me a macro dashboard"` |
| `get_yield_curve` | Full US Treasury curve (3M–30Y), spreads, inversion status | `"show me the yield curve"` |

---

## 📰 Y2 Intelligence

*Requires API key (`add y2`) — [Get one at y2.dev](https://y2.dev/app/developers/api-keys)*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `get_news_sentiment` | News with GloriaAI sentiment (bullish/bearish/neutral + score). 100+ editorial sources. | `"what's the institutional news sentiment on bitcoin?"` |
| `get_news_recap` | AI-generated summary of news over 12h/24h/3d/7d | `"give me a 7 day recap on crypto and macro"` |
| `get_intelligence_reports` | List AI-generated deep-dive intelligence briefs | `"show me my latest intelligence reports"` |
| `get_report_detail` | Full content of a specific intelligence report | `"read report [id]"` |
| `get_y2_feeds` | List all OSINT feed topics Y2 monitors | `"what topics can Y2 monitor?"` |
| `get_report_audio` | Audio narration URL for a report (MP3) | `"get me the audio for that report"` |
| `list_y2_profiles` | Your monitoring profiles — topics, schedule, status (read-only) | `"what Y2 profiles am I subscribed to?"` |

**Valid topics:** `ai`, `ai_agents`, `aptos`, `base`, `bitcoin`, `crypto`, `dats`, `defi`, `ethereum`, `hyperliquid`, `machine_learning`, `macro`, `ondo`, `perps`, `ripple`, `rwa`, `solana`, `tech`, `virtuals`

---

## 🔗 DEX Analytics (DexScreener)

*Free — no API key needed*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `dexscreener_search` | Search DEX pairs by token name, symbol, or address | `"find PEPE on DEX"` |
| `dexscreener_token_lookup` | All DEX pairs for a token by contract address | `"look up this contract: 0x..."` |
| `dexscreener_trending` | Hottest trending/boosted tokens across all DEXes | `"what's trending on DEX right now?"` |
| `dexscreener_pair` | Detailed pair info by chain + pair address | `"get pair info for..."` |

---

## 🐦 Social Intelligence

*Requires API keys (`add x`, `add elfa`)*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `search_x` | Search X (Twitter) for tweets by query | `"search X for Mario Nawfal on bitcoin"` |
| `get_trending_tokens` | Trending tokens from Elfa AI social intelligence | `"what tokens are trending on social?"` |
| `search_mentions` | Social media mentions for a token/topic | `"search social mentions for SOL"` |
| `get_trending_narratives` | Trending narratives in crypto from social data | `"what narratives are trending?"` |
| `get_top_mentions` | Top mentioned tokens from Elfa AI with volume and sentiment | `"what tokens are most mentioned right now?"` |
| `get_token_news` | News mentions for a specific token via Elfa AI | `"show me HYPE token news"` |

---

## 🔬 Quantitative Analysis (Built-In)

*Free — no API key needed. Works on any asset.*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `get_ta_indicators` | Full TA: SMA(9/21), EMA(12/26), RSI(14), MACD, Bollinger Bands | `"show me TA indicators for BTC"` |
| `get_ta_signal` | Quick signal: SMA crossover + RSI (bullish/bearish/neutral) | `"is ETH bullish or bearish?"` |
| `get_klines` | Raw OHLCV candlestick data | `"get 1h candles for SOL"` |
| `get_risk_metrics` | Sharpe, Sortino, Calmar, VaR (3 methods), CVaR, max drawdown | `"what's the Sharpe ratio on BTC?"` |
| `get_timeseries_forecast` | ARIMA forecast, GARCH volatility, stationarity test | `"is ETH trending or random?"` |
| `get_ml_signals` | ML signals: regression trend, K-Means regime, Random Forest, logistic prediction | `"what do the ML models say about SOL?"` |
| `get_options_analysis` | Options: P/C ratio, IV, ATM options, sentiment (stocks/ETFs only) | `"what's the put/call ratio on AAPL?"` |
| `get_options_expirations` | All available options expiration dates including LEAPS (>1yr out) | `"what expiries does AAPL have?"` |
| `get_options_chain` | Full options chain for a specific expiry — calls/puts with strike, Greeks, OI, IV | `"show me the AAPL Jan 2026 calls"` |

---

## ⚡ Trading — Hyperliquid

*Requires wallet connection (`add hl`)*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `get_hl_config` | Exchange config + connection status (crypto + TradFi) | `"check my HL connection"` |
| `get_hl_positions` | All open positions — crypto **and** TradFi (GOLD, TSLA, SP500, etc.) | `"show my Hyperliquid positions"` |
| `get_hl_account_info` | Account equity across all asset classes, margin, per-dex breakdown | `"what's my HL balance?"` |
| `get_hl_open_orders` | Pending orders — crypto + TradFi | `"show my open orders"` |
| `get_hl_orderbook` | Order book for any pair (crypto + TradFi) | `"show BTC orderbook"` |
| `place_hl_order` | Place a trade — crypto + TradFi (GOLD, TSLA, SP500, etc.) | `"long 0.1 BTC at market"` |
| `close_hl_position` | Close an open position | `"close my ETH position"` |
| `cancel_hl_order` | Cancel a pending order | `"cancel my BTC limit order"` |
| `set_hl_leverage` | Set leverage for a coin | `"set BTC leverage to 10x"` |
| `approve_hl_builder_fee` | One-time builder fee approval for trading | `"approve HL builder fee"` |
| `get_hl_tradfi_assets` | List available TradFi perps (GOLD, SILVER, OIL, TSLA, NVDA, 50+) | `"what TradFi assets can I trade?"` |
| `get_hl_tradfi_price` | Current price, spread, funding for a TradFi asset | `"what's GOLD trading at on HL?"` |

---

## 🚀 Trading — Aster DEX

*Requires wallet connection (`add aster`)*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `aster_ping` | Check Aster DEX API connectivity and latency | `"is Aster online?"` |
| `aster_ticker` | Current price/ticker for a futures pair | `"what's BTC on Aster?"` |
| `aster_orderbook` | Live order book (bids/asks) | `"show Aster BTC orderbook"` |
| `aster_klines` | Candlestick data from Aster | `"get Aster BTC candles"` |
| `aster_funding_rate` | Current funding rate and mark price | `"what's the BTC funding rate on Aster?"` |
| `aster_exchange_info` | Exchange info — trading pairs, contract specs, tick sizes | `"show Aster exchange info"` |
| `aster_diagnose` | Comprehensive diagnostics — API key, connectivity, account access | `"diagnose my Aster connection"` |
| `aster_balance` | Account balance on Aster DEX futures | `"what's my Aster balance?"` |
| `aster_account_info` | Full account info — assets, positions, margins | `"show my Aster account"` |
| `aster_positions` | Current open positions | `"show my Aster positions"` |
| `aster_open_orders` | All open/pending orders | `"show my Aster open orders"` |
| `aster_place_order` | Place an order on Aster DEX futures | `"buy 0.01 BTC on Aster"` |
| `aster_place_order_confirmed` | Place an order and poll until fill confirmation | `"buy 0.01 BTC on Aster and confirm fill"` |
| `aster_place_trailing_stop` | Place a trailing stop market order | `"place a 2% trailing stop on my Aster BTC"` |
| `aster_countdown_cancel` | Dead man's switch — auto-cancel all orders if not refreshed | `"set 60s countdown cancel on BTC"` |
| `aster_cancel_order` | Cancel an open order by ID | `"cancel my Aster BTC order"` |
| `aster_cancel_all_orders` | Cancel all open orders for a symbol | `"cancel all my Aster BTC orders"` |
| `aster_set_leverage` | Set leverage for a symbol (1-125x) | `"set Aster BTC to 10x"` |
| `aster_set_margin_mode` | Set margin mode — ISOLATED or CROSSED | `"set Aster BTC to isolated margin"` |
| `aster_order_history` | Recent order history for a symbol | `"show my Aster BTC order history"` |
| `aster_trade_history` | Recent trade fills for a symbol | `"show my Aster BTC fills"` |

---

## 📦 Portfolio & Usage

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `get_portfolio_summary` | Unified portfolio across all venues | `"show my full portfolio"` |
| `get_portfolio_risk` | Position concentration, leverage, risk level | `"analyze my portfolio risk"` |
| `get_usage_summary` | LLM usage: tokens, costs, profit | `"how much have I spent today?"` |

---

*Sentinel v0.9.8 — [Sentinel Labs LLC](https://hyper-sentinel.com) — AGPL-3.0*
