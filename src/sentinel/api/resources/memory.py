"""
Sentinel API — Memory Resource.

Per-user agent memory the assistant reads at session start and writes during use
(preferences, trading style, durable context). Distinct from the vault: this is
*content*, not secrets, stored server-side and scoped to your account.

    client.memory.get()                 # all memory → {key: value}
    client.memory.set("style", "swing") # upsert one entry
    client.memory.delete("style")       # remove one entry
"""

from typing import Dict


class MemoryResource:
    """Per-user agent memory (read at session start, written during use)."""

    def __init__(self, http):
        self._http = http

    def get(self) -> Dict[str, str]:
        """Return all memory entries for the account as a {key: value} dict."""
        resp = self._http.get("/api/v1/memory")
        if isinstance(resp, dict):
            return resp.get("memory", {})
        return {}

    def set(self, key: str, value: str) -> dict:
        """Upsert a single memory entry.

        Args:
            key: Memory key (e.g. "risk_tolerance").
            value: Value to store. Encode structured data as a JSON string if needed.
        """
        return self._http.put("/api/v1/memory", {"key": key, "value": value})

    def delete(self, key: str) -> dict:
        """Delete a single memory entry by key."""
        return self._http.delete(f"/api/v1/memory/{key}")
