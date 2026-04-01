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
    """429 — Rate limit exceeded (Free: 300/min, Pro: 1K/min, Enterprise: unlimited)."""

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


class ToolNotFoundError(SentinelError):
    """404 — Tool name doesn't exist."""
    pass
