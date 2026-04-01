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


@click.group()
@click.version_option()
def cli():
    """Sentinel CLI — REST API for 62+ AI trading tools."""
    pass


@cli.command()
@click.option("--key", required=True, help="Your AI provider key (sk-ant-*, sk-*, AIza*, xai-*)")
@click.option("--provider", default=None, help="AI provider (anthropic, openai, google, xai) — auto-detected if not given")
def auth(key: str, provider: Optional[str]):
    """Authenticate and generate your Sentinel API key.

    Exchanges your AI provider key (Claude, OpenAI, Google, Grok) for a
    Sentinel API key that stays valid indefinitely.

    Example:
        sentinel auth --key sk-ant-xxxxxxxxxxxxx
    """
    # Auto-detect provider if not provided
    if not provider:
        provider = detect_provider(key)

    if provider == "unknown":
        console.print("[red]Error:[/red] Could not auto-detect provider from key format.")
        console.print("Use --provider to specify: anthropic, openai, google, or xai")
        raise click.Abort()

    try:
        with console.status("[cyan]Exchanging key...[/cyan]", spinner="dots"):
            api_key, response = authenticate_with_ai_key(key)

        # Save secret key if returned (new user)
        if response.get("secret_key"):
            save_secret_key(response["secret_key"])
            secret_notice = "\n[cyan]Secret key saved to ~/.sentinel/secret_key[/cyan]"
        else:
            secret_notice = ""

        # Display success
        msg = (
            f"[bold #00e5ff]Authentication Successful[/]\n"
            f"\n"
            f"[white]Provider:[/white] {provider}\n"
            f"[white]API Key:[/white] {api_key[:20]}...\n"
            f"\n"
            f"[dim]Saved to ~/.sentinel/api_key[/dim]{secret_notice}"
        )
        console.print(Panel(msg, border_style="#00e5ff", padding=(1, 2)))
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
        console.print("[red]Not authenticated.[/red] Run: sentinel auth --key sk-ant-xxx")
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
        console.print("[red]Not authenticated.[/red] Run: sentinel auth --key sk-ant-xxx")
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
        console.print("[red]Not authenticated.[/red] Run: sentinel auth --key sk-ant-xxx")
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
        console.print("[red]Not authenticated.[/red] Run: sentinel auth --key sk-ant-xxx")
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
