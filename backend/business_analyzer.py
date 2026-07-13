"""AI Business Analyzer — l'IA comprend l'entreprise en profondeur avant toute recommandation.

Produit un profil business complet (activité, offres, cibles, zones, concurrents,
positionnement, SWOT, priorités marketing) stocké dans `business_profiles` et
réutilisé par Keyword Intelligence et les futurs agents IA.
"""
import json
import logging
from typing import List

from ai_visibility import fetch_pages, _parse_llm_json

logger = logging.getLogger("business-analyzer")


async def run_business_analysis(site: dict, llm_key: str) -> dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    pages = await fetch_pages(site.get("base_url") or "", max_pages=8)
    if not pages:
        raise RuntimeError(f"Impossible de récupérer les pages de {site.get('base_url') or 'ce site'} — vérifiez l'URL publique du site.")

    excerpts = "\n\n".join(f"URL: {p['url']}\n{p['text'][:1400]}" for p in pages[:5])
    prompt = f"""Tu es un directeur marketing senior. Analyse cette entreprise en profondeur à partir de son site web.

SITE : {site.get('name')} — {site.get('base_url')}

CONTENU DU SITE :
{excerpts}

Réponds en JSON STRICT (aucun texte hors JSON) :
{{
  "activity": "activité principale en 3-6 mots",
  "description": "description complète de l'entreprise en 3-4 phrases",
  "business_model": "B2B|B2C|B2B2C|mixte",
  "language": "langue principale",
  "tone_of_voice": "ton de communication détecté (ex: professionnel et technique)",
  "products_services": [{{"name": "...", "description": "1 phrase", "target": "à qui ça s'adresse"}}],
  "target_segments": [{{"segment": "nom du segment", "needs": "besoins principaux", "message": "message marketing qui résonnerait"}}],
  "cities_zones": ["villes/régions/pays desservis, identifiés ou probables"],
  "positioning": "positionnement en 1-2 phrases",
  "value_props": ["propositions de valeur clés"],
  "differentiators": ["éléments différenciants réels détectés"],
  "competitors": [{{"name": "...", "domain": "domaine si connu ou null", "positioning": "son positionnement", "strengths": "ses forces", "weaknesses": "ses faiblesses", "how_to_beat": "comment le dépasser concrètement"}}],
  "swot": {{
    "strengths": ["forces"],
    "weaknesses": ["faiblesses"],
    "opportunities": ["opportunités marché"],
    "threats": ["menaces"]
  }},
  "marketing_priorities": [{{"priority": "action marketing prioritaire", "why": "justification", "impact": "élevé|moyen|faible"}}]
}}
Donne 3-6 products_services, 2-4 target_segments, 3-6 concurrents RÉELS probables sur ce marché, 3-5 items par volet SWOT, 3-5 marketing_priorities triées par impact."""

    chat = LlmChat(
        api_key=llm_key,
        session_id=f"bizanalyzer-{site.get('id')}",
        system_message="Tu es un directeur marketing expert. Tu réponds uniquement en JSON strict valide.",
    ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=12000)
    profile = None
    last_err = None
    for attempt in range(2):
        resp = await chat.send_message(UserMessage(text=prompt))
        try:
            profile = _parse_llm_json(resp if isinstance(resp, str) else str(resp))
            break
        except (ValueError, json.JSONDecodeError) as exc:
            last_err = exc
            logger.warning("JSON invalide (tentative %s/2) : %s", attempt + 1, exc)
    if profile is None:
        raise RuntimeError(f"Réponse IA invalide après 2 tentatives : {last_err}")
    return {"profile": profile, "pages_analyzed": [p["url"] for p in pages]}
