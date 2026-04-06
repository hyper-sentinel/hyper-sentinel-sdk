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
SECRET_FILE = CONFIG_DIR / "secret_key"


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
@click.version_option(version=__version__, prog_name="sentinel")
@click.pass_context
def cli(ctx):
    """Sentinel — AI trading terminal with 62+ tools."""
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
[dim]Autonomous AI Trading Terminal · 62 Tools · 3 Venues[/]
""".format(version=__version__)
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
                    SECRET_FILE.chmod(0o600)

                # Save AI provider key for ChatResource.load_ai_key()
                from sentinel.api._http import save_ai_key
                save_ai_key(ai_key)

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
[dim]Autonomous AI Trading Terminal · 62 Tools · 3 Venues[/]
""".format(version=__version__)

    console.print()
    console.print(BANNER)

    # ── Boot Sequence ─────────────────────────────────────────
    boot_steps = [
        ("🔑", "API Key", f"[green]● Authenticated[/]", f"sk-sentinel-...{api_key[-6:]}"),
        ("🌐", "Gateway", None, "api.hyper-sentinel.com"),  # None = will check live
        ("🤖", "AI Agent", "[green]● Ready[/]", "Claude · GPT · Gemini · Grok"),
    ]

    infra = Table(
        title="[bold cyan]📡 Infrastructure[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    infra.add_column("Component", style="bold white", min_width=18)
    infra.add_column("Status", min_width=20)
    infra.add_column("Details", style="dim")

    # Auth
    infra.add_row("🔑 API Key", "[green]● Authenticated[/]", f"sk-sentinel-...{api_key[-4:]}")

    # Gateway health check
    gateway_status = "[yellow]● Checking...[/]"
    gateway_detail = "api.hyper-sentinel.com"
    try:
        result = client.health()
        gateway_status = "[green]● Connected[/]"
        tool_count = result.get("tools", result.get("tool_count", "62"))
        gateway_detail = f"api.hyper-sentinel.com · {tool_count} tools"
    except Exception:
        try:
            result = client.ping()
            gateway_status = "[green]● Connected[/]"
        except Exception:
            gateway_status = "[yellow]● Offline[/]"
            gateway_detail = "api.hyper-sentinel.com · will retry on query"
    infra.add_row("🌐 Gateway", gateway_status, gateway_detail)

    # AI Agent
    infra.add_row("🤖 AI Agent", "[green]● Ready[/]", "Claude · GPT · Gemini · Grok")

    console.print(infra)

    # ── Data Sources ──────────────────────────────────────────
    ds = Table(
        title="[bold cyan]📊 Venues & Data[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    ds.add_column("Source", style="bold white", min_width=18)
    ds.add_column("Status", min_width=20)
    ds.add_column("Details", style="dim")

    ds.add_row("⚡ Hyperliquid", "[green]● Available[/]", "perp futures · orders · positions")
    ds.add_row("🌟 Aster DEX", "[green]● Available[/]", "futures · orderbook · leverage")
    ds.add_row("🎲 Polymarket", "[green]● Available[/]", "prediction markets · positions")
    ds.add_row("📈 CoinGecko", "[green]● Always on[/]", "10,000+ crypto prices · search")
    ds.add_row("🏛️  FRED", "[green]● Always on[/]", "GDP, CPI, rates, VIX, yield curve")
    ds.add_row("📰 Y2 Intel", "[green]● Available[/]", "news sentiment · AI recaps · reports")
    ds.add_row("🔮 Elfa AI", "[green]● Available[/]", "trending tokens · social mentions")
    ds.add_row("📱 Telegram", "[green]● Available[/]", "channel monitoring · search · send")
    ds.add_row("💬 Discord", "[green]● Available[/]", "server monitoring · search · send")

    console.print(ds)

    # ── Commands ──────────────────────────────────────────────
    cmds = Table(
        title="[bold cyan]⌨️  Commands[/]", title_justify="left",
        show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan",
        padding=(0, 2), expand=False,
    )
    cmds.add_column("Command", style="bold cyan", min_width=18)
    cmds.add_column("Description", style="dim")

    cmds.add_row("/status", "Connection health + account info")
    cmds.add_row("/tools", "List all 62+ available tools")
    cmds.add_row("/quit", "Exit terminal")
    cmds.add_row("[bold]<anything else>[/]", "[bold white]Chat with the AI agent — it has all the tools[/]")

    console.print(cmds)

    console.print(f"  [dim]Type naturally. The agent handles the rest.[/]")
    console.print(f"  [dim italic]Soli Deo Gloria[/]")
    console.print()

    # ── REPL loop ─────────────────────────────────────────────
    while True:
        try:
            user_input = console.input("[bold #00e5ff]  ⚡ You →[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue

        # Slash commands
        if user_input.lower() in ("/quit", "/exit", "/q", "quit", "exit"):
            console.print("[dim]Goodbye.[/dim]")
            break
        elif user_input.lower() in ("/status", "status"):
            try:
                result = client.ping()
                console.print(Panel(
                    json.dumps(result, indent=2),
                    border_style="#00e5ff",
                    title="[bold cyan]📡 Status[/]"
                ))
            except Exception as e:
                console.print(f"[red]  ✗ Error:[/red] {e}")
            continue
        elif user_input.lower() in ("/tools", "tools"):
            try:
                result = client.tools.list()
                tools_list = result.get("tools", [])
                table = Table(
                    title=f"[bold cyan]🛠️  Available Tools ({len(tools_list)})[/]",
                    title_justify="left",
                    show_header=True,
                    header_style="bold #00e5ff",
                    box=box.SIMPLE_HEAVY,
                    border_style="cyan",
                )
                table.add_column("#", style="dim", width=4)
                table.add_column("Tool", style="cyan")
                table.add_column("Description", style="white")
                for i, t in enumerate(tools_list, 1):
                    desc = t.get("description", "")[:60]
                    table.add_row(str(i), t.get("name", ""), desc)
                console.print(table)
            except Exception as e:
                console.print(f"[red]  ✗ Error:[/red] {e}")
            continue
        elif user_input.lower() in ("/help", "help"):
            console.print()
            console.print("  [bold cyan]/status[/]   — Connection health + account")
            console.print("  [bold cyan]/tools[/]    — List all 62+ tools")
            console.print("  [bold cyan]/quit[/]     — Exit")
            console.print("  [dim]Or just type any question — the AI handles it.[/dim]")
            console.print()
            continue
        elif user_input.lower() == "clear":
            console.clear()
            console.print(BANNER)
            continue

        # Send to AI
        try:
            console.print()
            with console.status("[bold #8b5cf6]  🛡️  Sentinel is thinking...[/]", spinner="dots"):
                from sentinel import Sentinel as S
                s = S(api_key=api_key)
                response = s.chat(user_input)
            console.print(f"  [bold #8b5cf6]🛡️  Sentinel[/]")
            console.print()
            # Format response with left padding
            for line in str(response).split("\n"):
                console.print(f"  {line}")
            console.print()
        except SentinelAPIError as e:
            console.print(f"  [red]✗ API Error:[/red] {e}")
            console.print()
        except Exception as e:
            console.print(f"  [red]✗ Error:[/red] {e}")
            console.print()


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
    SECRET_FILE.chmod(0o600)


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


if __name__ == "__main__":
    cli()
