from datetime import datetime
from datetime import timedelta
from datetime import timezone
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from pydantic import BaseModel
from typing import Literal
import os
from app_core import api, db, gen_id, get_current_user, logger, now_iso

# ---------------------------------------------------------------------------
# Workspace + Billing (Stripe)
# ---------------------------------------------------------------------------
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")

PLANS = {
    "free": {
        "name": "Free",
        "price_eur": 0.0,
        "articles_per_month": 5,
        "sites_max": 1,
        "auto_publish": False,
        "features": ["1 site", "5 articles/mois", "SEO audit", "Publication manuelle"],
    },
    "pro": {
        "name": "Pro",
        "price_eur": 29.0,
        "articles_per_month": 50,
        "sites_max": 5,
        "auto_publish": True,
        "features": ["5 sites", "50 articles/mois", "Publication auto GitHub + LinkedIn", "Calendrier éditorial", "Google Search Console"],
    },
    "business": {
        "name": "Business",
        "price_eur": 99.0,
        "articles_per_month": 500,
        "sites_max": 20,
        "auto_publish": True,
        "features": ["20 sites", "500 articles/mois", "Toutes les fonctionnalités Pro", "Rapports personnalisés", "Suivi de classement avancé", "Support prioritaire"],
    },
    "agency": {
        "name": "Agency",
        "price_eur": 299.0,
        "articles_per_month": 5000,
        "sites_max": 200,
        "auto_publish": True,
        "features": ["200 sites", "5000 articles/mois", "White-label (bientôt)", "API publique (bientôt)", "Multi-utilisateurs (bientôt)", "Support dédié"],
    },
}


async def _get_or_create_workspace(user: dict) -> dict:
    """Return the user's workspace, creating a Free-plan workspace on first access."""
    ws = await db.workspaces.find_one({"owner_id": user["id"]}, {"_id": 0})
    if ws:
        return ws
    ws = {
        "id": gen_id(),
        "owner_id": user["id"],
        "name": f"{user.get('full_name', user.get('email', 'Espace'))}",
        "plan": "free",
        "plan_started_at": now_iso(),
        "plan_expires_at": None,  # no expiry for free
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "created_at": now_iso(),
    }
    await db.workspaces.insert_one(ws)
    return ws


async def _count_articles_this_month(user_id: str) -> int:
    """Count drafts created by user in the current calendar month."""
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    return await db.drafts.count_documents({"user_id": user_id, "created_at": {"$gte": start}})


async def _enforce_plan_quota(user: dict) -> None:
    """Raise HTTPException if user hits the article quota of their current plan."""
    ws = await _get_or_create_workspace(user)
    plan = PLANS.get(ws.get("plan", "free"), PLANS["free"])
    used = await _count_articles_this_month(user["id"])
    if used >= plan["articles_per_month"]:
        raise HTTPException(
            402,
            f"Quota mensuel atteint ({plan['articles_per_month']} articles/mois pour le plan {plan['name']}). Passez à un plan supérieur pour continuer.",
        )


@api.get("/workspace")
async def get_workspace(user=Depends(get_current_user)):
    ws = await _get_or_create_workspace(user)
    plan = PLANS.get(ws.get("plan", "free"), PLANS["free"])
    articles_used = await _count_articles_this_month(user["id"])
    return {
        "id": ws["id"],
        "name": ws["name"],
        "plan": ws["plan"],
        "plan_details": plan,
        "plan_expires_at": ws.get("plan_expires_at"),
        "usage": {
            "articles_this_month": articles_used,
            "articles_limit": plan["articles_per_month"],
            "articles_remaining": max(0, plan["articles_per_month"] - articles_used),
        },
    }


@api.get("/billing/plans")
async def list_plans():
    return {k: {**v, "id": k} for k, v in PLANS.items()}


class CheckoutRequest(BaseModel):
    plan_id: Literal["pro", "business", "agency"]
    origin_url: str  # sent from frontend: window.location.origin


@api.post("/billing/checkout")
async def create_billing_checkout(payload: CheckoutRequest, http_request: Request, user=Depends(get_current_user)):
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe n'est pas configuré côté serveur.")
    plan = PLANS.get(payload.plan_id)
    if not plan:
        raise HTTPException(400, "Plan inconnu")

    ws = await _get_or_create_workspace(user)

    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    host_url = str(http_request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/billing?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/billing?canceled=1"

    checkout_req = CheckoutSessionRequest(
        amount=float(plan["price_eur"]),
        currency="eur",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "workspace_id": ws["id"],
            "user_id": user["id"],
            "plan_id": payload.plan_id,
            "source": "logi-seo-billing",
        },
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)

    # Persist a pending payment transaction (mandatory per playbook)
    await db.payment_transactions.insert_one({
        "id": gen_id(),
        "user_id": user["id"],
        "workspace_id": ws["id"],
        "session_id": session.session_id,
        "amount": float(plan["price_eur"]),
        "currency": "eur",
        "plan_id": payload.plan_id,
        "payment_status": "initiated",
        "created_at": now_iso(),
        "processed_at": None,
    })
    return {"url": session.url, "session_id": session.session_id}


@api.get("/billing/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, http_request: Request, user=Depends(get_current_user)):
    """Poll checkout status; upgrade the workspace plan once payment succeeds. Idempotent."""
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe n'est pas configuré côté serveur.")
    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Transaction introuvable")

    # Already processed? Return cached state.
    if tx.get("payment_status") in ("paid", "expired", "failed"):
        return {"payment_status": tx["payment_status"], "plan_id": tx.get("plan_id"), "status": "processed"}

    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    host_url = str(http_request.base_url).rstrip("/")
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{host_url}/api/webhook/stripe")
    st = await stripe_checkout.get_checkout_status(session_id)

    new_status = st.payment_status  # "paid", "unpaid", "no_payment_required"
    if new_status == "paid" and tx["payment_status"] != "paid":
        # Idempotent guard via findOneAndUpdate condition
        res = await db.payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": {"payment_status": "paid", "processed_at": now_iso()}},
        )
        if res.modified_count > 0:
            # Upgrade workspace
            plan_id = tx.get("plan_id")
            expires_at = (datetime.now(timezone.utc) + timedelta(days=31)).isoformat()
            await db.workspaces.update_one(
                {"id": tx["workspace_id"]},
                {"$set": {
                    "plan": plan_id,
                    "plan_started_at": now_iso(),
                    "plan_expires_at": expires_at,
                }},
            )
            logger.info("Workspace %s upgraded to plan %s", tx["workspace_id"], plan_id)
    elif st.status == "expired":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "expired", "processed_at": now_iso()}},
        )
        new_status = "expired"

    return {
        "payment_status": new_status,
        "status": st.status,
        "amount_total": st.amount_total,
        "currency": st.currency,
        "plan_id": tx.get("plan_id"),
    }


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Stripe webhook — updates transaction + workspace plan when payment succeeds."""
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe non configuré")
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
    try:
        evt = await stripe_checkout.handle_webhook(body, sig)
    except Exception as exc:
        logger.warning("Stripe webhook parse error: %s", exc)
        raise HTTPException(400, "Invalid webhook payload")

    if evt.session_id and evt.payment_status == "paid":
        tx = await db.payment_transactions.find_one({"session_id": evt.session_id})
        if tx and tx.get("payment_status") != "paid":
            await db.payment_transactions.update_one(
                {"session_id": evt.session_id, "payment_status": {"$ne": "paid"}},
                {"$set": {"payment_status": "paid", "processed_at": now_iso()}},
            )
            plan_id = tx.get("plan_id")
            if plan_id:
                expires_at = (datetime.now(timezone.utc) + timedelta(days=31)).isoformat()
                await db.workspaces.update_one(
                    {"id": tx["workspace_id"]},
                    {"$set": {"plan": plan_id, "plan_started_at": now_iso(), "plan_expires_at": expires_at}},
                )
                logger.info("Webhook: workspace %s upgraded to %s", tx["workspace_id"], plan_id)
    return {"ok": True}


