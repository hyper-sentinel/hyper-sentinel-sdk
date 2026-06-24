# Changelog

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
