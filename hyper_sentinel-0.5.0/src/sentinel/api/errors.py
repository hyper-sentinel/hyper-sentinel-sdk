"""
Sentinel API — Error types.

Modeled after OpenAI's error hierarchy:
    SentinelAPIError
    ├── AuthenticationError   (401)
    ├── RateLimitError        (429)
    ├── InsufficientBalanceError (402)
    ├── ToolNotFoundError     (404)
    └── ServerError           (500+)
"""


class SentinelAPIError(Exception):
    """Base error for all Sentinel API errors."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response or {}
        super().__init__(self.message)

    def __str__(self):
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class AuthenticationError(SentinelAPIError):
    """401 — Invalid or missing API key."""

    def __init__(self, message: str = "Invalid or missing API key", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class RateLimitError(SentinelAPIError):
    """429 — Rate limit exceeded for your tier."""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = kwargs.get("retry_after")


class InsufficientBalanceError(SentinelAPIError):
    """402 — USDC balance too low."""

    def __init__(self, message: str = "Insufficient USDC balance", **kwargs):
        super().__init__(message, status_code=402, **kwargs)


class ToolNotFoundError(SentinelAPIError):
    """404 — Requested tool does not exist."""

    def __init__(self, tool_name: str, **kwargs):
        super().__init__(f"Tool not found: {tool_name}", status_code=404, **kwargs)
        self.tool_name = tool_name


class ServerError(SentinelAPIError):
    """500+ — Server-side error."""

    def __init__(self, message: str = "Internal server error", **kwargs):
        super().__init__(message, status_code=500, **kwargs)
