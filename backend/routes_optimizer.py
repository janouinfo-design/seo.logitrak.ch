from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from app_core import EMERGENT_LLM_KEY, api, db, gen_id, get_current_user, logger, now_iso
from routes_sites import _get_user_site, fetch_wix_pages
from routes_keywords import _parse_llm_json

# ---------------------------------------------------------------------------
# Page Optimizer (existing Wix pages) — current vs suggested
# ---------------------------------------------------------------------------
class PageOptimizeRequest(BaseModel):
    site_id: str
    page_id: str
    focus_keyword: Optional[str] = None
    city: Optional[str] = None


class PageOptimizationResult(BaseModel):
    id: str
    site_id: str
    page_id: str
    page_url: str
    focus_keyword: Optional[str]
    current: Dict[str, Any]
    suggested: Dict[str, Any]
    improvements: List[str]
    diff_summary: str
    created_at: str
    applied: bool = False
    wix_updated: bool = False
    draft_id: Optional[str] = None


OPTIMIZER_SYSTEM = """Tu es expert SEO on-page senior français.
Tu analyses une page existante et proposes UNE version optimisée concrète, prête à publier.

Objectifs :
- Atteindre la première page Google sur le mot-clé cible.
- Optimiser également pour les IA (ChatGPT, Gemini, Perplexity, AI Overviews) → réponse courte en intro, FAQ, structure claire.
- Conserver le ton et l'identité du site, ne pas hallucinations sur des chiffres.

RÈGLES OBLIGATOIRES :
1. Le titre SEO doit faire 50-60 caractères, contenir le mot-clé focus, et inclure la ville si fournie.
2. La meta description doit faire 140-160 caractères avec un appel à l'action.
3. UN seul H1, ciblé sur le mot-clé focus.
4. 3-5 H2 structurés par sous-thème.
5. Plan de contenu détaillé : intro réponse courte (2 phrases), sections, FAQ (4-6 questions), tableau comparatif si pertinent.
6. Lister 4-6 améliorations concrètes avec leur impact attendu.
7. JSON strict, aucun texte hors JSON.

FORMAT JSON IMPOSÉ :
{
  "suggested": {
    "title": "...",
    "meta_title": "...",
    "meta_description": "...",
    "h1": "...",
    "h2_plan": ["H2 1", "H2 2", ...],
    "intro_short_answer": "Réponse courte de 2-3 phrases optimisée AI Overviews.",
    "faq_suggested": [{"question": "...", "answer": "..."}],
    "content_outline": "Plan détaillé en markdown avec sections, points clés, tableau comparatif si pertinent."
  },
  "improvements": [
    "Concise et concrète. Ex: 'Titre allongé de 28 → 58 caractères pour intégrer le mot-clé et la ville.'"
  ],
  "diff_summary": "Synthèse 1-2 phrases du gain SEO attendu."
}"""


@api.post("/pages/optimize", response_model=PageOptimizationResult)
async def optimize_page(req: PageOptimizeRequest, user=Depends(get_current_user)):
    site = await _get_user_site(req.site_id, user)
    pages = await fetch_wix_pages(site)
    page = next((p for p in pages if p["id"] == req.page_id), None)
    if not page:
        raise HTTPException(404, "Page introuvable")

    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore

    current = {
        "title": page.get("title"),
        "meta_title": page.get("meta_title"),
        "meta_description": page.get("meta_description"),
        "h1": page.get("h1") or [],
        "h2": page.get("h2") or [],
        "word_count": page.get("word_count"),
        "images_without_alt": page.get("images_without_alt", 0),
        "url": page.get("url"),
    }

    prompt = f"""Analyse cette page Wix existante du site "{site['name']}" ({site['label']}) et propose une version optimisée.

URL : {current['url']}
Mot-clé focus : {req.focus_keyword or '(à déterminer en fonction du contenu)'}
Ville / zone cible : {req.city or 'France (national)'}

VERSION ACTUELLE :
- Titre page : {current['title']}
- Meta title : {current['meta_title'] or '(absent)'}
- Meta description : {current['meta_description'] or '(absente)'}
- H1 : {', '.join(current['h1']) or '(aucun)'}
- H2 : {', '.join(current['h2']) or '(aucun)'}
- Nombre de mots : {current['word_count']}
- Images sans alt : {current['images_without_alt']}

Propose une version optimisée pour ranker en première page Google sur le mot-clé focus, et aussi pour AI Overviews. Réponds en JSON strict."""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"opt-{user['id']}-{gen_id()}",
        system_message=OPTIMIZER_SYSTEM,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    try:
        response = await chat.send_message(UserMessage(text=prompt))
    except Exception as exc:
        logger.exception("Optimizer LLM call failed")
        raise HTTPException(502, f"Erreur optimiseur : {exc}")

    data = _parse_llm_json(response if isinstance(response, str) else str(response))
    suggested = data.get("suggested", {})
    improvements = data.get("improvements", [])
    diff_summary = data.get("diff_summary", "")

    doc = {
        "id": gen_id(),
        "user_id": user["id"],
        "site_id": req.site_id,
        "page_id": req.page_id,
        "page_url": current["url"] or "",
        "focus_keyword": req.focus_keyword,
        "current": current,
        "suggested": suggested,
        "improvements": improvements,
        "diff_summary": diff_summary,
        "applied": False,
        "wix_updated": False,
        "created_at": now_iso(),
    }
    await db.page_optimizations.insert_one(doc)
    return PageOptimizationResult(**{k: v for k, v in doc.items() if k != "user_id"})


@api.get("/pages/optimizations", response_model=List[PageOptimizationResult])
async def list_optimizations(site_id: Optional[str] = None, user=Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if site_id:
        q["site_id"] = site_id
    items = await db.page_optimizations.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [PageOptimizationResult(**{k: v for k, v in d.items() if k != "user_id"}) for d in items]


@api.get("/pages/optimizations/{opt_id}", response_model=PageOptimizationResult)
async def get_optimization(opt_id: str, user=Depends(get_current_user)):
    d = await db.page_optimizations.find_one({"id": opt_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Optimisation introuvable")
    return PageOptimizationResult(**{k: v for k, v in d.items() if k != "user_id"})


@api.post("/pages/optimizations/{opt_id}/apply", response_model=PageOptimizationResult)
async def apply_optimization(opt_id: str, user=Depends(get_current_user)):
    """Mark optimization as applied and create a corresponding draft for the new content.
    Idempotent: re-calling returns the existing draft_id."""
    d = await db.page_optimizations.find_one({"id": opt_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Optimisation introuvable")
    if d.get("applied") and d.get("draft_id"):
        return PageOptimizationResult(**{k: v for k, v in d.items() if k != "user_id"})
    suggested = d["suggested"] or {}
    # Build body markdown combining intro + outline + FAQ
    body_parts = []
    if suggested.get("intro_short_answer"):
        body_parts.append(suggested["intro_short_answer"])
    if suggested.get("content_outline"):
        body_parts.append(suggested["content_outline"])
    faq = suggested.get("faq_suggested") or []
    if faq:
        body_parts.append("## FAQ")
        for q in faq:
            body_parts.append(f"### {q.get('question','')}\n{q.get('answer','')}")
    body_md = "\n\n".join(p.strip() for p in body_parts if p and p.strip())

    draft = {
        "id": gen_id(),
        "user_id": user["id"],
        "site_id": d["site_id"],
        "content_type": "page_optimization",
        "title": suggested.get("h1") or suggested.get("title") or "Optimisation de page",
        "meta_title": suggested.get("meta_title"),
        "meta_description": suggested.get("meta_description"),
        "body_markdown": body_md,
        "keywords": [d.get("focus_keyword")] if d.get("focus_keyword") else [],
        "faq": faq,
        "status": "ready",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "wix_draft_id": None,
        "wix_published_at": None,
    }
    await db.drafts.insert_one(draft)
    await db.page_optimizations.update_one(
        {"id": opt_id, "user_id": user["id"]},
        {"$set": {"applied": True, "draft_id": draft["id"]}},
    )
    d["applied"] = True
    d["draft_id"] = draft["id"]
    return PageOptimizationResult(**{k: v for k, v in d.items() if k != "user_id"})


