"""billing.py

Subscription/billing seam — INTENTIONALLY A STUB. No payment processor is wired
up yet and nothing here charges anyone. This module exists to mark exactly where
a real billing integration (Stripe is assumed below) attaches, and to keep the
tier-change path SERVER-AUTHORITATIVE so a tier can never be self-escalated from
the browser.

Security model (do not weaken):
  * The browser may *request* a checkout for a tier, but that NEVER changes the
    tier. A tier only changes after a verified, server-side payment event.
  * The verified event arrives on the Stripe webhook (signed by Stripe, verified
    with the webhook secret) — NOT from the user's session. The webhook is the
    only thing that calls db.set_tier().
  * /checkout requires a valid session AND a CSRF token (same protections as
    every other mutating endpoint), but is inert until STRIPE keys are set.

When you integrate Stripe:
  1. Set TF_STRIPE_SECRET_KEY and TF_STRIPE_WEBHOOK_SECRET in the environment.
  2. In create_checkout_session(): create a Stripe Checkout Session with the
     price ID mapped from config.TIERS[tier] and return its URL.
  3. In stripe_webhook(): verify the signature, and on
     checkout.session.completed / customer.subscription.updated, map the Stripe
     price back to a tier key and call db.set_tier(email, tier). On cancellation
     downgrade to config.DEFAULT_TIER. (data.py already reads the tier from the
     DB on every /live call, so the change takes effect on the next refresh with
     no re-login required.)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

import config
from auth import current_user, require_csrf

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/checkout")
def checkout(
    body: dict,
    user: dict = Depends(current_user),
    _csrf: None = Depends(require_csrf),
):
    """Begin an upgrade. STUB: validates the target tier, then reports that
    billing is not configured. It never mutates the user's tier."""
    target = (body or {}).get("tier", "")
    tier = config.TIERS.get(target)
    # Only purchasable (public) tiers can be checked out; reject unknown/internal.
    if not tier or not tier.get("public"):
        raise HTTPException(status_code=400, detail="Unknown or non-purchasable tier")

    # >>> Stripe Checkout Session creation attaches HERE. <<<
    # session = stripe.checkout.Session.create(... price for `target` ...)
    # return {"checkout_url": session.url}
    raise HTTPException(
        status_code=501,
        detail="Billing is not configured yet. This is where Stripe Checkout attaches.",
    )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe -> us. STUB: the ONLY path allowed to change a tier, and only after
    verifying the Stripe signature. Inert until the webhook secret is set."""
    secret = config._get("TF_STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=501, detail="Billing webhook not configured.")
    # >>> Verify signature with `secret`, parse the event, map price -> tier key,
    #     then db.set_tier(email, tier). Never trust the request body unverified. <<<
    raise HTTPException(status_code=501, detail="Billing webhook not implemented.")
