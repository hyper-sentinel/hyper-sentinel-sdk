"""Defaults, catalog order, and coin resolution for the 0.9.8 rate card."""

import time

import pytest

from sentinel.chat import DEFAULT_MODELS, MODEL_CATALOG
from sentinel.scrapers import hyperliquid as hl


def test_default_is_catalog_head():
    assert set(DEFAULT_MODELS) == set(MODEL_CATALOG)
    for provider, models in MODEL_CATALOG.items():
        assert models, provider
        assert DEFAULT_MODELS[provider] == models[0]["id"]
        assert models[0]["id"]


def test_resolve_coin_uses_live_book_and_nicknames():
    saved = dict(hl._universe_cache)
    hl._universe_cache.update(
        fetched_at=time.time(),
        native=frozenset({"BTC", "ETH", "SPX"}),
        xyz=frozenset({"TSLA", "NVDA", "CRWD", "SP500", "CL", "GOLD"}),
        ok=True,
    )
    try:
        assert hl._resolve_coin("btc") == "BTC"
        assert hl._resolve_coin("CRWD") == "xyz:CRWD"
        assert hl._resolve_coin("xyz:NVDA") == "xyz:NVDA"
        assert hl._resolve_coin("OIL") == "xyz:CL"
        assert hl._resolve_coin("SPX") == "xyz:SP500"
        assert hl._resolve_coin("GOLD") == "xyz:GOLD"
        with pytest.raises(ValueError):
            hl._resolve_coin("NOTACOIN")
        with pytest.raises(ValueError):
            hl._resolve_coin("flx:ABC")
    finally:
        hl._universe_cache.clear()
        hl._universe_cache.update(saved)


def test_cold_cache_rejects_unknown_ticker(monkeypatch):
    saved = dict(hl._universe_cache)
    hl._universe_cache.update(
        fetched_at=0.0, native=frozenset(), xyz=frozenset(), ok=False,
    )
    monkeypatch.setattr(hl, "refresh_hl_universe", lambda force=False: False)
    try:
        with pytest.raises(ValueError):
            hl._resolve_coin("NOTACOIN")
        assert hl._resolve_coin("OIL") == "xyz:CL"
        with pytest.raises(ValueError):
            hl._resolve_coin("flx:ABC")
    finally:
        hl._universe_cache.clear()
        hl._universe_cache.update(saved)
