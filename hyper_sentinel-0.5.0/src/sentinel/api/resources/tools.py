"""
Sentinel API — Tools Resource (Generic).

    tools = client.tools.list()
    info = client.tools.info("get_crypto_price")
    result = client.tools.call("get_crypto_price", coin_id="bitcoin")
"""

from typing import Any, Dict, Optional


class ToolsResource:
    """Generic tool access — list, inspect, and call any of the 52 tools."""

    def __init__(self, http):
        self._http = http

    def list(self) -> dict:
        """List all available tools with names and descriptions."""
        return self._http.get("/api/v1/tools")

    def info(self, tool_name: str) -> dict:
        """Get detailed info about a specific tool.

        Args:
            tool_name: Tool name (e.g. "get_crypto_price", "hl_place_order")
        """
        return self._http.get(f"/api/v1/tools/{tool_name}")

    def call(self, tool_name: str, **kwargs) -> dict:
        """Call any tool by name with keyword arguments.

        This is the escape hatch — if a tool isn't wrapped by a
        resource method, you can call it directly here.

        Args:
            tool_name: Tool name (e.g. "get_crypto_price")
            **kwargs: Tool parameters as keyword arguments

        Example:
            result = client.tools.call("get_crypto_price", coin_id="bitcoin")
        """
        return self._http.post(f"/api/v1/tools/{tool_name}", kwargs)
