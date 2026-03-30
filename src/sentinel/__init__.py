"""
Hyper-Sentinel v3.0.0 — AI Agent + Python SDK for Sentinel.

© Sentinel Labs — https://hyper-sentinel.com

Full access on every tier — upgrade for lower fees.

Usage:
    from sentinel import SentinelClient

    client = SentinelClient(api_key="sk-sent-xxx")
    btc = client.get_crypto_price("bitcoin")
"""

from sentinel.client import SentinelClient
from sentinel.exceptions import (
    SentinelError,
    AuthError,
    ForbiddenError,
    RateLimitError,
    ToolNotFoundError,
)

__version__ = "0.3.9"
__all__ = [
    "SentinelClient",
    "SentinelError",
    "AuthError",
    "ForbiddenError",
    "RateLimitError",
    "ToolNotFoundError",
]

# ── First-run hint ────────────────────────────────────────────
# Show setup instructions on first import if no config exists.
def _first_run_hint():
    from pathlib import Path
    config = Path.home() / ".sentinel" / "config"
    if not config.exists():
        try:
            from rich.console import Console
            c = Console(stderr=True)
            c.print()
            c.print("  [bold #00e5ff]hyper-sentinel 0.3.9[/] installed ✓")
            c.print("  [dim]Run [bold]sentinel-chat[/dim][bold] to launch the AI agent with 80+ tools.[/]")
            c.print("  [dim]Or: [bold]sentinel-setup[/bold] · [bold]sentinel status[/bold] · [bold]sentinel test[/bold][/]")
            c.print()
        except Exception:
            print("\n  hyper-sentinel installed ✓")
            print("  Run 'sentinel-setup' to configure your AI key.\n")

_first_run_hint()
