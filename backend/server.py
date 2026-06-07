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
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
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
    site_type: Literal["wix", "url_crawl"] = "wix"
    wix_site_id: Optional[str] = None
    wix_account_id: Optional[str] = None
    wix_api_key: Optional[str] = None
    base_url: Optional[str] = None


class SiteUpdate(BaseModel):
    label: Optional[Literal["Logirent", "Logitime", "Autre"]] = None
    name: Optional[str] = None
    site_type: Optional[Literal["wix", "url_crawl"]] = None
    wix_site_id: Optional[str] = None
    wix_account_id: Optional[str] = None
    wix_api_key: Optional[str] = None
    base_url: Optional[str] = None


class SitePublic(BaseModel):
    id: str
    label: str
    name: str
    site_type: str
    wix_site_id: Optional[str] = None
    wix_account_id: Optional[str] = None
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
        site_type=site.get("site_type", "wix"),
        wix_site_id=site.get("wix_site_id"),
        wix_account_id=site.get("wix_account_id"),
        base_url=site.get("base_url"),
        has_api_key=bool(site.get("wix_api_key")),
        created_at=site["created_at"],
    )


@api.post("/sites", response_model=SitePublic)
async def create_site(payload: SiteCreate, user=Depends(get_current_user)):
    site_type = payload.site_type
    if site_type == "wix":
        if not (payload.wix_site_id and payload.wix_account_id and payload.wix_api_key):
            raise HTTPException(422, "Pour un site Wix, wix_site_id, wix_account_id et wix_api_key sont requis.")
    else:  # url_crawl
        if not payload.base_url:
            raise HTTPException(422, "Pour un site URL publique, base_url est requis.")
    site = {
        "id": gen_id(),
        "user_id": user["id"],
        "label": payload.label,
        "name": payload.name.strip(),
        "site_type": site_type,
        "wix_site_id": (payload.wix_site_id or "").strip() or None,
        "wix_account_id": (payload.wix_account_id or "").strip() or None,
        "wix_api_key": (payload.wix_api_key or "").strip() or None,
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


@api.post("/sites/quick-add-emergent")
async def quick_add_emergent_sites(user=Depends(get_current_user)):
    """One-click: add logirent.ch and logitime.ch as url_crawl sites if not already present."""
    presets = [
        {"label": "Logirent", "name": "Logirent (logirent.ch)", "base_url": "https://www.logirent.ch"},
        {"label": "Logitime", "name": "Logitime (logitime.ch)", "base_url": "https://www.logitime.ch"},
    ]
    added: List[SitePublic] = []
    skipped: List[str] = []
    for p in presets:
        existing = await db.sites.find_one({
            "user_id": user["id"],
            "base_url": p["base_url"],
        })
        if existing:
            skipped.append(p["name"])
            continue
        site = {
            "id": gen_id(),
            "user_id": user["id"],
            "label": p["label"],
            "name": p["name"],
            "site_type": "url_crawl",
            "wix_site_id": None,
            "wix_account_id": None,
            "wix_api_key": None,
            "base_url": p["base_url"],
            "created_at": now_iso(),
        }
        await db.sites.insert_one(site)
        added.append(site_to_public(site))
    return {"added": added, "skipped": skipped}


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


async def crawl_public_site(site: dict, max_pages: int = 12) -> List[dict]:
    """Crawl a public site by URL: try /sitemap.xml first, otherwise BFS from base_url.
    Extracts per-page: title, meta description, H1/H2 list, word count, images_total, images_without_alt.
    Pure scraping — no API needed. Detects SPA / client-rendered sites and flags them."""
    base_url = (site.get("base_url") or "").rstrip("/")
    if not base_url:
        return []
    try:
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return []
    except Exception:
        return []
    host = parsed.netloc

    def normalize(u: str) -> str:
        # Strip URL fragments (#…) and trailing slashes
        u = u.split("#")[0].rstrip("/")
        return u or u

    urls_to_visit: List[str] = []
    seen: set = set()
    headers = {"User-Agent": "LogiSEOBooster/1.0 (+https://emergent.sh)"}

    def add_url(u: str):
        n = normalize(u)
        if n and n not in seen and urlparse(n).netloc == host:
            seen.add(n)
            urls_to_visit.append(n)

    async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=True) as cli:
        # 1. Sitemap
        try:
            r = await cli.get(f"{base_url}/sitemap.xml")
            if r.status_code == 200 and "xml" in r.headers.get("content-type", "").lower():
                soup = BeautifulSoup(r.text, "xml")
                for loc in soup.find_all("loc"):
                    add_url(loc.text.strip())
                    if len(urls_to_visit) >= max_pages:
                        break
        except Exception as exc:
            logger.info("sitemap fetch failed for %s: %s", base_url, exc)

        # 2. Fallback: BFS from home
        if not urls_to_visit:
            add_url(base_url)
            try:
                r = await cli.get(base_url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "lxml")
                    for a in soup.find_all("a", href=True):
                        full = urljoin(base_url, a["href"])
                        add_url(full)
                        if len(urls_to_visit) >= max_pages:
                            break
            except Exception as exc:
                logger.info("home crawl failed for %s: %s", base_url, exc)

        # 3. Visit each URL
        results: List[dict] = []
        sem = asyncio.Semaphore(4)

        async def fetch_one(u: str) -> Optional[dict]:
            async with sem:
                try:
                    rr = await cli.get(u)
                    if rr.status_code >= 400:
                        return None
                    raw_html = rr.text
                    soup = BeautifulSoup(raw_html, "lxml")
                    page_title = (soup.title.string or "").strip() if soup.title else ""
                    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
                    meta_desc = (meta_desc_tag.get("content") or "").strip() if meta_desc_tag else None
                    h1s = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
                    h2s = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)]
                    # Body text (strip non-content tags)
                    body_soup = BeautifulSoup(raw_html, "lxml")
                    for tag in body_soup(["script", "style", "noscript"]):
                        tag.decompose()
                    body_text = body_soup.get_text(" ", strip=True)
                    word_count = len([w for w in re.split(r"\s+", body_text) if w])
                    imgs = soup.find_all("img")
                    imgs_total = len(imgs)
                    imgs_no_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
                    # SPA detection: client-rendered apps often have <div id="root"> with very little body text
                    spa_markers = bool(soup.find(id=re.compile(r"^(root|app|__next)$"))) or "react" in raw_html.lower()[:5000]
                    is_spa = spa_markers and word_count < 100 and len(h1s) == 0
                    return {
                        "id": "crawl-" + str(abs(hash(u))),
                        "title": page_title or u,
                        "url": u,
                        "meta_title": page_title or None,
                        "meta_description": meta_desc,
                        "h1": h1s,
                        "h2": h2s,
                        "word_count": word_count,
                        "images_total": imgs_total,
                        "images_without_alt": imgs_no_alt,
                        "spa_detected": is_spa,
                    }
                except Exception as exc:
                    logger.info("crawl page failed %s: %s", u, exc)
                    return None

        tasks = [fetch_one(u) for u in urls_to_visit[:max_pages]]
        for res in await asyncio.gather(*tasks):
            if res:
                results.append(res)
        return results


async def fetch_wix_pages(site: dict) -> List[dict]:
    """Dispatcher: routes to Wix API or URL crawl depending on site_type. Falls back to mock if both fail."""
    site_type = site.get("site_type", "wix")
    if site_type == "url_crawl":
        pages = await crawl_public_site(site)
        if pages:
            return pages
        return _mock_pages(site)
    # Default Wix API path
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
    # SPA / client-rendered detection — critical for SEO
    if page.get("spa_detected"):
        issues.append({"severity": "high", "category": "Rendu côté client",
                       "message": "Page rendue côté client (SPA) — Google et les IA voient un HTML quasi vide",
                       "recommendation": "Activer le rendu côté serveur (SSR) ou la pré-génération statique (SSG), ou utiliser un service de prerendering. Sans cela, le SEO est fortement pénalisé même si le contenu visible côté utilisateur paraît correct."})
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


class BatchIdsRequest(BaseModel):
    ids: List[str]


@api.post("/drafts/batch-delete")
async def batch_delete_drafts(payload: BatchIdsRequest, user=Depends(get_current_user)):
    res = await db.drafts.delete_many({"id": {"$in": payload.ids}, "user_id": user["id"]})
    return {"deleted": res.deleted_count}


@api.post("/keywords/saved/batch-delete")
async def batch_delete_keywords(payload: BatchIdsRequest, user=Depends(get_current_user)):
    res = await db.saved_keywords.delete_many({"id": {"$in": payload.ids}, "user_id": user["id"]})
    return {"deleted": res.deleted_count}


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

    site_type = site.get("site_type", "wix")
    wix_draft_id: Optional[str] = None
    status_label: str

    if site_type == "wix":
        wix_draft_id = await create_wix_draft_post(
            site=site,
            title=d["title"],
            body_markdown=d["body_markdown"],
            seo_title=d.get("meta_title"),
            seo_description=d.get("meta_description"),
        )
        status_label = "success" if wix_draft_id else "wix_unavailable"
    else:
        # URL crawl sites (Emergent-hosted etc.) — no API yet, mark as ready/exported.
        status_label = "ready_for_export"

    log_entry = {
        "id": gen_id(),
        "user_id": user["id"],
        "site_id": d["site_id"],
        "draft_id": draft_id,
        "title": d["title"],
        "action": "publish_attempt",
        "wix_draft_id": wix_draft_id,
        "status": status_label,
        "site_type": site_type,
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
