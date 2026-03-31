"""
Hyper-Sentinel v0.3.16 — Quantitative AI Agent + Python SDK

  Soli Deo Gloria — To the Glory of God alone.
  Dedicated to the Glory of Jesus Christ, the Son of God.

© Sentinel Labs — https://hyper-sentinel.com

52 tools · 13 scrapers · 3 trading venues · TradFi + Crypto + Macro
Hyperliquid · Aster DEX · Polymarket · Technical Analysis · DexScreener

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

__version__ = "0.3.16"
__all__ = [
    "SentinelClient",
    "SentinelError",
    "AuthError",
    "ForbiddenError",
    "RateLimitError",
    "ToolNotFoundError",
]

# ── Post-install message ──────────────────────────────────────
# Shows once on first import when no config exists yet.
def _first_run_hint():
    from pathlib import Path
    config = Path.home() / ".sentinel" / "config"
    if not config.exists():
        try:
            from rich.console import Console
            from rich.panel import Panel
            c = Console(stderr=True)
            c.print()
            msg = (
                "[bold #00e5ff]H Y P E R  ·  S E N T I N E L[/]\n"
                f"[dim]v{__version__} · Quantitative AI Agent · Local-First[/]\n"
                "\n"
                "[bold white]→ Type [bold #00e5ff]sentinel[/bold #00e5ff] to launch[/bold white]"
            )
            c.print(Panel(msg, border_style="#007a8a", padding=(1, 4)))
            c.print()
        except Exception:
            print(f"\n  hyper-sentinel v{__version__} installed ✓")
            print("  Type 'sentinel' to launch.\n")

_first_run_hint()
