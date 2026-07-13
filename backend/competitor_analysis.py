"""Analyse concurrentielle automatique — l'IA compare le site à ses vrais concurrents.

Produit : mots-clés dominés par chaque concurrent, contenus manquants (gaps),
avantages/faiblesses, et plan de bataille priorisé. Utilise le profil business
(concurrents corrigés par l'utilisateur en priorité) + snapshot des sites concurrents.
"""
import asyncio
import json
import logging

import httpx
from bs4 import BeautifulSoup

from ai_visibility import fetch_pages
from keyword_intelligence import _llm

logger = logging.getLogger("competitor-analysis")


async def _fetch_competitor_snapshot(name: str, domain: str):
    if not domain:
        return None
    url = domain if domain.startswith("http") else f"https://{domain}"
    try:
        async with httpx.AsyncClient(
            timeout=10, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LogiSEOBooster/1.0)"},
        ) as cli:
            r = await cli.get(url)
            if r.status_code >= 400:
                return None
            soup = BeautifulSoup(r.text, "lxml")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            meta = soup.find("meta", attrs={"name": "description"})
            return {
                "name": name,
                "url": url,
                "title": soup.title.get_text(strip=True) if soup.title else "",
                "description": meta.get("content", "") if meta else "",
                "headings": [h.get_text(strip=True) for h in soup.find_all(["h1", "h2"])][:10],
                "excerpt": " ".join(soup.get_text(" ", strip=True).split())[:1200],
            }
    except Exception as exc:
        logger.info("Snapshot concurrent échoué (%s): %s", name, exc)
        return None


async def run_competitor_analysis(site: dict, profile: dict, llm_key: str) -> dict:
    competitors = [c for c in (profile.get("competitors") or []) if c.get("name")]
    if not competitors:
        raise RuntimeError("Aucun concurrent défini. Lancez d'abord le Business Analyzer (ou ajoutez vos concurrents via « Corriger »).")

    pages = await fetch_pages(site.get("base_url") or "", max_pages=3)
    own_excerpt = "\n".join(p["text"][:1200] for p in pages[:2]) if pages else "(site non accessible)"

    snapshots = [
        s for s in await asyncio.gather(
            *[_fetch_competitor_snapshot(c.get("name"), c.get("domain")) for c in competitors[:8]]
        ) if s
    ]

    ctx = {k: profile.get(k) for k in ("activity", "description", "positioning", "cities_zones", "business_model") if profile.get(k)}
    prompt = f"""Tu es un stratège marketing de guerre concurrentielle. Compare cette entreprise à ses concurrents et produis un plan de bataille actionnable.

NOTRE ENTREPRISE :
{json.dumps(ctx, ensure_ascii=False, indent=1)}
Site : {site.get('name')} — {site.get('base_url')}
Extrait du site : {own_excerpt[:1500]}

CONCURRENTS À ANALYSER (liste validée par l'utilisateur) :
{json.dumps([{"name": c.get("name"), "domain": c.get("domain")} for c in competitors[:8]], ensure_ascii=False)}

SNAPSHOTS RÉELS DES SITES CONCURRENTS (quand disponibles) :
{json.dumps(snapshots, ensure_ascii=False)[:6000] if snapshots else "(aucun crawl disponible — utilise ta connaissance de ces acteurs du marché)"}

Réponds en JSON STRICT :
{{
  "summary": "synthèse du paysage concurrentiel et de notre position en 3-4 phrases",
  "your_advantages": ["3-5 avantages réels de notre entreprise face à ces concurrents"],
  "competitors": [
    {{
      "name": "...",
      "positioning": "son positionnement en 1 phrase",
      "keywords_they_dominate": [{{"keyword": "...", "why": "pourquoi il domine dessus"}}],
      "their_strengths": "ses forces principales",
      "their_weaknesses": "ses faiblesses exploitables",
      "how_to_beat": "tactique concrète pour le dépasser"
    }}
  ],
  "content_gaps": [
    {{"title": "titre du contenu à créer", "type": "article|page_locale|faq|service_description", "inspired_by": "concurrent qui l'a déjà", "target_keywords": ["2-3 mots-clés"], "city": "ville ciblée ou null", "why": "pourquoi ce gap nous coûte du trafic"}}
  ],
  "battle_plan": [
    {{"action": "titre court", "details": "quoi faire concrètement", "impact": "élevé|moyen|faible", "effort": "faible|moyen|élevé", "timeframe": "ex: semaine 1-2"}}
  ]
}}
Analyse chacun des concurrents listés (3-4 keywords_they_dominate chacun), 6-10 content_gaps, 5-7 actions de battle_plan triées par impact. content_gaps[].type DOIT être exactement l'un de : article, page_locale, faq, service_description."""

    report = await _llm(prompt, f"competitor-{site.get('id')}", llm_key, max_tokens=16000, retries=2)
    valid_types = {"article", "page_locale", "faq", "service_description"}
    report["content_gaps"] = [g for g in report.get("content_gaps", []) if g.get("type") in valid_types and g.get("title")]
    report["competitors_crawled"] = [s["name"] for s in snapshots]
    return report
