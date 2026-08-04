# Changelog

## v0.9.7 — 2026-08-04

### 🔴 Bug Fix — Doubled Portfolio Balance on Unified Accounts

**`get_hl_account_info()` was reporting 2× the real account value** for users on Hyperliquid's
Unified Account or Portfolio Margin mode. The function summed `accountValue` from both the native
and xyz dex queries, but on unified accounts both return the same consolidated balance.

- **Account mode detection** — new `_get_account_mode()` queries HL's `userAbstraction` endpoint
  to detect unified/portfolio-margin vs standard accounts.
- **Unified accounts** — uses a single `user_state` query for total equity; does not double-sum
  native + xyz `accountValue` and does not add `spot_value` (already included in unified equity).
- **Standard accounts** — unchanged, sum-both-dexes logic preserved.
- **`account_mode` field** — returned in `get_hl_account_info()`, `get_hl_config()`, and
  `get_portfolio_summary()` responses for transparency.
- **`get_hl_config()` `total_balance`** — same fix applied; no longer sums `perps + xyz + spot`
  on unified accounts.

### ⚠️ Impact

- Account equity, leverage calculations, and risk assessments are now correct
- No changes to trade execution, positions, orderbook, or billing
- Version synced across `pyproject.toml`, `__init__.py`, `TOOLS.md`, `docs.go`, SDK docs

---

## v0.9.4 — 2026-06-26

### 🔴 Identity Fix (cont.) — stale config key no longer blocks registration

0.9.3 registered with the gateway only `if not api_key`. But users upgrading across versions carry a
**stale `sentinel_api_key`** in `~/.sentinel/config` (from an old session / the pre-Supabase ephemeral
DB). That stale key made the guard skip registration, the key failed to resolve, and every call fell
through to `anonymous` — counter stuck at 10/10, usage unbilled.

- **`run_chat` now ALWAYS registers the current `ai_key` at launch**, idempotently. `/auth/ai-key`
  creates-or-returns the account for the key; a valid key is a no-op, a stale key is replaced with the
  correct canonical Sentinel key (persisted to `~/.sentinel/api_key`). Identity then resolves on every
  call — `X-API-Key` (Path 2) and the `X-AI-Key` header from 0.9.3 (Path 3) both work.

Upgraded users self-heal on next launch — no need to delete `~/.sentinel/config`.

## v0.9.3 — 2026-06-26

### 🔴 Identity Fix — free-prompt counting for UPGRADED users

**Symptom:** after upgrading 0.9.1 → 0.9.2, the prompt counter stayed frozen at "10/10" and usage was
never billed. Root cause: an upgraded user already has `~/.sentinel/config` with an AI key, so the
first-run setup block (which registers with the gateway and saves a Sentinel key) was **skipped**.
With no saved Sentinel key, every gateway call — the LLM chat **and** the billing/status poll that draws
the counter — went out as `anonymous`, so nothing was counted or attributed.

- **Register at launch (`run_chat`)** — if an AI key is present but no Sentinel key is saved, the SDK now
  registers with the gateway on startup (idempotent) and persists the returned key to `~/.sentinel/api_key`.
  Every subsequent call sends `X-API-Key` → the user is identified, counted, and billed.
- **`X-AI-Key` header on LLM calls (`_gateway_llm_request`)** — belt-and-suspenders: the AI key is now
  also sent as a header so the gateway resolves identity even if the local key-file save fails (e.g. on
  Windows). The provider key still travels in the body for the upstream call.

No gateway changes — the gateway (0.9.2, deployed) was already correct; the SDK simply never identified
upgraded users.

## v0.9.2 — 2026-06-26

### 🔴 Revenue Fix — Free-tier prompts now actually count (paid-conversion funnel)

**Free prompts were never being counted, so the paywall never triggered.** The CLI showed a frozen "10/10 prompts left" no matter how many prompts you sent.

Root cause: the SDK sent the LLM key as the `X-AI-Key` header, but the gateway's auth middleware only recognized `Authorization: Bearer` and `X-API-Key` — so every BYO-key user fell through to `anonymous` and was bypassed uncounted (and unmetered).

- **SDK** — `_register_with_gateway()` now persists the gateway-issued key via `save_api_key()`, so `load_api_key()` returns it and **every** LLM call sends `X-API-Key`. The post-turn line now shows the live `Quota: N/M free prompts remaining`.
- **Gateway** — added a third auth path: a request carrying only `X-AI-Key` is resolved to the account created by `POST /auth/ai-key` (deterministic `sha256("sentinel-ai:"+key)`), so the quota gate counts it. Existing JWT and API-key paths are unchanged (read-only, additive).
- **Gateway** — `/api/v1/billing/status` and `/billing/usage` now return `prompt_limit: 0` for paying (`active`) users, so the counter is shown only to free users.

### 🐛 Scraper / Tool Fixes (work for real end users)

- **Aster DEX** — added missing `tenacity>=8.2.0` dependency (was `No module named 'tenacity'` on every Aster call for pip-install users).
- **CoinGecko** — added `tenacity` retry with exponential backoff on 429/5xx, lengthened the price cache to 5 min, proper demo/pro API-key headers, and a graceful rate-limit message instead of a crash. Fixes lookups failing even for `bitcoin` under burst.
- **`get_news_sentiment`** — fixed tool-schema mismatch (`query=` ↔ `topics=`) that raised `unexpected keyword argument 'query'`.
- **`search_crypto`** — fixed a latent `ImportError` (imported `search_coins`; the function is `search_crypto`).
- **X / Twitter** — a 402 from the X API now returns a clear "billing/quota on your X account, not a Sentinel bug" message instead of crashing the turn.

### 🧪 Diagnostics

- New `tools diagnose` command runs a per-category tool smoke test (CoinGecko, DexScreener, YFinance, and any key-gated sources) and reports pass/fail.

### 📋 Version Sync

- Bumped to 0.9.2 across `pyproject.toml`, `__init__.py`, SDK banner, and the gateway OpenAPI spec.

### ⚠️ Known limitations

- **Polymarket** remains lazy-imported and is not in the active tool schema (avoids shipping Web3/Ethereum binaries to all users); install `py-clob-client` manually to use it.
- **Quota persistence** — durable. The production gateway runs on **Supabase Postgres** (`DATABASE_URL` set on Cloud Run; SQLite is local-dev only), so prompt counts and accounts persist across deploys.

---

## v0.9.1 — 2026-06-24

### 🐛 Bug Fix — Config→Environment Bridge

**Services configured via `add <service>` mid-session now work immediately** without requiring a restart.

Previously, `_add_service()` wrote credentials to `~/.sentinel/config` but didn't update `os.environ`, so tools (scrapers) that read environment variables would fail until the next session boot. The new `_bridge_config_to_env()` function syncs config→env at boot AND after any `add` call.

### ⚡ Gateway Improvements (v0.9.1)

- **Metering diagnostics** — Boot-time logs confirm Stripe meter configuration (restricted key, price ID, event name). Meter event failures now log full context (customer, model, fee, HTTP status) instead of swallowing errors.
- **Meter retry** — 1× retry with 2s delay for transient 5xx/network errors. Uses idempotent request IDs so retries can't double-bill.
- **Google Gemini streaming** — Fixed missing `"google"` in the streaming provider case. Gemini users can now use `?stream=true`.

---

## v0.9.0 — 2026-06-22

### 🐛 Bug Fix — TradFi Position Visibility

**`get_hl_positions()`, `get_hl_account_info()`, `get_hl_open_orders()`, and `get_hl_config()` now return data from ALL Hyperliquid asset classes** — crypto perps, stocks (NVDA, AAPL, MU, TSLA...), commodities (GOLD, SILVER, OIL), indices (SP500), and forex (EUR/USD).

Previously, these functions only queried native crypto perps (`dex=""`), missing all TradFi positions on the xyz builder dex. Trading functions (`place_hl_order`, `close_hl_position`) were unaffected — you could open/close TradFi positions, but couldn't see them.

### ⚡ New Response Fields

| Function | New Fields |
|----------|-----------|
| `get_hl_positions()` | `asset_type` ("crypto" or "tradfi"), `dex` ("native" or "xyz") |
| `get_hl_account_info()` | `dex_breakdown` (per-dex equity/margin) |
| `get_hl_config()` | `xyz_connection`, `xyz_account_value` |
| `get_hl_open_orders()` | `dex` ("native" or "xyz") |

### 📋 Version Sync

- Bumped all version strings across 6 locations (pyproject.toml, __init__.py, server.py, TOOLS.md, docs.go)
- Fixed server.py version drift — was stuck at v0.8.6 for 3 releases
- TOOLS.md now lists all 12 Hyperliquid tools (was missing 5)
- Updated tool count from 60 to 69

### 📦 Internal

- Added `_PERP_DEXES` constant for future HIP-3 dex expansion
- Position deduplication handles Unified Account mode
- Per-dex error isolation — one dex failing doesn't block the other

---

## v0.8.9

- 150s response timeout
- Free-tier 402 handling with quota meter
- Upgrade command + redesigned 402 panel

## v0.8.8

- Aster builder fee
- Shelved USDC + swarm features

## v0.8.7

- 8 LLM providers (added DeepSeek, GLM, Minimax, Kimi)

## v0.8.6

- 69 tools parity sync
- Options chain + LEAPS + Greeks
- Shelved dead features
