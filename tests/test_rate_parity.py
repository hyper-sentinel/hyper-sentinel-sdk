"""
Rate parity: every model in MODEL_CATALOG must have an entry in usage.MODEL_COSTS,
and the rates must match the accepted 0.9.8 table.

If this test breaks it means one file was updated without the other.
Fix both together — the gateway usage.go is the live billing source,
usage.py is the local estimate, and MODEL_CATALOG is what the user sees.
"""

import pytest
from sentinel.chat import MODEL_CATALOG
from sentinel.scrapers.usage import MODEL_COSTS

# Accepted rate table for every id in the 0.9.8 catalog.
# input / output in $/MTok (same unit as MODEL_COSTS).
ACCEPTED_RATES = {
    "claude-fable-5-1":  (10.00, 50.00),
    "claude-opus-5-5":   (4.00,  20.00),
    "claude-sonnet-5-5": (2.00,  10.00),
    "claude-haiku-5-5":  (0.10,   0.50),
    "gpt-6-astra":       (10.00, 50.00),
    "gpt-6.1-sol":       (2.00,  10.00),
    "gpt-6-luna":        (0.10,   0.50),
    "gemini-4-argon":    (2.00,  10.00),
    "gemini-3.8-flash":  (0.75,   3.75),
    "grok-4.7":          (2.00,   6.00),
    "grok-4.3":          (1.25,   2.50),
    "deepseek-v4-pro":   (1.32,   3.96),
    "deepseek-flash":    (0.30,   1.20),
    "glm-5.3":           (1.40,   4.40),
    "glm-5.3-flash":     (0.15,   0.50),
    "minimax-m3":        (0.30,   1.20),
    "kimi-k3":           (3.00,  15.00),
    "kimi-k2.7-code":    (0.95,   4.00),
}


def _lookup_cost(model_id: str):
    """Mirror usage.py prefix matching: longest-match wins."""
    best_key = None
    for key in MODEL_COSTS:
        if model_id.startswith(key):
            if best_key is None or len(key) > len(best_key):
                best_key = key
    return MODEL_COSTS.get(best_key)


def test_every_catalog_model_has_a_rate():
    missing = []
    for provider, models in MODEL_CATALOG.items():
        for m in models:
            mid = m["id"]
            if _lookup_cost(mid) is None:
                missing.append(f"{provider}/{mid}")
    assert not missing, f"Models in catalog with no usage.py rate: {missing}"


def test_catalog_rates_match_accepted_table():
    mismatches = []
    for model_id, (want_in, want_out) in ACCEPTED_RATES.items():
        got = _lookup_cost(model_id)
        if got is None:
            mismatches.append(f"{model_id}: not found in MODEL_COSTS")
            continue
        got_in, got_out = got
        if abs(got_in - want_in) > 1e-9 or abs(got_out - want_out) > 1e-9:
            mismatches.append(
                f"{model_id}: got ({got_in}, {got_out}), want ({want_in}, {want_out})"
            )
    assert not mismatches, "Rate mismatches:\n" + "\n".join(mismatches)
