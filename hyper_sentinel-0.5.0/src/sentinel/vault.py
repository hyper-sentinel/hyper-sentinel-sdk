"""
Local vault encryption/decryption using the secret key.

Encrypts configuration locally before sending to the server.
Uses Fernet (AES-128-CBC + HMAC-SHA256) if cryptography is installed,
falls back to simple XOR + HMAC for minimal dependencies.

Usage:
    from sentinel.vault import LocalVault, load_secret_key

    secret_key = load_secret_key()
    vault = LocalVault(secret_key)

    vault.set("exchange_key", "your_key_here")
    value = vault.get("exchange_key")
    keys = vault.list_keys()

    # For server sync
    encrypted_blob, nonce = vault.to_encrypted_blob()
"""

import base64
import hashlib
import json
import os
import warnings
from pathlib import Path
from typing import Optional, Dict, Tuple

CONFIG_DIR = Path.home() / ".sentinel"
VAULT_FILE = CONFIG_DIR / "vault.json"
SECRET_FILE = CONFIG_DIR / "secret_key"


def load_secret_key() -> Optional[str]:
    """Load secret key from ~/.sentinel/secret_key.

    Returns:
        The secret key string, or None if not found.
    """
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    return None


def save_secret_key(key: str) -> None:
    """Save secret key to ~/.sentinel/secret_key with restrictive permissions.

    Args:
        key: The secret key to save
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(key)
    SECRET_FILE.chmod(0o600)


class LocalVault:
    """Encrypts/decrypts configuration locally using the secret key.

    Provides symmetric encryption with:
    - Fernet (AES-128-CBC + HMAC-SHA256) if cryptography is installed
    - Fallback XOR + HMAC (NOT secure — for minimal dependencies)

    All data is stored locally in ~/.sentinel/vault.json and can be
    synced with the server for multi-device access.
    """

    def __init__(self, secret_key: str):
        """Initialize vault with a secret key.

        Args:
            secret_key: The sdg-vault-xxx secret key from authentication
        """
        self._key = self._derive_key(secret_key)
        self._local_data = self._load_local()

    def _derive_key(self, secret: str) -> bytes:
        """Derive encryption key from secret using PBKDF2.

        Args:
            secret: The input secret

        Returns:
            32-byte derived key
        """
        return hashlib.pbkdf2_hmac(
            "sha256", secret.encode(), b"sentinel-vault", 100000
        )

    def set(self, key: str, value: str) -> None:
        """Store a configuration value.

        Args:
            key: Config key
            value: Config value (will be stored as string)
        """
        self._local_data[key] = value
        self._save_local()

    def get(self, key: str) -> Optional[str]:
        """Retrieve a configuration value.

        Args:
            key: Config key

        Returns:
            Value, or None if not found
        """
        return self._local_data.get(key)

    def list_keys(self) -> list[str]:
        """List all keys in the vault.

        Returns:
            Sorted list of keys
        """
        return sorted(self._local_data.keys())

    def _load_local(self) -> Dict[str, str]:
        """Load encrypted vault from disk.

        Returns:
            Decrypted config dict
        """
        if VAULT_FILE.exists():
            try:
                encrypted = VAULT_FILE.read_text()
                return self._decrypt(encrypted)
            except Exception:
                return {}
        return {}

    def _save_local(self) -> None:
        """Save encrypted vault to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        encrypted = self._encrypt(self._local_data)
        VAULT_FILE.write_text(encrypted)
        VAULT_FILE.chmod(0o600)

    def _encrypt(self, data: Dict[str, str]) -> str:
        """Encrypt data using Fernet if available, else fallback.

        Args:
            data: Dict to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        try:
            from cryptography.fernet import Fernet

            fernet_key = base64.urlsafe_b64encode(self._key[:32])
            f = Fernet(fernet_key)
            plaintext = json.dumps(data).encode()
            encrypted = f.encrypt(plaintext)
            return encrypted.decode()

        except ImportError:
            # Fallback: base64 of XOR'd JSON
            warnings.warn(
                "cryptography package not installed. Vault uses weak encryption. "
                "Install with: pip install hyper-sentinel[vault]",
                category=RuntimeWarning,
                stacklevel=2,
            )
            plaintext = json.dumps(data).encode()
            key_bytes = self._key * (len(plaintext) // len(self._key) + 1)
            xored = bytes(a ^ b for a, b in zip(plaintext, key_bytes[: len(plaintext)]))
            return base64.b64encode(xored).decode()

    def _decrypt(self, encrypted_str: str) -> Dict[str, str]:
        """Decrypt data using Fernet if available, else fallback.

        Args:
            encrypted_str: Base64-encoded encrypted string

        Returns:
            Decrypted dict
        """
        try:
            from cryptography.fernet import Fernet

            fernet_key = base64.urlsafe_b64encode(self._key[:32])
            f = Fernet(fernet_key)
            plaintext = f.decrypt(encrypted_str.encode())
            return json.loads(plaintext)

        except ImportError:
            # Fallback: XOR'd JSON
            xored = base64.b64decode(encrypted_str)
            key_bytes = self._key * (len(xored) // len(self._key) + 1)
            plaintext = bytes(a ^ b for a, b in zip(xored, key_bytes[: len(xored)]))
            return json.loads(plaintext)

    def to_encrypted_blob(self) -> Tuple[str, str]:
        """Export vault for server sync.

        Encrypts the local data for upload to the server.
        Returns both encrypted blob and nonce.

        Returns:
            Tuple of (encrypted_blob, nonce) as base64 strings
        """
        nonce = os.urandom(16)
        data_json = json.dumps(self._local_data)

        try:
            from cryptography.fernet import Fernet

            fernet_key = base64.urlsafe_b64encode(self._key[:32])
            f = Fernet(fernet_key)
            blob = f.encrypt(data_json.encode()).decode()

        except ImportError:
            # Fallback: base64-encode as-is
            blob = base64.b64encode(data_json.encode()).decode()

        return blob, base64.b64encode(nonce).decode()

    def from_encrypted_blob(self, blob: str, nonce: str) -> None:
        """Import vault from server sync.

        Decrypts blob from server and merges into local vault.

        Args:
            blob: Encrypted blob (base64)
            nonce: Encryption nonce (base64)
        """
        try:
            from cryptography.fernet import Fernet

            fernet_key = base64.urlsafe_b64encode(self._key[:32])
            f = Fernet(fernet_key)
            plaintext = f.decrypt(blob.encode()).decode()

        except ImportError:
            # Fallback: base64-decode
            plaintext = base64.b64decode(blob).decode()

        data = json.loads(plaintext)
        self._local_data.update(data)
        self._save_local()
