from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
import re
from app_core import EMERGENT_LLM_KEY, api, db, gen_id, get_current_user, logger, now_iso
from routes_sites import _get_user_site

# ---------------------------------------------------------------------------
# Keyword Research (Claude-powered)
# ---------------------------------------------------------------------------
class KeywordResearchRequest(BaseModel):
    site_id: str
    theme: str
    city: Optional[str] = None
    competitors: Optional[List[str]] = None


class KeywordCluster(BaseModel):
    intent: Literal["locale", "informationnelle", "transactionnelle", "navigationnelle"]
    intent_label: str
    keywords: List[Dict[str, Any]]


class KeywordResearchResponse(BaseModel):
    id: str
    site_id: str
    theme: str
    city: Optional[str] = None
    clusters: List[KeywordCluster]
    summary: str
    created_at: str


class SavedKeywordCreate(BaseModel):
    site_id: str
    keyword: str
    intent: str
    priority: Literal["high", "medium", "low"] = "medium"
    notes: Optional[str] = None


class SavedKeywordPublic(BaseModel):
    id: str
    site_id: str
    keyword: str
    intent: str
    priority: str
    notes: Optional[str] = None
    created_at: str


KEYWORD_SYSTEM = """Tu es expert SEO senior français, spécialisé immobilier et services aux entreprises.
Tu génères des recherches de mots-clés concrètes, actionnables, focalisées sur la première page Google.

RÈGLES OBLIGATOIRES :
1. Toujours en français.
2. Mots-clés réels, recherchés par les utilisateurs (pas de jargon interne).
3. 4 clusters par intention : locale, informationnelle, transactionnelle, navigationnelle.
4. Chaque mot-clé : difficulty (low/medium/high), volume_estimate (low/medium/high), priority (high/medium/low) + courte justification (1 phrase).
5. Mélange courte traîne + longue traîne (60% longue traîne car plus facile à ranker).
6. Toujours intégrer la ville si fournie dans les variantes locales.
7. JSON strict.

FORMAT JSON IMPOSÉ (aucun texte avant/après) :
{
  "summary": "Synthèse stratégique 2-3 phrases pointant les opportunités prioritaires.",
  "clusters": [
    {
      "intent": "locale",
      "intent_label": "Recherches locales",
      "keywords": [
        {"keyword": "...", "difficulty": "low|medium|high", "volume_estimate": "low|medium|high", "priority": "high|medium|low", "rationale": "..."}
      ]
    },
    {"intent": "informationnelle", "intent_label": "Recherches informationnelles", "keywords": [...]},
    {"intent": "transactionnelle", "intent_label": "Recherches transactionnelles", "keywords": [...]},
    {"intent": "navigationnelle", "intent_label": "Recherches navigationnelles / marque", "keywords": [...]}
  ]
}
Minimum 6 mots-clés par cluster."""


def _parse_llm_json(text: str) -> dict:
    import json
    s = text.strip() if isinstance(text, str) else str(text).strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            raise HTTPException(502, "Réponse IA non parsable")
        return json.loads(m.group(0))


@api.post("/keywords/research", response_model=KeywordResearchResponse)
async def keyword_research(req: KeywordResearchRequest, user=Depends(get_current_user)):
    site = await _get_user_site(req.site_id, user)
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore

    prompt = f"""Génère une recherche de mots-clés SEO pour le site "{site['name']}" ({site['label']}).

Thématique principale : {req.theme}
Ville / zone cible : {req.city or 'France (national)'}
Concurrents directs : {', '.join(req.competitors) if req.competitors else '(non précisés)'}

Objectif : aider ce site à atteindre la première page Google rapidement.
Privilégie la longue traîne (>3 mots) plus facile à ranker.
Réponds en JSON strict selon le format imposé."""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"kw-{user['id']}-{gen_id()}",
        system_message=KEYWORD_SYSTEM,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    try:
        response = await chat.send_message(UserMessage(text=prompt))
    except Exception as exc:
        logger.exception("Keyword LLM call failed")
        raise HTTPException(502, f"Erreur recherche mots-clés : {exc}")

    data = _parse_llm_json(response if isinstance(response, str) else str(response))
    clusters_raw = data.get("clusters", [])
    clusters = []
    for c in clusters_raw:
        clusters.append(KeywordCluster(
            intent=c.get("intent", "informationnelle"),
            intent_label=c.get("intent_label", c.get("intent", "")),
            keywords=c.get("keywords", []),
        ))
    doc = {
        "id": gen_id(),
        "user_id": user["id"],
        "site_id": req.site_id,
        "theme": req.theme,
        "city": req.city,
        "summary": data.get("summary", ""),
        "clusters": [c.model_dump() for c in clusters],
        "created_at": now_iso(),
    }
    await db.keyword_research.insert_one(doc)
    return KeywordResearchResponse(**{k: v for k, v in doc.items() if k != "user_id"})


@api.get("/keywords/research")
async def list_keyword_research(site_id: Optional[str] = None, user=Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if site_id:
        q["site_id"] = site_id
    items = await db.keyword_research.find(q, {"_id": 0, "user_id": 0}).sort("created_at", -1).to_list(50)
    return {"items": items}


@api.post("/keywords/saved", response_model=SavedKeywordPublic)
async def save_keyword(payload: SavedKeywordCreate, user=Depends(get_current_user)):
    await _get_user_site(payload.site_id, user)
    existing = await db.saved_keywords.find_one({
        "user_id": user["id"],
        "site_id": payload.site_id,
        "keyword": payload.keyword.strip().lower(),
    })
    if existing:
        raise HTTPException(409, "Ce mot-clé est déjà dans votre liste")
    doc = {
        "id": gen_id(),
        "user_id": user["id"],
        "site_id": payload.site_id,
        "keyword": payload.keyword.strip().lower(),
        "intent": payload.intent,
        "priority": payload.priority,
        "notes": payload.notes,
        "created_at": now_iso(),
    }
    await db.saved_keywords.insert_one(doc)
    return SavedKeywordPublic(**{k: v for k, v in doc.items() if k != "user_id"})


class BatchKeywordsRequest(BaseModel):
    keywords: List[SavedKeywordCreate]


@api.post("/keywords/saved/batch")
async def batch_save_keywords(payload: BatchKeywordsRequest, user=Depends(get_current_user)):
    added = 0
    skipped = 0
    for kw in payload.keywords:
        await _get_user_site(kw.site_id, user)
        existing = await db.saved_keywords.find_one({
            "user_id": user["id"],
            "site_id": kw.site_id,
            "keyword": kw.keyword.strip().lower(),
        })
        if existing:
            skipped += 1
            continue
        doc = {
            "id": gen_id(),
            "user_id": user["id"],
            "site_id": kw.site_id,
            "keyword": kw.keyword.strip().lower(),
            "intent": kw.intent,
            "priority": kw.priority,
            "notes": kw.notes,
            "created_at": now_iso(),
        }
        await db.saved_keywords.insert_one(doc)
        added += 1
    return {"added": added, "skipped": skipped}


@api.get("/keywords/saved", response_model=List[SavedKeywordPublic])
async def list_saved_keywords(site_id: Optional[str] = None, user=Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if site_id:
        q["site_id"] = site_id
    items = await db.saved_keywords.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [SavedKeywordPublic(**{k: v for k, v in d.items() if k != "user_id"}) for d in items]


@api.delete("/keywords/saved/{kw_id}")
async def delete_saved_keyword(kw_id: str, user=Depends(get_current_user)):
    res = await db.saved_keywords.delete_one({"id": kw_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Mot-clé introuvable")
    return {"ok": True}


