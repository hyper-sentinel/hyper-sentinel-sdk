"""
Sentinel API — Vault Resource.

Zero-trust encrypted configuration vault for storing exchange keys,
API credentials, and configuration. All data is encrypted locally with
your sdg-vault-xxx secret key — the server never sees plaintext.

    client.vault.init()                                     # First-time setup
    client.vault.get_config()                               # Fetch encrypted config
    client.vault.put_config(encrypted_blob, nonce, version) # Sync encrypted config
    client.vault.delete_config()                            # Erase config
"""

from typing import Any, Dict, Optional


class VaultResource:
    """Zero-trust encrypted configuration vault.

    Stores exchange keys, API credentials, and configuration encrypted
    with your sdg-vault-xxx secret key. Server never sees plaintext.

    Usage:
        client = SentinelAPI(api_key="sk-sentinel-xxx")

        # First time
        result = client.vault.init()

        # Store encrypted config
        from sentinel.vault import LocalVault
        vault = LocalVault(secret_key)
        vault.set("exchange_key", "your_key")
        encrypted_blob, nonce = vault.to_encrypted_blob()

        # Sync with server
        response = client.vault.put_config(encrypted_blob, nonce)
    """

    def __init__(self, http):
        self._http = http

    def init(self) -> dict:
        """Initialize the vault for the first time.

        Returns:
            {"status": "initialized", "vault_id": "..."}
        """
        return self._http.post("/api/v1/vault/init", {})

    def get_config(self) -> dict:
        """Fetch the encrypted vault configuration from the server.

        Returns:
            {"encrypted_blob": "...", "nonce": "...", "version": 1}
        """
        return self._http.get("/api/v1/vault/config")

    def put_config(self, encrypted_blob: str, nonce: str, version: int = 1) -> dict:
        """Upload encrypted vault configuration to the server.

        Args:
            encrypted_blob: Base64-encoded encrypted JSON
            nonce: Base64-encoded encryption nonce
            version: Config version (default 1)

        Returns:
            {"status": "saved", "version": 1}
        """
        data = {
            "encrypted_blob": encrypted_blob,
            "nonce": nonce,
            "version": version,
        }
        return self._http.put("/api/v1/vault/config", data)

    def delete_config(self) -> dict:
        """Delete the vault configuration from the server.

        Warning: This action cannot be undone.

        Returns:
            {"status": "deleted"}
        """
        return self._http.delete("/api/v1/vault/config")
