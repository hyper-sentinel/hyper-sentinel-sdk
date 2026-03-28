"""Tests for SentinelClient v2.0 — validates the SDK revamp."""

import sentinel
from sentinel import SentinelClient
from sentinel.exceptions import (
    SentinelError,
    AuthError,
    ForbiddenError,
    RateLimitError,
    ToolNotFoundError,
)


# ── Version ──────────────────────────────────────────────────

def test_version():
    assert sentinel.__version__ == "2.0.0"


# ── Client instantiation ────────────────────────────────────

def test_default_client():
    c = SentinelClient()
    assert "sentinel-api" in c.base_url
    assert c.api_key == ""
    assert c.token == ""
    assert c.tier == ""


def test_client_with_key():
    c = SentinelClient(api_key="sk-sentinel-test123")
    assert c.api_key == "sk-sentinel-test123"
    headers = c._headers()
    assert headers["X-API-Key"] == "sk-sentinel-test123"


def test_client_with_token():
    c = SentinelClient(token="jwt-test-token")
    headers = c._headers()
    assert headers["Authorization"] == "Bearer jwt-test-token"


def test_client_custom_base_url():
    c = SentinelClient(base_url="http://localhost:8080/")
    assert c.base_url == "http://localhost:8080"  # trailing slash stripped


def test_client_repr():
    c = SentinelClient(api_key="sk-sentinel-abcdef1234567890xyz")
    r = repr(c)
    assert "sk-sentinel-abcd" in r  # shows first 16 chars truncated


def test_context_manager():
    with SentinelClient() as c:
        assert isinstance(c, SentinelClient)


# ── Docstrings reflect v2.0 pricing ─────────────────────────

def test_module_docstring_no_stale_pricing():
    import sentinel.client as mod
    doc = mod.__doc__
    assert "$50" not in doc
    assert "all tiers" in doc.lower()
    assert "upgrade" in doc.lower()


def test_class_docstring_no_feature_gating():
    doc = SentinelClient.__doc__
    assert "paid tier" not in doc.lower()
    assert "$50" not in doc
    assert "every tier" in doc.lower() or "all tiers" in doc.lower()


def test_chat_docstring_tier_markup():
    doc = SentinelClient.chat.__doc__
    assert "$0.17" not in doc
    assert "40%" in doc
    assert "20%" in doc
    assert "10%" in doc


# ── Billing methods exist and have correct signatures ────────

def test_upgrade_method_exists():
    c = SentinelClient()
    assert hasattr(c, "upgrade")
    assert callable(c.upgrade)


def test_checkout_deprecated_alias():
    """checkout() should exist as a deprecated alias for upgrade()."""
    c = SentinelClient()
    assert hasattr(c, "checkout")
    assert "Deprecated" in SentinelClient.checkout.__doc__


def test_upgrade_enterprise_exists():
    c = SentinelClient()
    assert hasattr(c, "upgrade_enterprise")


def test_billing_usage_exists():
    c = SentinelClient()
    assert hasattr(c, "billing_usage")
    assert callable(c.billing_usage)


def test_billing_history_exists():
    c = SentinelClient()
    assert hasattr(c, "billing_history")
    assert callable(c.billing_history)


def test_billing_status_exists():
    c = SentinelClient()
    assert hasattr(c, "billing_status")


# ── Exception classes ────────────────────────────────────────

def test_forbidden_error_docstring():
    doc = ForbiddenError.__doc__
    assert "Rare" in doc or "rare" in doc


def test_rate_limit_error_fields():
    detail = {
        "tier": "free",
        "limit_per_min": 300,
        "remaining": 0,
        "retry_after_seconds": 30,
    }
    e = RateLimitError("rate limited", detail=detail)
    assert e.tier == "free"
    assert e.limit_per_min == 300
    assert e.remaining == 0
    assert e.retry_after == 30
    assert e.status_code == 429


def test_rate_limit_error_defaults():
    e = RateLimitError("rate limited")
    assert e.tier == "unknown"
    assert e.limit_per_min == 0
    assert e.remaining == 0
    assert e.retry_after == 60


def test_sentinel_error_base():
    e = SentinelError("test", status_code=500, detail={"foo": "bar"})
    assert e.message == "test"
    assert e.status_code == 500
    assert e.detail == {"foo": "bar"}


def test_auth_error_inherits():
    assert issubclass(AuthError, SentinelError)


def test_tool_not_found_inherits():
    assert issubclass(ToolNotFoundError, SentinelError)


# ── No stale references in source ───────────────────────────

def test_no_stale_references_in_client():
    import inspect
    source = inspect.getsource(SentinelClient)
    stale = ["$50/mo", "calls_today", "limit_day", "requires 'trade' scope",
             "requires paid", "token limit", "30% flat", "$0.17"]
    for term in stale:
        assert term not in source, f"Stale reference found: {term!r}"


def test_no_old_billing_routes():
    import inspect
    source = inspect.getsource(SentinelClient)
    assert '"/billing/checkout' not in source
    assert '"/billing/status"' not in source
    assert '"/admin/stats"' not in source


# ── All typed tool methods exist ─────────────────────────────

EXPECTED_TOOLS = [
    "get_crypto_price", "get_crypto_top_n", "search_crypto",
    "get_fred_series", "search_fred", "get_economic_dashboard",
    "get_news_sentiment", "get_news_recap", "get_intelligence_reports",
    "get_trending_tokens", "get_top_mentions", "search_mentions",
    "search_x",
    "get_hl_config", "get_hl_orderbook", "get_hl_account_info",
    "get_hl_positions", "place_hl_order", "cancel_hl_order", "close_hl_position",
    "aster_ping", "aster_ticker", "aster_orderbook", "aster_place_order",
    "aster_balance", "aster_positions",
    "get_polymarket_markets", "search_polymarket", "buy_polymarket",
    "get_polymarket_positions",
    "dex_buy_sol", "dex_buy_eth", "dex_sell_sol", "dex_sell_eth",
    "generate_wallet", "import_wallet", "list_wallets", "get_wallet_balance",
    "get_strategy", "set_strategy", "list_algos", "start_strategy", "stop_strategy",
    "get_trade_journal", "get_trade_stats",
    "get_tv_alerts",
    "chat", "llm_usage",
    "health", "list_tools", "tool_info",
    "admin_stats",
]


def test_all_tool_methods_exist():
    c = SentinelClient()
    missing = [t for t in EXPECTED_TOOLS if not hasattr(c, t)]
    assert not missing, f"Missing methods: {missing}"
