"""
Sentinel API — Billing Resource.

    status = client.billing.status()      # tier, subscription info
    usage = client.billing.usage()        # API calls, LLM usage, costs
    history = client.billing.history()    # payment history

    # USDC
    balance = client.billing.usdc_balance()
"""


class BillingResource:
    """Billing and subscription management."""

    def __init__(self, http):
        self._http = http

    # ── Stripe ────────────────────────────────────────────────

    def status(self) -> dict:
        """Get subscription status — tier, plan, renewal date."""
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
    def subscribe(self, tier: str = "pro") -> dict:
        """Create a Stripe checkout session to upgrade your tier.

        Returns a checkout URL — redirect user to this URL to complete payment.

        Args:
            tier: "pro" ($100/mo) or "enterprise" ($1,000/mo)
        """
        return self._http.post("/api/v1/billing/subscribe", {"tier": tier})

    # ── USDC (On-Chain) ───────────────────────────────────────

    def usdc_balance(self) -> dict:
        """Get your USDC balance, tier, and markup info."""
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
