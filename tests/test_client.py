"""Tests for Sentinel SDK v0.5.x — thin REST client."""

import sentinel
from sentinel import Sentinel, SentinelAPI


# ── Version ──────────────────────────────────────────────────

def test_version():
    import re
    with open("pyproject.toml") as f:
        expected = re.search(r'version\s*=\s*"(.+?)"', f.read()).group(1)
    assert sentinel.__version__ == expected, f"Expected {expected}, got {sentinel.__version__}"


# ── Client instantiation ────────────────────────────────────

def test_sentinel_class_exists():
    assert Sentinel is not None
    assert issubclass(Sentinel, SentinelAPI)


def test_sentinel_has_flat_methods():
    """Verify the flattened API surface exists."""
    expected = ["chat", "price", "top_coins", "stock", "macro",
                "news", "trending", "orderbook", "buy", "sell",
                "positions", "orders", "tool"]
    for method in expected:
        assert hasattr(Sentinel, method), f"Missing method: {method}"
        assert callable(getattr(Sentinel, method)), f"Not callable: {method}"


def test_sentinel_api_class():
    """Verify SentinelAPI is importable and is the base class."""
    assert SentinelAPI is not None
    assert issubclass(Sentinel, SentinelAPI)


# ── Exports ──────────────────────────────────────────────────

def test_all_exports():
    from sentinel import __all__
    assert "Sentinel" in __all__
    assert "SentinelAPI" in __all__
    assert "SentinelAPIError" in __all__
    assert "AuthenticationError" in __all__


def test_hyper_sentinel_import():
    from hyper_sentinel import Sentinel as S
    assert S is Sentinel


# ── Version string format ────────────────────────────────────

def test_version_format():
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", sentinel.__version__)
