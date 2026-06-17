"""
Sentinel API — Error types.

Modeled after OpenAI's error hierarchy:
    SentinelAPIError
    ├── AuthenticationError      (401)
    ├── QuotaExceededError       (402 quota_exceeded — free-tier weekly limit)
    ├── InsufficientBalanceError (402 payment_failed  — payment method issue)
    ├── RateLimitError           (429)
    ├── ToolNotFoundError        (404)
    └── ServerError              (500+)
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


class QuotaExceededError(SentinelAPIError):
    """402 quota_exceeded — Free-tier weekly prompt quota exhausted.

    Free tier = 10 prompts per rolling 7-day window.  Add a payment method
    at ``checkout_url`` for unlimited access (flat 20% platform fee).

    Attributes:
        prompts_used: Prompts consumed in the current 7-day window.
        prompt_limit: Allowed prompts on the free tier (default 10).
        window_days: Rolling window length in days.
        resets_at: ISO-8601 timestamp when quota next resets.
        checkout_url: Stripe Checkout URL to add a payment method.
    """

    def __init__(self, message: str = "Free-tier weekly prompt quota exceeded", **kwargs):
        response = kwargs.get("response", {})
        self.prompts_used = response.get("prompts_used", 0)
        self.prompt_limit = response.get("prompt_limit", 10)
        self.window_days = response.get("window_days", 7)
        self.resets_at = response.get("resets_at", "")
        self.checkout_url = response.get("checkout_url", "")
        super().__init__(message, status_code=402, **kwargs)


class InsufficientBalanceError(SentinelAPIError):
    """402 payment_failed — Payment method failed or insufficient balance."""

    def __init__(self, message: str = "Payment method failed or balance insufficient", **kwargs):
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
