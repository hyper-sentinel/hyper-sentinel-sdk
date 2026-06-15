"""
Sentinel CLI — Command-line interface for the Sentinel SDK.

Thin wrapper around the SentinelAPI for quick access to tools,
configuration, and vault management.

Usage:
    sentinel auth --key sk-ant-xxx              # Authenticate
    sentinel status                              # Show account status
    sentinel call get_crypto_price --param coin_id=bitcoin
    sentinel tools                               # List available tools
    sentinel vault init                          # Initialize vault
    sentinel vault set KEY VALUE                 # Store a config value
    sentinel vault get KEY                       # Retrieve a config value
    sentinel vault list                          # List all keys
"""

import click
import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from sentinel import __version__
from sentinel.api.auth import authenticate_with_ai_key
from sentinel.api._http import load_api_key, save_api_key
from sentinel.api.client import SentinelAPI
from sentinel.api.errors import AuthenticationError, SentinelAPIError

console = Console()
CONFIG_DIR = Path.home() / ".sentinel"
CONFIG_FILE = CONFIG_DIR / "config"
SECRET_FILE = CONFIG_DIR / "secret_key"


def _tool_count() -> int:
    """Live count of the SDK's tool schemas (single source of truth for the banner)."""
    try:
        from sentinel.chat import TOOL_SCHEMAS
        return len(TOOL_SCHEMAS)
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════
# Config Helpers (restored from v0.3.16)
# ══════════════════════════════════════════════════════════════

def _load_config() -> dict:
    """Load config from ~/.sentinel/config."""
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_config(config: dict):
    """Save config to ~/.sentinel/config with restrictive permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass


# ══════════════════════════════════════════════════════════════
# Service Configuration (restored from v0.3.16)
# ══════════════════════════════════════════════════════════════

ADD_HANDLERS = {
    "y2":          ("📰 Y2 Intelligence", "y2_api_key", "Y2 news sentiment + AI recaps + reports", "https://y2.finance"),
    "x":           ("🐦 X (Twitter)", "x_bearer_token", "tweets, trends & sentiment", "https://developer.x.com"),
    "twitter":     ("🐦 X (Twitter)", "x_bearer_token", "tweets, trends & sentiment", "https://developer.x.com"),
    "fred":        ("🏛️  FRED", "fred_api_key", "GDP, CPI, interest rates, yield curve", "https://fred.stlouisfed.org/docs/api/api_key.html"),
    "elfa":        ("🔮 Elfa AI", "elfa_api_key", "trending tokens + social mentions", "https://elfa.ai"),
    "brave":       ("🔍 Brave Search", "brave_api_key", "web search for AI agents", "https://brave.com/search/api/"),
    "discord":     ("💬 Discord", "discord_token", "Discord bot integration", "https://discord.com/developers"),
    "tv":          ("📺 TradingView", "tradingview_secret", "webhook alerts for auto-trading", "https://tradingview.com"),
    "tradingview": ("📺 TradingView", "tradingview_secret", "webhook alerts for auto-trading", "https://tradingview.com"),
}


def _approve_builder_fee_step(priv_key: str) -> None:
    """Explicit, one-time builder-fee approval during onboarding (revenue capture).

    Transparent on purpose: tells the user about the 0.01% builder fee up front so it's
    never a surprise mid-trade. Best-effort — if it can't approve now (offline, SDK not
    installed), the first trade auto-approves as a fallback. Never blocks setup.
    """
    console.print(
        "\n  [dim]Sentinel earns 0.01% per trade via Hyperliquid's builder code —\n"
        "  a one-time, gasless signature, capped at 0.01%, revocable anytime.[/]"
    )
    try:
        import os
        os.environ["HYPERLIQUID_PRIVATE_KEY"] = priv_key
        from sentinel.scrapers.hyperliquid import approve_hl_builder_fee
        result = approve_hl_builder_fee()
        if isinstance(result, dict) and result.get("status") == "APPROVED":
            console.print("  [green]✓ Builder fee approved[/] [dim](one-time).[/]\n")
        else:
            console.print("  [dim]→ Will be approved automatically on your first trade.[/]\n")
    except Exception:
        console.print("  [dim]→ Will be approved automatically on your first trade.[/]\n")


def _step_hyperliquid(config: dict) -> dict:
    """Hyperliquid wallet + key setup."""
    from rich import box
    from rich.text import Text

    console.print()
    step = Text()
    step.append("Hyperliquid DEX ", style="bold white")
    step.append("(wallet + optional trading key)", style="dim")
    console.print(Panel(step, border_style="cyan", box=box.HORIZONTALS))

    console.print("  [dim]For perp trading on Hyperliquid (ETH, BTC, SOL futures).[/]")
    console.print("  [dim]Create a wallet at app.hyperliquid.xyz[/]\n")

    # Show current if exists
    current_wallet = config.get("hyperliquid_wallet", "")
    if current_wallet:
        mask = current_wallet[:6] + "..." + current_wallet[-4:]
        console.print(f"  [green]✓[/] Current wallet: [dim]{mask}[/]")
        try:
            overwrite = console.input("  [dim]Overwrite? (y/N):[/] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Cancelled.[/]")
            return config
        if overwrite != "y":
            console.print("  [dim]Kept existing config.[/]\n")
            return config

    try:
        wallet = console.input("  [bold]Wallet address (0x...):[/] ").strip()
    except (EOFError, KeyboardInterrupt):
        wallet = ""

    if wallet:
        config["hyperliquid_wallet"] = wallet
        console.print("  [green]✓ Wallet saved[/] — read-only mode enabled.")

        try:
            priv_key = console.input("\n  [bold]Private key for trading[/] [dim](Enter to skip)[/]: ").strip()
        except (EOFError, KeyboardInterrupt):
            priv_key = ""

        if priv_key:
            config["hyperliquid_key"] = priv_key
            console.print("  [green]✓ Trading enabled[/]")
            _approve_builder_fee_step(priv_key)
        else:
            console.print("  [dim]Read-only — use 'add hl' later to enable trading.[/]\n")
    else:
        console.print("  [dim]Skipped — use 'add hl' anytime.[/]\n")

    return config


def _step_polymarket(config: dict) -> dict:
    """Polymarket key setup."""
    from rich import box
    from rich.text import Text

    console.print()
    step = Text()
    step.append("Polymarket ", style="bold white")
    step.append("(prediction market trading)", style="dim")
    console.print(Panel(step, border_style="cyan", box=box.HORIZONTALS))

    console.print("  [dim]For prediction market trading and positions.[/]\n")

    current = config.get("polymarket_key", "")
    if current:
        mask = current[:4] + "..." + current[-4:] if len(current) > 8 else "****"
        console.print(f"  [green]✓[/] Current: [dim]{mask}[/] (already set)")
        try:
            overwrite = console.input("  [dim]Overwrite? (y/N):[/] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Cancelled.[/]")
            return config
        if overwrite != "y":
            console.print("  [dim]Kept existing key.[/]\n")
            return config

    try:
        key = console.input("  [bold]Private key:[/] [dim](Enter to skip)[/] ").strip()
    except (EOFError, KeyboardInterrupt):
        key = ""

    if key:
        config["polymarket_key"] = key
        console.print("  [green]✓ Polymarket trading enabled[/]\n")
    else:
        console.print("  [dim]Skipped — use 'add polymarket' anytime.[/]\n")

    return config


def _step_aster(config: dict) -> dict:
    """Aster DEX key setup."""
    from rich import box
    from rich.text import Text

    console.print()
    step = Text()
    step.append("Aster DEX ", style="bold white")
    step.append("(futures trading)", style="dim")
    console.print(Panel(step, border_style="cyan", box=box.HORIZONTALS))

    console.print("  [dim]For futures trading on Aster DEX.[/]\n")

    current = config.get("aster_api_key", "")
    if current:
        mask = current[:4] + "..." + current[-4:] if len(current) > 8 else "****"
        console.print(f"  [green]✓[/] Current: [dim]{mask}[/] (already set)")
        try:
            overwrite = console.input("  [dim]Overwrite? (y/N):[/] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Cancelled.[/]")
            return config
        if overwrite != "y":
            console.print("  [dim]Kept existing key.[/]\n")
            return config

    try:
        api_key = console.input("  [bold]API key:[/] [dim](Enter to skip)[/] ").strip()
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
        console.print("  [green]✓ Aster DEX trading enabled[/]\n")
    else:
        console.print("  [dim]Skipped — use 'add aster' anytime.[/]\n")

    return config


def _step_telegram(config: dict) -> dict:
    """Telegram Client — multi-field (API ID + API Hash)."""
    from rich import box
    from rich.text import Text

    console.print()
    step = Text()
    step.append("Telegram Client ", style="bold white")
    step.append("(API ID + Hash from my.telegram.org)", style="dim")
    console.print(Panel(step, border_style="cyan", box=box.HORIZONTALS))
    console.print("  [dim]Get credentials at: my.telegram.org[/]\n")
    try:
        api_id = console.input("  [bold]API ID:[/] ").strip()
        if api_id:
            config["telegram_api_id"] = api_id
            api_hash = console.input("  [bold]API Hash:[/] ").strip()
            if api_hash:
                config["telegram_api_hash"] = api_hash
                console.print("  [green]✓ Telegram configured[/]\n")
            else:
                console.print("  [dim]Partially configured.[/]\n")
        else:
            console.print("  [dim]Skipped.[/]\n")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Cancelled.[/]")
    return config


def _verify_after_save(config_key: str, label: str):
    """Confirm service key was saved."""
    console.print(f"  [dim]Key saved — {label} will be used on next query.[/]")


def _show_add_list():
    """Show all available integrations."""
    console.print()
    cmds = Table(show_header=False, box=None, padding=(0, 1))
    cmds.add_column("Command", style="cyan bold", min_width=26)
    cmds.add_column("Description", style="dim")
    cmds.add_row("add y2", "Y2 news intelligence + AI recaps")
    cmds.add_row("add x", "X (Twitter) tweets & sentiment")
    cmds.add_row("add fred", "FRED economic data (GDP, CPI, rates)")
    cmds.add_row("add elfa", "Elfa AI trending tokens + social")
    cmds.add_row("add hl", "Hyperliquid DEX trading")
    cmds.add_row("add aster", "Aster DEX futures trading")
    # cmds.add_row("add polymarket", "Prediction market trading")  # archived
    cmds.add_row("add telegram", "Telegram Client (API ID + Hash)")
    cmds.add_row("add discord", "Discord bot integration")
    cmds.add_row("add tv", "TradingView webhook alerts")
    cmds.add_row("add brave", "Brave web search for AI agents")
    console.print(Panel(cmds, title="[bold cyan]Available Integrations[/]", border_style="cyan", padding=(1, 2)))
    console.print()


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
        console.print(f"  [red]Unknown service: {name}[/]")
        _show_add_list()
        return

    label, config_key, desc, url = handler
    console.print(f"\n  [bold]{label}[/] — [dim]{desc}[/]")
    console.print(f"  [dim]Get keys at: {url}[/]\n")

    # Overwrite protection
    current = config.get(config_key, "")
    if current:
        mask = current[:4] + "..." + current[-4:] if len(current) > 8 else "****"
        console.print(f"  [green]✓[/] Current: [dim]{mask}[/] (already set)")
        try:
            overwrite = console.input("  [dim]Overwrite? (y/N):[/] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Cancelled.[/]")
            return
        if overwrite != "y":
            console.print("  [dim]Kept existing key.[/]\n")
            return

    try:
        key = console.input(f"  [bold cyan]{label} key:[/] ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Cancelled.[/]")
        return

    if key:
        config[config_key] = key
        _save_config(config)
        console.print(f"  [green]✓ {label} configured[/]")
        _verify_after_save(config_key, label)
        console.print()
    else:
        console.print(f"  [dim]Skipped.[/]\n")


def detect_provider(key: str) -> str:
    """Auto-detect AI provider from key prefix.

    Args:
        key: The AI provider key

    Returns:
        Provider name (anthropic, openai, google, xai)
    """
    if key.startswith("sk-ant-"):
        return "anthropic"
    elif key.startswith("sk-") and not key.startswith("sk-sentinel-"):
        return "openai"
    elif key.startswith("AIza"):
        return "google"
    elif key.startswith("xai-"):
        return "xai"
    else:
        return "unknown"

@click.group(invoke_without_command=True)
@click.version_option(__version__, "-v", "-V", "--version", prog_name="sentinel")
@click.pass_context
def cli(ctx):
    """Sentinel — AI trading terminal with quant + market tools."""
    if ctx.invoked_subcommand is None:
        # No subcommand → launch the interactive terminal with first-run onboarding
        _run_repl()


def _run_repl():
    """Interactive AI chat REPL — the Sentinel terminal experience."""
    import time
    from rich import box
    from rich.text import Text
    from rich.live import Live

    api_key = load_api_key()

    # ── First-Run Setup (seamless — no dead ends) ─────────────
    if not api_key:
        console.print()

        welcome_banner = """
[bold cyan]██╗  ██╗██╗   ██╗██████╗ ███████╗██████╗[/]
[bold cyan]██║  ██║╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗[/]
[bold cyan]███████║ ╚████╔╝ ██████╔╝█████╗  ██████╔╝[/]
[bold cyan]██╔══██║  ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗[/]
[bold cyan]██║  ██║   ██║   ██║     ███████╗██║  ██║[/]
[bold cyan]╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝[/]

[bold white]S E N T I N E L[/]  [dim]v{version}[/]
[dim]Quantitative AI Agent · {n_tools} Tools · Local-First[/]
""".format(version=__version__, n_tools=_tool_count())
        console.print(welcome_banner)

        welcome = Text()
        welcome.append("Welcome to Sentinel!\n", style="bold cyan")
        welcome.append("Let's get you set up. This only takes 10 seconds.\n", style="dim")
        welcome.append("Your keys are saved locally — you won't be asked again.", style="dim")
        console.print(Panel(welcome, border_style="cyan", padding=(1, 3)))
        console.print()

        # Step 1 — AI Provider Key
        step1 = Text()
        step1.append("Step 1 — AI Provider Key ", style="bold white")
        step1.append("(required)", style="bold yellow")
        console.print(Panel(step1, border_style="cyan", box=box.HORIZONTALS))

        console.print("  Paste any API key from a supported provider:\n")
        console.print("    [dim]•[/] [bold]Anthropic (Claude)[/]  [dim]→ console.anthropic.com[/]")
        console.print("    [dim]•[/] [bold]OpenAI (GPT)[/]        [dim]→ platform.openai.com[/]")
        console.print("    [dim]•[/] [bold]Google (Gemini)[/]     [dim]→ aistudio.google.com[/]")
        console.print("    [dim]•[/] [bold]xAI (Grok)[/]          [dim]→ console.x.ai[/]")
        console.print()

        while True:
            try:
                ai_key = console.input("  [bold cyan]Paste your AI API key:[/] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Setup cancelled.[/dim]")
                return

            if not ai_key:
                console.print("  [red]No key entered. You need an AI provider key to use Sentinel.[/]")
                continue

            # Auto-detect provider
            provider = detect_provider(ai_key)
            PROVIDER_LABELS = {
                "anthropic": ("🟣", "Anthropic (Claude)"),
                "openai":    ("🟢", "OpenAI (GPT)"),
                "google":    ("🔵", "Google (Gemini)"),
                "xai":       ("⚡", "xAI (Grok)"),
            }

            if provider == "unknown":
                console.print("  [yellow]⚠ Couldn't detect provider. Double-check your key.[/]")
                continue

            emoji, label = PROVIDER_LABELS.get(provider, ("", provider))
            console.print(f"\n  [green]✓ Detected: {emoji} {label}[/]")

            # Exchange for Sentinel API key
            try:
                with console.status("[cyan]  Creating your Sentinel account...[/]", spinner="dots"):
                    api_key, response = authenticate_with_ai_key(ai_key)

                is_new = response.get("status") == "created"
                secret_key = response.get("secret_key")
                tier = response.get("tier", "free")

                # Save secret key
                if secret_key:
                    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                    SECRET_FILE.write_text(secret_key)
                    try:
                        SECRET_FILE.chmod(0o600)
                    except OSError:
                        pass

                # Save AI provider key for ChatResource.load_ai_key()
                from sentinel.api._http import save_ai_key
                save_ai_key(ai_key)

                # Also sync to JSON config so run_chat() finds it
                json_config = _load_config()
                json_config["ai_key"] = ai_key
                json_config["ai_provider"] = provider
                if api_key:
                    json_config["sentinel_api_key"] = api_key
                json_config["tier"] = tier
                _save_config(json_config)

                if is_new and secret_key:
                    console.print(f"  [green]✓ Account created![/] Tier: [bold]{tier}[/]")
                    console.print()
                    console.print(Panel(
                        f"[bold white]API Key[/] [dim](authenticates all calls)[/]\n"
                        f"[bold #00e5ff]{api_key}[/]\n"
                        f"\n"
                        f"[bold white]Secret Key[/] [dim](vault recovery — SAVE THIS)[/]\n"
                        f"[bold #f0883e]{secret_key}[/]\n"
                        f"\n"
                        f"[dim]Both saved to ~/.sentinel/[/]",
                        border_style="green",
                        padding=(1, 2),
                        title="[bold green]✓ Setup Complete[/]",
                    ))
                    console.print()
                    console.print("  [yellow]⚠️  The secret key will NOT be shown again. Save it now.[/]")
                else:
                    console.print(f"  [green]✓ Welcome back![/] Tier: [bold]{tier}[/]")

                console.print()
                break

            except Exception as e:
                console.print(f"  [red]✗ Auth failed:[/] {e}")
                console.print("  [dim]Check your key and try again.[/]")
                continue

    # ── Ensure AI key exists (returning users from older versions may not have it) ──
    from sentinel.api._http import load_ai_key, save_ai_key
    if not load_ai_key():
        console.print()
        console.print("  [yellow]⚠ Missing AI provider key.[/] Your Sentinel account exists but we need your LLM key for chat.")
        console.print("  [dim]Paste the same AI key you used to sign up (Claude, GPT, Gemini, or Grok).[/]")
        console.print()
        while True:
            try:
                ai_key_input = console.input("  [bold cyan]Paste your AI API key:[/] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Cancelled.[/dim]")
                return
            if not ai_key_input:
                continue
            provider = detect_provider(ai_key_input)
            if provider == "unknown":
                console.print("  [yellow]⚠ Unrecognized key prefix. Try again.[/]")
                continue
            save_ai_key(ai_key_input)
            PROVIDER_LABELS = {
                "anthropic": ("🟣", "Anthropic (Claude)"),
                "openai":    ("🟢", "OpenAI (GPT)"),
                "google":    ("🔵", "Google (Gemini)"),
                "xai":       ("⚡", "xAI (Grok)"),
            }
            emoji, label = PROVIDER_LABELS.get(provider, ("", provider))
            console.print(f"  [green]✓ {emoji} {label} saved to ~/.sentinel/ai_key[/]")
            console.print()
            break

    # ── Create client ─────────────────────────────────────────
    try:
        client = SentinelAPI()
    except AuthenticationError:
        console.print("[red]Invalid API key.[/red] Delete ~/.sentinel/api_key and run [cyan]sentinel[/cyan] again.")
        return

    # ── ASCII Art Banner (the OG) ─────────────────────────────
    BANNER = """
[bold cyan]██╗  ██╗██╗   ██╗██████╗ ███████╗██████╗[/]
[bold cyan]██║  ██║╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗[/]
[bold cyan]███████║ ╚████╔╝ ██████╔╝█████╗  ██████╔╝[/]
[bold cyan]██╔══██║  ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗[/]
[bold cyan]██║  ██║   ██║   ██║     ███████╗██║  ██║[/]
[bold cyan]╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝[/]

[bold white]S E N T I N E L[/]  [dim]v{version}[/]
[dim]Quantitative AI Agent · {n_tools} Tools · Local-First[/]
""".format(version=__version__, n_tools=_tool_count())

    # ── Hand off to chat.py's full engine ────────────────────
    # chat.py has the working REPL: 60 tool schemas, local tool execution,
    # session memory, swarm mode, markdown formatting — everything.
    # cli.py handles onboarding + auth. chat.py handles the actual chat.
    from sentinel.chat import run_chat, _load_config as _load_chat_config
    config = _load_chat_config()
    run_chat(config)



@cli.command()
@click.argument("question", nargs=-1, required=True)
def ask(question):
    """One-shot question to the AI agent.

    Usage:
        sentinel ask "what is BTC at?"
        sentinel ask "show my HL positions"
    """
    from sentinel.chat import run_ask, _load_config
    config = _load_config()
    run_ask(config, " ".join(question))


@cli.command()
@click.option("--key", default=None, help="Your AI provider key (sk-ant-*, sk-*, AIza*, xai-*)")
@click.option("--provider", default=None, help="AI provider (anthropic, openai, google, xai) — auto-detected if not given")
def auth(key: Optional[str], provider: Optional[str]):
    """Authenticate and generate your Sentinel API key.

    Exchanges your AI provider key (Claude, OpenAI, Google, Grok) for a
    Sentinel API key + Secret key. The API key authenticates all calls.

    Usage:
        sentinel auth                              # Interactive prompt
        sentinel auth --key sk-ant-xxxxxxxxxxxxx   # Direct
    """
    # Interactive mode if no key provided
    if not key:
        console.print()
        console.print(Panel(
            "[bold #00e5ff]Welcome to Sentinel[/]\n"
            "\n"
            "Exchange your AI provider key for a Sentinel API key.\n"
            "Supported providers:\n"
            "\n"
            "  [#a97cf8]🟣 Claude[/]   — sk-ant-api03-...\n"
            "  [#00c853]🟢 GPT[/]      — sk-...\n"
            "  [#4285f4]🔵 Gemini[/]   — AIza...\n"
            "  [#ff6b35]⚡ Grok[/]     — xai-...\n",
            border_style="#00e5ff",
            padding=(1, 2),
            title="[bold]SENTINEL",
            subtitle="[dim]Soli Deo Gloria",
        ))
        console.print()
        key = click.prompt("Enter your AI provider key", hide_input=True)

    if not key or not key.strip():
        console.print("[red]Error:[/red] No key provided.")
        raise click.Abort()

    key = key.strip()

    # Auto-detect provider if not provided
    if not provider:
        provider = detect_provider(key)

    if provider == "unknown":
        console.print("[red]Error:[/red] Could not auto-detect provider from key format.")
        console.print("Use --provider to specify: anthropic, openai, google, or xai")
        raise click.Abort()

    try:
        with console.status(f"[cyan]Authenticating with {provider}...[/cyan]", spinner="dots"):
            api_key, response = authenticate_with_ai_key(key)

        is_new = response.get("status") == "created"
        secret_key = response.get("secret_key")

        # Save secret key if returned (new user)
        if secret_key:
            save_secret_key(secret_key)

        # Display success
        if is_new and secret_key:
            msg = (
                f"[bold #00e5ff]✓ Account Created[/]\n"
                f"\n"
                f"[white]Provider:[/white] {provider}\n"
                f"[white]Tier:[/white] {response.get('tier', 'free')}\n"
                f"\n"
                f"[bold white]API Key[/bold white] [dim](authenticates all API calls)[/dim]\n"
                f"[bold #00e5ff]{api_key}[/]\n"
                f"\n"
                f"[bold white]Secret Key[/bold white] [dim](vault recovery — SAVE THIS NOW)[/dim]\n"
                f"[bold #f0883e]{secret_key}[/]\n"
                f"\n"
                f"[dim]Saved to ~/.sentinel/api_key and ~/.sentinel/secret_key[/dim]"
            )
            console.print()
            console.print(Panel(msg, border_style="#00e5ff", padding=(1, 2), title="[bold]SENTINEL", subtitle="[dim]Save both keys"))
            console.print()
            console.print("[yellow]⚠️  The secret key will NOT be shown again.[/yellow]")
        else:
            msg = (
                f"[bold #00e5ff]✓ Welcome Back[/]\n"
                f"\n"
                f"[white]Provider:[/white] {provider}\n"
                f"[white]Tier:[/white] {response.get('tier', 'free')}\n"
                f"[white]API Key:[/white] {api_key[:20]}...\n"
                f"\n"
                f"[dim]Saved to ~/.sentinel/api_key[/dim]"
            )
            console.print()
            console.print(Panel(msg, border_style="#00e5ff", padding=(1, 2), title="[bold]SENTINEL"))

        console.print()
        console.print("[green]Ready to use![/green] Try:")
        console.print("  [cyan]sentinel status[/cyan]")
        console.print("  [cyan]sentinel tools[/cyan]")
        console.print("  [cyan]sentinel call get_crypto_price --param coin_id=bitcoin[/cyan]")

    except AuthenticationError as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@cli.command()
def status():
    """Show your account status and current balance.

    Requires authentication (sentinel auth).
    """
    try:
        client = SentinelAPI()
        result = client.ping()

        msg = (
            f"[bold #00e5ff]Account Status[/]\n"
            f"\n"
            f"{json.dumps(result, indent=2)}"
        )
        console.print(Panel(msg, border_style="#00e5ff", padding=(1, 2)))

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@cli.command()
@click.argument("tool_name")
@click.option("--param", multiple=True, help="Pass parameters as key=value (repeatable)")
def call(tool_name: str, param: tuple):
    """Call any Sentinel tool by name.

    Example:
        sentinel call get_crypto_price --param coin_id=bitcoin
        sentinel call stock_price --param symbol=AAPL
        sentinel call get_fred_series --param series_id=GDP
    """
    try:
        client = SentinelAPI()

        # Parse params
        params = {}
        for p in param:
            if "=" not in p:
                console.print(f"[red]Invalid param:[/red] {p} (expected key=value)")
                raise click.Abort()
            key, value = p.split("=", 1)
            # Try to parse as number or JSON, otherwise treat as string
            try:
                params[key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                params[key] = value

        with console.status(f"[cyan]Calling {tool_name}...[/cyan]", spinner="dots"):
            result = client.tools.call(tool_name, **params)

        # Pretty-print result
        syntax = Syntax(
            json.dumps(result, indent=2),
            "json",
            theme="monokai",
            line_numbers=False,
        )
        console.print()
        console.print(syntax)
        console.print()

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@cli.command()
def tools():
    """List all available tools.

    Shows tool names, descriptions, and parameters.
    """
    try:
        client = SentinelAPI()

        with console.status("[cyan]Fetching tools...[/cyan]", spinner="dots"):
            result = client.tools.list()

        tools_list = result.get("tools", [])

        if not tools_list:
            console.print("[yellow]No tools found.[/yellow]")
            return

        table = Table(title=f"Available Tools ({len(tools_list)})", show_header=True, header_style="bold #00e5ff")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")

        for tool in tools_list:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            # Truncate long descriptions
            if len(desc) > 50:
                desc = desc[:47] + "..."
            table.add_row(name, desc)

        console.print()
        console.print(table)
        console.print()
        console.print(f"[dim]Use 'sentinel call <tool_name> --param key=value' to call a tool[/dim]")

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@cli.group()
def vault():
    """Manage encrypted configuration vault.

    Store and retrieve sensitive configuration like exchange keys,
    API credentials, and settings. Encrypted locally with your secret key.
    """
    pass


def load_secret_key() -> Optional[str]:
    """Load secret key from ~/.sentinel/secret_key."""
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    return None


def save_secret_key(key: str):
    """Save secret key to ~/.sentinel/secret_key."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(key)
    try:
        SECRET_FILE.chmod(0o600)
    except OSError:
        pass


@vault.command(name="init")
def vault_init():
    """Initialize the vault for the first time.

    Creates ~/.sentinel/vault.json and generates encryption keys.
    """
    try:
        client = SentinelAPI()

        with console.status("[cyan]Initializing vault...[/cyan]", spinner="dots"):
            result = client.vault.init()

        msg = (
            f"[bold #00e5ff]Vault Initialized[/]\n"
            f"\n"
            f"[white]Location:[/white] ~/.sentinel/vault.json\n"
            f"[white]Status:[/white] Ready to store secrets\n"
            f"\n"
            f"[dim]Secrets are encrypted locally with your secret key.[/dim]"
        )
        console.print(Panel(msg, border_style="#00e5ff", padding=(1, 2)))

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@vault.command(name="set")
@click.argument("key")
@click.argument("value")
def vault_set(key: str, value: str):
    """Set a configuration value in the vault.

    Example:
        sentinel vault set exchange_key "your_key_here"
        sentinel vault set dex_address "0x..."
    """
    secret_key = load_secret_key()
    if not secret_key:
        console.print("[red]Vault not initialized.[/red] Run: sentinel vault init")
        raise click.Abort()

    try:
        from sentinel.vault import LocalVault
        vault = LocalVault(secret_key)
        vault.set(key, value)
        console.print(f"[green]✓[/green] Stored: {key}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@vault.command(name="get")
@click.argument("key")
def vault_get(key: str):
    """Retrieve a configuration value from the vault.

    Example:
        sentinel vault get exchange_key
    """
    secret_key = load_secret_key()
    if not secret_key:
        console.print("[red]Vault not initialized.[/red] Run: sentinel vault init")
        raise click.Abort()

    try:
        from sentinel.vault import LocalVault
        vault = LocalVault(secret_key)
        value = vault.get(key)

        if value is None:
            console.print(f"[yellow]Key not found:[/yellow] {key}")
        else:
            console.print(f"[cyan]{key}:[/cyan]")
            console.print(f"  {value}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@vault.command(name="list")
def vault_list():
    """List all keys in the vault."""
    secret_key = load_secret_key()
    if not secret_key:
        console.print("[red]Vault not initialized.[/red] Run: sentinel vault init")
        raise click.Abort()

    try:
        from sentinel.vault import LocalVault
        vault = LocalVault(secret_key)
        keys = vault.list_keys()

        if not keys:
            console.print("[yellow]Vault is empty.[/yellow]")
        else:
            table = Table(title=f"Vault Keys ({len(keys)})", show_header=True, header_style="bold #00e5ff")
            table.add_column("Key", style="cyan")

            for k in keys:
                table.add_row(k)

            console.print()
            console.print(table)
            console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


# ══════════════════════════════════════════════════════════════
# Strategy Management
# ══════════════════════════════════════════════════════════════


@cli.group()
def strategy():
    """Manage algo trading strategies.

    Configure, start, stop, and switch between 6 built-in algorithms.
    Paper trading is the default — no real orders until you switch to live.

    Examples:
        sentinel strategy algos
        sentinel strategy config --algo sma --symbol BTC --venue hl
        sentinel strategy start
        sentinel strategy status
        sentinel strategy stop
    """
    pass


@strategy.command(name="status")
def strategy_status():
    """Show current strategy status — mode, algo, symbol, venue, config."""
    try:
        client = SentinelAPI()

        with console.status("[cyan]Fetching strategy status...[/cyan]", spinner="dots"):
            result = client.strategy.status()

        data = result.get("data", result)
        algo = data.get("algo", "—")
        symbol = data.get("symbol", "—")
        venue = data.get("venue", "—")
        mode = data.get("mode", "—")
        running = data.get("running", False)
        status_icon = "[green]● RUNNING[/]" if running else "[yellow]○ STOPPED[/]"

        msg = (
            f"[bold #00e5ff]Strategy Status[/]\n"
            f"\n"
            f"  {status_icon}\n"
            f"  [white]Algo:[/]     {algo}\n"
            f"  [white]Symbol:[/]   {symbol}\n"
            f"  [white]Venue:[/]    {venue}\n"
            f"  [white]Mode:[/]     {mode}\n"
        )

        # Show extra config if present
        for key in ("interval", "trade_usd", "leverage"):
            if key in data:
                label = key.replace("_", " ").title()
                msg += f"  [white]{label}:[/]  {data[key]}\n"

        console.print(Panel(msg, border_style="#00e5ff", padding=(1, 2)))

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@strategy.command(name="start")
def strategy_start():
    """Start the trading strategy with the current configuration."""
    try:
        client = SentinelAPI()

        with console.status("[cyan]Starting strategy...[/cyan]", spinner="dots"):
            result = client.strategy.start()

        console.print("[green]▶ Strategy started[/green]")
        data = result.get("data", result)
        if isinstance(data, dict):
            for key in ("algo", "symbol", "venue", "mode"):
                if key in data:
                    console.print(f"  [white]{key}:[/] {data[key]}")

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@strategy.command(name="stop")
def strategy_stop():
    """Stop the running strategy."""
    try:
        client = SentinelAPI()

        with console.status("[cyan]Stopping strategy...[/cyan]", spinner="dots"):
            client.strategy.stop()

        console.print("[yellow]■ Strategy stopped[/yellow]")

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@strategy.command(name="config")
@click.option("--algo", help="Algorithm: sma, bb, macd, ema_spread, rsi_ict, gain_ema")
@click.option("--symbol", help="Trading symbol (BTC, ETH, SOL)")
@click.option("--venue", help="Venue (hl, aster)")
@click.option("--interval", help="Candle interval (1m, 5m, 15m, 1h)")
@click.option("--trade-usd", type=float, help="Trade size in USD")
@click.option("--leverage", type=int, help="Leverage multiplier")
def strategy_config(algo, symbol, venue, interval, trade_usd, leverage):
    """Update strategy configuration.

    Pass only the options you want to change — others stay as they are.

    Examples:
        sentinel strategy config --algo sma --symbol BTC --venue hl
        sentinel strategy config --leverage 5 --trade-usd 100
    """
    # Build kwargs from non-None values
    kwargs = {}
    if algo:
        kwargs["algo"] = algo
    if symbol:
        kwargs["symbol"] = symbol
    if venue:
        kwargs["venue"] = venue
    if interval:
        kwargs["interval"] = interval
    if trade_usd is not None:
        kwargs["trade_usd"] = trade_usd
    if leverage is not None:
        kwargs["leverage"] = leverage

    if not kwargs:
        console.print("[yellow]No options given.[/yellow] Use --algo, --symbol, --venue, etc.")
        raise click.Abort()

    try:
        client = SentinelAPI()

        with console.status("[cyan]Updating config...[/cyan]", spinner="dots"):
            result = client.strategy.config(**kwargs)

        data = result.get("data", result)
        msg = "[bold #00e5ff]Strategy Config Updated[/]\n\n"
        if isinstance(data, dict):
            for key, val in data.items():
                label = key.replace("_", " ").title()
                msg += f"  [white]{label}:[/] {val}\n"
        else:
            msg += f"  {data}\n"

        console.print(Panel(msg, border_style="#00e5ff", padding=(1, 2)))

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@strategy.command(name="set-algo")
@click.argument("name")
@click.option("--param", multiple=True, help="Algo param as key=value (repeatable)")
def strategy_set_algo(name, param):
    """Switch the active algorithm.

    Examples:
        sentinel strategy set-algo bb
        sentinel strategy set-algo rsi_ict --param oversold=30 --param overbought=70
    """
    # Parse --param pairs
    params = {}
    for p in param:
        if "=" not in p:
            console.print(f"[red]Invalid param:[/red] {p} (expected key=value)")
            raise click.Abort()
        key, value = p.split("=", 1)
        try:
            params[key] = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            params[key] = value

    try:
        client = SentinelAPI()

        with console.status(f"[cyan]Switching to {name}...[/cyan]", spinner="dots"):
            result = client.strategy.set_algo(name, params=params if params else None)

        console.print(f"[green]✓ Algorithm switched to [bold]{name}[/bold][/green]")
        data = result.get("data", result)
        if isinstance(data, dict) and "params" in data:
            console.print(f"  [dim]Params: {json.dumps(data['params'])}[/dim]")

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@strategy.command(name="algos")
def strategy_algos():
    """List all available trading algorithms."""
    try:
        client = SentinelAPI()

        with console.status("[cyan]Fetching algorithms...[/cyan]", spinner="dots"):
            result = client.strategy.list_algos()

        data = result.get("data", result)

        if isinstance(data, dict) and "algos" in data:
            algos = data["algos"]
        elif isinstance(data, list):
            algos = data
        else:
            algos = [data]

        table = Table(
            title=f"Available Algorithms ({len(algos)})",
            show_header=True,
            header_style="bold #00e5ff",
        )
        table.add_column("Name", style="cyan", min_width=12)
        table.add_column("Description", style="white")
        table.add_column("Default Params", style="dim")

        for algo in algos:
            if isinstance(algo, dict):
                name = algo.get("name", algo.get("key", "?"))
                desc = algo.get("description", algo.get("desc", ""))
                params = algo.get("default_params", algo.get("params", {}))
                params_str = ", ".join(f"{k}={v}" for k, v in params.items()) if isinstance(params, dict) else str(params)
                table.add_row(name, desc, params_str)
            else:
                table.add_row(str(algo), "", "")

        console.print()
        console.print(table)
        console.print()

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


@strategy.command(name="algo-info")
@click.argument("name")
def strategy_algo_info(name):
    """Get detailed info about a specific algorithm.

    Example:
        sentinel strategy algo-info rsi_ict
    """
    try:
        client = SentinelAPI()

        with console.status(f"[cyan]Fetching {name}...[/cyan]", spinner="dots"):
            result = client.strategy.algo_info(name)

        data = result.get("data", result)
        syntax = Syntax(
            json.dumps(data, indent=2),
            "json",
            theme="monokai",
            line_numbers=False,
        )
        console.print()
        console.print(f"[bold #00e5ff]{name}[/]")
        console.print(syntax)
        console.print()

    except AuthenticationError:
        console.print("[red]Not authenticated.[/red] Run [cyan]sentinel[/cyan] to set up.")
        raise click.Abort()
    except SentinelAPIError as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise click.Abort()


if __name__ == "__main__":
    cli()
