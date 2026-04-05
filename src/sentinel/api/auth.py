"""
Sentinel API — Auth helpers.

Handles first-launch API key generation:
1. User provides their AI key (Claude, GPT, Gemini, Grok)
2. SDK calls POST /auth/ai-key
3. Server generates sk-sentinel-xxx
4. SDK saves it to ~/.sentinel/api_key
5. All future calls use that key automatically
"""

from typing import Optional, Tuple

from sentinel.api._http import HTTPClient, save_api_key, save_ai_key, CONFIG_DIR

# Use a separate unauthenticated client for auth flows
import httpx

DEFAULT_BASE_URL = "https://api.hyper-sentinel.com"


def authenticate_with_ai_key(
    ai_key: str,
    base_url: str = DEFAULT_BASE_URL,
) -> Tuple[str, dict]:
    """Exchange an AI provider key for a Sentinel API key.

    Args:
        ai_key: An API key from Claude, GPT, Gemini, or Grok
        base_url: API base URL

    Returns:
        Tuple of (sentinel_api_key, response_dict)
    """
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        response = client.post(
            "/auth/ai-key",
            json={"ai_key": ai_key},
            headers={"Content-Type": "application/json"},
        )

        if response.status_code not in (200, 201):
            error = response.json().get("error", "Authentication failed")
            raise Exception(f"Auth failed: {error}")

        data = response.json()
        sentinel_key = data["api_key"]

        # Save API key for future use
        save_api_key(sentinel_key)

        # Save AI provider key for chat requests
        save_ai_key(ai_key)

        # Save secret key if returned (new user)
        if "secret_key" in data:
            secret_key = data["secret_key"]
            secret_file = CONFIG_DIR / "secret_key"
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            secret_file.write_text(secret_key)
            secret_file.chmod(0o600)

        return sentinel_key, data


def register_with_email(
    email: str,
    password: str,
    name: str = "",
    base_url: str = DEFAULT_BASE_URL,
) -> Tuple[str, dict]:
    """Register with email/password, then generate an API key.

    Args:
        email: User's email
        password: User's password
        name: Display name (optional)

    Returns:
        Tuple of (sentinel_api_key, response_dict)
    """
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        # Step 1: Register
        reg_response = client.post(
            "/auth/register",
            json={"email": email, "password": password, "name": name},
            headers={"Content-Type": "application/json"},
        )

        if reg_response.status_code == 409:
            # Already registered — try login
            reg_response = client.post(
                "/auth/login",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"},
            )

        if reg_response.status_code not in (200, 201):
            error = reg_response.json().get("error", "Registration failed")
            raise Exception(f"Registration failed: {error}")

        reg_data = reg_response.json()
        jwt_token = reg_data.get("token")

        if not jwt_token:
            raise Exception("No token received from registration")

        # Step 2: Generate API key
        key_response = client.post(
            "/auth/keys",
            json={"name": "default"},
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json",
            },
        )

        if key_response.status_code not in (200, 201):
            error = key_response.json().get("error", "Key generation failed")
            raise Exception(f"Key generation failed: {error}")

        key_data = key_response.json()
        sentinel_key = key_data["api_key"]

        # Save for future use
        save_api_key(sentinel_key)

        return sentinel_key, {**reg_data, **key_data}
