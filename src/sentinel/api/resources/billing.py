"""
Sentinel API — Billing Resource.

Pay-as-you-go: a flat 20% markup on LLM provider cost, metered and billed
monthly in arrears via Stripe. No tiers, no subscriptions, no plans.

    status = client.billing.status()      # plan, payment status, monthly usage
    usage = client.billing.usage()        # API calls, LLM usage, costs
    history = client.billing.history()    # invoice history

    # USDC (shelved — code retained, not active)
    balance = client.billing.usdc_balance()
"""


class BillingResource:
    """Billing — pay-as-you-go metered usage (flat 20%, no tiers)."""

    def __init__(self, http):
        self._http = http

    # ── Stripe ────────────────────────────────────────────────

    def status(self) -> dict:
        """Get billing status.

        Returns a dict with at minimum:

        - ``payment_status`` — "free" | "active" | "payment_failed"
        - ``prompts_used`` — prompts consumed in the current rolling window
        - ``prompt_limit`` — weekly prompt cap (10 on free tier; null when unlimited)
        - ``window_days`` — rolling window length in days (7)
        - ``resets_at`` — ISO-8601 timestamp when the oldest counted prompt ages out
        - ``gated`` — True when the user has hit the quota and must add a payment method
        - ``monthly_usage_usd`` — accumulated cost in the current billing month
        - ``fee_rate`` — platform markup rate (e.g. 0.20 = 20%)
        """
        return self._http.get("/api/v1/billing/status")

    def usage(self) -> dict:
        """Get usage breakdown — API calls, LLM tokens, costs."""
        return self._http.get("/api/v1/billing/usage")

    def history(self) -> dict:
        """Get payment history."""
        return self._http.get("/api/v1/billing/history")

    def breakdown(self) -> dict:
        """Get detailed usage breakdown — per-tool calls, per-day costs."""
        return self._http.get("/api/v1/usage/breakdown")

    def manage_payment(self) -> dict:
        """Open the Stripe Customer Portal to manage billing (update card, view invoices).

        Returns a dict with ``portal_url`` — redirect the user there.
        Raises ``SentinelAPIError`` (400) with ``{action: "add_payment_method"}`` if the
        user has no Stripe customer record yet (use :meth:`add_payment_method` instead).
        """
        return self._http.get("/api/v1/billing/portal")

    def add_payment_method(self) -> dict:
        """Start Stripe Checkout to attach a payment method for pay-as-you-go billing.

        Returns a dict with ``checkout_url`` — redirect the user there to add a card.
        Unlocks unlimited prompts at a flat 20% platform fee, billed monthly in arrears.
        Free tier = 10 prompts per rolling 7-day window; no payment method required to
        start, but adding one removes the cap entirely.
        """
        return self._http.post("/api/v1/billing/subscribe", {})

    def subscribe(self, tier: str = None) -> dict:
        """Deprecated alias for :meth:`add_payment_method`.

        Kept for backward compatibility. ``tier`` is ignored — billing is
        pay-as-you-go with no tiers. Prefer ``add_payment_method()``.
        """
        return self.add_payment_method()

    # ── USDC (On-Chain) ───────────────────────────────────────

    def usdc_balance(self) -> dict:
        """Get your USDC balance and markup info (USDC shelved — may be inactive)."""
        return self._http.get("/api/v1/billing/usdc/balance")

    def usdc_deposit_address(self) -> dict:
        """Get the Solana USDC deposit address."""
        return self._http.get("/api/v1/billing/usdc/deposit-address")

    def usdc_deposits(self) -> dict:
        """Get your USDC deposit history."""
        return self._http.get("/api/v1/billing/usdc/deposits")

    def usdc_register_wallet(self, sol_address: str) -> dict:
        """Register your Solana wallet for USDC deposits.

        Args:
            sol_address: Your Solana wallet address
        """
        return self._http.post("/api/v1/billing/usdc/register-wallet", {
            "sol_address": sol_address
        })

    def usdc_check_deposits(self) -> dict:
        """Force-check for new USDC deposits."""
        return self._http.post("/api/v1/billing/usdc/check-deposits", {})
