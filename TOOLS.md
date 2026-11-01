# Sentinel Tool Reference

> **42 tools** across 8 categories. Updated for v0.9.12.
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

*Requires API key (`add x`)*

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `search_x` | Search X (Twitter) for tweets by query | `"search X for Mario Nawfal on bitcoin"` |

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

## 📦 Portfolio & Usage

| Tool | Description | Example Prompt |
|------|-------------|---------------|
| `get_portfolio_summary` | Unified portfolio across all venues | `"show my full portfolio"` |
| `get_portfolio_risk` | Position concentration, leverage, risk level | `"analyze my portfolio risk"` |
| `get_usage_summary` | LLM usage: tokens, costs, profit | `"how much have I spent today?"` |

---

*Sentinel v0.9.12 — [Sentinel Labs LLC](https://hyper-sentinel.com) — AGPL-3.0*
