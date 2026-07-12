"""Keyword Intelligence Engine 2.0 — analyse business + intelligence mots-clés complète.

Pipeline :
1. Crawl des pages clés (réutilise ai_visibility.fetch_pages)
2. Appel LLM 1 — Business Profile : l'IA comprend l'entreprise (activité, produits,
   cibles, villes, concurrents, positionnement) → réutilisable par l'AI Business Analyzer
3. Appel LLM 2 — Intelligence mots-clés : clusters scorés (potentiel, difficulté,
   rentabilité), quick wins, plan de contenu, pages locales manquantes, concurrents
"""
import json
import logging
import re
from typing import List, Optional

from ai_visibility import fetch_pages, _parse_llm_json

logger = logging.getLogger("kw-intelligence")

MODEL = ("anthropic", "claude-sonnet-4-5-20250929")


async def _llm(prompt: str, session_id: str, llm_key: str) -> dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    chat = LlmChat(
        api_key=llm_key,
        session_id=session_id,
        system_message="Tu es un expert en stratégie SEO/marketing. Tu réponds uniquement en JSON strict valide, sans texte hors JSON.",
    ).with_model(*MODEL)
    resp = await chat.send_message(UserMessage(text=prompt))
    return _parse_llm_json(resp if isinstance(resp, str) else str(resp))


async def build_business_profile(site: dict, pages: List[dict], llm_key: str) -> dict:
    excerpts = "\n\n".join(f"URL: {p['url']}\n{p['text'][:1800]}" for p in pages[:3])
    prompt = f"""Analyse cette entreprise à partir de son site web.

SITE : {site.get('name')} — {site.get('base_url')}

CONTENU DU SITE :
{excerpts}

Réponds en JSON STRICT :
{{
  "activity": "activité principale en 3-6 mots",
  "description": "description de l'entreprise en 2-3 phrases",
  "products_services": ["liste des produits/services identifiés"],
  "target_audience": ["segments de clientèle cible"],
  "cities_zones": ["villes/régions/pays desservis identifiés ou probables"],
  "positioning": "positionnement et proposition de valeur en 1-2 phrases",
  "business_model": "B2B|B2C|B2B2C|mixte",
  "language": "langue principale du site",
  "likely_competitors": ["3-6 concurrents réels probables (noms d'entreprises ou de produits connus sur ce marché)"],
  "differentiators": ["éléments différenciants détectés"]
}}"""
    return await _llm(prompt, f"bizprofile-{site.get('id')}", llm_key)


async def build_keyword_intelligence(site: dict, profile: dict, saved_keywords: List[str], llm_key: str) -> dict:
    prompt = f"""Tu es le meilleur stratège SEO du marché. Voici le profil d'une entreprise. Produis une analyse mots-clés COMPLÈTE et ACTIONNABLE.

PROFIL ENTREPRISE :
{json.dumps(profile, ensure_ascii=False, indent=2)}

SITE : {site.get('name')} — {site.get('base_url')}
MOTS-CLÉS DÉJÀ SUIVIS PAR L'UTILISATEUR : {', '.join(saved_keywords) if saved_keywords else 'aucun'}

CONSIGNES :
- Mots-clés dans la langue du site, adaptés à sa zone géographique réelle.
- "potential" = potentiel business (volume × pertinence × conversion), 0-100.
- "difficulty" = difficulté à ranker (low = facile à conquérir).
- Les quick_wins sont des mots-clés à difficulté low/medium avec potential ≥ 55.
- Le content_plan doit couvrir : articles, pages locales, FAQ, pages service.
- content_plan[].type DOIT être exactement l'un de : "article", "page_locale", "faq", "service_description".
- clusters[].intent DOIT être exactement l'un de : "locale", "informationnelle", "transactionnelle", "navigationnelle".

Réponds en JSON STRICT :
{{
  "summary": "synthèse stratégique en 3-4 phrases : où sont les meilleures opportunités et pourquoi",
  "clusters": [
    {{
      "name": "nom du cluster",
      "intent": "locale|informationnelle|transactionnelle|navigationnelle",
      "priority": "high|medium|low",
      "why": "pourquoi ce cluster est stratégique en 1 phrase",
      "keywords": [
        {{"keyword": "...", "potential": 0-100, "difficulty": "low|medium|high", "profitability": "élevée|moyenne|faible", "est_volume": "élevé|moyen|faible", "quick_win": true|false, "reason": "justification courte"}}
      ]
    }}
  ],
  "quick_wins": [{{"keyword": "...", "cluster": "nom du cluster", "why": "pourquoi facile à conquérir + gain attendu"}}],
  "top_opportunities": [{{"keyword": "...", "potential": 0-100, "why": "pourquoi c'est le meilleur potentiel business"}}],
  "content_plan": [
    {{"type": "article|page_locale|faq|service_description", "title": "titre proposé", "target_keywords": ["..."], "city": "ville ou null", "why": "objectif de ce contenu", "expected_impact": "élevé|moyen|faible"}}
  ],
  "missing_local_pages": [{{"city": "...", "service": "...", "suggested_title": "...", "target_keyword": "..."}}],
  "competitors": [{{"name": "...", "domain": "domaine si connu ou null", "strengths": "où il domine", "opportunity": "comment le dépasser"}}]
}}
Donne 4-6 clusters de 4-6 mots-clés, 5-8 quick_wins, 5 top_opportunities, 6-10 items de content_plan, 3-8 missing_local_pages (ou [] si non pertinent), 3-6 competitors."""
    return await _llm(prompt, f"kwintel-{site.get('id')}", llm_key)


VALID_INTENTS = {"locale", "informationnelle", "transactionnelle", "navigationnelle"}
VALID_TYPES = {"article", "page_locale", "faq", "service_description"}


def _sanitize(report: dict) -> dict:
    for c in report.get("clusters", []):
        if c.get("intent") not in VALID_INTENTS:
            c["intent"] = "informationnelle"
        for k in c.get("keywords", []):
            try:
                k["potential"] = max(0, min(100, int(k.get("potential", 50))))
            except Exception:
                k["potential"] = 50
    report["content_plan"] = [p for p in report.get("content_plan", []) if p.get("type") in VALID_TYPES]
    return report


async def run_keyword_intelligence(site: dict, saved_keywords: List[str], llm_key: str, existing_profile: Optional[dict] = None) -> dict:
    if existing_profile:
        profile = existing_profile
        pages_urls: List[str] = []
    else:
        pages = await fetch_pages(site.get("base_url") or "")
        if not pages:
            raise RuntimeError(f"Impossible de récupérer les pages de {site.get('base_url') or 'ce site'} — vérifiez l'URL publique du site.")
        profile = await build_business_profile(site, pages, llm_key)
        pages_urls = [p["url"] for p in pages]
    intelligence = await build_keyword_intelligence(site, profile, saved_keywords, llm_key)
    report = _sanitize(intelligence)
    report["business_profile"] = profile
    report["pages_analyzed"] = pages_urls
    return report
