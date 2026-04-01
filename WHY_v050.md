# Why v0.5.0

## The Version Number

Sentinel SDK v0.5.0 is the halfway mark to 1.0. The number is deliberate.

**v0.1–0.3** was the prototype era. Local-first MCP client. Everything ran on the user's machine — scrapers, LLM calls, trading, all of it. Heavy. 20+ dependencies. Worked, but didn't scale and couldn't bill.

**v0.4** was the bridge. We stood up the Go gateway, got Cloud Run deployed, started routing LLM calls through it for metering. But the SDK was still fat. It still bundled anthropic, openai, google-generativeai, telethon, discord.py, yfinance, eth-account, py-clob-client — the full kitchen. Users who just wanted to call `get_crypto_price` had to install 200MB of dependencies. The `SentinelAPI` REST client existed inside the package, but it lived alongside all the legacy code. Two architectures in one package.

**v0.5.0 is the clean break.** The SDK is now what it should have been from the start: a thin REST client. Three dependencies. Every call goes through the gateway. The gateway handles auth, billing, metering, rate limiting, and proxying. The SDK just wraps HTTP.

This is the version where the architecture matches the business model. Every `client.chat()` call, every `client.call("get_crypto_price")`, every trade — all metered, all billed, all flowing through one gateway. The SDK doesn't do anything locally anymore. It's a remote control.

## What Changed

**Removed:** 5 heavy dependencies (requests, yfinance, tenacity, py-clob-client, eth-account). All optional dep groups for serve, swarm, and telegram.

**Added:** Click CLI for terminal auth (`sentinel auth --key sk-ant-xxx`). Zero-trust encrypted vault for storing exchange credentials client-side. Dual-key system — API key for auth, secret key for vault encryption.

**Kept:** httpx (HTTP client), rich (terminal UI), and added click (CLI framework). That's it. Three deps.

**Legacy code** (scrapers, MCP client, FastAPI server, swarm orchestrator) remains in the git repo but is excluded from the published package via setuptools filtering. Users who need the old local tools can pin v0.4.1. Everyone else gets the thin client.

## Why Not 1.0

v0.5.0 is not 1.0 because there's still work to do:

- The vault sync (client-to-server encrypted blob backup) needs real-world testing
- The CLI needs `sentinel chat` for interactive terminal sessions via the gateway
- SDK needs async support (`AsyncSentinel` using httpx async)
- Trading via SDK needs integration tests against testnet
- Error messages and edge cases need polish from real user feedback
- Documentation needs a proper hosted site (not just README)

When all of that is solid and we've had a few hundred users run through it without surprises, that's 1.0.

## The Principle

The REST API is the single source of truth. The SDK is a thin wrapper. The console is a reference implementation. All roads go through the gateway.

v0.5.0 is the first version where every line of SDK code follows that principle.

---

*Soli Deo Gloria*
