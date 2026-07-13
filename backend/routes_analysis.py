from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any
from typing import Dict
import asyncio
import json
from app_core import EMERGENT_LLM_KEY, api, db, gen_id, get_current_user, logger, now_iso
from routes_sites import _get_user_site

# ---------------------------------------------------------------------------
# AI Visibility Center (GEO — Generative Engine Optimization)
# ---------------------------------------------------------------------------
@api.post("/sites/{site_id}/ai-visibility")
async def start_ai_visibility(site_id: str, user=Depends(get_current_user)):
    """Lance une analyse AI Visibility asynchrone. Poll via /content/jobs/{job_id}."""
    site = await _get_user_site(site_id, user)
    job_id = gen_id()
    await db.generation_jobs.insert_one({
        "id": job_id,
        "user_id": user["id"],
        "type": "ai_visibility",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_iso(),
        "completed_at": None,
    })

    async def _bg():
        try:
            from ai_visibility import run_ai_visibility_analysis
            report = await run_ai_visibility_analysis(site, EMERGENT_LLM_KEY)
            report.update({
                "id": gen_id(),
                "site_id": site_id,
                "site_name": site.get("name"),
                "created_at": now_iso(),
            })
            await db.ai_visibility_reports.insert_one({**report, "user_id": user["id"]})
            await db.generation_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "completed", "result": report, "completed_at": now_iso()}},
            )
        except Exception as exc:
            logger.exception("AI visibility analysis failed")
            await db.generation_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "failed", "error": str(exc), "completed_at": now_iso()}},
            )

    asyncio.create_task(_bg())
    return {"job_id": job_id, "status": "pending"}


@api.get("/sites/{site_id}/ai-visibility/latest")
async def get_latest_ai_visibility(site_id: str, user=Depends(get_current_user)):
    await _get_user_site(site_id, user)
    rep = await db.ai_visibility_reports.find_one(
        {"site_id": site_id, "user_id": user["id"]}, {"_id": 0, "user_id": 0}, sort=[("created_at", -1)]
    )
    return rep or {}


@api.get("/sites/{site_id}/ai-visibility/history")
async def get_ai_visibility_history(site_id: str, user=Depends(get_current_user)):
    await _get_user_site(site_id, user)
    return await db.ai_visibility_reports.find(
        {"site_id": site_id, "user_id": user["id"]},
        {"_id": 0, "created_at": 1, "global_score": 1, "scores": 1},
    ).sort("created_at", -1).to_list(30)


# ---------------------------------------------------------------------------
# Keyword Intelligence Engine 2.0
# ---------------------------------------------------------------------------
@api.post("/sites/{site_id}/keyword-intelligence")
async def start_keyword_intelligence(site_id: str, user=Depends(get_current_user)):
    """Lance une analyse Keyword Intelligence asynchrone. Poll via /content/jobs/{job_id}."""
    site = await _get_user_site(site_id, user)
    job_id = gen_id()
    await db.generation_jobs.insert_one({
        "id": job_id,
        "user_id": user["id"],
        "type": "keyword_intelligence",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_iso(),
        "completed_at": None,
    })

    async def _bg():
        try:
            from keyword_intelligence import run_keyword_intelligence
            saved = await db.saved_keywords.find({"site_id": site_id, "user_id": user["id"]}, {"keyword": 1}).to_list(100)
            prof_doc = await db.business_profiles.find_one({"site_id": site_id, "user_id": user["id"]})
            report = await run_keyword_intelligence(
                site, [s["keyword"] for s in saved], EMERGENT_LLM_KEY,
                existing_profile=(prof_doc or {}).get("profile"),
            )
            report.update({
                "id": gen_id(),
                "site_id": site_id,
                "site_name": site.get("name"),
                "created_at": now_iso(),
            })
            await db.keyword_intelligence_reports.insert_one({**report, "user_id": user["id"]})
            if not prof_doc:
                await db.business_profiles.update_one(
                    {"site_id": site_id, "user_id": user["id"]},
                    {"$set": {"profile": report.get("business_profile"), "source": "keyword_intelligence", "updated_at": now_iso()}},
                    upsert=True,
                )
            await db.generation_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "completed", "result": report, "completed_at": now_iso()}},
            )
        except Exception as exc:
            logger.exception("Keyword intelligence analysis failed")
            await db.generation_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "failed", "error": str(exc), "completed_at": now_iso()}},
            )

    asyncio.create_task(_bg())
    return {"job_id": job_id, "status": "pending"}


@api.get("/sites/{site_id}/keyword-intelligence/latest")
async def get_latest_keyword_intelligence(site_id: str, user=Depends(get_current_user)):
    await _get_user_site(site_id, user)
    rep = await db.keyword_intelligence_reports.find_one(
        {"site_id": site_id, "user_id": user["id"]}, {"_id": 0, "user_id": 0}, sort=[("created_at", -1)]
    )
    return rep or {}


# ---------------------------------------------------------------------------
# AI Business Analyzer
# ---------------------------------------------------------------------------
@api.post("/sites/{site_id}/business-analyzer")
async def start_business_analysis(site_id: str, user=Depends(get_current_user)):
    """Lance une analyse business approfondie asynchrone. Poll via /content/jobs/{job_id}."""
    site = await _get_user_site(site_id, user)
    job_id = gen_id()
    await db.generation_jobs.insert_one({
        "id": job_id,
        "user_id": user["id"],
        "type": "business_analyzer",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_iso(),
        "completed_at": None,
    })

    async def _bg():
        try:
            from business_analyzer import run_business_analysis
            res = await run_business_analysis(site, EMERGENT_LLM_KEY)
            doc = {
                "profile": res["profile"],
                "pages_analyzed": res["pages_analyzed"],
                "source": "analyzer",
                "edited": False,
                "updated_at": now_iso(),
            }
            await db.business_profiles.update_one(
                {"site_id": site_id, "user_id": user["id"]},
                {"$set": doc},
                upsert=True,
            )
            await db.generation_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "completed", "result": {**doc, "site_id": site_id}, "completed_at": now_iso()}},
            )
        except Exception as exc:
            logger.exception("Business analysis failed")
            await db.generation_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "failed", "error": str(exc), "completed_at": now_iso()}},
            )

    asyncio.create_task(_bg())
    return {"job_id": job_id, "status": "pending"}


@api.get("/sites/{site_id}/business-profile")
async def get_business_profile(site_id: str, user=Depends(get_current_user)):
    await _get_user_site(site_id, user)
    doc = await db.business_profiles.find_one(
        {"site_id": site_id, "user_id": user["id"]}, {"_id": 0, "user_id": 0}
    )
    return doc or {}


class BusinessProfileUpdate(BaseModel):
    profile: Dict[str, Any]


@api.put("/sites/{site_id}/business-profile")
async def update_business_profile(site_id: str, payload: BusinessProfileUpdate, user=Depends(get_current_user)):
    await _get_user_site(site_id, user)
    doc = await db.business_profiles.find_one({"site_id": site_id, "user_id": user["id"]})
    merged = {**((doc or {}).get("profile") or {}), **payload.profile}
    await db.business_profiles.update_one(
        {"site_id": site_id, "user_id": user["id"]},
        {"$set": {"profile": merged, "edited": True, "updated_at": now_iso()}},
        upsert=True,
    )
    return {"profile": merged, "edited": True}


# ---------------------------------------------------------------------------
# Suggestions de sujets (villes ciblées auto) pour le Générateur
# ---------------------------------------------------------------------------
@api.get("/sites/{site_id}/content-suggestions")
async def get_content_suggestions(site_id: str, content_type: str = "article", user=Depends(get_current_user)):
    """Propose des sujets adaptés au type de contenu, avec villes ciblées automatiquement.
    Source 1 : rapport Keyword Intelligence (instantané). Source 2 : IA via profil business."""
    site = await _get_user_site(site_id, user)
    suggestions = []
    ki = await db.keyword_intelligence_reports.find_one(
        {"site_id": site_id, "user_id": user["id"]}, sort=[("created_at", -1)]
    )
    if ki:
        for p in ki.get("content_plan", []):
            if p.get("type") == content_type and p.get("title"):
                suggestions.append({
                    "topic": p["title"],
                    "city": p.get("city"),
                    "keywords": p.get("target_keywords") or [],
                    "why": p.get("why"),
                    "source": "keyword_intelligence",
                })
        if content_type == "page_locale":
            for lp in ki.get("missing_local_pages", []):
                if lp.get("suggested_title"):
                    suggestions.append({
                        "topic": lp["suggested_title"],
                        "city": lp.get("city"),
                        "keywords": [lp["target_keyword"]] if lp.get("target_keyword") else [],
                        "why": f"Page locale manquante — {lp.get('service', '')}",
                        "source": "keyword_intelligence",
                    })
    if len(suggestions) < 4:
        prof_doc = await db.business_profiles.find_one({"site_id": site_id, "user_id": user["id"]})
        profile = (prof_doc or {}).get("profile") or {}
        try:
            from keyword_intelligence import _llm
            type_label = {
                "article": "articles de blog",
                "page_locale": "pages locales SEO",
                "faq": "pages FAQ",
                "service_description": "pages de description de service",
            }.get(content_type, content_type)
            ctx = {k: profile.get(k) for k in ("activity", "description", "cities_zones", "positioning") if profile.get(k)}
            cities = ", ".join((profile.get("cities_zones") or [])[:8]) or "les villes pertinentes de son marché"
            prompt = f"""Entreprise : {json.dumps(ctx, ensure_ascii=False) if ctx else site.get('name')}
Site : {site.get('name')} — {site.get('base_url')}

Propose 6 sujets de {type_label} à fort potentiel SEO pour cette entreprise, en ciblant automatiquement ses villes/zones ({cities}). Sujets précis, prêts à générer, dans la langue du site.

Réponds en JSON STRICT :
{{"suggestions": [{{"topic": "titre précis", "city": "ville ciblée ou null", "keywords": ["2-3 mots-clés"], "why": "intérêt en 1 phrase"}}]}}"""
            res = await _llm(prompt, f"sugg-{site_id}-{content_type}", EMERGENT_LLM_KEY, max_tokens=3000, retries=2)
            for s in (res.get("suggestions") or [])[:6]:
                if s.get("topic"):
                    s["source"] = "ai"
                    suggestions.append(s)
        except Exception:
            logger.exception("Content suggestions LLM failed")
    return {"suggestions": suggestions[:8]}


# ---------------------------------------------------------------------------
# Pré-remplissage intelligent pour la recherche de mots-clés
# ---------------------------------------------------------------------------
@api.get("/sites/{site_id}/keyword-prefill")
async def get_keyword_prefill(site_id: str, user=Depends(get_current_user)):
    """Thématiques, zones (villes/régions/pays) et concurrents issus du profil business et du dernier rapport Keyword Intelligence."""
    await _get_user_site(site_id, user)
    prof = ((await db.business_profiles.find_one({"site_id": site_id, "user_id": user["id"]})) or {}).get("profile") or {}
    ki = await db.keyword_intelligence_reports.find_one(
        {"site_id": site_id, "user_id": user["id"]}, sort=[("created_at", -1)]
    ) or {}

    def dedupe(items):
        seen, out = set(), []
        for x in items:
            x = (x or "").strip()
            if x and x.lower() not in seen:
                seen.add(x.lower())
                out.append(x)
        return out

    themes = dedupe(
        [c.get("name") for c in ki.get("clusters", [])]
        + [ps.get("name") for ps in prof.get("products_services", [])]
        + [prof.get("activity")]
    )
    zones = dedupe(prof.get("cities_zones") or [])
    competitors = dedupe(
        [c.get("name") for c in prof.get("competitors", [])]
        + [c.get("name") for c in ki.get("competitors", [])]
    )
    return {"themes": themes[:8], "zones": zones[:10], "competitors": competitors[:10]}


# ---------------------------------------------------------------------------
# Analyse concurrentielle automatique
# ---------------------------------------------------------------------------
@api.post("/sites/{site_id}/competitor-analysis")
async def start_competitor_analysis(site_id: str, user=Depends(get_current_user)):
    """Lance une analyse concurrentielle asynchrone. Poll via /content/jobs/{job_id}."""
    site = await _get_user_site(site_id, user)
    prof_doc = await db.business_profiles.find_one({"site_id": site_id, "user_id": user["id"]})
    profile = (prof_doc or {}).get("profile") or {}
    if not profile.get("competitors"):
        raise HTTPException(400, "Aucun concurrent défini. Lancez d'abord le Business Analyzer, ou ajoutez vos concurrents via « Corriger ».")
    job_id = gen_id()
    await db.generation_jobs.insert_one({
        "id": job_id,
        "user_id": user["id"],
        "type": "competitor_analysis",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_iso(),
        "completed_at": None,
    })

    async def _bg():
        try:
            from competitor_analysis import run_competitor_analysis
            report = await run_competitor_analysis(site, profile, EMERGENT_LLM_KEY)
            report.update({
                "id": gen_id(),
                "site_id": site_id,
                "site_name": site.get("name"),
                "created_at": now_iso(),
            })
            await db.competitor_analysis_reports.insert_one({**report, "user_id": user["id"]})
            await db.generation_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "completed", "result": report, "completed_at": now_iso()}},
            )
        except Exception as exc:
            logger.exception("Competitor analysis failed")
            await db.generation_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "failed", "error": str(exc), "completed_at": now_iso()}},
            )

    asyncio.create_task(_bg())
    return {"job_id": job_id, "status": "pending"}


@api.get("/sites/{site_id}/competitor-analysis/latest")
async def get_latest_competitor_analysis(site_id: str, user=Depends(get_current_user)):
    await _get_user_site(site_id, user)
    rep = await db.competitor_analysis_reports.find_one(
        {"site_id": site_id, "user_id": user["id"]}, {"_id": 0, "user_id": 0}, sort=[("created_at", -1)]
    )
    return rep or {}
