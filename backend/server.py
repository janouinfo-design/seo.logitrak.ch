"""LOGI SEO Booster - FastAPI backend.

Modules:
- Auth (JWT, bcrypt)
- Sites (Wix multi-site connection: Logirent / Logitime)
- Wix integration (read pages / blog posts, create draft posts)
- SEO Audit
- AI content generation (Claude Sonnet 4.5 via Emergent Universal Key)
- Drafts CRUD + publish workflow
- Publish history & rollback
- Performance (mocked GSC/GA for MVP)
"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import uuid
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Dict, Any

import jwt
import bcrypt
import httpx
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "168"))
EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("logi-seo")

app = FastAPI(title="LOGI SEO Booster")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gen_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=1)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class SiteCreate(BaseModel):
    label: Literal["Logirent", "Logitime", "Autre"]
    name: str
    wix_site_id: str
    wix_account_id: str
    wix_api_key: str
    base_url: Optional[str] = None


class SiteUpdate(BaseModel):
    label: Optional[Literal["Logirent", "Logitime", "Autre"]] = None
    name: Optional[str] = None
    wix_site_id: Optional[str] = None
    wix_account_id: Optional[str] = None
    wix_api_key: Optional[str] = None
    base_url: Optional[str] = None


class SitePublic(BaseModel):
    id: str
    label: str
    name: str
    wix_site_id: str
    wix_account_id: str
    base_url: Optional[str] = None
    has_api_key: bool
    created_at: str


class AuditRequest(BaseModel):
    site_id: str


class AuditIssue(BaseModel):
    page_id: str
    page_title: str
    page_url: str
    severity: Literal["high", "medium", "low"]
    category: str
    message: str
    recommendation: str


class AuditReport(BaseModel):
    id: str
    site_id: str
    score: int
    total_pages: int
    issues: List[AuditIssue]
    summary: Dict[str, int]
    created_at: str


class ContentGenerateRequest(BaseModel):
    site_id: str
    content_type: Literal["article", "page_locale", "faq", "service_description"]
    topic: str
    keywords: List[str] = []
    city: Optional[str] = None
    tone: Literal["professionnel", "amical", "expert", "pedagogique"] = "professionnel"
    target_length: Literal["court", "moyen", "long"] = "moyen"
    extra_instructions: Optional[str] = None


class DraftCreate(BaseModel):
    site_id: str
    content_type: str
    title: str
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    body_markdown: str
    keywords: List[str] = []
    faq: List[Dict[str, str]] = []


class DraftUpdate(BaseModel):
    title: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    body_markdown: Optional[str] = None
    keywords: Optional[List[str]] = None
    faq: Optional[List[Dict[str, str]]] = None
    status: Optional[Literal["draft", "ready", "published", "archived"]] = None


class DraftPublic(BaseModel):
    id: str
    site_id: str
    content_type: str
    title: str
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    body_markdown: str
    keywords: List[str]
    faq: List[Dict[str, str]]
    status: str
    created_at: str
    updated_at: str
    wix_draft_id: Optional[str] = None
    wix_published_at: Optional[str] = None


class PublishRequest(BaseModel):
    publish_immediately: bool = False  # if False, only creates a Wix draft


# ---------------------------------------------------------------------------
# Auth utilities
# ---------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token manquant")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur introuvable")
    return user


def user_to_public(user: dict) -> UserPublic:
    return UserPublic(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        created_at=user["created_at"],
    )


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@api.post("/auth/register", response_model=AuthResponse)
async def register(payload: UserCreate):
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(409, "Un compte existe déjà avec cet email")
    user_doc = {
        "id": gen_id(),
        "email": payload.email.lower(),
        "full_name": payload.full_name.strip(),
        "password_hash": hash_password(payload.password),
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc)
    return AuthResponse(token=create_token(user_doc["id"]), user=user_to_public(user_doc))


@api.post("/auth/login", response_model=AuthResponse)
async def login(payload: UserLogin):
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    return AuthResponse(token=create_token(user["id"]), user=user_to_public(user))


@api.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return user_to_public(user)


# ---------------------------------------------------------------------------
# Sites (Wix) endpoints
# ---------------------------------------------------------------------------
def site_to_public(site: dict) -> SitePublic:
    return SitePublic(
        id=site["id"],
        label=site["label"],
        name=site["name"],
        wix_site_id=site["wix_site_id"],
        wix_account_id=site["wix_account_id"],
        base_url=site.get("base_url"),
        has_api_key=bool(site.get("wix_api_key")),
        created_at=site["created_at"],
    )


@api.post("/sites", response_model=SitePublic)
async def create_site(payload: SiteCreate, user=Depends(get_current_user)):
    site = {
        "id": gen_id(),
        "user_id": user["id"],
        "label": payload.label,
        "name": payload.name.strip(),
        "wix_site_id": payload.wix_site_id.strip(),
        "wix_account_id": payload.wix_account_id.strip(),
        "wix_api_key": payload.wix_api_key.strip(),
        "base_url": (payload.base_url or "").strip() or None,
        "created_at": now_iso(),
    }
    await db.sites.insert_one(site)
    return site_to_public(site)


@api.get("/sites", response_model=List[SitePublic])
async def list_sites(user=Depends(get_current_user)):
    sites = await db.sites.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    return [site_to_public(s) for s in sites]


@api.get("/sites/{site_id}", response_model=SitePublic)
async def get_site(site_id: str, user=Depends(get_current_user)):
    site = await db.sites.find_one({"id": site_id, "user_id": user["id"]}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Site introuvable")
    return site_to_public(site)


@api.patch("/sites/{site_id}", response_model=SitePublic)
async def update_site(site_id: str, payload: SiteUpdate, user=Depends(get_current_user)):
    site = await db.sites.find_one({"id": site_id, "user_id": user["id"]})
    if not site:
        raise HTTPException(404, "Site introuvable")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        await db.sites.update_one({"id": site_id}, {"$set": updates})
    site = await db.sites.find_one({"id": site_id}, {"_id": 0})
    return site_to_public(site)


@api.delete("/sites/{site_id}")
async def delete_site(site_id: str, user=Depends(get_current_user)):
    res = await db.sites.delete_one({"id": site_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Site introuvable")
    return {"ok": True}


async def _get_user_site(site_id: str, user: dict) -> dict:
    site = await db.sites.find_one({"id": site_id, "user_id": user["id"]}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Site introuvable")
    return site


# ---------------------------------------------------------------------------
# Wix API helpers (with graceful fallback to mock data for MVP)
# ---------------------------------------------------------------------------
def wix_headers(site: dict) -> Dict[str, str]:
    return {
        "Authorization": site["wix_api_key"],
        "wix-account-id": site["wix_account_id"],
        "wix-site-id": site["wix_site_id"],
        "Content-Type": "application/json",
    }


def _mock_pages(site: dict) -> List[dict]:
    label = site["label"]
    city_hint = "Paris" if label == "Logirent" else "Lyon"
    base = site.get("base_url") or f"https://www.{label.lower()}.fr"
    return [
        {
            "id": f"page-home-{site['id']}",
            "title": f"Accueil - {site['name']}",
            "url": f"{base}/",
            "meta_title": f"{site['name']} | Location et gestion immobilière",
            "meta_description": "Service professionnel.",  # trop court
            "h1": [f"Bienvenue chez {site['name']}"],
            "h2": ["Nos services", "Pourquoi nous choisir"],
            "word_count": 180,
            "images_total": 5,
            "images_without_alt": 3,
        },
        {
            "id": f"page-services-{site['id']}",
            "title": "Nos Services",
            "url": f"{base}/services",
            "meta_title": "Services",
            "meta_description": None,
            "h1": ["Services"],
            "h2": [],
            "word_count": 420,
            "images_total": 2,
            "images_without_alt": 1,
        },
        {
            "id": f"page-contact-{site['id']}",
            "title": "Contact",
            "url": f"{base}/contact",
            "meta_title": f"Contact | {site['name']}",
            "meta_description": f"Contactez {site['name']} pour toute demande concernant nos services à {city_hint} et alentours.",
            "h1": ["Nous contacter"],
            "h2": ["Adresse", "Téléphone"],
            "word_count": 95,
            "images_total": 1,
            "images_without_alt": 0,
        },
        {
            "id": f"page-blog-{site['id']}",
            "title": "Blog",
            "url": f"{base}/blog",
            "meta_title": "Blog",
            "meta_description": "Articles.",
            "h1": ["Blog"],
            "h2": [],
            "word_count": 60,
            "images_total": 0,
            "images_without_alt": 0,
        },
        {
            "id": f"page-tarifs-{site['id']}",
            "title": "Tarifs",
            "url": f"{base}/tarifs",
            "meta_title": f"Tarifs {site['name']} | Devis personnalisé",
            "meta_description": f"Découvrez nos tarifs transparents pour {site['name']}. Demandez un devis personnalisé adapté à vos besoins.",
            "h1": ["Nos tarifs"],
            "h2": ["Formules", "Devis gratuit"],
            "word_count": 540,
            "images_total": 3,
            "images_without_alt": 0,
        },
    ]


async def fetch_wix_pages(site: dict) -> List[dict]:
    """Try Wix REST API first; fall back to mock data if unreachable / unauthorized."""
    url = "https://www.wixapis.com/site-pages/v2/pages/query"
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(url, headers=wix_headers(site), json={"query": {"paging": {"limit": 50}}})
        if r.status_code == 200:
            data = r.json()
            pages = []
            for p in data.get("pages", []) or []:
                seo = p.get("seo", {}) or {}
                pages.append({
                    "id": p.get("id", gen_id()),
                    "title": p.get("title") or p.get("pageName") or "Sans titre",
                    "url": p.get("url") or "",
                    "meta_title": seo.get("title"),
                    "meta_description": seo.get("description"),
                    "h1": [],
                    "h2": [],
                    "word_count": 0,
                    "images_total": 0,
                    "images_without_alt": 0,
                })
            if pages:
                return pages
        logger.info("Wix pages API returned %s — using mock data", r.status_code)
    except Exception as exc:
        logger.info("Wix pages API unreachable (%s) — using mock data", exc)
    return _mock_pages(site)


async def fetch_wix_blog_posts(site: dict) -> List[dict]:
    """Try Wix Blog API; fall back to small mock list."""
    url = "https://www.wixapis.com/blog/v3/posts/query"
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(url, headers=wix_headers(site), json={"query": {"paging": {"limit": 25}}})
        if r.status_code == 200:
            data = r.json()
            posts = []
            for p in data.get("posts", []) or []:
                posts.append({
                    "id": p.get("id"),
                    "title": p.get("title", ""),
                    "slug": p.get("slug", ""),
                    "url": p.get("url", {}).get("base", "") + p.get("url", {}).get("path", "") if isinstance(p.get("url"), dict) else "",
                    "first_published_date": p.get("firstPublishedDate"),
                    "excerpt": p.get("excerpt", ""),
                })
            return posts
    except Exception as exc:
        logger.info("Wix blog API unreachable (%s) — using mock data", exc)
    base = site.get("base_url") or f"https://www.{site['label'].lower()}.fr"
    return [
        {"id": "post-1", "title": "Comment optimiser votre bail locatif", "slug": "optimiser-bail-locatif",
         "url": f"{base}/blog/optimiser-bail-locatif", "first_published_date": "2025-09-12", "excerpt": "Guide complet…"},
        {"id": "post-2", "title": "Gestion locative à distance : 5 conseils", "slug": "gestion-locative-distance",
         "url": f"{base}/blog/gestion-locative-distance", "first_published_date": "2025-10-04", "excerpt": "Astuces et bonnes pratiques."},
    ]


async def create_wix_draft_post(site: dict, title: str, body_markdown: str, seo_title: Optional[str],
                                seo_description: Optional[str]) -> Optional[str]:
    """Try to create a draft post on Wix. Returns Wix draft id or None on failure."""
    url = "https://www.wixapis.com/blog/v3/draft-posts"
    rich_content = {
        "nodes": [
            {
                "type": "PARAGRAPH",
                "id": gen_id(),
                "nodes": [{"type": "TEXT", "id": gen_id(), "textData": {"text": body_markdown}}],
            }
        ]
    }
    payload = {
        "draftPost": {
            "title": title,
            "richContent": rich_content,
            "seoData": {
                "tags": [
                    {"type": "title", "children": seo_title or title},
                    {"type": "meta", "props": {"name": "description", "content": seo_description or ""}},
                ]
            },
        }
    }
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(url, headers=wix_headers(site), json=payload)
        if r.status_code in (200, 201):
            data = r.json()
            return data.get("draftPost", {}).get("id")
        logger.warning("Wix create draft failed: %s %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("Wix create draft error: %s", exc)
    return None


@api.get("/sites/{site_id}/pages")
async def list_site_pages(site_id: str, user=Depends(get_current_user)):
    site = await _get_user_site(site_id, user)
    pages = await fetch_wix_pages(site)
    return {"pages": pages}


@api.get("/sites/{site_id}/blog-posts")
async def list_site_blog_posts(site_id: str, user=Depends(get_current_user)):
    site = await _get_user_site(site_id, user)
    posts = await fetch_wix_blog_posts(site)
    return {"posts": posts}


# ---------------------------------------------------------------------------
# SEO Audit
# ---------------------------------------------------------------------------
def _audit_page(page: dict) -> List[dict]:
    issues = []
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
# AI Content generator (Claude Sonnet 4.5)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Tu es un rédacteur SEO senior spécialisé immobilier et services aux entreprises.
Tu écris en français, ton professionnel, naturel, jamais spammy.
Tu structures tes contenus pour Google ET pour les IA (ChatGPT, Gemini, Perplexity, Google AI Overviews).

RÈGLES OBLIGATOIRES pour chaque contenu :
1. Commencer par une "réponse courte" de 2-3 phrases (résumé direct, factuel) — utile pour AI Overviews.
2. Paragraphes courts (3-4 lignes max), titres H2/H3 hiérarchisés.
3. Inclure une section FAQ avec 4-6 questions/réponses naturelles.
4. Inclure au moins 1 tableau comparatif ou liste structurée en markdown.
5. Mentionner des données locales (ville/région) si fournies.
6. Style crédible, factuel, sans superlatifs creux.
7. Densité de mots-clés naturelle (3-5 mentions du keyword principal).
8. Toujours répondre en JSON valide.

FORMAT DE RÉPONSE OBLIGATOIRE (JSON strict, aucun texte avant/après) :
{
  "title": "Titre H1 du contenu",
  "meta_title": "Titre SEO 50-60 caractères",
  "meta_description": "Méta description 140-160 caractères",
  "body_markdown": "Contenu complet en markdown avec H2/H3, paragraphes, listes, tableaux",
  "faq": [{"question": "...", "answer": "..."}],
  "keywords": ["mot-clé 1", "mot-clé 2", ...]
}"""


def _length_hint(length: str) -> str:
    return {"court": "500-700 mots", "moyen": "900-1200 mots", "long": "1500-2000 mots"}.get(length, "900-1200 mots")


def _type_hint(t: str) -> str:
    return {
        "article": "Article de blog SEO",
        "page_locale": "Page locale SEO (ciblage géographique)",
        "faq": "Page FAQ exhaustive (10-15 Q/R)",
        "service_description": "Description de service commercial optimisée SEO",
    }.get(t, "Contenu SEO")


@api.post("/content/generate", response_model=DraftPublic)
async def generate_content(req: ContentGenerateRequest, user=Depends(get_current_user)):
    site = await _get_user_site(req.site_id, user)

    # Lazy import emergentintegrations to avoid load failures at startup
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore

    user_prompt = f"""Génère un contenu SEO pour le site "{site['name']}" ({site['label']}).

Type de contenu : {_type_hint(req.content_type)}
Sujet : {req.topic}
Ville / zone : {req.city or 'France (national)'}
Mots-clés cibles : {', '.join(req.keywords) if req.keywords else '(à déterminer)'}
Ton : {req.tone}
Longueur visée : {_length_hint(req.target_length)}
Instructions supplémentaires : {req.extra_instructions or '(aucune)'}

Réponds en JSON strict selon le format imposé."""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"gen-{user['id']}-{gen_id()}",
        system_message=SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    try:
        response = await chat.send_message(UserMessage(text=user_prompt))
    except Exception as exc:
        logger.exception("LLM call failed")
        raise HTTPException(502, f"Erreur génération IA : {exc}")

    # Parse JSON (Claude returns JSON in response text)
    import json
    text = response if isinstance(response, str) else str(response)
    # Strip code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract first {...} block
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            raise HTTPException(502, "Réponse IA non parsable")
        data = json.loads(m.group(0))

    draft = {
        "id": gen_id(),
        "user_id": user["id"],
        "site_id": req.site_id,
        "content_type": req.content_type,
        "title": data.get("title") or req.topic,
        "meta_title": data.get("meta_title"),
        "meta_description": data.get("meta_description"),
        "body_markdown": data.get("body_markdown") or "",
        "keywords": data.get("keywords") or req.keywords,
        "faq": data.get("faq") or [],
        "status": "draft",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "wix_draft_id": None,
        "wix_published_at": None,
    }
    await db.drafts.insert_one(draft)
    return DraftPublic(**{k: v for k, v in draft.items() if k != "user_id"})


# ---------------------------------------------------------------------------
# Drafts CRUD
# ---------------------------------------------------------------------------
def _draft_public(d: dict) -> DraftPublic:
    return DraftPublic(**{k: v for k, v in d.items() if k in DraftPublic.model_fields})


@api.get("/drafts", response_model=List[DraftPublic])
async def list_drafts(site_id: Optional[str] = None, user=Depends(get_current_user)):
    query: Dict[str, Any] = {"user_id": user["id"]}
    if site_id:
        query["site_id"] = site_id
    items = await db.drafts.find(query, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return [_draft_public(d) for d in items]


@api.get("/drafts/{draft_id}", response_model=DraftPublic)
async def get_draft(draft_id: str, user=Depends(get_current_user)):
    d = await db.drafts.find_one({"id": draft_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Brouillon introuvable")
    return _draft_public(d)


@api.post("/drafts", response_model=DraftPublic)
async def create_draft(payload: DraftCreate, user=Depends(get_current_user)):
    await _get_user_site(payload.site_id, user)
    d = {
        "id": gen_id(),
        "user_id": user["id"],
        **payload.model_dump(),
        "status": "draft",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "wix_draft_id": None,
        "wix_published_at": None,
    }
    await db.drafts.insert_one(d)
    return _draft_public(d)


@api.patch("/drafts/{draft_id}", response_model=DraftPublic)
async def update_draft(draft_id: str, payload: DraftUpdate, user=Depends(get_current_user)):
    d = await db.drafts.find_one({"id": draft_id, "user_id": user["id"]})
    if not d:
        raise HTTPException(404, "Brouillon introuvable")
    # Save version snapshot
    snapshot = {
        "id": gen_id(),
        "draft_id": draft_id,
        "user_id": user["id"],
        "snapshot": {k: d.get(k) for k in ("title", "meta_title", "meta_description", "body_markdown", "keywords", "faq")},
        "created_at": now_iso(),
    }
    await db.versions.insert_one(snapshot)
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    updates["updated_at"] = now_iso()
    await db.drafts.update_one({"id": draft_id}, {"$set": updates})
    d = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    return _draft_public(d)


@api.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str, user=Depends(get_current_user)):
    res = await db.drafts.delete_one({"id": draft_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Brouillon introuvable")
    return {"ok": True}


@api.get("/drafts/{draft_id}/versions")
async def list_draft_versions(draft_id: str, user=Depends(get_current_user)):
    versions = await db.versions.find(
        {"draft_id": draft_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"versions": versions}


@api.post("/drafts/{draft_id}/rollback/{version_id}", response_model=DraftPublic)
async def rollback_draft(draft_id: str, version_id: str, user=Depends(get_current_user)):
    v = await db.versions.find_one({"id": version_id, "draft_id": draft_id, "user_id": user["id"]})
    if not v:
        raise HTTPException(404, "Version introuvable")
    snap = v["snapshot"]
    snap["updated_at"] = now_iso()
    await db.drafts.update_one({"id": draft_id, "user_id": user["id"]}, {"$set": snap})
    d = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    return _draft_public(d)


# ---------------------------------------------------------------------------
# Publish to Wix
# ---------------------------------------------------------------------------
@api.post("/drafts/{draft_id}/publish", response_model=DraftPublic)
async def publish_draft(draft_id: str, payload: PublishRequest, user=Depends(get_current_user)):
    d = await db.drafts.find_one({"id": draft_id, "user_id": user["id"]})
    if not d:
        raise HTTPException(404, "Brouillon introuvable")
    site = await _get_user_site(d["site_id"], user)

    wix_draft_id = await create_wix_draft_post(
        site=site,
        title=d["title"],
        body_markdown=d["body_markdown"],
        seo_title=d.get("meta_title"),
        seo_description=d.get("meta_description"),
    )

    log_entry = {
        "id": gen_id(),
        "user_id": user["id"],
        "site_id": d["site_id"],
        "draft_id": draft_id,
        "title": d["title"],
        "action": "publish_attempt",
        "wix_draft_id": wix_draft_id,
        "status": "success" if wix_draft_id else "wix_unavailable",
        "created_at": now_iso(),
    }
    await db.publish_logs.insert_one(log_entry)

    updates = {
        "wix_draft_id": wix_draft_id,
        "status": "published" if wix_draft_id else "ready",
        "updated_at": now_iso(),
    }
    if wix_draft_id:
        updates["wix_published_at"] = now_iso()
    await db.drafts.update_one({"id": draft_id}, {"$set": updates})
    d = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    return _draft_public(d)


@api.get("/publish-logs")
async def list_publish_logs(site_id: Optional[str] = None, user=Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if site_id:
        q["site_id"] = site_id
    logs = await db.publish_logs.find(q, {"_id": 0, "user_id": 0}).sort("created_at", -1).to_list(200)
    return {"logs": logs}


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


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": "LOGI SEO Booster", "status": "ok"}


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
