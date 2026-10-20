"""
Usage Tracker — Token counting and cost logging for LLM API arbitrage.

Tracks every LLM call made through Sentinel:
- Estimates token counts from response length
- Calculates actual provider cost
- Calculates billed cost (with markup)
- Logs to SQLite for billing and analytics

Revenue model:
  actual_cost = provider price * tokens
  billed_cost = actual_cost * (1 + MARKUP_PCT)
  profit      = billed_cost - actual_cost

Default markup: 20% (configurable via SENTINEL_MARKUP_PCT env var).
The live meter is the Go gateway (LLM_MARKUP). This module is a local estimate only.
"""

import os
import sqlite3
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sentinel.usage")

# ── Cost per million tokens (standard short-context, checked 2026-10-20) ─
# Format: {model_prefix: (input_cost_per_mtok, output_cost_per_mtok)}
# Longer prefixes must come first: matching is "prefix in model string".
# Live billing is the gateway rate card, not this dict.
MODEL_COSTS = {
    # ── Current catalog (keep in sync with chat.MODEL_CATALOG) ─
    "claude-fable-5-1":    (10.00, 50.00),
    "claude-fable-5":      (10.00, 50.00),
    "claude-opus-5-5":     (4.00, 20.00),
    "claude-sonnet-5-5":   (2.00, 10.00),
    "claude-haiku-5-5":    (0.10, 0.50),
    "gpt-6-astra":         (10.00, 50.00),
    "gpt-6.1-sol":         (2.00, 10.00),
    "gpt-6-luna":          (0.10, 0.50),
    "gpt-5.5":             (5.00, 30.00),
    "gemini-4-argon":      (2.00, 10.00),
    "gemini-3.8-flash":    (0.75, 3.75),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "grok-4.7":            (2.00, 6.00),
    "grok-4.3":            (1.25, 2.50),
    "deepseek-v4-pro":     (1.32, 3.96),
    "deepseek-flash":      (0.30, 1.20),
    "deepseek-v4-flash":   (0.30, 1.20),
    "glm-5.3-flash":       (0.15, 0.50),
    "glm-5.3":             (1.40, 4.40),
    "glm-5.2":             (1.40, 4.40),
    "minimax-m3":          (0.30, 1.20),
    "kimi-k3":             (3.00, 15.00),
    "kimi-k2.7-code":      (0.95, 4.00),
    "kimi-k2.6":           (0.95, 4.00),
    # ── Older ids still seen in logs ───────────────────────────
    "claude-opus-4-8":     (5.00, 25.00),
    "claude-opus-4":       (15.00, 75.00),   # claude-opus-4-20250514
    "claude-sonnet-4-5":   (3.00, 15.00),    # claude-sonnet-4-5-20250514 (thinking)
    "claude-sonnet-4":     (3.00, 15.00),    # claude-sonnet-4-6 (legacy)
    "claude-3-5-sonnet":   (3.00, 15.00),    # claude-3-5-sonnet-20241022 (legacy)
    "claude-3-5-haiku":    (0.80, 4.00),     # claude-3-5-haiku-20241022
    "claude-3-opus":       (15.00, 75.00),   # claude-3-opus-20240229 (legacy)
    "claude-3-haiku":      (0.25, 1.25),     # claude-3-haiku-20240307 (legacy)
    # ── OpenAI ────────────────────────────────────────────────
    "gpt-4.1":             (2.00, 8.00),     # flagship production model
    "gpt-4.1-mini":        (0.40, 1.60),     # cost-efficient
    "gpt-4.1-nano":        (0.10, 0.40),     # cheapest capable
    "gpt-4o-mini":         (0.15, 0.60),
    "gpt-4o":              (2.50, 10.00),    # gpt-4o (updated pricing)
    "gpt-4-turbo":         (10.00, 30.00),   # legacy
    "o3":                  (2.00, 8.00),     # flagship reasoning
    "o4-mini":             (1.10, 4.40),     # fast reasoning (math/code)
    "o1-mini":             (1.10, 4.40),     # legacy reasoning mini
    "o1":                  (15.00, 60.00),   # legacy reasoning
    # ── Google Gemini ─────────────────────────────────────────
    "gemini-2.5-pro":      (1.25, 10.00),   # latest pro (≤200K context)
    "gemini-2.5-flash":    (0.30, 2.50),    # latest flash
    "gemini-2.0-flash":    (0.10, 0.40),
    "gemini-1.5-pro":      (1.25, 5.00),    # legacy
    "gemini-1.5-flash":    (0.075, 0.30),   # legacy
    # ── xAI ───────────────────────────────────────────────────
    "grok-2":              (2.00, 10.00),
    "grok-3":              (3.00, 15.00),
    # ── Self-hosted ───────────────────────────────────────────
    "ollama":              (0.00, 0.00),
}

# Default markup percentage — configurable via environment
MARKUP_PCT = float(os.getenv("SENTINEL_MARKUP_PCT", "20")) / 100  # matches gateway LLM_MARKUP

# DB path — stored in ~/.sentinel/data/ for persistence across installs
_DATA_DIR = Path.home() / ".sentinel" / "data"
_DB_PATH = str(_DATA_DIR / "usage.db")


def _get_db() -> sqlite3.Connection:
    """Get or create the usage database."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     REAL    NOT NULL,
            provider      TEXT    NOT NULL,
            model         TEXT    NOT NULL,
            input_tokens  INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            actual_cost   REAL    NOT NULL,
            billed_cost   REAL    NOT NULL,
            markup_pct    REAL    NOT NULL,
            profit        REAL    NOT NULL,
            query_preview TEXT,
            mode          TEXT    DEFAULT 'sdk'
        )
    """)
    conn.commit()
    return conn


def estimate_tokens(text: str) -> int:
    """Estimate token count from text. ~4 chars per token for English."""
    return max(1, len(text) // 4)


def _match_model_cost(model_string: str) -> tuple[float, float]:
    """Find the best matching cost entry for a model string."""
    model_lower = model_string.lower()
    for prefix, costs in MODEL_COSTS.items():
        if prefix in model_lower:
            return costs
    # Default fallback: assume mid-range pricing
    logger.warning(f"Unknown model '{model_string}', using flagship fallback ($10/$50 per MTok)")
    return (10.00, 50.00)


def log_usage(
    provider: str,
    model: str,
    input_text: str,
    output_text: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    mode: str = "sdk",
) -> dict:
    """
    Log a single LLM call's usage to the database.

    Args:
        provider: LLM provider (CLAUDE, OPENAI, GEMINI, GROK, OLLAMA)
        model: Full model string (e.g. "anthropic/claude-sonnet-4-5")
        input_text: The user's query (for token estimation if no exact count)
        output_text: The LLM's response
        input_tokens: Exact input token count (if available from provider)
        output_tokens: Exact output token count (if available from provider)
        mode: 'terminal', 'api', or 'sdk'

    Returns:
        Dict with usage details and costs.
    """
    # Estimate tokens if not provided
    if input_tokens is None:
        input_tokens = estimate_tokens(input_text)
    if output_tokens is None:
        output_tokens = estimate_tokens(output_text)

    # Calculate costs
    input_cost_per_mtok, output_cost_per_mtok = _match_model_cost(model)
    actual_cost = (
        (input_tokens * input_cost_per_mtok / 1_000_000)
        + (output_tokens * output_cost_per_mtok / 1_000_000)
    )
    billed_cost = actual_cost * (1 + MARKUP_PCT)
    profit = billed_cost - actual_cost

    # Log to database
    try:
        conn = _get_db()
        conn.execute("""
            INSERT INTO usage_log
                (timestamp, provider, model, input_tokens, output_tokens,
                 actual_cost, billed_cost, markup_pct, profit, query_preview, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(), provider, model,
            input_tokens, output_tokens,
            actual_cost, billed_cost, MARKUP_PCT, profit,
            input_text[:100],  # preview first 100 chars
            mode,
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log usage: {e}")

    usage_data = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "actual_cost": round(actual_cost, 6),
        "billed_cost": round(billed_cost, 6),
        "profit": round(profit, 6),
        "markup_pct": f"{MARKUP_PCT * 100:.0f}%",
        "model": model,
        "provider": provider,
    }
    logger.debug(
        f"Usage: {input_tokens}+{output_tokens} tokens, "
        f"cost=${actual_cost:.4f}, billed=${billed_cost:.4f}, "
        f"profit=${profit:.4f}"
    )
    return usage_data


def get_usage_summary(period: str = "today") -> dict:
    """
    Get usage summary for a time period.

    Args:
        period: 'today', 'week', 'month', or 'all'

    Returns:
        Dict with total tokens, costs, profit, and call count.
    """
    try:
        conn = _get_db()
    except Exception as e:
        return {"error": f"Cannot access usage database: {e}"}

    now = time.time()
    if period == "today":
        since = now - 86400
    elif period == "week":
        since = now - 604800
    elif period == "month":
        since = now - 2592000
    else:
        since = 0

    cursor = conn.execute("""
        SELECT
            COUNT(*) as calls,
            COALESCE(SUM(input_tokens), 0) as total_input,
            COALESCE(SUM(output_tokens), 0) as total_output,
            COALESCE(SUM(actual_cost), 0) as total_actual,
            COALESCE(SUM(billed_cost), 0) as total_billed,
            COALESCE(SUM(profit), 0) as total_profit
        FROM usage_log
        WHERE timestamp >= ?
    """, (since,))
    row = cursor.fetchone()

    # Per-model breakdown
    model_cursor = conn.execute("""
        SELECT
            model,
            COUNT(*) as calls,
            SUM(input_tokens + output_tokens) as tokens,
            SUM(actual_cost) as cost,
            SUM(profit) as profit
        FROM usage_log
        WHERE timestamp >= ?
        GROUP BY model
        ORDER BY cost DESC
    """, (since,))
    models = []
    for m in model_cursor.fetchall():
        models.append({
            "model": m[0],
            "calls": m[1],
            "tokens": m[2],
            "cost": round(m[3], 4),
            "profit": round(m[4], 4),
        })

    conn.close()

    return {
        "period": period,
        "total_calls": row[0],
        "total_input_tokens": row[1],
        "total_output_tokens": row[2],
        "total_tokens": row[1] + row[2],
        "actual_cost": round(row[3], 4),
        "billed_amount": round(row[4], 4),
        "your_profit": round(row[5], 4),
        "markup": f"{MARKUP_PCT * 100:.0f}%",
        "models": models,
    }
