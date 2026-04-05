"""
Sentinel API — Core HTTP Client.

Thin wrapper around httpx that handles:
- Authentication (sk-sentinel-xxx API keys)
- Auto-retry with exponential backoff
- Error mapping (HTTP status → typed exceptions)
- Response parsing
- Streaming (SSE for LLM responses)

Modeled after OpenAI's _client.py.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import httpx

from sentinel.api.errors import (
    AuthenticationError,
    InsufficientBalanceError,
    RateLimitError,
    SentinelAPIError,
    ServerError,
    ToolNotFoundError,
)

# ── Constants ─────────────────────────────────────────────────
DEFAULT_BASE_URL = "https://api.hyper-sentinel.com"
FALLBACK_BASE_URL = "https://sentinel-api-281199879392.us-central1.run.app"
CONFIG_DIR = Path.home() / ".sentinel"
CONFIG_FILE = CONFIG_DIR / "api_key"
AI_KEY_FILE = CONFIG_DIR / "ai_key"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


# ── Config helpers ────────────────────────────────────────────

def load_api_key() -> Optional[str]:
    """Load saved API key from ~/.sentinel/api_key."""
    if CONFIG_FILE.exists():
        key = CONFIG_FILE.read_text().strip()
        if key:
            return key
    return None


def save_api_key(key: str) -> None:
    """Save API key to ~/.sentinel/api_key."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(key)
    CONFIG_FILE.chmod(0o600)  # Owner read/write only


def load_ai_key() -> Optional[str]:
    """Load saved AI provider key from ~/.sentinel/ai_key or ~/.sentinel/config.

    Checks two locations because different setup paths save the key differently:
    - ~/.sentinel/ai_key (plaintext) — saved by save_ai_key()
    - ~/.sentinel/config (JSON with "ai_key" field) — saved by chat.py first-run setup
    """
    # Check dedicated ai_key file first
    if AI_KEY_FILE.exists():
        key = AI_KEY_FILE.read_text().strip()
        if key:
            return key
    # Fallback: check config JSON (chat.py stores ai_key here)
    config_file = CONFIG_DIR / "config"
    if config_file.exists():
        try:
            import json as _json
            config = _json.loads(config_file.read_text())
            key = config.get("ai_key", "").strip()
            if key:
                return key
        except (ValueError, OSError):
            pass
    return None


def save_ai_key(key: str) -> None:
    """Save AI provider key to ~/.sentinel/ai_key."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AI_KEY_FILE.write_text(key)
    AI_KEY_FILE.chmod(0o600)


# ── HTTP Client ───────────────────────────────────────────────

class HTTPClient:
    """Low-level HTTP client with auth, retry, and error handling."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "sentinel-sdk/1.0.0",
            },
        )

    def get(self, path: str, params: dict = None) -> dict:
        """GET request with auto-retry."""
        return self._request("GET", path, params=params)

    def post(self, path: str, data: dict = None) -> dict:
        """POST request with auto-retry."""
        return self._request("POST", path, json_data=data)

    def put(self, path: str, data: dict = None) -> dict:
        """PUT request with auto-retry."""
        return self._request("PUT", path, json_data=data)

    def delete(self, path: str) -> dict:
        """DELETE request with auto-retry."""
        return self._request("DELETE", path)

    def post_stream(self, path: str, data: dict = None) -> Generator[dict, None, None]:
        """POST request that yields SSE events for streaming responses."""
        url = path
        with self._client.stream(
            "POST", url, json=data, params={"stream": "true"}
        ) as response:
            if response.status_code != 200:
                body = json.loads(response.read())
                self._raise_for_status(response.status_code, body)

            for line in response.iter_lines():
                if line.startswith("data: "):
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        return
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        continue

    def _request(
        self,
        method: str,
        path: str,
        params: dict = None,
        json_data: dict = None,
    ) -> dict:
        """Execute HTTP request with retry and error handling."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self._client.request(
                    method, path, params=params, json=json_data
                )

                # Success
                if 200 <= response.status_code < 300:
                    if response.headers.get("content-type", "").startswith("application/json"):
                        return response.json()
                    return {"text": response.text}

                # Parse error body
                try:
                    body = response.json()
                except Exception:
                    body = {"error": response.text}

                # Retry on 429 (rate limit) and 5xx (server errors)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(retry_after)
                    last_error = RateLimitError(
                        body.get("error", "Rate limit exceeded"),
                        response=body,
                    )
                    continue

                if response.status_code >= 500:
                    time.sleep(2 ** attempt)
                    last_error = ServerError(
                        body.get("error", "Server error"),
                        response=body,
                    )
                    continue

                # Non-retryable errors
                self._raise_for_status(response.status_code, body)

            except httpx.TimeoutException:
                last_error = SentinelAPIError("Request timed out", status_code=408)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise last_error

            except httpx.ConnectError:
                last_error = SentinelAPIError(
                    f"Cannot connect to {self.base_url}. Check your internet connection.",
                    status_code=0,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise last_error

        # All retries exhausted
        if last_error:
            raise last_error
        raise SentinelAPIError("Request failed after retries")

    def _raise_for_status(self, status_code: int, body: dict) -> None:
        """Map HTTP status codes to typed exceptions."""
        msg = body.get("error") or body.get("detail") or body.get("title") or str(body)

        if status_code == 401:
            raise AuthenticationError(msg, response=body)
        elif status_code == 402:
            raise InsufficientBalanceError(msg, response=body)
        elif status_code == 404:
            raise ToolNotFoundError(msg, response=body)
        elif status_code == 429:
            raise RateLimitError(msg, response=body)
        elif status_code >= 500:
            raise ServerError(msg, response=body)
        else:
            raise SentinelAPIError(msg, status_code=status_code, response=body)

    def close(self):
        """Close the underlying httpx client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
