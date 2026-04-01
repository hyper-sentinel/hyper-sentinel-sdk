"""
Hyper-Sentinel v0.5.1 — Thin Python SDK for the Sentinel AI Trading API

Soli Deo Gloria — To the Glory of God alone.
Dedicated to the Glory of Jesus Christ, the Son of God.

© Sentinel Labs — https://hyper-sentinel.com

62+ AI trading tools via clean REST API. Market data, technical analysis, trading,
portfolio tracking, AI chat, vault encryption. Access via:

Usage (option 1 — convenience wrapper):
    from sentinel import Sentinel

    client = Sentinel(api_key="sk-sentinel-xxx")
    btc = client.call("get_crypto_price", coin_id="bitcoin")
    response = client.chat("analyze BTC macro outlook")

Usage (option 2 — full API):
    from sentinel import SentinelAPI

    client = SentinelAPI(api_key="sk-sentinel-xxx")
    btc = client.market.price("bitcoin")
    response = client.chat.send("analyze BTC macro outlook")
"""

from typing import Optional
from sentinel.api.client import SentinelAPI
from sentinel.api.errors import (
    SentinelAPIError,
    AuthenticationError,
)

__version__ = "0.5.1"


class Sentinel(SentinelAPI):
    """Convenience wrapper — the simplest way to use the Sentinel API.

    Provides simpler method names for common operations.
    """

    def chat(self, message: str, **kwargs) -> str:
        """Send a message to the AI and get a text response.

        Args:
            message: Your message or query
            **kwargs: Additional parameters (stream, etc.)

        Returns:
            Plain text response from the AI
        """
        response = self._chat.send(message, **kwargs)
        return response.get("text", "")

    def call(self, tool_name: str, **params) -> dict:
        """Call any tool by name.

        Args:
            tool_name: The tool name (e.g. "get_crypto_price")
            **params: Tool parameters

        Returns:
            Tool response as a dict
        """
        return self.tools.call(tool_name, **params)


__all__ = [
    "Sentinel",
    "SentinelAPI",
    "SentinelAPIError",
    "AuthenticationError",
]

# ── Post-install message ──────────────────────────────────────
# Shows once on first import when no config exists yet.
def _first_run_hint():
    from pathlib import Path
    config_file = Path.home() / ".sentinel" / "api_key"
    if not config_file.exists():
        try:
            from rich.console import Console
            from rich.panel import Panel
            c = Console(stderr=True)
            c.print()
            msg = (
                "[bold #00e5ff]S E N T I N E L   v0.5[/]\n"
                "[dim]Thin REST SDK for the Sentinel AI Trading API[/]\n"
                "\n"
                "[bold white]→ Get started: [bold #00e5ff]sentinel auth --key sk-ant-xxx[/bold #00e5ff][/bold white]"
            )
            c.print(Panel(msg, border_style="#007a8a", padding=(1, 4)))
            c.print()
        except Exception:
            print(f"\n  sentinel v{__version__} installed")
            print("  Type 'sentinel auth --key sk-ant-xxx' to get started.\n")

_first_run_hint()
