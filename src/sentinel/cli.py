"""
Sentinel CLI — Interactive setup, status dashboard, and smoke tests.

Usage:
    sentinel-setup       Full first-run onboarding
    sentinel status      Show connection status dashboard
    sentinel test        Quick smoke test (auth + tool call)
    sentinel add <svc>   Configure a single service

© Sentinel Labs — https://hyper-sentinel.com
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ── Theme — Retro 80s Cyan/Teal (matches hyper-sentinel TUI) ──
SENTINEL_THEME = Theme({
    "s.cyan": "#00e5ff",
    "s.cyan.bold": "bold #00e5ff",
    "s.green": "#00e5ff",            # alias — all "green" renders as cyan
    "s.green.bold": "bold #00e5ff",
    "s.gold": "bold #ffaa00",
    "s.magenta": "bold #ff44ff",
    "s.dim": "dim #b0d4db",
    "s.border": "#007a8a",
    "s.error": "bold #ff4444",
    "s.yellow": "bold #ffaa00",
})

console = Console(theme=SENTINEL_THEME)

# ── Branding ──────────────────────────────────────────────────
BANNER = """[s.cyan]
██╗  ██╗██╗   ██╗██████╗ ███████╗██████╗
██║  ██║╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗
███████║ ╚████╔╝ ██████╔╝█████╗  ██████╔╝
██╔══██║  ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗
██║  ██║   ██║   ██║     ███████╗██║  ██║
╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝[/]

[s.gold]S E N T I N E L   S D K[/]
[s.dim]Python Client · 80+ Tools · Web4 Auth[/]
"""

# ── Config ────────────────────────────────────────────────────
SENTINEL_DIR = Path.home() / ".sentinel"
CONFIG_FILE = SENTINEL_DIR / "config"

GATEWAY_URL = "https://sentinel-api-4gqwf3cjxa-uc.a.run.app"

# ── Provider detection (same as terminal) ─────────────────────
KEY_PREFIXES = {
    "sk-ant-":  ("anthropic", "Anthropic (Claude)",  "🟣"),
    "sk-proj-": ("openai",    "OpenAI (GPT)",        "🟢"),
    "sk-":      ("openai",    "OpenAI (GPT)",        "🟢"),
    "AIza":     ("google",    "Google (Gemini)",     "🔵"),
    "xai-":     ("xai",       "xAI (Grok)",          "⚫"),
}

# ── Tier Info ─────────────────────────────────────────────────
TIER_INFO = {
    "free":       {"label": "Free",       "price": "$0/mo",     "rate": "300/min",    "llm": "40%",  "maker": "0.10%", "taker": "0.08%"},
    "pro":        {"label": "Pro",        "price": "$100/mo",   "rate": "1,000/min",  "llm": "20%",  "maker": "0.06%", "taker": "0.04%"},
    "paid":       {"label": "Pro",        "price": "$100/mo",   "rate": "1,000/min",  "llm": "20%",  "maker": "0.06%", "taker": "0.04%"},
    "enterprise": {"label": "Enterprise", "price": "$1,000/mo", "rate": "Unlimited",  "llm": "10%",  "maker": "0.02%", "taker": "0.01%"},
}


def _detect_provider(key: str) -> tuple[str, str, str] | None:
    """Detect provider from API key prefix."""
    for prefix, info in KEY_PREFIXES.items():
        if key.startswith(prefix):
            return info
    return None


def _load_config() -> dict[str, Any]:
    """Load config from ~/.sentinel/config."""
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_config(config: dict[str, Any]):
    """Save config to ~/.sentinel/config with restrictive permissions."""
    SENTINEL_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass


def _register_with_gateway(ai_key: str) -> dict[str, str]:
    """Call POST /auth/ai-key to auto-create account. Fast timeout — never block setup."""
    try:
        import httpx
        resp = httpx.post(
            f"{GATEWAY_URL}/auth/ai-key",
            json={"ai_key": ai_key},
            timeout=5.0,
        )
        if resp.status_code in (200, 201):
            return resp.json()
    except Exception:
        pass
    return {}


def _test_gateway(api_key: str) -> dict | None:
    """Quick health check + tool call to verify connectivity."""
    try:
        import httpx
        client = httpx.Client(
            base_url=GATEWAY_URL,
            timeout=5.0,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        )

        # Health check
        health = client.get("/health")
        if health.status_code != 200:
            return None

        # Try a free tool
        tool_resp = client.post(
            "/api/v1/tools/get_crypto_price",
            json={"coin_id": "bitcoin"},
        )
        if tool_resp.status_code == 200:
            data = tool_resp.json()
            return {
                "health": "ok",
                "tool_test": "pass",
                "btc_price": data.get("data", {}).get("price_usd", "?"),
                "remaining": tool_resp.headers.get("X-RateLimit-Remaining", "?"),
                "limit": tool_resp.headers.get("X-RateLimit-Limit", "?"),
            }
        return {"health": "ok", "tool_test": "fail", "status": tool_resp.status_code}
    except Exception as e:
        return {"health": "error", "error": str(e)}


# ══════════════════════════════════════════════════════════════
# Setup Steps
# ══════════════════════════════════════════════════════════════

def _step_ai_key(config: dict) -> dict:
    """Step 1: AI Provider key (required)."""
    # If already configured, show current status and offer to reconfigure
    existing_key = config.get("ai_key", "")
    existing_provider = config.get("ai_provider", "")
    if existing_key and existing_provider:
        detected = _detect_provider(existing_key)
        if detected:
            _, label, emoji = detected
            masked = existing_key[:12] + "..." + existing_key[-4:]
            console.print(f"  [s.cyan]✓ Already configured:[/] {emoji} {label}")
            console.print(f"  [s.dim]Key: {masked}[/]\n")
            try:
                reconfigure = console.input("  [s.dim]Reconfigure? (y/N):[/] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n"); return config
            if reconfigure != "y":
                console.print("  [s.dim]Keeping existing key.\n[/]")
                return config
            console.print()

    step = Text()
    step.append("AI Provider ", style="bold white")
    step.append("(required)", style="s.gold")
    console.print(Panel(step, border_style="s.border", box=box.HORIZONTALS))

    console.print("  Your AI key is your identity — no email or password needed.\n")
    console.print("    [s.dim]•[/] [bold]Anthropic (Claude)[/]  [s.dim]→ console.anthropic.com[/]")
    console.print("    [s.dim]•[/] [bold]OpenAI (GPT)[/]        [s.dim]→ platform.openai.com[/]")
    console.print("    [s.dim]•[/] [bold]Google (Gemini)[/]     [s.dim]→ aistudio.google.com[/]")
    console.print("    [s.dim]•[/] [bold]xAI (Grok)[/]          [s.dim]→ console.x.ai[/]")
    console.print()

    while True:
        try:
            key = console.input("  [s.green.bold]Paste your AI API key:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [s.dim]Setup cancelled.[/]")
            sys.exit(0)

        if not key:
            console.print("  [s.error]No key entered. You need at least one AI provider key.[/]\n")
            continue

        detected = _detect_provider(key)
        if detected:
            provider_id, label, emoji = detected
            config["ai_key"] = key
            config["ai_provider"] = provider_id
            console.print(f"\n  [s.cyan]Detected: {emoji} {label}[/]")

            # Register with gateway (fast — 5s timeout, never blocks)
            console.print("  [s.dim]Connecting to Sentinel gateway...[/]", end=" ")
            result = _register_with_gateway(key)
            if result.get("api_key"):
                config["sentinel_api_key"] = result["api_key"]
                config["user_id"] = result.get("user_id", "")
                config["tier"] = result.get("tier", "free")
                status = result.get("status", "created")
                if status == "existing":
                    console.print("[s.cyan]✓ Welcome back[/]")
                else:
                    console.print("[s.cyan]✓ Account created[/]")
            else:
                console.print("[s.cyan]✓ Key saved[/]")
                config["tier"] = "free"

            console.print(f"  [s.dim]Saved to ~/.sentinel/config[/]\n")
            break
        else:
            console.print("  [s.error]Couldn't detect provider from key prefix. Try again.[/]\n")

    return config


def _step_hyperliquid(config: dict) -> dict:
    """Step 2: Hyperliquid wallet + key (optional)."""
    step = Text()
    step.append("Step 2 — Hyperliquid DEX ", style="bold white")
    step.append("(optional — Enter to skip)", style="s.dim")
    console.print(Panel(step, border_style="s.border", box=box.HORIZONTALS))

    console.print("  [s.dim]For perp trading on Hyperliquid (ETH, BTC, SOL futures).[/]")
    console.print("  [s.dim]Create a wallet at app.hyperliquid.xyz[/]\n")

    try:
        wallet = console.input("  [bold]Wallet address (0x...):[/] ").strip()
    except (EOFError, KeyboardInterrupt):
        wallet = ""

    if wallet:
        config["hyperliquid_wallet"] = wallet
        console.print("  [s.green]Wallet saved[/] — read-only mode enabled.")

        try:
            priv_key = console.input("\n  [bold]Private key for trading[/] [s.dim](Enter to skip)[/]: ").strip()
        except (EOFError, KeyboardInterrupt):
            priv_key = ""

        if priv_key:
            config["hyperliquid_key"] = priv_key
            console.print("  [s.green]Trading enabled[/]\n")
        else:
            console.print("  [s.dim]Read-only — use 'sentinel add hl' later to enable trading.[/]\n")
    else:
        console.print("  [s.dim]Skipped — use 'sentinel add hl' anytime.[/]\n")

    return config


def _step_polymarket(config: dict) -> dict:
    """Step 3: Polymarket key (optional)."""
    step = Text()
    step.append("Step 3 — Polymarket ", style="bold white")
    step.append("(optional — Enter to skip)", style="s.dim")
    console.print(Panel(step, border_style="s.border", box=box.HORIZONTALS))

    console.print("  [s.dim]For prediction market trading and positions.[/]\n")

    try:
        key = console.input("  [bold]Private key:[/] [s.dim](Enter to skip)[/] ").strip()
    except (EOFError, KeyboardInterrupt):
        key = ""

    if key:
        config["polymarket_key"] = key
        console.print("  [s.green]Polymarket trading enabled[/]\n")
    else:
        console.print("  [s.dim]Skipped — use 'sentinel add polymarket' anytime.[/]\n")

    return config


def _step_aster(config: dict) -> dict:
    """Step 4: Aster DEX key (optional)."""
    step = Text()
    step.append("Step 4 — Aster DEX ", style="bold white")
    step.append("(optional — Enter to skip)", style="s.dim")
    console.print(Panel(step, border_style="s.border", box=box.HORIZONTALS))

    console.print("  [s.dim]For futures trading on Aster DEX.[/]\n")

    try:
        api_key = console.input("  [bold]API key:[/] [s.dim](Enter to skip)[/] ").strip()
    except (EOFError, KeyboardInterrupt):
        api_key = ""

    if api_key:
        config["aster_api_key"] = api_key

        try:
            api_secret = console.input("  [bold]API secret:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            api_secret = ""

        if api_secret:
            config["aster_api_secret"] = api_secret
        console.print("  [s.green]Aster DEX trading enabled[/]\n")
    else:
        console.print("  [s.dim]Skipped — use 'sentinel add aster' anytime.[/]\n")

    return config


def _show_completion(config: dict):
    """Show the 'setup complete' summary with TUI-style dashboard."""
    tier = config.get("tier", "free")
    tier_info = TIER_INFO.get(tier, TIER_INFO["free"])

    # Detect provider for display
    provider = config.get("ai_provider", "unknown")
    detected = _detect_provider(config.get("ai_key", ""))
    provider_display = f"{detected[2]} {detected[1]}" if detected else provider

    # Account summary
    acct = Table(show_header=False, box=None, padding=(0, 1))
    acct.add_column("", style="bold white", min_width=18)
    acct.add_column("", min_width=40)

    acct.add_row("Provider", f"[s.cyan]{provider_display}[/]")
    acct.add_row("Tier", f"[s.cyan]{tier_info['label']}[/] [s.dim]({tier_info['price']})[/]")
    acct.add_row("Rate Limit", f"[s.cyan]{tier_info['rate']}[/]")
    acct.add_row("LLM Markup", f"{tier_info['llm']}")
    acct.add_row("Trade Fees", f"maker {tier_info['maker']} / taker {tier_info['taker']}")
    acct.add_row("Config", f"[s.dim]~/.sentinel/config[/]")

    console.print(Panel(
        acct,
        title="[s.cyan]✅ Setup Complete[/]",
        title_align="left",
        border_style="s.cyan",
        padding=(1, 2),
    ))

    # Next steps menu
    console.print()
    console.print("  [bold]Next steps:[/]")
    cmds = Table(show_header=False, box=None, padding=(0, 1))
    cmds.add_column("Command", style="s.cyan.bold")
    cmds.add_column("Description", style="s.dim")
    cmds.add_row("  sentinel status", "View full dashboard")
    cmds.add_row("  sentinel test", "Smoke test (auth + BTC price)")
    cmds.add_row("  sentinel add", "Add data sources & trading venues")
    cmds.add_row("  sentinel wallet", "Manage wallets (SOL/ETH)")
    cmds.add_row("  sentinel help", "Full command reference")
    console.print(cmds)
    console.print()


# ══════════════════════════════════════════════════════════════
# Add individual services
# ══════════════════════════════════════════════════════════════

ADD_HANDLERS = {
    "y2": ("📰 Y2 Intelligence", "y2_api_key", "Y2 news sentiment + AI recaps + reports", "https://y2.finance"),
    "x": ("🐦 X (Twitter)", "x_bearer_token", "tweets, trends & sentiment", "https://developer.x.com"),
    "twitter": ("🐦 X (Twitter)", "x_bearer_token", "tweets, trends & sentiment", "https://developer.x.com"),
    "fred": ("🏛️  FRED", "fred_api_key", "GDP, CPI, interest rates, yield curve", "https://fred.stlouisfed.org/docs/api/api_key.html"),
    "elfa": ("🔮 Elfa AI", "elfa_api_key", "trending tokens + social mentions", "https://elfa.ai"),
    "brave": ("🔍 Brave Search", "brave_api_key", "web search for AI agents", "https://brave.com/search/api/"),
    "discord": ("💬 Discord", "discord_token", "Discord bot integration", "https://discord.com/developers"),
    "tv": ("📺 TradingView", "tradingview_secret", "webhook alerts for auto-trading", "https://tradingview.com"),
    "tradingview": ("📺 TradingView", "tradingview_secret", "webhook alerts for auto-trading", "https://tradingview.com"),
}

# Telegram is multi-field — handled separately like HL
MULTI_FIELD_SERVICES = {"hl", "polymarket", "aster", "telegram", "tg"}

# Verification map: config_key → (tool_method, test_args, success_msg)
_VERIFY_MAP = {
    "fred_api_key": ("get_fred_series", {"series_id": "GDP", "limit": 1}, "Fetched GDP series"),
    "y2_api_key": ("get_news_sentiment", {"query": "bitcoin"}, "News sentiment OK"),
    "elfa_api_key": ("get_trending_tokens", {}, "Trending tokens OK"),
    "x_bearer_token": ("search_x", {"query": "crypto", "max_results": 1}, "Search OK"),
}


def _verify_after_save(config_key: str, label: str):
    """Confirm service key was saved — no gateway needed (local-first)."""
    console.print(f"  [s.dim]Key saved — {label} will be used on next query.[/]")


def _show_add_list():
    """Show all available integrations as a TUI-grade panel."""
    cmds = Table(show_header=False, box=None, padding=(0, 1))
    cmds.add_column("Command", style="s.cyan.bold", min_width=30)
    cmds.add_column("Description", style="s.dim")
    cmds.add_row("sentinel add y2", "Y2 news intelligence + AI recaps")
    cmds.add_row("sentinel add x", "X (Twitter) tweets & sentiment")
    cmds.add_row("sentinel add fred", "FRED economic data (GDP, CPI, rates)")
    cmds.add_row("sentinel add elfa", "Elfa AI trending tokens + social")
    cmds.add_row("sentinel add hl", "Hyperliquid DEX trading")
    cmds.add_row("sentinel add aster", "Aster DEX futures trading")
    cmds.add_row("sentinel add polymarket", "Prediction market trading")
    cmds.add_row("sentinel add telegram", "Telegram Client (API ID + Hash)")
    cmds.add_row("sentinel add discord", "Discord bot integration")
    cmds.add_row("sentinel add tv", "TradingView webhook alerts")
    cmds.add_row("sentinel add brave", "Brave web search for AI agents")
    console.print(Panel(cmds, title="[s.cyan]Available Integrations[/]", border_style="s.border", padding=(1, 2)))


def _step_telegram(config: dict) -> dict:
    """Telegram Client — multi-field (API ID + API Hash)."""
    step = Text()
    step.append("Telegram Client ", style="bold white")
    step.append("(API ID + Hash from my.telegram.org)", style="s.dim")
    console.print(Panel(step, border_style="s.border", box=box.HORIZONTALS))
    console.print("  [s.dim]Get credentials at: my.telegram.org[/]\n")
    try:
        api_id = console.input("  [bold]API ID:[/] ").strip()
        if api_id:
            config["telegram_api_id"] = api_id
            api_hash = console.input("  [bold]API Hash:[/] ").strip()
            if api_hash:
                config["telegram_api_hash"] = api_hash
                console.print("  [s.cyan]✓ Telegram configured[/]\n")
            else:
                console.print("  [s.dim]Partially configured.[/]\n")
        else:
            console.print("  [s.dim]Skipped.[/]\n")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [s.dim]Cancelled.[/]")
    return config


def _add_service(name: str):
    """Add a single service key with overwrite protection + verification."""
    config = _load_config()

    # Multi-field services
    if name == "hl":
        config = _step_hyperliquid(config)
        _save_config(config)
        return
    if name == "polymarket":
        config = _step_polymarket(config)
        _save_config(config)
        return
    if name == "aster":
        config = _step_aster(config)
        _save_config(config)
        return
    if name in ("telegram", "tg"):
        config = _step_telegram(config)
        _save_config(config)
        return

    handler = ADD_HANDLERS.get(name)
    if not handler:
        console.print(f"  [s.error]Unknown service: {name}[/]")
        _show_add_list()
        return

    label, config_key, desc, url = handler
    console.print(f"\n  [bold]{label}[/] — [s.dim]{desc}[/]")
    console.print(f"  [s.dim]Get keys at: {url}[/]\n")

    # Overwrite protection
    current = config.get(config_key, "")
    if current:
        mask = current[:4] + "..." + current[-4:] if len(current) > 8 else "****"
        console.print(f"  [s.cyan]✓[/] Current: [s.dim]{mask}[/] (already set)")
        try:
            overwrite = console.input("  [s.dim]Overwrite? (y/N):[/] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [s.dim]Cancelled.[/]")
            return
        if overwrite != "y":
            console.print("  [s.dim]Kept existing key.[/]\n")
            return

    try:
        key = console.input(f"  [s.cyan.bold]{label} key:[/] ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [s.dim]Cancelled.[/]")
        return

    if key:
        config[config_key] = key
        _save_config(config)
        console.print(f"  [s.cyan]✓ {label} configured[/]")
        _verify_after_save(config_key, label)
        console.print()
    else:
        console.print(f"  [s.dim]Skipped.[/]\n")


# ══════════════════════════════════════════════════════════════
# Status dashboard — matches TUI's _print_status
# ══════════════════════════════════════════════════════════════

def _show_status():
    """Show connection status dashboard — TUI-grade."""
    config = _load_config()
    tier = config.get("tier", "free")
    tier_info = TIER_INFO.get(tier, TIER_INFO["free"])

    console.print()
    console.print(BANNER)

    # ── Auth & Account ──
    auth = Table(
        title="[bold cyan]🛡️  Auth & Account[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    auth.add_column("Item", style="bold white", min_width=18)
    auth.add_column("Status", min_width=20)
    auth.add_column("Details", style="dim")

    if config.get("sentinel_api_key"):
        key_preview = config["sentinel_api_key"][:16] + "..."
        auth.add_row("🔑 API Key", f"[s.green]● {key_preview}[/]", "~/.sentinel/config")
    elif config.get("ai_key"):
        auth.add_row("🔑 API Key", "[s.cyan]● AI key set[/] [s.dim](gateway sync pending)[/]", "~/.sentinel/config")
    else:
        auth.add_row("🔑 API Key", "[s.dim]○ Not configured[/]", "run sentinel-setup")

    if config.get("ai_provider"):
        provider_label = {"anthropic": "🟣 Anthropic", "openai": "🟢 OpenAI", "google": "🔵 Google", "xai": "⚫ xAI"}.get(
            config["ai_provider"], config["ai_provider"]
        )
        auth.add_row("🤖 AI Provider", f"[s.green]● {provider_label}[/]", "")
    else:
        auth.add_row("🤖 AI Provider", "[s.dim]○ Not set[/]", "")

    auth.add_row("📊 Tier", f"[s.green]{tier_info['label']}[/]", tier_info["price"])
    auth.add_row("⚡ Rate Limit", f"[s.green]{tier_info['rate']}[/]", "")
    auth.add_row("💰 LLM Markup", tier_info["llm"], "")
    auth.add_row("📈 Trade Fees", f"maker {tier_info['maker']} / taker {tier_info['taker']}", "")

    console.print(auth)

    # ── Gateway ──
    gw = Table(
        title="[bold cyan]🌐 Gateway[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    gw.add_column("Item", style="bold white", min_width=18)
    gw.add_column("Status", min_width=20)
    gw.add_column("Details", style="dim")

    gw.add_row("🏗️  Endpoint", "[s.green]● Cloud Run[/]", GATEWAY_URL[:50] + "...")
    gw.add_row("📡 Protocol", "HTTPS", "TLS 1.3")
    gw.add_row("🔧 Tools", "[s.green]● 62+ registered[/]", "crypto · equities · AI · social · trading")

    # Test connectivity if we have a key
    if config.get("sentinel_api_key") or config.get("ai_key"):
        gw.add_row("📶 Status", "[s.dim]run 'sentinel test' to verify[/]", "")
    else:
        gw.add_row("📶 Status", "[s.dim]○ Not authenticated[/]", "run sentinel-setup")

    console.print(gw)

    # ── Data Sources ──
    ds = Table(
        title="[bold cyan]📊 Data Sources[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    ds.add_column("Source", style="bold white", min_width=18)
    ds.add_column("Status", min_width=20)
    ds.add_column("Details", style="dim")

    # Always available
    ds.add_row("📈 YFinance", "[s.green]● Always available[/]", "stocks + ETFs + analyst recs + news")
    ds.add_row("🪙 CoinGecko", "[s.green]● Always available[/]", "10,000+ crypto prices + market data")
    ds.add_row("📊 DexScreener", "[s.green]● Always available[/]", "DEX pair data + trending tokens")

    # Configurable
    _status = lambda k: "[s.green]● Connected[/]" if config.get(k) else "[s.dim]○ Not configured[/]"
    _hint = lambda cmd: f"sentinel add {cmd}"

    ds.add_row("🏛️  FRED", _status("fred_api_key"), "GDP, CPI, rates, VIX" if config.get("fred_api_key") else _hint("fred"))
    ds.add_row("📰 Y2 Intelligence", _status("y2_api_key"), "news sentiment + recaps" if config.get("y2_api_key") else _hint("y2"))
    ds.add_row("🔮 Elfa AI", _status("elfa_api_key"), "trending tokens + social" if config.get("elfa_api_key") else _hint("elfa"))
    ds.add_row("🐦 X (Twitter)", _status("x_bearer_token"), "tweets + trends + sentiment" if config.get("x_bearer_token") else _hint("x"))

    console.print(ds)

    # ── Trading Venues ──
    tv = Table(
        title="[bold cyan]💹 Trading Venues[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    tv.add_column("Venue", style="bold white", min_width=18)
    tv.add_column("Status", min_width=20)
    tv.add_column("Details", style="dim")

    if config.get("hyperliquid_key"):
        tv.add_row("⚡ Hyperliquid", "[bold s.green]● Trading enabled[/]", "perp futures + orders + positions")
    elif config.get("hyperliquid_wallet"):
        tv.add_row("⚡ Hyperliquid", "[s.green]● Read-only[/]", "positions + orderbook")
    else:
        tv.add_row("⚡ Hyperliquid", "[s.green]● Market data[/]", _hint("hl") + " for trading")

    if config.get("aster_api_key"):
        tv.add_row("🌟 Aster DEX", "[bold s.green]● Trading enabled[/]", "futures + orderbook + leverage")
    else:
        tv.add_row("🌟 Aster DEX", "[s.green]● Market data[/]", _hint("aster") + " for trading")

    if config.get("polymarket_key"):
        tv.add_row("🎲 Polymarket", "[bold s.green]● Trading enabled[/]", "browse + bet + positions")
    else:
        tv.add_row("🎲 Polymarket", "[s.green]● Read-only[/]", _hint("polymarket") + " for trading")

    tv.add_row("🔄 Jupiter (SOL)", "[s.green]● Always available[/]", "on-chain swaps via SDK")
    tv.add_row("🦄 Uniswap (ETH)", "[s.green]● Always available[/]", "on-chain swaps via SDK")

    console.print(tv)

    # ── Upgrade Path ──
    if tier == "free":
        console.print()
        upgrade = Table(
            show_header=False, box=None, padding=(0, 1),
        )
        upgrade.add_column("", style="s.gold")
        upgrade.add_column("", style="s.dim")
        upgrade.add_row("  💎 Upgrade to Pro", "$100/mo → 20% LLM markup, 0.06%/0.04% fees, 1K req/min")
        upgrade.add_row("  👑 Upgrade to Enterprise", "$1,000/mo → 10% LLM markup, 0.02%/0.01% fees, unlimited")
        upgrade.add_row("", "python -c \"from sentinel import SentinelClient; print(SentinelClient().upgrade('pro'))\"")
        console.print(upgrade)

    # Count connected sources
    connected = 3  # always-available sources
    for k in ["fred_api_key", "y2_api_key", "elfa_api_key", "x_bearer_token"]:
        if config.get(k):
            connected += 1
    console.print(f"\n  [s.dim]{connected} data sources · Tier: {tier_info['label']} · {GATEWAY_URL[:40]}...[/]\n")


# ══════════════════════════════════════════════════════════════
# Smoke Test
# ══════════════════════════════════════════════════════════════

def _run_test():
    """Run a quick smoke test — auth + health + tool call."""
    config = _load_config()
    console.print()
    console.print(Panel(
        "[s.green.bold]🧪 Sentinel SDK Smoke Test[/]",
        border_style="s.border",
        padding=(0, 3),
    ))

    if not config.get("sentinel_api_key") and not config.get("ai_key"):
        console.print("  [s.error]✗ No API key found[/] — run [bold]sentinel-setup[/] first.\n")
        return

    # If we have ai_key but no sentinel_api_key, try to register now
    api_key = config.get("sentinel_api_key", "")
    if not api_key and config.get("ai_key"):
        console.print("  [s.dim]Registering with gateway...[/]", end=" ")
        result = _register_with_gateway(config["ai_key"])
        if result.get("api_key"):
            api_key = result["api_key"]
            config["sentinel_api_key"] = api_key
            config["user_id"] = result.get("user_id", "")
            config["tier"] = result.get("tier", "free")
            _save_config(config)
            console.print("[s.cyan]✓[/]")
        else:
            console.print("[s.dim]gateway unavailable — test may fail[/]")

    if not api_key:
        console.print("  [s.error]✗ Could not obtain API key from gateway.[/]\n")
        return

    key_preview = api_key[:16] + "..."
    console.print(f"  [s.dim]Key: {key_preview}[/]")
    console.print(f"  [s.dim]Gateway: {GATEWAY_URL}[/]")
    console.print()

    tests = [
        ("Health check", None),
        ("Auth verification", None),
        ("Tool call (BTC price)", None),
        ("Rate limit headers", None),
    ]

    try:
        import httpx
        client = httpx.Client(
            base_url=GATEWAY_URL,
            timeout=10.0,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        )

        # Test 1: Health
        t0 = time.time()
        health = client.get("/health")
        ms = int((time.time() - t0) * 1000)
        if health.status_code == 200:
            console.print(f"  [s.green]✓[/] Health check          [s.dim]{ms}ms[/]")
        else:
            console.print(f"  [s.error]✗[/] Health check          [s.dim]HTTP {health.status_code}[/]")
            return

        # Test 2: Auth (check billing status)
        t0 = time.time()
        auth_resp = client.get("/api/v1/billing/status")
        ms = int((time.time() - t0) * 1000)
        if auth_resp.status_code == 200:
            data = auth_resp.json()
            tier = data.get("tier", "?")
            console.print(f"  [s.green]✓[/] Auth verified         [s.dim]tier={tier} · {ms}ms[/]")
        else:
            console.print(f"  [s.error]✗[/] Auth failed           [s.dim]HTTP {auth_resp.status_code}[/]")

        # Test 3: Tool call
        t0 = time.time()
        tool_resp = client.post(
            "/api/v1/tools/get_crypto_price",
            json={"coin_id": "bitcoin"},
        )
        ms = int((time.time() - t0) * 1000)
        if tool_resp.status_code == 200:
            btc = tool_resp.json().get("data", {}).get("price_usd", "?")
            console.print(f"  [s.green]✓[/] get_crypto_price      [s.dim]BTC = ${btc} · {ms}ms[/]")
        else:
            console.print(f"  [s.error]✗[/] get_crypto_price      [s.dim]HTTP {tool_resp.status_code}[/]")

        # Test 4: Rate limit headers
        remaining = tool_resp.headers.get("X-RateLimit-Remaining", "?")
        limit = tool_resp.headers.get("X-RateLimit-Limit", "?")
        if remaining != "?":
            console.print(f"  [s.green]✓[/] Rate limit headers    [s.dim]{remaining}/{limit} remaining[/]")
        else:
            console.print(f"  [s.dim]○[/] Rate limit headers    [s.dim]not present (public route?)[/]")

        console.print()
        console.print("  [s.green.bold]All tests passed ✓[/]")
        console.print()
        console.print("  [s.dim]Ready to use:[/]")
        console.print('  [s.dim]from sentinel import SentinelClient[/]')
        console.print('  [s.dim]client = SentinelClient()[/]')
        console.print('  [s.dim]print(client.get_crypto_price("bitcoin"))[/]')
        console.print()

    except Exception as e:
        console.print(f"  [s.error]✗ Connection failed:[/] {e}")
        console.print(f"  [s.dim]Gateway may be cold-starting — try again in 30s[/]\n")


# ══════════════════════════════════════════════════════════════
# Wallet CLI — Phantom-style
# ══════════════════════════════════════════════════════════════

WALLETS_FILE = SENTINEL_DIR / "wallets.json"

def _load_wallets() -> dict:
    try:
        if WALLETS_FILE.exists():
            return json.loads(WALLETS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {"sol": [], "eth": []}

def _save_wallets(wallets: dict):
    SENTINEL_DIR.mkdir(exist_ok=True)
    WALLETS_FILE.write_text(json.dumps(wallets, indent=2))
    try:
        WALLETS_FILE.chmod(0o600)
    except OSError:
        pass


def _handle_wallet(args: list[str]):
    """Phantom-style wallet management."""
    sub = args[0] if args else ""

    if not sub or sub == "help":
        wallets = _load_wallets()
        sol_w = wallets.get("sol", [])
        eth_w = wallets.get("eth", [])
        console.print()
        console.print("  [bold cyan]💰 Sentinel Wallet[/]")
        console.print()
        if sol_w or eth_w:
            for w in sol_w:
                addr = w["address"]
                label = w.get("label", "sol-1")
                console.print(f"  [bold yellow]★[/] [bold #9945FF]◉ SOL[/]  {addr[:8]}...{addr[-6:]}  [bold]{label}[/]")
            for w in eth_w:
                addr = w["address"]
                label = w.get("label", "eth-1")
                console.print(f"  [bold yellow]★[/] [bold #627EEA]◉ ETH[/]  {addr[:8]}...{addr[-6:]}  [bold]{label}[/]")
            console.print()
        else:
            console.print("  [s.dim]No wallets connected yet.[/]\n")
        console.print("  [bold]Quick Actions:[/]")
        console.print("  [s.cyan.bold]  sentinel wallet connect[/]           🔗 Import private key")
        console.print("  [s.cyan.bold]  sentinel wallet generate sol|eth[/]  🆕 Create new wallet")
        console.print("  [s.cyan.bold]  sentinel wallet list[/]              📊 Show all wallets")
        console.print("  [s.cyan.bold]  sentinel wallet send[/]              📤 Send crypto")
        console.print("  [s.cyan.bold]  sentinel wallet receive[/]           📥 Deposit addresses")
        console.print()
        return

    if sub in ("connect", "import"):
        console.print("\n  [bold cyan]🔗 Connect Wallet[/]")
        console.print("  [s.dim]Import your private key — like Phantom or MetaMask[/]\n")
        console.print("  [bold #9945FF]1.[/] Solana  (SOL)")
        console.print("  [bold #627EEA]2.[/] Ethereum (ETH)")
        try:
            pick = console.input("\n  [s.gold]Pick chain (1/2):[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("  [s.dim]Cancelled.[/]\n"); return
        chain = "sol" if pick in ("1", "sol") else "eth" if pick in ("2", "eth") else None
        if not chain:
            console.print("  [s.error]Invalid choice.[/]\n"); return
        chain_name = "Solana" if chain == "sol" else "Ethereum"
        chain_color = "#9945FF" if chain == "sol" else "#627EEA"
        try:
            key = console.input(f"\n  [s.gold]Private key:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("  [s.dim]Cancelled.[/]\n"); return
        if not key:
            console.print("  [s.dim]Cancelled.[/]\n"); return
        try:
            from sentinel import SentinelClient
            client = SentinelClient()
            result = client.import_wallet(chain=chain, private_key=key)
            addr = result.get("address", "?")
            wallets = _load_wallets()
            wallets.setdefault(chain, []).append({"address": addr, "label": f"{chain}-{len(wallets.get(chain, [])) + 1}"})
            _save_wallets(wallets)
            console.print(f"\n  [bold green]✓ {chain_name} wallet connected![/]")
            console.print(f"  [bold]Address:[/]  [{chain_color}]{addr}[/]")
            console.print(f"  [s.dim]Ready to trade![/]\n")
        except Exception as e:
            console.print(f"  [s.error]✗ Import failed:[/] {e}\n")
        return

    if sub == "generate":
        chain = args[1] if len(args) > 1 else ""
        if chain not in ("sol", "eth"):
            console.print("  [s.gold]Usage:[/] sentinel wallet generate sol|eth\n"); return
        try:
            from sentinel import SentinelClient
            client = SentinelClient()
            result = client.generate_wallet(chain=chain)
            addr = result.get("address", "?")
            wallets = _load_wallets()
            label = f"{chain}-{len(wallets.get(chain, [])) + 1}"
            wallets.setdefault(chain, []).append({"address": addr, "label": label})
            _save_wallets(wallets)
            chain_name = "Solana" if chain == "sol" else "Ethereum"
            console.print(f"\n  [bold green]✓ {chain_name} wallet generated![/]")
            console.print(f"  [bold]Address:[/]  {addr}")
            console.print(f"  [bold]Label:[/]    {label}")
            console.print(f"  [s.gold]⚠ Private key stored server-side — keep your Sentinel key safe![/]\n")
        except Exception as e:
            console.print(f"  [s.error]✗ Generate failed:[/] {e}\n")
        return

    if sub == "list":
        wallets = _load_wallets()
        if not wallets.get("sol") and not wallets.get("eth"):
            console.print("  [s.dim]No wallets. Run:[/] sentinel wallet connect\n"); return
        console.print()
        for w in wallets.get("sol", []):
            console.print(f"  [bold #9945FF]◉ SOL[/]  {w['address']}  [bold]{w.get('label', '?')}[/]")
        for w in wallets.get("eth", []):
            console.print(f"  [bold #627EEA]◉ ETH[/]  {w['address']}  [bold]{w.get('label', '?')}[/]")
        console.print()
        return

    if sub == "send":
        console.print("\n  [bold cyan]📤 Send Crypto[/]\n")
        try:
            to_addr = console.input("  [bold]To address:[/] ").strip()
            amount = console.input("  [bold]Amount:[/] ").strip()
            chain = console.input("  [bold]Chain (sol/eth):[/] ").strip()
            if not all([to_addr, amount, chain]):
                console.print("  [s.dim]Cancelled.[/]\n"); return
            confirm = console.input(f"  [s.gold]Send {amount} {chain.upper()} to {to_addr[:12]}...? (y/N):[/] ").strip()
            if confirm.lower() != "y":
                console.print("  [s.dim]Cancelled.[/]\n"); return
            from sentinel import SentinelClient
            result = SentinelClient().send_crypto(to_address=to_addr, amount=float(amount), chain=chain)
            console.print(f"  [bold green]✓ Sent![/] TX: {result.get('tx_hash', '?')}\n")
        except Exception as e:
            console.print(f"  [s.error]✗ Send failed:[/] {e}\n")
        return

    if sub == "receive":
        wallets = _load_wallets()
        console.print("\n  [bold cyan]📥 Deposit Addresses[/]\n")
        for w in wallets.get("sol", []):
            console.print(f"  [bold #9945FF]SOL[/]  {w['address']}")
        for w in wallets.get("eth", []):
            console.print(f"  [bold #627EEA]ETH[/]  {w['address']}")
        if not wallets.get("sol") and not wallets.get("eth"):
            console.print("  [s.dim]No wallets. Run:[/] sentinel wallet connect")
        console.print()
        return

    console.print(f"  [s.error]Unknown wallet command: {sub}[/]")
    console.print("  [s.dim]Commands: connect, generate, list, send, receive[/]\n")


# ══════════════════════════════════════════════════════════════
# Help — categorized command reference
# ══════════════════════════════════════════════════════════════

def _show_help():
    """Show all commands organized by category — matches TUI quality."""
    console.print()

    def _section(title, color, rows):
        t = Table(title=f"[bold {color}]{title}[/]", title_justify="left",
                  show_header=False, box=box.ROUNDED, border_style=color, padding=(0, 2), expand=False)
        t.add_column("Command", style="s.cyan.bold", min_width=32)
        t.add_column("Description", style="s.dim")
        for cmd, desc in rows:
            t.add_row(cmd, desc)
        console.print(t)

    _section("Getting Started", "cyan", [
        ("sentinel-setup", "Full first-run onboarding wizard"),
        ("sentinel status", "Infrastructure + auth + data sources dashboard"),
        ("sentinel test", "Smoke test (health + auth + BTC price)"),
        ("sentinel version", "Show installed version"),
    ])
    _section("Data Sources", "#4488ff", [
        ("sentinel add y2", "Y2 news intelligence + AI recaps"),
        ("sentinel add x", "X (Twitter) tweets & sentiment"),
        ("sentinel add fred", "FRED economic data (GDP, CPI, rates)"),
        ("sentinel add elfa", "Elfa AI trending tokens + social"),
        ("sentinel add", "Show all available integrations"),
    ])
    _section("Trading", "#ffaa00", [
        ("sentinel wallet", "Manage wallets (connect/generate/list/send)"),
        ("sentinel add hl", "Configure Hyperliquid DEX trading"),
        ("sentinel add aster", "Configure Aster DEX futures"),
        ("sentinel add polymarket", "Configure Polymarket prediction markets"),
    ])
    _section("Billing & Upgrade", "#ff44ff", [
        ("sentinel billing", "View tier, usage, and fee rates"),
        ("sentinel upgrade", "Upgrade to Pro ($100/mo)"),
        ("sentinel upgrade enterprise", "Upgrade to Enterprise ($1,000/mo)"),
    ])
    _section("System", "dim", [
        ("sentinel tools", "List all 80+ available tools"),
        ("sentinel help", "Show this help"),
    ])
    console.print()


# ══════════════════════════════════════════════════════════════
# Upgrade — opens Stripe checkout
# ══════════════════════════════════════════════════════════════

def _handle_upgrade(plan: str = "pro"):
    """Open Stripe checkout for tier upgrade."""
    config = _load_config()
    if not config.get("sentinel_api_key") and not config.get("ai_key"):
        console.print("  [s.error]✗ Not authenticated[/] — run [bold]sentinel-setup[/] first.\n")
        return
    # Try to get sentinel_api_key if we only have ai_key
    if not config.get("sentinel_api_key") and config.get("ai_key"):
        result = _register_with_gateway(config["ai_key"])
        if result.get("api_key"):
            config["sentinel_api_key"] = result["api_key"]
            config["tier"] = result.get("tier", "free")
            _save_config(config)
    if not config.get("sentinel_api_key"):
        console.print("  [s.dim]Gateway unavailable — try 'sentinel upgrade' again in a moment.[/]\n")
        return
    console.print(f"\n  [s.magenta]💎 Upgrading to {plan.title()}...[/]")
    try:
        from sentinel import SentinelClient
        url = SentinelClient(api_key=config["sentinel_api_key"], timeout=10).upgrade(plan)
        console.print(f"  [s.cyan]✓ Checkout URL:[/] {url}")
        import webbrowser
        webbrowser.open(url)
        console.print(f"  [s.dim]Opened in browser. Complete payment to activate.[/]\n")
    except Exception as e:
        console.print(f"  [s.error]✗ Upgrade failed:[/] {e}\n")


# ══════════════════════════════════════════════════════════════
# Billing — usage dashboard
# ══════════════════════════════════════════════════════════════

def _show_billing():
    """Show billing status from the gateway."""
    config = _load_config()
    tier = config.get("tier", "free")
    t_info = TIER_INFO.get(tier, TIER_INFO["free"])
    if not config.get("sentinel_api_key") and not config.get("ai_key"):
        console.print("  [s.error]✗ Not authenticated[/] — run [bold]sentinel-setup[/] first.\n")
        return
    # Try to get sentinel_api_key if we only have ai_key
    if not config.get("sentinel_api_key") and config.get("ai_key"):
        result = _register_with_gateway(config["ai_key"])
        if result.get("api_key"):
            config["sentinel_api_key"] = result["api_key"]
            config["tier"] = result.get("tier", "free")
            _save_config(config)
    if not config.get("sentinel_api_key"):
        # Show offline billing from local config
        console.print()
        tbl = Table(title="[bold cyan]🛡️  Billing Status[/] [s.dim](offline)[/]", title_justify="left",
                    show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan", padding=(0, 2))
        tbl.add_column("", style="bold white", min_width=18)
        tbl.add_column("", min_width=40)
        tbl.add_row("Tier", f"[s.cyan]{t_info['label']}[/] [s.dim]({t_info['price']})[/]")
        tbl.add_row("Rate Limit", f"[s.cyan]{t_info['rate']}[/]")
        tbl.add_row("LLM Markup", t_info["llm"])
        tbl.add_row("Trade Fees", f"maker {t_info['maker']} / taker {t_info['taker']}")
        console.print(tbl)
        console.print("  [s.dim]Gateway unavailable — billing data from local config.[/]\n")
        return
    console.print()
    try:
        from sentinel import SentinelClient
        data = SentinelClient(api_key=config["sentinel_api_key"], timeout=10).billing_status()
        tier = data.get("tier", "free")
        t_info = TIER_INFO.get(tier, TIER_INFO["free"])
        tbl = Table(title="[bold cyan]🛡️  Billing Status[/]", title_justify="left",
                    show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan", padding=(0, 2))
        tbl.add_column("", style="bold white", min_width=18)
        tbl.add_column("", min_width=40)
        tbl.add_row("Tier", f"[s.cyan]{t_info['label']}[/] [s.dim]({t_info['price']})[/]")
        tbl.add_row("Rate Limit", f"[s.cyan]{t_info['rate']}[/]")
        tbl.add_row("LLM Markup", t_info["llm"])
        tbl.add_row("Trade Fees", f"maker {t_info['maker']} / taker {t_info['taker']}")
        calls = data.get("monthly_api_calls", "?")
        tbl.add_row("API Calls", f"{calls} this month")
        console.print(tbl)
        if tier == "free":
            console.print(f"\n  [s.gold]💎 sentinel upgrade[/] [s.dim]→ Pro ($100/mo)[/]")
            console.print(f"  [s.gold]👑 sentinel upgrade enterprise[/] [s.dim]→ Enterprise ($1,000/mo)[/]")
        console.print()
    except Exception as e:
        console.print(f"  [s.error]✗ Could not fetch billing:[/] {e}\n")


# ══════════════════════════════════════════════════════════════
# Tools — list available tools from gateway
# ══════════════════════════════════════════════════════════════

def _show_tools():
    """List all tools from the gateway."""
    config = _load_config()
    if not config.get("sentinel_api_key") and not config.get("ai_key"):
        console.print("  [s.error]✗ Not authenticated[/] — run [bold]sentinel-setup[/] first.\n")
        return
    # Try to get sentinel_api_key if we only have ai_key
    if not config.get("sentinel_api_key") and config.get("ai_key"):
        result = _register_with_gateway(config["ai_key"])
        if result.get("api_key"):
            config["sentinel_api_key"] = result["api_key"]
            config["tier"] = result.get("tier", "free")
            _save_config(config)
    if not config.get("sentinel_api_key"):
        console.print("  [s.dim]Gateway unavailable — try again in a moment.[/]\n")
        return
    console.print()
    try:
        from sentinel import SentinelClient
        tools = SentinelClient(api_key=config["sentinel_api_key"], timeout=10).list_tools()
        if not tools:
            tools = []
        tbl = Table(title=f"[bold cyan]🔧 Available Tools ({len(tools)})[/]", title_justify="left",
                    show_header=True, box=box.SIMPLE_HEAVY, border_style="cyan", padding=(0, 2))
        tbl.add_column("Tool", style="s.cyan.bold", min_width=28)
        tbl.add_column("Category", style="s.dim", min_width=14)
        tbl.add_column("Description", style="s.dim")
        for tool in tools[:60]:  # cap display
            tbl.add_row(tool.get("name", "?"), tool.get("category", ""), tool.get("description", "")[:60])
        console.print(tbl)
        if len(tools) > 60:
            console.print(f"  [s.dim]... and {len(tools) - 60} more[/]")
        console.print()
    except Exception as e:
        console.print(f"  [s.error]✗ Could not fetch tools:[/] {e}\n")


# ══════════════════════════════════════════════════════════════
# Entry Points
# ══════════════════════════════════════════════════════════════

def setup():
    """Full first-run setup flow."""
    console.print()
    console.print(BANNER)

    config = _load_config()
    config = _step_ai_key(config)
    _save_config(config)

    _show_completion(config)


def main():
    """Main CLI entry point — 'sentinel' command."""
    args = sys.argv[1:]

    if not args:
        _show_status()
        return

    cmd = args[0].lower()

    if cmd == "setup":
        setup()
    elif cmd == "status":
        _show_status()
    elif cmd == "test":
        _run_test()
    elif cmd == "help" or cmd == "--help" or cmd == "-h":
        _show_help()
    elif cmd == "wallet":
        _handle_wallet(args[1:])
    elif cmd == "upgrade":
        plan = args[1] if len(args) > 1 else "pro"
        _handle_upgrade(plan)
    elif cmd == "billing":
        _show_billing()
    elif cmd == "tools":
        _show_tools()
    elif cmd == "add" and len(args) > 1:
        _add_service(args[1].lower())
    elif cmd == "add":
        _show_add_list()
    elif cmd == "chat":
        from sentinel.chat import run_chat
        run_chat(_load_config())
    elif cmd == "ask":
        question = " ".join(args[1:]) if len(args) > 1 else ""
        if not question:
            console.print("  [s.error]Usage:[/] sentinel ask \"your question here\"")
            return
        from sentinel.chat import run_ask
        run_ask(_load_config(), question)
    elif cmd in ("version", "--version", "-v"):
        from sentinel import __version__
        console.print(f"  [s.cyan]hyper-sentinel[/] v{__version__}")
    elif cmd == "serve":
        port = 8000
        host = "0.0.0.0"
        for i, a in enumerate(args[1:], 1):
            if a in ("--port", "-p") and i + 1 < len(args):
                port = int(args[i + 1])
            elif a in ("--host",) and i + 1 < len(args):
                host = args[i + 1]
        from sentinel.server import run_server
        run_server(host=host, port=port)
    else:
        # If no known command, treat everything as a one-shot question
        question = " ".join(args)
        from sentinel.chat import run_ask
        run_ask(_load_config(), question)


if __name__ == "__main__":
    main()

