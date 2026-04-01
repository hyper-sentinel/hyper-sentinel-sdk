"""Integration tests — hits the live Sentinel Go gateway on Cloud Run."""

import time

import pytest

from sentinel import SentinelClient
from sentinel.exceptions import AuthError, ToolNotFoundError

pytestmark = pytest.mark.integration


# ── Health & Meta ────────────────────────────────────────────

def test_health(client):
    data = client.health()
    assert data["status"] == "ok"
    assert data["gateway"] == "sentinel-go"


def test_list_tools(client):
    tools = client.list_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    # each tool should have a name
    names = [t["name"] for t in tools]
    assert "get_crypto_price" in names


def test_tool_info(client):
    info = client.tool_info("get_crypto_price")
    assert "name" in info or "tool" in info


# ── Auth Flow ────────────────────────────────────────────────

def test_register_sets_state(client):
    """Client should have token and tier set after register (done in fixture)."""
    assert client.token != ""
    assert client.user_id != ""
    assert client.tier == "free"


def test_login(base_url, test_creds):
    c = SentinelClient(base_url=base_url)
    data = c.login(email=test_creds["email"], password=test_creds["password"])
    assert data["tier"] == "free"
    assert data["token"] != ""
    assert c.token != ""
    c.close()


def test_generate_key(client):
    key_data = client.generate_key(name=f"test-{int(time.time())}")
    assert "api_key" in key_data
    assert key_data["api_key"].startswith("sk-")


# ── Billing ──────────────────────────────────────────────────

def test_billing_status(client):
    status = client.billing_status()
    assert status["tier"] == "free"
    assert "your_fees" in status
    assert "rate_limit_per_min" in status


def test_billing_usage(client):
    usage = client.billing_usage()
    assert isinstance(usage, dict)


# ── Market Data Tools (read-only, no side effects) ──────────

def test_get_crypto_price(client):
    result = client.get_crypto_price("bitcoin")
    assert "price" in result
    assert result["price"] > 0


def test_get_crypto_top_n(client):
    result = client.get_crypto_top_n(5)
    assert isinstance(result, list)
    assert len(result) == 5


def test_search_crypto(client):
    result = client.search_crypto("ethereum")
    assert isinstance(result, list)
    assert len(result) > 0


def test_get_stock_price(client):
    result = client.get_stock_price("AAPL")
    assert "price" in result or "regularMarketPrice" in result


# ── LLM Proxy ───────────────────────────────────────────────

def test_chat(client, ai_key):
    result = client.chat(
        message="Say hello in exactly 3 words.",
        ai_key=ai_key,
    )
    assert isinstance(result, dict)


# ── Error Handling ───────────────────────────────────────────

def test_invalid_tool_raises_404(client):
    with pytest.raises(ToolNotFoundError):
        client.call_tool("definitely_not_a_real_tool_xyz")


def test_bad_auth_raises_401(base_url):
    c = SentinelClient(base_url=base_url, api_key="sk-bogus-key-12345")
    with pytest.raises(AuthError):
        c.call_tool("get_crypto_price", coin_id="bitcoin")
    c.close()
