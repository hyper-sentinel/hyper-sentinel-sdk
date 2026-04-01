"""
Sentinel API — Keys Resource (API Key Management).

    keys = client.keys.list()
    new_key = client.keys.create(name="my-bot")
    client.keys.revoke("key_abc123")
"""


class KeysResource:
    """API key management — list, create, and revoke API keys."""

    def __init__(self, http):
        self._http = http

    def list(self) -> dict:
        """List all active API keys (prefix + name + created, never full key)."""
        return self._http.get("/api/v1/auth/keys")

    def create(self, name: str = "default") -> dict:
        """Generate a new API key.

        ⚠️ The full key is only shown ONCE in the response. Save it immediately.

        Args:
            name: Friendly name for this key (e.g. "my-bot", "trading-server")
        """
        return self._http.post("/api/v1/auth/keys", {"name": name})

    def revoke(self, key_id: str) -> dict:
        """Revoke an API key by ID (soft delete).

        Args:
            key_id: The key ID (from keys.list() response)
        """
        return self._http.delete(f"/api/v1/auth/keys/{key_id}")
