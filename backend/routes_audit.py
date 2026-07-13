from fastapi import Depends
from typing import List
import re
from app_core import AuditIssue, AuditReport, api, db, gen_id, get_current_user, now_iso
from routes_sites import _get_user_site, fetch_wix_pages

# ---------------------------------------------------------------------------
# SEO Audit
# ---------------------------------------------------------------------------
def _audit_page(page: dict) -> List[dict]:
    issues = []
    # SPA / client-rendered detection — critical for SEO
    if page.get("spa_detected"):
        rendered_note = " (LOGI a pu lire le contenu grâce au rendu JS Playwright, mais Google ne le voit pas par défaut sans SSR/SSG/prerender)"
        recommendation = (
            "Activer le rendu côté serveur (SSR) ou la pré-génération statique (SSG), "
            "ou utiliser un service de prerendering. Sans cela, le SEO est fortement "
            "pénalisé même si le contenu visible côté utilisateur paraît correct."
        )
        if page.get("js_rendered"):
            recommendation = (
                "LOGI SEO Booster lit ce contenu via un crawler Playwright qui exécute le JS. "
                "Mais Google et la plupart des IA ne font PAS cela par défaut. " + recommendation
            )
        issues.append({"severity": "high", "category": "Rendu côté client",
                       "message": "Page rendue côté client (SPA) — Google et les IA voient un HTML quasi vide" + rendered_note,
                       "recommendation": recommendation})
    title = page.get("meta_title") or page.get("title") or ""
    desc = page.get("meta_description") or ""
    if not title:
        issues.append({"severity": "high", "category": "Titre SEO",
                       "message": "Titre SEO manquant",
                       "recommendation": "Ajouter un titre SEO de 50 à 60 caractères contenant le mot-clé principal."})
    elif len(title) < 30:
        issues.append({"severity": "medium", "category": "Titre SEO",
                       "message": f"Titre trop court ({len(title)} caractères)",
                       "recommendation": "Allonger le titre SEO à 50-60 caractères en intégrant la localisation et le service."})
    elif len(title) > 65:
        issues.append({"severity": "low", "category": "Titre SEO",
                       "message": f"Titre trop long ({len(title)} caractères)",
                       "recommendation": "Raccourcir le titre à 60 caractères max pour éviter la troncature dans Google."})
    if not desc:
        issues.append({"severity": "high", "category": "Meta description",
                       "message": "Meta description manquante",
                       "recommendation": "Rédiger une méta description de 140-160 caractères, incitant au clic."})
    elif len(desc) < 80:
        issues.append({"severity": "medium", "category": "Meta description",
                       "message": f"Méta description trop courte ({len(desc)} caractères)",
                       "recommendation": "Allonger à 140-160 caractères, inclure mots-clés et appel à l'action."})
    elif len(desc) > 165:
        issues.append({"severity": "low", "category": "Meta description",
                       "message": f"Méta description trop longue ({len(desc)} caractères)",
                       "recommendation": "Limiter la méta description à 160 caractères max."})
    h1s = page.get("h1") or []
    if len(h1s) == 0:
        issues.append({"severity": "high", "category": "Structure H1",
                       "message": "Aucun H1 détecté",
                       "recommendation": "Ajouter un H1 unique reprenant le mot-clé cible."})
    elif len(h1s) > 1:
        issues.append({"severity": "medium", "category": "Structure H1",
                       "message": f"{len(h1s)} balises H1 détectées",
                       "recommendation": "Conserver un seul H1 par page."})
    if len(page.get("h2") or []) == 0:
        issues.append({"severity": "low", "category": "Structure H2",
                       "message": "Aucun H2 détecté",
                       "recommendation": "Ajouter 2-4 H2 pour structurer le contenu."})
    if (page.get("images_without_alt") or 0) > 0:
        issues.append({"severity": "medium", "category": "Images",
                       "message": f"{page['images_without_alt']} image(s) sans attribut alt",
                       "recommendation": "Renseigner un alt descriptif pour chaque image (accessibilité + SEO)."})
    wc = page.get("word_count") or 0
    if wc < 300:
        issues.append({"severity": "high", "category": "Contenu",
                       "message": f"Contenu trop court ({wc} mots)",
                       "recommendation": "Étoffer la page à minimum 600 mots avec FAQ, données locales et tableaux comparatifs."})
    elif wc < 600:
        issues.append({"severity": "medium", "category": "Contenu",
                       "message": f"Contenu moyen ({wc} mots)",
                       "recommendation": "Enrichir avec sections supplémentaires (FAQ, témoignages, ancrages locaux)."})
    url = page.get("url") or ""
    if url and not re.match(r"^https?://[^/]+/[a-z0-9-/]*$", url):
        issues.append({"severity": "low", "category": "URL",
                       "message": "URL non-optimisée",
                       "recommendation": "Préférer des URLs courtes, en minuscules, avec des tirets et mots-clés."})
    return issues


@api.post("/sites/{site_id}/audit", response_model=AuditReport)
async def run_audit(site_id: str, user=Depends(get_current_user)):
    site = await _get_user_site(site_id, user)
    pages = await fetch_wix_pages(site)
    all_issues: List[AuditIssue] = []
    summary = {"high": 0, "medium": 0, "low": 0}
    for p in pages:
        for it in _audit_page(p):
            all_issues.append(AuditIssue(
                page_id=p["id"], page_title=p.get("title", ""), page_url=p.get("url", ""),
                severity=it["severity"], category=it["category"], message=it["message"],
                recommendation=it["recommendation"],
            ))
            summary[it["severity"]] += 1
    max_issues = max(len(pages) * 6, 1)
    weighted = summary["high"] * 3 + summary["medium"] * 2 + summary["low"] * 1
    raw = max(0, 100 - int((weighted / max_issues) * 100))
    score = min(100, max(5, raw))
    report = AuditReport(
        id=gen_id(),
        site_id=site_id,
        score=score,
        total_pages=len(pages),
        issues=all_issues,
        summary=summary,
        created_at=now_iso(),
    )
    await db.audits.insert_one({**report.model_dump(), "user_id": user["id"]})
    return report


@api.get("/sites/{site_id}/audits", response_model=List[AuditReport])
async def list_audits(site_id: str, user=Depends(get_current_user)):
    await _get_user_site(site_id, user)
    items = await db.audits.find(
        {"site_id": site_id, "user_id": user["id"]}, {"_id": 0, "user_id": 0}
    ).sort("created_at", -1).to_list(20)
    return items


# ---------------------------------------------------------------------------
# Duplicate content detection (P2)
# ---------------------------------------------------------------------------
def _normalize_text(s: str) -> str:
    import unicodedata
    s = (s or "").lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"<[^>]+>", " ", s)  # strip HTML
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _bigrams(text: str) -> set:
    tokens = text.split()
    return set(zip(tokens, tokens[1:])) if len(tokens) > 1 else set(tokens)


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@api.post("/sites/{site_id}/duplicate-scan")
async def duplicate_scan(site_id: str, threshold: float = 0.55, user=Depends(get_current_user)):
    """Scan all pages of a site to detect content/title/meta duplicates.
    Returns pairs whose similarity is >= threshold (default 0.55 = ~55% bigram overlap).
    Also detects exact-match titles & meta descriptions across pages.
    """
    site = await _get_user_site(site_id, user)
    pages = await fetch_wix_pages(site)
    if len(pages) < 2:
        return {"site_id": site_id, "pages_scanned": len(pages), "pairs": [], "duplicate_titles": [], "duplicate_metas": []}

    # Pre-compute fingerprints
    fps = []
    for p in pages:
        title = p.get("title", "") or ""
        meta = p.get("meta_description", "") or p.get("description", "") or ""
        body = p.get("content_text") or p.get("body") or p.get("excerpt") or ""
        norm = _normalize_text(f"{title} {meta} {body}")
        fps.append({
            "id": p.get("id"),
            "title": title.strip(),
            "url": p.get("url"),
            "meta": meta.strip(),
            "bigrams": _bigrams(norm),
            "tokens_count": len(norm.split()),
        })

    # Pair-wise similarity
    pairs = []
    n = len(fps)
    for i in range(n):
        for j in range(i + 1, n):
            sim = _jaccard(fps[i]["bigrams"], fps[j]["bigrams"])
            if sim >= threshold and (fps[i]["tokens_count"] + fps[j]["tokens_count"]) > 20:
                pairs.append({
                    "page_a": {"id": fps[i]["id"], "title": fps[i]["title"], "url": fps[i]["url"]},
                    "page_b": {"id": fps[j]["id"], "title": fps[j]["title"], "url": fps[j]["url"]},
                    "similarity": round(sim, 3),
                    "severity": "high" if sim >= 0.85 else "medium" if sim >= 0.7 else "low",
                })
    pairs.sort(key=lambda x: -x["similarity"])

    # Exact-match titles & metas
    from collections import defaultdict
    by_title = defaultdict(list)
    by_meta = defaultdict(list)
    for f in fps:
        if f["title"]:
            by_title[f["title"].lower()].append({"id": f["id"], "url": f["url"], "title": f["title"]})
        if f["meta"]:
            by_meta[f["meta"].lower()].append({"id": f["id"], "url": f["url"], "title": f["title"], "meta": f["meta"]})
    duplicate_titles = [v for v in by_title.values() if len(v) > 1]
    duplicate_metas = [v for v in by_meta.values() if len(v) > 1]

    # Recommendations
    recs = []
    if pairs:
        recs.append(f"{len(pairs)} paire(s) de pages avec contenu très similaire (≥{int(threshold*100)}%). Risque de cannibalisation SEO : fusionnez ou différenciez fortement.")
    if duplicate_titles:
        recs.append(f"{len(duplicate_titles)} groupe(s) de pages avec un titre H1 identique. Google va choisir une seule page à indexer.")
    if duplicate_metas:
        recs.append(f"{len(duplicate_metas)} groupe(s) avec la même meta description. Rédigez des metas uniques par page (140-160 caractères).")
    if not (pairs or duplicate_titles or duplicate_metas):
        recs.append("Aucun doublon détecté. Excellent travail sur l'unicité du contenu.")

    return {
        "site_id": site_id,
        "pages_scanned": len(pages),
        "threshold": threshold,
        "pairs": pairs,
        "duplicate_titles": duplicate_titles,
        "duplicate_metas": duplicate_metas,
        "recommendations": recs,
        "scanned_at": now_iso(),
    }


