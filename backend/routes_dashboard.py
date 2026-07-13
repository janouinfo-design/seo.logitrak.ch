from datetime import datetime
from datetime import timedelta
from datetime import timezone
from fastapi import Depends
from typing import Any
from typing import Dict
from typing import Optional
from app_core import api, db, get_current_user
from routes_sites import _get_user_site
from routes_billing import PLANS, _count_articles_this_month, _get_or_create_workspace

# ---------------------------------------------------------------------------
# Performance (mocked GSC/GA for MVP)
# ---------------------------------------------------------------------------
@api.get("/sites/{site_id}/performance")
async def site_performance(site_id: str, user=Depends(get_current_user)):
    site = await _get_user_site(site_id, user)
    label = site["label"]
    base = 1800 if label == "Logirent" else 1200
    days = []
    import random
    random.seed(site_id)
    for i in range(28):
        d = datetime.now(timezone.utc) - timedelta(days=27 - i)
        impressions = base + random.randint(-200, 600) + i * 15
        clicks = max(5, int(impressions * (0.03 + random.random() * 0.025)))
        days.append({
            "date": d.strftime("%Y-%m-%d"),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions * 100, 2),
            "position": round(8 + random.random() * 6, 1),
        })
    keywords = [
        {"keyword": f"location {site['label'].lower()} paris", "clicks": 142, "impressions": 4210, "position": 6.2, "trend": "up"},
        {"keyword": f"{site['label'].lower()} gestion locative", "clicks": 98, "impressions": 3100, "position": 8.9, "trend": "up"},
        {"keyword": "agence immobilière proche", "clicks": 76, "impressions": 5900, "position": 14.3, "trend": "down"},
        {"keyword": f"avis {site['label'].lower()}", "clicks": 54, "impressions": 1200, "position": 4.1, "trend": "stable"},
        {"keyword": "location courte durée", "clicks": 41, "impressions": 7800, "position": 18.7, "trend": "up"},
    ]
    return {
        "site_id": site_id,
        "label": label,
        "mocked": True,
        "totals": {
            "impressions": sum(d["impressions"] for d in days),
            "clicks": sum(d["clicks"] for d in days),
            "avg_position": round(sum(d["position"] for d in days) / len(days), 1),
            "avg_ctr": round(sum(d["ctr"] for d in days) / len(days), 2),
        },
        "daily": days,
        "keywords": keywords,
        "recommendations": [
            "Créer une page locale dédiée pour les requêtes 'agence immobilière proche' (position 14.3 → opportunité).",
            "Étoffer les pages de blog avec une FAQ structurée pour viser les AI Overviews.",
            "Ajouter du contenu de comparaison (tableau) sur 'location courte durée'.",
        ],
    }


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------
@api.get("/dashboard/stats")
async def dashboard_stats(site_id: Optional[str] = None, user=Depends(get_current_user)):
    site_query: Dict[str, Any] = {"user_id": user["id"]}
    if site_id:
        site_query["site_id"] = site_id
    sites_count = await db.sites.count_documents({"user_id": user["id"]})
    drafts_count = await db.drafts.count_documents(site_query)
    published_count = await db.drafts.count_documents({**site_query, "status": "published"})
    last_audit = None
    aq: Dict[str, Any] = {"user_id": user["id"]}
    if site_id:
        aq["site_id"] = site_id
    last = await db.audits.find_one(aq, {"_id": 0}, sort=[("created_at", -1)])
    if last:
        last_audit = {"id": last["id"], "score": last["score"], "created_at": last["created_at"], "total_pages": last["total_pages"]}
    return {
        "sites": sites_count,
        "drafts": drafts_count,
        "published": published_count,
        "last_audit": last_audit,
    }


@api.get("/agents/overview")
async def agents_overview(site_id: Optional[str] = None, user=Depends(get_current_user)):
    """Aggregated data powering the '4 Agents' dashboard (SEO, GEO, Content, Social)."""
    uid = user["id"]
    sq: Dict[str, Any] = {"user_id": uid}
    if site_id:
        sq["site_id"] = site_id

    udoc = await db.users.find_one(
        {"id": uid}, {"google_oauth": 1, "linkedin": 1, "meta": 1, "gbp": 1, "_id": 0}
    ) or {}

    # --- SEO Agent ---
    last_audit = await db.audits.find_one(
        sq, {"_id": 0, "id": 1, "score": 1, "total_pages": 1, "issues": 1, "created_at": 1},
        sort=[("created_at", -1)],
    )
    rank_drops = []
    tracked_keywords = 0
    if site_id:
        dates = sorted(await db.rank_snapshots.distinct(
            "snapshot_date", {"user_id": uid, "site_id": site_id}))
        if dates:
            curr = await db.rank_snapshots.find(
                {"user_id": uid, "site_id": site_id, "snapshot_date": dates[-1]}, {"_id": 0}
            ).to_list(2000)
            tracked_keywords = len(curr)
            if len(dates) >= 2:
                prev_docs = await db.rank_snapshots.find(
                    {"user_id": uid, "site_id": site_id, "snapshot_date": dates[-2]}, {"_id": 0}
                ).to_list(2000)
                prev = {s["keyword"]: s.get("position") for s in prev_docs}
                for s in curr:
                    p = prev.get(s["keyword"])
                    if p and s.get("position") and s["position"] - p >= 3:
                        rank_drops.append({
                            "keyword": s["keyword"],
                            "from": round(p, 1),
                            "to": round(s["position"], 1),
                        })
                rank_drops.sort(key=lambda x: -(x["to"] - x["from"]))
                rank_drops = rank_drops[:5]
    seo = {
        "audit": ({"score": last_audit["score"], "total_pages": last_audit.get("total_pages"),
                   "issues_count": len(last_audit.get("issues") or []),
                   "created_at": last_audit["created_at"]} if last_audit else None),
        "saved_keywords": await db.saved_keywords.count_documents(sq),
        "gsc_connected": bool(udoc.get("google_oauth")),
        "tracked_keywords": tracked_keywords,
        "rank_drops": rank_drops,
    }

    # --- GEO Agent (AI Visibility) ---
    geo_rep = await db.ai_visibility_reports.find_one(
        sq, {"_id": 0, "global_score": 1, "created_at": 1, "priority_actions": 1},
        sort=[("created_at", -1)],
    )
    geo = {
        "report": ({"global_score": geo_rep.get("global_score"), "created_at": geo_rep["created_at"]}
                   if geo_rep else None),
        "actions": [
            {"action": a.get("action"), "impact": a.get("impact"), "estimated_gain": a.get("estimated_gain")}
            for a in (geo_rep or {}).get("priority_actions", [])[:3]
        ],
    }

    # --- Content Agent ---
    ws = await _get_or_create_workspace(user)
    plan = PLANS.get(ws.get("plan", "free"), PLANS["free"])
    used = await _count_articles_this_month(uid)
    last_draft = await db.drafts.find_one(
        sq, {"_id": 0, "id": 1, "title": 1, "status": 1, "updated_at": 1},
        sort=[("updated_at", -1)],
    )
    content = {
        "pending": await db.drafts.count_documents({**sq, "status": {"$in": ["draft", "ready"]}}),
        "published": await db.drafts.count_documents({**sq, "status": "published"}),
        "last_draft": last_draft,
        "quota": {"used": used, "limit": plan["articles_per_month"], "plan": plan["name"]},
    }

    # --- Social Agent ---
    async def _net(field: str, connected: bool):
        count = await db.drafts.count_documents({**sq, field: {"$exists": True, "$nin": [None, ""]}})
        last = await db.drafts.find_one(
            {**sq, field: {"$exists": True, "$nin": [None, ""]}},
            {"_id": 0, field: 1}, sort=[(field, -1)],
        )
        return {"connected": connected, "posts": count, "last_posted_at": (last or {}).get(field)}

    meta_connected = bool((udoc.get("meta") or {}).get("user_token"))
    has_ig = any(p.get("instagram_id") for p in (udoc.get("meta") or {}).get("pages", []))
    social = {
        "networks": {
            "linkedin": await _net("linkedin_posted_at", bool((udoc.get("linkedin") or {}).get("access_token"))),
            "facebook": await _net("facebook_posted_at", meta_connected),
            "instagram": await _net("instagram_posted_at", meta_connected and has_ig),
            "gbp": await _net("gbp_posted_at", bool((udoc.get("gbp") or {}).get("refresh_token"))),
        },
    }
    social["connected_count"] = sum(1 for n in social["networks"].values() if n["connected"])
    social["total_posts"] = sum(n["posts"] for n in social["networks"].values())

    return {"seo": seo, "geo": geo, "content": content, "social": social}


