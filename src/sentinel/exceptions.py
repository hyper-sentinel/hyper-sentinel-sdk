"""
Sentinel SDK — Exception classes.
"""


class SentinelError(Exception):
    """Base exception for all Sentinel SDK errors."""

    def __init__(self, message: str, status_code: int = 0, detail: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)


class AuthError(SentinelError):
    """401 — Invalid or missing API key."""
    pass


class ForbiddenError(SentinelError):
    """403 — Access denied. Rare since all tools are accessible on all tiers."""
    pass


class RateLimitError(SentinelError):
    """429 — Per-minute request rate limit exceeded."""

    def __init__(self, message: str, detail: dict | None = None):
        d = detail or {}
        self.tier = d.get("tier", "unknown")
        self.limit_per_min = d.get("limit_per_min", 0)
        self.remaining = d.get("remaining", 0)
        self.retry_after = d.get("retry_after_seconds", 60)
        self.upgrade_url = d.get("upgrade_url", "")
        self.upgrade_to = d.get("upgrade_to", "")
        self.upgrade_price = d.get("upgrade_price", "")
        super().__init__(message, status_code=429, detail=detail)


class QuotaExceededError(SentinelError):
    """402 — Free-tier weekly prompt quota exceeded.

    Free tier = 10 prompts per rolling 7-day window.  Add a payment method at
    ``checkout_url`` for unlimited access (flat 20% platform fee, pay-as-you-go).

    Attributes:
        prompts_used: Number of prompts used in the current window.
        prompt_limit: Maximum prompts allowed on the free tier.
        window_days: Length of the rolling window in days.
        resets_at: ISO-8601 timestamp when the oldest prompt ages out.
        checkout_url: Stripe Checkout URL to add a payment method.
    """

    def __init__(self, message: str, detail: dict | None = None):
        d = detail or {}
        self.prompts_used = d.get("prompts_used", 0)
        self.prompt_limit = d.get("prompt_limit", 10)
        self.window_days = d.get("window_days", 7)
        self.resets_at = d.get("resets_at", "")
        self.checkout_url = d.get("checkout_url", "")
        super().__init__(message, status_code=402, detail=detail)


class ToolNotFoundError(SentinelError):
    """404 — Tool name doesn't exist."""
    pass
