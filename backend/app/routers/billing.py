"""
Stripe Billing Router — subscription management and webhooks.

Endpoints:
    POST /api/billing/checkout       — create Stripe Checkout session
    POST /api/billing/portal         — create Stripe Customer Portal session
    POST /api/billing/webhook        — handle Stripe webhook events
    GET  /api/billing/status         — get current subscription status

All subscription state is persisted in the ``users`` table (plan, stripe_customer_id).
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import User
from app.services.auth import get_current_user
from app.services.database import get_db

router = APIRouter(prefix="/api/billing", tags=["billing"])


# ── Stripe price IDs — loaded from pricing_config (single source of truth) ────

from app.pricing_config import (
    get_stripe_price_map, get_one_time_plans, get_plan_from_price,
)

_PLAN_PRICE_MAP  = get_stripe_price_map()
_PLAN_FROM_PRICE = {v: k for k, v in _PLAN_PRICE_MAP.items()}
_ONE_TIME_PLANS  = get_one_time_plans()


# ── Request models ────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str  # "starter", "pro", "unlimited", "byok"
    success_url: str = "https://glassnote.ai/billing/success"
    cancel_url: str  = "https://glassnote.ai/billing/cancel"


# ── Create Checkout Session ───────────────────────────────────────────────────

@router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout session for subscription upgrade.

    Returns a checkout URL that the desktop app opens in the browser.
    After payment, Stripe sends a webhook to update the user's plan.
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(500, "Stripe not configured on server")

    price_id = _PLAN_PRICE_MAP.get(req.plan)
    if not price_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid plan: {req.plan}. Choose from: {list(_PLAN_PRICE_MAP.keys())}",
        )

    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key

        user_id = user["sub"]
        email   = user.get("email", "")

        # FIX: Prevent free plan from accessing checkout (it's free)
        # BYOK is now a feature flag, not a plan - use /api/auth/toggle-byok instead
        if req.plan == "free":
            raise HTTPException(
                status_code=400,
                detail="Free plan does not require payment"
            )

        # BYOK is no longer a plan - it's a feature toggle
        if req.plan == "byok":
            raise HTTPException(
                status_code=400,
                detail="BYOK is a feature, not a plan. Use /api/auth/toggle-byok to enable it."
            )

        # Get user from DB for existing Stripe customer ID
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        db_user = result.scalar_one_or_none()

        customer_id = db_user.stripe_customer_id if db_user else None

        if not customer_id:
            # Create Stripe customer
            customer = stripe.Customer.create(
                email=email,
                metadata={"glassnote_user_id": user_id},
            )
            customer_id = customer.id
            # Save to DB
            if db_user:
                db_user.stripe_customer_id = customer_id

        # Create checkout session
        # BYOK is a one-time payment; everything else is a subscription
        checkout_mode = "payment" if req.plan in _ONE_TIME_PLANS else "subscription"
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode=checkout_mode,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=req.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=req.cancel_url,
            metadata={"glassnote_user_id": user_id, "plan": req.plan},
        )

        return {
            "checkout_url": session.url,
            "session_id":   session.id,
        }

    except ImportError:
        raise HTTPException(500, "stripe package not installed")
    except Exception as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")


# ── Customer Portal ──────────────────────────────────────────────────────────

@router.post("/portal")
async def create_portal(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session for self-service management.

    The portal allows users to:
    - View invoices
    - Update payment method
    - Cancel or change subscription
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(500, "Stripe not configured on server")

    user_id = user["sub"]

    # Get user from DB
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    db_user = result.scalar_one_or_none()
    customer_id = db_user.stripe_customer_id if db_user else None

    if not customer_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No billing account found. Please subscribe first.",
        )

    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="https://glassnote.ai/settings",
        )

        return {"portal_url": session.url}

    except Exception as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")


# ── Webhook Handler ──────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.

    Events handled:
    - checkout.session.completed → activate subscription
    - customer.subscription.updated → plan change
    - customer.subscription.deleted → downgrade to free
    - invoice.payment_failed → flag account

    Webhook creates its own DB session since it's not a user-authenticated
    request (comes from Stripe directly).
    """
    from app.services.database import async_session_factory

    settings = get_settings()
    body = await request.body()
    sig  = request.headers.get("stripe-signature", "")

    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key

        # Verify webhook signature
        if settings.stripe_webhook_secret:
            event = stripe.Webhook.construct_event(
                body, sig, settings.stripe_webhook_secret
            )
        else:
            # Dev mode — no signature verification
            event = json.loads(body)

    except Exception as e:
        raise HTTPException(400, f"Webhook verification failed: {e}")

    event_type = event.get("type", "")
    data       = event.get("data", {}).get("object", {})

    print(f"[billing] Webhook: {event_type}")

    async with async_session_factory() as db:
        try:
            if event_type == "checkout.session.completed":
                metadata = data.get("metadata", {})
                user_id  = metadata.get("glassnote_user_id", "")
                plan     = metadata.get("plan", "starter")
                customer = data.get("customer", "")

                if user_id:
                    # Compute expiry: free = no expiry, paid plans = 30 days
                    # BYOK is no longer a plan - it's a feature flag
                    expires_at = None
                    if plan not in ("free",):
                        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

                    await db.execute(
                        update(User).where(User.id == user_id).values(
                            plan=plan,
                            stripe_customer_id=customer,
                            plan_expires_at=expires_at,
                        )
                    )
                    expiry_str = expires_at.strftime("%Y-%m-%d") if expires_at else "lifetime"
                    print(f"[billing] ✓ User {user_id[:8]} activated plan={plan}  expires={expiry_str}")

            elif event_type == "customer.subscription.updated":
                customer_id = data.get("customer", "")
                result = await db.execute(
                    select(User).where(User.stripe_customer_id == customer_id)
                )
                db_user = result.scalar_one_or_none()
                if db_user:
                    items = data.get("items", {}).get("data", [])
                    if items:
                        price_id = items[0].get("price", {}).get("id", "")
                        new_plan = _PLAN_FROM_PRICE.get(price_id, "starter")
                        db_user.plan = new_plan
                        print(f"[billing] ✓ User {str(db_user.id)[:8]} plan updated: {new_plan}")

            elif event_type == "customer.subscription.deleted":
                customer_id = data.get("customer", "")
                await db.execute(
                    update(User).where(User.stripe_customer_id == customer_id).values(
                        plan="free",
                        plan_expires_at=None,   # clear expiry on downgrade
                    )
                )
                print(f"[billing] ✓ Customer {customer_id[:8]} downgraded to free")

            elif event_type == "invoice.payment_failed":
                customer_id = data.get("customer", "")
                result = await db.execute(
                    select(User).where(User.stripe_customer_id == customer_id)
                )
                db_user = result.scalar_one_or_none()
                if db_user:
                    db_user.is_active = False
                    print(f"[billing] ⚠ User {str(db_user.id)[:8]} payment failed")

            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"[billing] ⚠ Webhook processing error: {e}")

    return {"received": True}


# ── Subscription Status ──────────────────────────────────────────────────────

@router.get("/status")
async def billing_status(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current subscription status for the authenticated user.

    Returns plan, status, and usage limits from the database.
    """
    settings = get_settings()
    user_id  = user["sub"]

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    db_user = result.scalar_one_or_none()

    plan = db_user.plan if db_user else user.get("plan", "free")
    limits = settings.plan_limits.get(plan, 3)

    return {
        "plan":            plan,
        "status":          "active" if db_user and db_user.is_active else "inactive",
        "sessions_limit":  limits,
        "stripe_customer": db_user.stripe_customer_id if db_user else "",
        "activated_at":    db_user.created_at.isoformat() if db_user else None,
        "plan_expires_at": (
            db_user.plan_expires_at.isoformat()
            if db_user and getattr(db_user, "plan_expires_at", None)
            else None
        ),
    }
