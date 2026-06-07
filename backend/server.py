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

# ---------------------------------------------------------------------------
# Encryption at-rest for sensitive tokens (Fernet)
# ---------------------------------------------------------------------------
from cryptography.fernet import Fernet, InvalidToken

_ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")
_fernet: Optional[Fernet] = None
if _ENCRYPTION_KEY:
    try:
        _fernet = Fernet(_ENCRYPTION_KEY.encode())
    except Exception as exc:
        logging.getLogger(__name__).error("Invalid ENCRYPTION_KEY: %s — encryption disabled", exc)
        _fernet = None

_ENC_PREFIX = "enc::"


def enc(value: Optional[str]) -> Optional[str]:
    """Encrypt a string value. Returns ciphertext prefixed with 'enc::'. Idempotent (already-encrypted → returned as-is). None → None."""
    if value is None or value == "":
        return value
    if not _fernet:
        return value  # graceful fallback if not configured
    if isinstance(value, str) and value.startswith(_ENC_PREFIX):
        return value
    try:
        return _ENC_PREFIX + _fernet.encrypt(value.encode()).decode()
    except Exception:
        return value


def dec(value: Optional[str]) -> Optional[str]:
    """Decrypt a value previously encrypted by enc(). If not encrypted (no prefix), return as-is (legacy plaintext)."""
    if value is None or value == "":
        return value
    if not isinstance(value, str) or not value.startswith(_ENC_PREFIX):
        return value
    if not _fernet:
        return value
    try:
        return _fernet.decrypt(value[len(_ENC_PREFIX):].encode()).decode()
    except (InvalidToken, Exception):
        return value

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
    site_type: Literal["wix", "url_crawl", "vps_api", "ftp"] = "wix"
    wix_site_id: Optional[str] = None
    wix_account_id: Optional[str] = None
    wix_api_key: Optional[str] = None
    base_url: Optional[str] = None
    vps_api_url: Optional[str] = None
    vps_api_token: Optional[str] = None
    ftp_host: Optional[str] = None
    ftp_port: Optional[int] = 21
    ftp_user: Optional[str] = None
    ftp_password: Optional[str] = None
    ftp_remote_path: Optional[str] = None  # ex: /public_html/blog/
    ftp_public_url: Optional[str] = None  # ex: https://www.logirent.ch/blog
    # GitHub publishing (any site_type can also have GitHub config)
    github_token: Optional[str] = None  # Personal Access Token
    github_owner: Optional[str] = None  # ex: "username" ou "myorg"
    github_repo: Optional[str] = None   # ex: "logirent-site"
    github_branch: Optional[str] = "main"
    github_folder: Optional[str] = None  # ex: "public/blog" (sans / initial)
    github_public_url: Optional[str] = None  # ex: https://www.logirent.ch/blog


class SiteUpdate(BaseModel):
    label: Optional[Literal["Logirent", "Logitime", "Autre"]] = None
    name: Optional[str] = None
    site_type: Optional[Literal["wix", "url_crawl", "vps_api", "ftp"]] = None
    wix_site_id: Optional[str] = None
    wix_account_id: Optional[str] = None
    wix_api_key: Optional[str] = None
    base_url: Optional[str] = None
    vps_api_url: Optional[str] = None
    vps_api_token: Optional[str] = None
    ftp_host: Optional[str] = None
    ftp_port: Optional[int] = None
    ftp_user: Optional[str] = None
    ftp_password: Optional[str] = None
    ftp_remote_path: Optional[str] = None
    ftp_public_url: Optional[str] = None
    github_token: Optional[str] = None
    github_owner: Optional[str] = None
    github_repo: Optional[str] = None
    github_branch: Optional[str] = None
    github_folder: Optional[str] = None
    github_public_url: Optional[str] = None


class SitePublic(BaseModel):
    id: str
    label: str
    name: str
    site_type: str
    wix_site_id: Optional[str] = None
    wix_account_id: Optional[str] = None
    base_url: Optional[str] = None
    vps_api_url: Optional[str] = None
    ftp_host: Optional[str] = None
    ftp_port: Optional[int] = None
    ftp_user: Optional[str] = None
    ftp_remote_path: Optional[str] = None
    ftp_public_url: Optional[str] = None
    github_owner: Optional[str] = None
    github_repo: Optional[str] = None
    github_branch: Optional[str] = None
    github_folder: Optional[str] = None
    github_public_url: Optional[str] = None
    has_github_token: bool = False
    gsc_site_url: Optional[str] = None
    ga4_property_id: Optional[str] = None
    has_api_key: bool
    has_vps_token: bool = False
    has_ftp_password: bool = False
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
    github_commit_sha: Optional[str] = None
    github_committed_at: Optional[str] = None
    github_public_url: Optional[str] = None


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
        vps_api_url=site.get("vps_api_url"),
        ftp_host=site.get("ftp_host"),
        ftp_port=site.get("ftp_port"),
        ftp_user=site.get("ftp_user"),
        ftp_remote_path=site.get("ftp_remote_path"),
        ftp_public_url=site.get("ftp_public_url"),
        github_owner=site.get("github_owner"),
        github_repo=site.get("github_repo"),
        github_branch=site.get("github_branch"),
        github_folder=site.get("github_folder"),
        github_public_url=site.get("github_public_url"),
        has_github_token=bool(site.get("github_token")),
        gsc_site_url=site.get("gsc_site_url"),
        ga4_property_id=site.get("ga4_property_id"),
        has_api_key=bool(site.get("wix_api_key")),
        has_vps_token=bool(site.get("vps_api_token")),
        has_ftp_password=bool(site.get("ftp_password")),
        created_at=site["created_at"],
    )


@api.post("/sites", response_model=SitePublic)
async def create_site(payload: SiteCreate, user=Depends(get_current_user)):
    site_type = payload.site_type
    if site_type == "wix":
        if not (payload.wix_site_id and payload.wix_account_id and payload.wix_api_key):
            raise HTTPException(422, "Pour un site Wix, wix_site_id, wix_account_id et wix_api_key sont requis.")
    elif site_type == "vps_api":
        if not (payload.base_url and payload.vps_api_url and payload.vps_api_token):
            raise HTTPException(422, "Pour un site VPS API, base_url, vps_api_url et vps_api_token sont requis.")
    elif site_type == "ftp":
        if not (payload.ftp_host and payload.ftp_user and payload.ftp_password and payload.ftp_remote_path):
            raise HTTPException(422, "Pour un site FTP, ftp_host, ftp_user, ftp_password et ftp_remote_path sont requis.")
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
        "wix_api_key": enc((payload.wix_api_key or "").strip()) or None,
        "base_url": (payload.base_url or "").strip() or None,
        "vps_api_url": (payload.vps_api_url or "").strip() or None,
        "vps_api_token": enc((payload.vps_api_token or "").strip()) or None,
        "ftp_host": (payload.ftp_host or "").strip() or None,
        "ftp_port": payload.ftp_port or 21,
        "ftp_user": (payload.ftp_user or "").strip() or None,
        "ftp_password": enc(payload.ftp_password) or None,
        "ftp_remote_path": (payload.ftp_remote_path or "").strip() or None,
        "ftp_public_url": (payload.ftp_public_url or "").strip() or None,
        "github_token": enc((payload.github_token or "").strip()) or None,
        "github_owner": (payload.github_owner or "").strip() or None,
        "github_repo": (payload.github_repo or "").strip() or None,
        "github_branch": (payload.github_branch or "main").strip() or "main",
        "github_folder": (payload.github_folder or "").strip().strip("/") or None,
        "github_public_url": (payload.github_public_url or "").strip().rstrip("/") or None,
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
    # Encrypt sensitive fields before persisting
    for sensitive in ("wix_api_key", "vps_api_token", "ftp_password", "github_token"):
        if sensitive in updates and updates[sensitive]:
            updates[sensitive] = enc(updates[sensitive])
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
        "Authorization": dec(site["wix_api_key"]),
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


async def crawl_public_site(site: dict, max_pages: int = 12, render_js: bool = True) -> List[dict]:
    """Crawl a public site by URL.
    Strategy:
      1. Try sitemap.xml for URL discovery
      2. Otherwise BFS from base_url (also using rendered JS if render_js=True)
      3. For each URL, fetch with httpx; if it looks like a SPA AND render_js=True, re-fetch with Playwright (headless Chromium) to see the JS-rendered content.
    Extracts per-page: title, meta description, H1/H2 list, word count, images_total, images_without_alt.
    Also detects the framework (Next.js / React CRA / Vite / Vue / static) and reports a `stack_hint`.
    """
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

    def detect_stack(raw_html: str) -> Optional[str]:
        lower = raw_html.lower()
        if "/_next/" in lower or '"__next"' in lower or '<div id="__next"' in lower:
            return "Next.js"
        if 'id="root"' in lower and "react" in lower[:8000]:
            return "React (CRA / Vite)"
        if "data-v-app" in lower or "vue" in lower[:5000]:
            return "Vue.js"
        if "/wp-content/" in lower or "wp-includes" in lower:
            return "WordPress"
        if "wix.com" in lower or "_wixCIDX" in lower:
            return "Wix"
        return None

    async with httpx.AsyncClient(timeout=12, headers=headers, follow_redirects=True) as cli:
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

        # If no sitemap, BFS — but for SPA we may need playwright to extract links
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
                    # If still very few URLs and content is small (SPA), use Playwright to discover links
                    if render_js and len(urls_to_visit) <= 1:
                        rendered_links = await _playwright_discover_links(base_url, host, max_pages)
                        for u in rendered_links:
                            add_url(u)
                            if len(urls_to_visit) >= max_pages:
                                break
            except Exception as exc:
                logger.info("home crawl failed for %s: %s", base_url, exc)

        results: List[dict] = []
        sem = asyncio.Semaphore(4)

        async def fetch_one(u: str) -> Optional[dict]:
            async with sem:
                try:
                    rr = await cli.get(u)
                    if rr.status_code >= 400:
                        return None
                    raw_html = rr.text
                    stack = detect_stack(raw_html)
                    soup = BeautifulSoup(raw_html, "lxml")
                    page_title = (soup.title.string or "").strip() if soup.title else ""
                    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
                    meta_desc = (meta_desc_tag.get("content") or "").strip() if meta_desc_tag else None
                    h1s = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
                    h2s = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)]
                    body_soup = BeautifulSoup(raw_html, "lxml")
                    for tag in body_soup(["script", "style", "noscript"]):
                        tag.decompose()
                    body_text = body_soup.get_text(" ", strip=True)
                    word_count = len([w for w in re.split(r"\s+", body_text) if w])
                    imgs = soup.find_all("img")
                    imgs_total = len(imgs)
                    imgs_no_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
                    spa_markers = bool(soup.find(id=re.compile(r"^(root|app|__next)$"))) or "react" in raw_html.lower()[:5000]
                    is_spa = spa_markers and word_count < 100 and len(h1s) == 0

                    # If SPA, re-fetch with Playwright to see real content
                    rendered = False
                    if is_spa and render_js:
                        try:
                            rendered_data = await _playwright_render_page(u)
                            if rendered_data:
                                rendered = True
                                page_title = rendered_data.get("title") or page_title
                                meta_desc = rendered_data.get("meta_description") or meta_desc
                                h1s = rendered_data.get("h1") or h1s
                                h2s = rendered_data.get("h2") or h2s
                                word_count = max(word_count, rendered_data.get("word_count", 0))
                                imgs_total = max(imgs_total, rendered_data.get("images_total", 0))
                                imgs_no_alt = rendered_data.get("images_without_alt", imgs_no_alt)
                        except Exception as exc:
                            logger.info("playwright render failed for %s: %s", u, exc)
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
                        "js_rendered": rendered,
                        "stack_hint": stack,
                    }
                except Exception as exc:
                    logger.info("crawl page failed %s: %s", u, exc)
                    return None

        tasks = [fetch_one(u) for u in urls_to_visit[:max_pages]]
        for res in await asyncio.gather(*tasks):
            if res:
                results.append(res)
        return results


async def _playwright_discover_links(base_url: str, host: str, max_pages: int) -> List[str]:
    """Render the base URL with headless Chromium and return internal links."""
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return []
    links: List[str] = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(user_agent="LogiSEOBooster/1.0")
                page = await ctx.new_page()
                await page.goto(base_url, wait_until="networkidle", timeout=15000)
                hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                for h in hrefs:
                    if urlparse(h).netloc == host and h not in links:
                        links.append(h.split("#")[0].rstrip("/"))
                        if len(links) >= max_pages:
                            break
            finally:
                await browser.close()
    except Exception as exc:
        logger.info("playwright discover failed: %s", exc)
    return links


async def _playwright_render_page(url: str) -> Optional[dict]:
    """Render a single URL with headless Chromium and extract SEO data after JS execution."""
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(user_agent="LogiSEOBooster/1.0")
                page = await ctx.new_page()
                await page.goto(url, wait_until="networkidle", timeout=15000)
                await page.wait_for_timeout(800)  # allow late hydration
                html = await page.content()
            finally:
                await browser.close()
        soup = BeautifulSoup(html, "lxml")
        title = (soup.title.string or "").strip() if soup.title else ""
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        meta_desc = (meta_desc_tag.get("content") or "").strip() if meta_desc_tag else None
        h1s = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
        h2s = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)]
        body = BeautifulSoup(html, "lxml")
        for tag in body(["script", "style", "noscript"]):
            tag.decompose()
        text = body.get_text(" ", strip=True)
        wc = len([w for w in re.split(r"\s+", text) if w])
        imgs = soup.find_all("img")
        imgs_no_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
        return {
            "title": title or None,
            "meta_description": meta_desc,
            "h1": h1s,
            "h2": h2s,
            "word_count": wc,
            "images_total": len(imgs),
            "images_without_alt": imgs_no_alt,
        }
    except Exception as exc:
        logger.info("playwright render error %s: %s", url, exc)
        return None


async def fetch_wix_pages(site: dict) -> List[dict]:
    """Dispatcher: routes to Wix API or URL crawl depending on site_type. Falls back to mock if both fail."""
    site_type = site.get("site_type", "wix")
    if site_type in ("url_crawl", "vps_api", "ftp"):
        # All non-Wix types are crawled by URL
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
async def publish_to_vps_api(site: dict, draft: dict) -> Optional[dict]:
    """POST the draft content to the VPS mini-API. Returns the JSON response on success."""
    url = (site.get("vps_api_url") or "").rstrip("/") + "/api/seo/publish"
    token = dec(site.get("vps_api_token")) or ""
    payload = {
        "content_type": draft.get("content_type"),
        "title": draft.get("title"),
        "meta_title": draft.get("meta_title"),
        "meta_description": draft.get("meta_description"),
        "body_markdown": draft.get("body_markdown"),
        "keywords": draft.get("keywords", []),
        "faq": draft.get("faq", []),
        "source": "logi-seo-booster",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as cli:
            r = await cli.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload)
        if r.status_code in (200, 201):
            return r.json() if r.headers.get("content-type", "").startswith("application/json") else {"ok": True}
        logger.warning("VPS API publish failed: %s %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("VPS API publish error: %s", exc)
    return None


# ---------- FTP publication --------------------------------------------------
def _slugify(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:80] or gen_id()[:8]


def _markdown_to_html(md: str) -> str:
    """Tiny markdown→HTML converter (headings, paragraphs, lists, tables, bold/italic)."""
    s = (md or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    def table_repl(m):
        lines = m.group(0).strip().split("\n")
        if len(lines) < 2:
            return m.group(0)
        cells = lambda l: [c.strip() for c in l.strip("|").split("|")]
        header = cells(lines[0])
        rows = [cells(l) for l in lines[2:]]
        thead = "<thead><tr>" + "".join(f"<th>{h}</th>" for h in header) + "</tr></thead>"
        tbody = "<tbody>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody>"
        return f"<table>{thead}{tbody}</table>"
    s = re.sub(r"((?:^\|.*\|\s*\n)+)", table_repl, s, flags=re.MULTILINE)
    s = re.sub(r"^### (.+)$", r"<h3>\1</h3>", s, flags=re.MULTILINE)
    s = re.sub(r"^## (.+)$", r"<h2>\1</h2>", s, flags=re.MULTILINE)
    s = re.sub(r"^# (.+)$", r"<h1>\1</h1>", s, flags=re.MULTILINE)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    def ul_repl(m):
        items = m.group(0).strip().split("\n")
        cleaned = [re.sub(r"^\s*[-*] ", "", l) for l in items]
        lis = "".join(f"<li>{c}</li>" for c in cleaned)
        return f"<ul>{lis}</ul>"
    s = re.sub(r"((?:^\s*[-*] .+\n?)+)", ul_repl, s, flags=re.MULTILINE)
    out = []
    for block in re.split(r"\n{2,}", s):
        b = block.strip()
        if not b:
            continue
        if re.match(r"^<(h\d|ul|ol|table|p|li)", b):
            out.append(b)
        else:
            out.append(f"<p>{b.replace(chr(10), '<br/>')}</p>")
    return "\n".join(out)


def _render_html(draft: dict, site: dict) -> str:
    import json as _json
    title = draft.get("title", "")
    meta_title = draft.get("meta_title") or title
    meta_desc = draft.get("meta_description") or ""
    body_html = _markdown_to_html(draft.get("body_markdown", ""))
    faq = draft.get("faq", []) or []
    keywords = draft.get("keywords", []) or []
    slug = _slugify(title)
    canonical_base = (site.get("ftp_public_url") or site.get("base_url") or "").rstrip("/")
    canonical = f"{canonical_base}/{slug}.html" if canonical_base else f"{slug}.html"
    faq_html = ""
    faq_jsonld = ""
    if faq:
        items = "".join(
            f'<details class="faq-item"><summary>{q.get("question","")}</summary>'
            f'<p>{q.get("answer","")}</p></details>'
            for q in faq
        )
        faq_html = f'<section class="faq"><h2>Questions fréquentes</h2>{items}</section>'
        jsonld_obj = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q.get("question", ""),
                 "acceptedAnswer": {"@type": "Answer", "text": q.get("answer", "")}}
                for q in faq
            ],
        }
        faq_jsonld = f'<script type="application/ld+json">{_json.dumps(jsonld_obj, ensure_ascii=False)}</script>'
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{meta_title}</title>
  <meta name="description" content="{meta_desc}">
  <meta name="keywords" content="{', '.join(keywords)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{meta_title}">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical}">
  <meta name="generator" content="LOGI SEO Booster">
  {faq_jsonld}
  <style>
    body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;line-height:1.65;color:#020617}}
    h1{{font-size:2.2rem;line-height:1.2;letter-spacing:-0.01em;margin-bottom:1rem}}
    h2{{font-size:1.5rem;margin-top:2rem;color:#0f172a}}
    h3{{font-size:1.2rem;margin-top:1.4rem;color:#1e293b}}
    p{{margin:0.7rem 0}}
    a{{color:#002FA7}}
    table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.95rem}}
    th,td{{border:1px solid #e2e8f0;padding:.5rem .75rem;text-align:left}}
    th{{background:#f8fafc;font-weight:600}}
    .faq-item{{border:1px solid #e2e8f0;border-radius:6px;padding:.75rem 1rem;margin:.5rem 0}}
    .faq-item summary{{cursor:pointer;font-weight:600;color:#020617}}
    .faq-item p{{margin-top:.5rem;color:#334155}}
    .meta{{color:#64748b;font-size:.85rem;margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid #e2e8f0}}
  </style>
</head>
<body>
  <article>
    <h1>{title}</h1>
    <div class="meta">Publié le {datetime.now(timezone.utc).strftime("%d/%m/%Y")} · {site.get("name","")}</div>
    {body_html}
    {faq_html}
  </article>
</body>
</html>
"""


async def publish_to_ftp(site: dict, draft: dict) -> Optional[dict]:
    """Upload HTML + JSON files to the configured FTP server."""
    import json as _json
    from ftplib import FTP, error_perm
    from io import BytesIO

    host = site.get("ftp_host")
    port = site.get("ftp_port") or 21
    user = site.get("ftp_user")
    pwd = dec(site.get("ftp_password"))
    remote_path = (site.get("ftp_remote_path") or "/").rstrip("/") + "/"
    if not all((host, user, pwd, remote_path)):
        return None

    slug = _slugify(draft.get("title", ""))
    html_bytes = _render_html(draft, site).encode("utf-8")
    json_bytes = _json.dumps({
        "id": draft.get("id"),
        "slug": slug,
        "title": draft.get("title"),
        "meta_title": draft.get("meta_title"),
        "meta_description": draft.get("meta_description"),
        "content_type": draft.get("content_type"),
        "body_markdown": draft.get("body_markdown"),
        "keywords": draft.get("keywords", []),
        "faq": draft.get("faq", []),
        "published_at": now_iso(),
    }, ensure_ascii=False, indent=2).encode("utf-8")

    def _do_upload() -> dict:
        ftp = FTP()
        ftp.connect(host, port, timeout=15)
        ftp.login(user, pwd)
        # Ensure remote_path exists
        parts = [p for p in remote_path.strip("/").split("/") if p]
        cur = ""
        for p in parts:
            cur = (cur + "/" + p) if cur else "/" + p
            try:
                ftp.cwd(cur)
            except error_perm:
                try:
                    ftp.mkd(cur)
                    ftp.cwd(cur)
                except error_perm:
                    pass
        ftp.storbinary(f"STOR {slug}.html", BytesIO(html_bytes))
        ftp.storbinary(f"STOR {slug}.json", BytesIO(json_bytes))
        ftp.quit()
        return {"slug": slug, "files": [f"{slug}.html", f"{slug}.json"], "remote_path": remote_path}

    try:
        return await asyncio.to_thread(_do_upload)
    except Exception as exc:
        logger.warning("FTP publish error: %s", exc)
        return None


@api.post("/sites/{site_id}/test-ftp")
async def test_ftp_connection(site_id: str, user=Depends(get_current_user)):
    """Test FTP credentials without uploading anything."""
    from ftplib import FTP
    site = await _get_user_site(site_id, user)
    if site.get("site_type") != "ftp":
        raise HTTPException(400, "Ce site n'est pas configuré en FTP.")
    def _do_test() -> dict:
        ftp = FTP()
        ftp.connect(site["ftp_host"], site.get("ftp_port") or 21, timeout=10)
        ftp.login(site["ftp_user"], dec(site["ftp_password"]))
        try:
            ftp.cwd(site.get("ftp_remote_path") or "/")
            cwd = ftp.pwd()
        except Exception:
            cwd = "?"
        ftp.quit()
        return {"ok": True, "cwd": cwd}
    try:
        return await asyncio.to_thread(_do_test)
    except Exception as exc:
        raise HTTPException(502, f"Connexion FTP impossible : {exc}")


# ---------------------------------------------------------------------------
# GitHub publishing (commit HTML files to a repo via PAT)
# ---------------------------------------------------------------------------
GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


def _github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "LOGI-SEO-Booster",
    }


async def _github_get_file_sha(client: httpx.AsyncClient, token: str, owner: str, repo: str, path: str, branch: str) -> Optional[str]:
    """Return the SHA of an existing file, or None if it does not exist."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    resp = await client.get(url, headers=_github_headers(token), params={"ref": branch})
    if resp.status_code == 200:
        return resp.json().get("sha")
    if resp.status_code == 404:
        return None
    raise HTTPException(
        502,
        f"GitHub GET contents a échoué ({resp.status_code}): {resp.text[:200]}"
    )


async def _github_put_file(
    client: httpx.AsyncClient,
    token: str,
    owner: str,
    repo: str,
    path: str,
    branch: str,
    message: str,
    content_text: str,
    sha: Optional[str],
) -> dict:
    """Create or update a file via the GitHub contents API. Returns {commit_sha, commit_url, html_url}."""
    import base64
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    encoded = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    payload = {"message": message, "content": encoded, "branch": branch}
    if sha:
        payload["sha"] = sha
    resp = await client.put(url, headers=_github_headers(token), json=payload)
    if resp.status_code not in (200, 201):
        raise HTTPException(
            502,
            f"GitHub PUT contents a échoué ({resp.status_code}): {resp.text[:300]}"
        )
    data = resp.json()
    commit = data.get("commit") or {}
    content = data.get("content") or {}
    return {
        "commit_sha": commit.get("sha"),
        "commit_url": commit.get("html_url"),
        "file_url": content.get("html_url"),
        "path": content.get("path") or path,
    }


@api.post("/sites/{site_id}/test-github")
async def test_github_connection(site_id: str, user=Depends(get_current_user)):
    """Verify GitHub PAT + repo + branch are valid by listing the target folder."""
    site = await _get_user_site(site_id, user)
    token = dec(site.get("github_token"))
    owner = site.get("github_owner")
    repo = site.get("github_repo")
    branch = site.get("github_branch") or "main"
    folder = (site.get("github_folder") or "").strip("/")
    if not (token and owner and repo):
        raise HTTPException(400, "Configurez d'abord github_token, github_owner et github_repo sur ce site.")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Check repo + branch exists
        repo_resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/branches/{branch}",
            headers=_github_headers(token),
        )
        if repo_resp.status_code == 401:
            raise HTTPException(401, "Token GitHub invalide ou expiré.")
        if repo_resp.status_code == 404:
            raise HTTPException(404, f"Repo introuvable ou branche '{branch}' inexistante. Vérifiez owner/repo/branch et les permissions du token.")
        if repo_resp.status_code != 200:
            raise HTTPException(502, f"Erreur GitHub ({repo_resp.status_code}): {repo_resp.text[:200]}")
        repo_data = repo_resp.json()
        # 2. List target folder (if specified) to confirm path
        listing = []
        if folder:
            list_resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{folder}",
                headers=_github_headers(token),
                params={"ref": branch},
            )
            if list_resp.status_code == 200:
                items = list_resp.json()
                if isinstance(items, list):
                    listing = [{"name": i.get("name"), "type": i.get("type")} for i in items[:20]]
            elif list_resp.status_code == 404:
                listing = []  # folder doesn't exist yet — will be created on first commit
            else:
                raise HTTPException(502, f"Erreur GitHub ({list_resp.status_code}): {list_resp.text[:200]}")
        else:
            # List root
            list_resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents",
                headers=_github_headers(token),
                params={"ref": branch},
            )
            if list_resp.status_code == 200:
                items = list_resp.json()
                if isinstance(items, list):
                    listing = [{"name": i.get("name"), "type": i.get("type")} for i in items[:20]]
        return {
            "ok": True,
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "folder": folder or "(racine)",
            "commit_sha": (repo_data.get("commit") or {}).get("sha", "")[:7],
            "listing": listing,
        }


@api.post("/drafts/{draft_id}/publish-github")
async def publish_draft_to_github(draft_id: str, user=Depends(get_current_user)):
    """Commit the draft's HTML file (and JSON) to the configured GitHub repo."""
    import json as _json
    d = await db.drafts.find_one({"id": draft_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Brouillon introuvable")
    site = await db.sites.find_one({"id": d["site_id"], "user_id": user["id"]}, {"_id": 0}) or {}
    token = dec(site.get("github_token"))
    owner = site.get("github_owner")
    repo = site.get("github_repo")
    branch = site.get("github_branch") or "main"
    folder = (site.get("github_folder") or "").strip("/")
    if not (token and owner and repo):
        raise HTTPException(400, "GitHub n'est pas configuré pour ce site. Configurez le token, owner et repo dans la page Sites.")

    slug = _slugify(d.get("title", ""))
    html_str = _render_html(d, site)
    json_str = _json.dumps({
        "id": d.get("id"),
        "slug": slug,
        "title": d.get("title"),
        "meta_title": d.get("meta_title"),
        "meta_description": d.get("meta_description"),
        "content_type": d.get("content_type"),
        "body_markdown": d.get("body_markdown"),
        "keywords": d.get("keywords", []),
        "faq": d.get("faq", []),
        "published_at": now_iso(),
    }, ensure_ascii=False, indent=2)

    html_path = f"{folder}/{slug}.html" if folder else f"{slug}.html"
    json_path = f"{folder}/{slug}.json" if folder else f"{slug}.json"
    commit_msg = f"LOGI SEO: publish {slug} ({d.get('content_type','article')})"

    results = []
    sitemap_result = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        for path, content in ((html_path, html_str), (json_path, json_str)):
            existing_sha = await _github_get_file_sha(client, token, owner, repo, path, branch)
            res = await _github_put_file(client, token, owner, repo, path, branch, commit_msg, content, existing_sha)
            res["updated"] = existing_sha is not None
            results.append(res)
        # Update sitemap.xml if public URL is configured
        public_base = (site.get("github_public_url") or "").rstrip("/")
        if public_base:
            page_url = f"{public_base}/{slug}.html"
            try:
                sitemap_result = await _github_update_sitemap(client, token, owner, repo, branch, folder, page_url, slug)
            except Exception as exc:
                logger.warning("Sitemap update failed: %s", exc)
                sitemap_result = {"error": str(exc)}

    # Update draft status
    public_base = (site.get("github_public_url") or "").rstrip("/")
    public_url = f"{public_base}/{slug}.html" if public_base else None
    await db.drafts.update_one(
        {"id": draft_id},
        {"$set": {
            "status": "published",
            "github_commit_sha": results[0].get("commit_sha"),
            "github_committed_at": now_iso(),
            "github_public_url": public_url,
        }},
    )
    return {
        "ok": True,
        "files": results,
        "sitemap": sitemap_result,
        "public_url": public_url,
        "commit_sha": results[0].get("commit_sha"),
        "commit_url": results[0].get("commit_url"),
    }


async def _github_update_sitemap(client, token, owner, repo, branch, folder, page_url, slug):
    """Add page_url to sitemap.xml in the repo. Looks for sitemap at known locations.
    Strategy: try `public/sitemap.xml`, then `sitemap.xml`, then `folder/sitemap.xml`.
    If not found, create a minimal sitemap.xml in the same folder as the page.
    """
    import base64
    candidate_paths = ["public/sitemap.xml", "sitemap.xml"]
    if folder:
        candidate_paths.insert(0, f"{folder}/sitemap.xml")
        # Also check for sitemap at the root of public/ inferred from folder
        if "/" in folder:
            root = folder.split("/")[0]
            candidate_paths.insert(0, f"{root}/sitemap.xml")
    seen = set()
    candidate_paths = [p for p in candidate_paths if not (p in seen or seen.add(p))]

    existing_sha = None
    existing_xml = None
    existing_path = None
    for path in candidate_paths:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        r = await client.get(url, headers=_github_headers(token), params={"ref": branch})
        if r.status_code == 200:
            data = r.json()
            existing_sha = data.get("sha")
            try:
                existing_xml = base64.b64decode(data.get("content", "")).decode("utf-8")
            except Exception:
                existing_xml = None
            existing_path = path
            break

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_entry = f'  <url>\n    <loc>{page_url}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>'

    if existing_xml and "<urlset" in existing_xml:
        # If URL already present, just update the lastmod via simple regex
        import re
        if page_url in existing_xml:
            new_xml = re.sub(
                r"(<url>\s*<loc>" + re.escape(page_url) + r"</loc>\s*<lastmod>)[^<]*(</lastmod>)",
                rf"\g<1>{today}\g<2>",
                existing_xml,
            )
            action = "updated_existing_entry"
        else:
            # Insert new entry before closing </urlset>
            new_xml = existing_xml.replace("</urlset>", f"{new_entry}\n</urlset>")
            action = "appended_entry"
        target_path = existing_path
    else:
        # Create a new minimal sitemap
        new_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{new_entry}\n"
            "</urlset>\n"
        )
        target_path = f"{folder}/sitemap.xml" if folder else "public/sitemap.xml"
        action = "created_new"
        existing_sha = None

    msg = f"LOGI SEO: sitemap.xml — {action} ({slug})"
    res = await _github_put_file(client, token, owner, repo, target_path, branch, msg, new_xml, existing_sha)
    return {"path": target_path, "action": action, "commit_sha": res.get("commit_sha"), "commit_url": res.get("commit_url")}


@api.get("/drafts/{draft_id}/export")
async def export_draft(draft_id: str, user=Depends(get_current_user)):
    """Generate and return a ZIP file with HTML + JSON ready to FTP-upload manually."""
    from fastapi.responses import Response
    import json as _json
    import zipfile
    from io import BytesIO

    d = await db.drafts.find_one({"id": draft_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Brouillon introuvable")
    site = await db.sites.find_one({"id": d["site_id"], "user_id": user["id"]}, {"_id": 0}) or {}

    slug = _slugify(d.get("title", ""))
    html_str = _render_html(d, site)
    json_str = _json.dumps({
        "id": d.get("id"),
        "slug": slug,
        "title": d.get("title"),
        "meta_title": d.get("meta_title"),
        "meta_description": d.get("meta_description"),
        "content_type": d.get("content_type"),
        "body_markdown": d.get("body_markdown"),
        "keywords": d.get("keywords", []),
        "faq": d.get("faq", []),
        "published_at": now_iso(),
    }, ensure_ascii=False, indent=2)

    readme = f"""LOGI SEO Booster — Export manuel
================================

Contenu généré le {datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")}

Fichiers inclus :
- {slug}.html : page HTML complète, optimisée SEO (canonical, Open Graph,
  JSON-LD FAQ schema, mobile-friendly). Indexable directement par Google.
- {slug}.json : données structurées (à consommer côté React/JS si besoin).

Comment publier :
1. Connectez-vous à votre FTP (FileZilla, Cyberduck, WinSCP, etc.)
2. Naviguez vers votre dossier web (ex: /public_html/blog ou /var/www/.../blog)
3. Uploadez les 2 fichiers
4. Votre contenu sera accessible à :
     https://VOTRE-DOMAINE/blog/{slug}.html

Astuce SEO : ajoutez ce nouveau lien à votre sitemap.xml et soumettez-le
dans Google Search Console pour accélérer l'indexation.
"""

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug}.html", html_str)
        zf.writestr(f"{slug}.json", json_str)
        zf.writestr("README.txt", readme)
    buf.seek(0)
    filename = f"logi-seo-{slug}.zip"
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.get("/drafts/{draft_id}/export.html")
async def export_draft_html(draft_id: str, user=Depends(get_current_user)):
    """Return just the HTML file for direct download."""
    from fastapi.responses import Response

    d = await db.drafts.find_one({"id": draft_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Brouillon introuvable")
    site = await db.sites.find_one({"id": d["site_id"], "user_id": user["id"]}, {"_id": 0}) or {}
    slug = _slugify(d.get("title", ""))
    return Response(
        content=_render_html(d, site),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}.html"'},
    )


# ---------- end FTP helpers --------------------------------------------------


@api.post("/drafts/{draft_id}/publish", response_model=DraftPublic)
async def publish_draft(draft_id: str, payload: PublishRequest, user=Depends(get_current_user)):
    d = await db.drafts.find_one({"id": draft_id, "user_id": user["id"]})
    if not d:
        raise HTTPException(404, "Brouillon introuvable")
    site = await _get_user_site(d["site_id"], user)

    site_type = site.get("site_type", "wix")
    wix_draft_id: Optional[str] = None
    vps_published_id: Optional[str] = None
    ftp_published_slug: Optional[str] = None
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
    elif site_type == "vps_api":
        vps_resp = await publish_to_vps_api(site, d)
        if vps_resp:
            vps_published_id = vps_resp.get("id") or vps_resp.get("slug") or "published"
            status_label = "vps_success"
        else:
            status_label = "vps_unavailable"
    elif site_type == "ftp":
        ftp_resp = await publish_to_ftp(site, d)
        if ftp_resp:
            ftp_published_slug = ftp_resp.get("slug")
            status_label = "ftp_success"
        else:
            status_label = "ftp_unavailable"
    else:
        status_label = "ready_for_export"

    log_entry = {
        "id": gen_id(),
        "user_id": user["id"],
        "site_id": d["site_id"],
        "draft_id": draft_id,
        "title": d["title"],
        "action": "publish_attempt",
        "wix_draft_id": wix_draft_id,
        "vps_published_id": vps_published_id,
        "ftp_published_slug": ftp_published_slug,
        "status": status_label,
        "site_type": site_type,
        "created_at": now_iso(),
    }
    await db.publish_logs.insert_one(log_entry)

    is_published = bool(wix_draft_id or vps_published_id or ftp_published_slug)
    updates = {
        "wix_draft_id": wix_draft_id,
        "status": "published" if is_published else "ready",
        "updated_at": now_iso(),
    }
    if is_published:
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
# Google OAuth 2.0 + Search Console + Analytics (real, replaces mocks)
# ---------------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
    "openid",
    "email",
]


def _google_oauth_client_config() -> dict:
    if not (GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI):
        raise HTTPException(503, "Google OAuth n'est pas configuré côté serveur. Demandez à l'admin de renseigner GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI dans backend/.env.")
    return {
        "web": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_OAUTH_REDIRECT_URI],
        }
    }


async def _get_google_credentials(user_id: str):
    """Load + auto-refresh Google credentials for a user. Returns google.oauth2.credentials.Credentials."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest

    doc = await db.users.find_one({"id": user_id}, {"google_oauth": 1, "_id": 0})
    gc = (doc or {}).get("google_oauth")
    if not gc or not gc.get("refresh_token"):
        raise HTTPException(401, "Google non connecté. Connectez votre compte Google dans la page Performance.")
    creds = Credentials(
        token=dec(gc.get("access_token")),
        refresh_token=dec(gc["refresh_token"]),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_OAUTH_CLIENT_ID,
        client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=gc.get("scopes", GOOGLE_SCOPES),
    )
    if not creds.valid:
        try:
            await asyncio.to_thread(creds.refresh, GoogleRequest())
            await db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "google_oauth.access_token": enc(creds.token),
                    "google_oauth.expiry": creds.expiry.isoformat() if creds.expiry else None,
                }},
            )
        except Exception as exc:
            logger.warning("Google refresh failed for user %s: %s", user_id, exc)
            raise HTTPException(401, f"Token Google expiré ou révoqué. Reconnectez votre compte Google. ({exc})")
    return creds


@api.get("/google/status")
async def google_status(user=Depends(get_current_user)):
    """Return whether the user has connected Google + which features are configured per site."""
    doc = await db.users.find_one({"id": user["id"]}, {"google_oauth": 1, "google_email": 1, "_id": 0})
    gc = (doc or {}).get("google_oauth") or {}
    configured = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI)
    return {
        "server_configured": configured,
        "connected": bool(gc.get("refresh_token")),
        "google_email": (doc or {}).get("google_email"),
        "scopes": gc.get("scopes", []),
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI if configured else None,
    }


@api.get("/google/login")
async def google_login(user=Depends(get_current_user)):
    """Return the Google authorization URL. Frontend should open it in a popup or full-page redirect."""
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(_google_oauth_client_config(), scopes=GOOGLE_SCOPES)
    flow.redirect_uri = GOOGLE_OAUTH_REDIRECT_URI
    # encode user_id in state (signed via jwt to prevent tampering)
    state_token = jwt.encode(
        {"sub": user["id"], "exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state_token,
    )
    return {"authorization_url": auth_url}


@api.get("/google/callback")
async def google_callback(code: str, state: str, scope: Optional[str] = None):
    """OAuth callback. Exchanges code for tokens, stores refresh_token, redirects to frontend /performance."""
    from google_auth_oauthlib.flow import Flow
    from fastapi.responses import RedirectResponse
    # Decode state to get user_id
    try:
        payload = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload["sub"]
    except Exception as exc:
        raise HTTPException(400, f"État OAuth invalide ou expiré: {exc}")

    flow = Flow.from_client_config(_google_oauth_client_config(), scopes=GOOGLE_SCOPES, state=state)
    flow.redirect_uri = GOOGLE_OAUTH_REDIRECT_URI
    callback_url = f"{GOOGLE_OAUTH_REDIRECT_URI}?code={code}&state={state}"
    if scope:
        callback_url += f"&scope={scope}"
    try:
        await asyncio.to_thread(flow.fetch_token, authorization_response=callback_url)
    except Exception as exc:
        raise HTTPException(400, f"Échec d'échange du code OAuth: {exc}")

    creds = flow.credentials
    if not creds.refresh_token:
        raise HTTPException(400, "Pas de refresh_token reçu de Google. Révoquez l'accès dans https://myaccount.google.com/permissions et reconnectez.")

    # Get user's Google email via userinfo endpoint for display
    google_email = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            if r.status_code == 200:
                google_email = r.json().get("email")
    except Exception:
        pass

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "google_oauth": {
                "access_token": enc(creds.token),
                "refresh_token": enc(creds.refresh_token),
                "scopes": list(creds.scopes or GOOGLE_SCOPES),
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
                "connected_at": now_iso(),
            },
            "google_email": google_email,
        }},
    )

    # Redirect to frontend
    # Frontend URL is derived from redirect_uri (replace /api/google/callback with /performance?google=connected)
    frontend_url = GOOGLE_OAUTH_REDIRECT_URI.replace("/api/google/callback", "/performance?google=connected")
    return RedirectResponse(url=frontend_url)


@api.post("/google/disconnect")
async def google_disconnect(user=Depends(get_current_user)):
    await db.users.update_one(
        {"id": user["id"]},
        {"$unset": {"google_oauth": "", "google_email": ""}},
    )
    return {"ok": True}


@api.get("/google/gsc-sites")
async def google_list_gsc_sites(user=Depends(get_current_user)):
    """List Search Console properties the user has access to."""
    from googleapiclient.discovery import build
    creds = await _get_google_credentials(user["id"])
    def _list():
        service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        return service.sites().list().execute()
    try:
        data = await asyncio.to_thread(_list)
    except Exception as exc:
        raise HTTPException(502, f"Erreur Search Console: {exc}")
    items = data.get("siteEntry", [])
    return {"sites": [{"site_url": s.get("siteUrl"), "permission": s.get("permissionLevel")} for s in items]}


class GoogleSiteSettings(BaseModel):
    gsc_site_url: Optional[str] = None  # e.g. "https://www.logirent.ch/" or "sc-domain:logirent.ch"
    ga4_property_id: Optional[str] = None  # e.g. "123456789"


@api.patch("/sites/{site_id}/google-settings", response_model=SitePublic)
async def update_site_google_settings(site_id: str, payload: GoogleSiteSettings, user=Depends(get_current_user)):
    site = await db.sites.find_one({"id": site_id, "user_id": user["id"]})
    if not site:
        raise HTTPException(404, "Site introuvable")
    updates = {}
    if payload.gsc_site_url is not None:
        updates["gsc_site_url"] = payload.gsc_site_url.strip() or None
    if payload.ga4_property_id is not None:
        updates["ga4_property_id"] = (payload.ga4_property_id or "").strip() or None
    if updates:
        await db.sites.update_one({"id": site_id}, {"$set": updates})
    site = await db.sites.find_one({"id": site_id}, {"_id": 0})
    return site_to_public(site)


@api.get("/sites/{site_id}/performance-real")
async def site_performance_real(site_id: str, days: int = 28, user=Depends(get_current_user)):
    """Fetch real GSC + GA4 performance for a site over the last N days."""
    from googleapiclient.discovery import build
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

    site = await _get_user_site(site_id, user)
    gsc_url = site.get("gsc_site_url")
    ga4_id = site.get("ga4_property_id")
    if not (gsc_url or ga4_id):
        raise HTTPException(400, "Aucune propriété GSC ni GA4 n'est configurée pour ce site. Allez sur Performance → Configurer Google.")

    creds = await _get_google_credentials(user["id"])
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)

    result: Dict[str, Any] = {"site_id": site_id, "label": site.get("label"), "mocked": False,
                              "gsc_site_url": gsc_url, "ga4_property_id": ga4_id,
                              "period": {"start": start_date.isoformat(), "end": end_date.isoformat()}}

    # --- GSC ---
    if gsc_url:
        def _gsc():
            svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
            # Daily aggregates
            daily = svc.searchanalytics().query(siteUrl=gsc_url, body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["date"],
                "rowLimit": 1000,
            }).execute()
            # Top queries
            queries = svc.searchanalytics().query(siteUrl=gsc_url, body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 25,
            }).execute()
            return daily, queries
        try:
            daily_data, queries_data = await asyncio.to_thread(_gsc)
            daily_rows = []
            for r in daily_data.get("rows", []):
                impressions = r.get("impressions", 0)
                clicks = r.get("clicks", 0)
                daily_rows.append({
                    "date": r["keys"][0],
                    "impressions": int(impressions),
                    "clicks": int(clicks),
                    "ctr": round((r.get("ctr") or 0) * 100, 2),
                    "position": round(r.get("position") or 0, 1),
                })
            keywords = []
            for r in queries_data.get("rows", []):
                keywords.append({
                    "keyword": r["keys"][0],
                    "clicks": int(r.get("clicks", 0)),
                    "impressions": int(r.get("impressions", 0)),
                    "ctr": round((r.get("ctr") or 0) * 100, 2),
                    "position": round(r.get("position") or 0, 1),
                })
            result["gsc"] = {
                "daily": daily_rows,
                "keywords": keywords,
                "totals": {
                    "impressions": sum(d["impressions"] for d in daily_rows),
                    "clicks": sum(d["clicks"] for d in daily_rows),
                    "avg_position": round(sum(d["position"] for d in daily_rows) / len(daily_rows), 1) if daily_rows else 0,
                    "avg_ctr": round(sum(d["ctr"] for d in daily_rows) / len(daily_rows), 2) if daily_rows else 0,
                },
            }
        except HTTPException:
            raise
        except Exception as exc:
            result["gsc_error"] = f"Erreur Search Console: {exc}"

    # --- GA4 ---
    if ga4_id:
        def _ga4():
            client = BetaAnalyticsDataClient(credentials=creds)
            req = RunReportRequest(
                property=f"properties/{ga4_id}",
                date_ranges=[DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())],
                dimensions=[Dimension(name="date")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="totalUsers"),
                    Metric(name="bounceRate"),
                    Metric(name="conversions"),
                    Metric(name="engagementRate"),
                ],
            )
            return client.run_report(req)
        try:
            resp = await asyncio.to_thread(_ga4)
            rows = []
            for row in resp.rows:
                d = row.dimension_values[0].value  # YYYYMMDD
                pretty = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
                rows.append({
                    "date": pretty,
                    "sessions": int(float(row.metric_values[0].value or 0)),
                    "users": int(float(row.metric_values[1].value or 0)),
                    "bounce_rate": round(float(row.metric_values[2].value or 0) * 100, 1),
                    "conversions": int(float(row.metric_values[3].value or 0)),
                    "engagement_rate": round(float(row.metric_values[4].value or 0) * 100, 1),
                })
            rows.sort(key=lambda x: x["date"])
            result["ga4"] = {
                "daily": rows,
                "totals": {
                    "sessions": sum(r["sessions"] for r in rows),
                    "users": sum(r["users"] for r in rows),
                    "avg_bounce_rate": round(sum(r["bounce_rate"] for r in rows) / len(rows), 1) if rows else 0,
                    "conversions": sum(r["conversions"] for r in rows),
                },
            }
        except Exception as exc:
            result["ga4_error"] = f"Erreur GA4: {exc}"

    return result


# ---------------------------------------------------------------------------
# Rank Tracking (snapshots quotidiens de la position GSC par mot-clé)
# ---------------------------------------------------------------------------
async def _capture_rank_snapshot(user_id: str, site_id: str, lookback_days: int = 7) -> dict:
    """Fetch top GSC queries for the last `lookback_days` and persist a snapshot for today."""
    from googleapiclient.discovery import build
    site = await db.sites.find_one({"id": site_id, "user_id": user_id}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Site introuvable")
    gsc_url = site.get("gsc_site_url")
    if not gsc_url:
        raise HTTPException(400, "Aucune propriété GSC n'est configurée pour ce site.")
    creds = await _get_google_credentials(user_id)
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=lookback_days)
    def _query():
        svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        return svc.searchanalytics().query(siteUrl=gsc_url, body={
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query"],
            "rowLimit": 100,
        }).execute()
    data = await asyncio.to_thread(_query)
    today_iso = end_date.isoformat()
    # Idempotent: delete today's snapshot for this site before inserting
    await db.rank_snapshots.delete_many({"user_id": user_id, "site_id": site_id, "snapshot_date": today_iso})
    rows = data.get("rows", [])
    docs = []
    for r in rows:
        docs.append({
            "id": gen_id(),
            "user_id": user_id,
            "site_id": site_id,
            "keyword": r["keys"][0],
            "position": round(r.get("position") or 0, 1),
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": round((r.get("ctr") or 0) * 100, 2),
            "snapshot_date": today_iso,
            "lookback_days": lookback_days,
            "created_at": now_iso(),
        })
    if docs:
        await db.rank_snapshots.insert_many(docs)
    return {"snapshot_date": today_iso, "count": len(docs)}


@api.post("/sites/{site_id}/rank-snapshot")
async def take_rank_snapshot(site_id: str, user=Depends(get_current_user)):
    """Manually trigger a rank snapshot for today."""
    return await _capture_rank_snapshot(user["id"], site_id)


@api.get("/sites/{site_id}/rank-tracking")
async def get_rank_tracking(site_id: str, days: int = 30, top: int = 20, user=Depends(get_current_user)):
    """Return per-keyword time series for the last N days. Returns the top-N keywords by latest clicks."""
    await _get_user_site(site_id, user)
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    cursor = db.rank_snapshots.find(
        {"user_id": user["id"], "site_id": site_id, "snapshot_date": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("snapshot_date", 1)
    snapshots = await cursor.to_list(50000)
    if not snapshots:
        return {"site_id": site_id, "days": days, "snapshots_count": 0, "dates": [], "keywords": []}
    # Distinct dates (sorted)
    dates = sorted({s["snapshot_date"] for s in snapshots})
    # Pick top-N keywords by clicks in the latest snapshot
    latest_date = dates[-1]
    latest_kw = sorted(
        [s for s in snapshots if s["snapshot_date"] == latest_date],
        key=lambda s: -s["clicks"],
    )[:top]
    keyword_list = [k["keyword"] for k in latest_kw]
    # Build per-keyword series
    series = []
    for kw in keyword_list:
        kw_snaps = [s for s in snapshots if s["keyword"] == kw]
        kw_snaps.sort(key=lambda s: s["snapshot_date"])
        oldest = kw_snaps[0]
        newest = kw_snaps[-1]
        delta = round(oldest["position"] - newest["position"], 1)  # positive = improved (lower position = better)
        series.append({
            "keyword": kw,
            "current_position": newest["position"],
            "current_clicks": newest["clicks"],
            "current_impressions": newest["impressions"],
            "current_ctr": newest["ctr"],
            "previous_position": oldest["position"],
            "delta": delta,
            "trend": "up" if delta > 0.5 else "down" if delta < -0.5 else "stable",
            "series": [{"date": s["snapshot_date"], "position": s["position"]} for s in kw_snaps],
        })
    return {
        "site_id": site_id,
        "days": days,
        "snapshots_count": len(dates),
        "dates": dates,
        "latest_date": latest_date,
        "keywords": series,
    }


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
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    client.close()


# ---------------------------------------------------------------------------
# Scheduler: daily rank snapshot at 04:00 UTC for every site that has GSC config
# ---------------------------------------------------------------------------
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler(timezone="UTC")


async def _daily_rank_snapshots_job():
    """Background task: snapshot rank tracking for every site that has GSC + connected user."""
    try:
        # Find all sites with a GSC URL configured
        sites = await db.sites.find({"gsc_site_url": {"$exists": True, "$ne": None}}, {"_id": 0}).to_list(1000)
        for s in sites:
            uid = s.get("user_id")
            sid = s.get("id")
            if not uid or not sid:
                continue
            try:
                user_doc = await db.users.find_one({"id": uid}, {"google_oauth": 1})
                if not (user_doc or {}).get("google_oauth", {}).get("refresh_token"):
                    continue
                res = await _capture_rank_snapshot(uid, sid, lookback_days=7)
                logger.info("Daily rank snapshot done for site %s: %s keywords", sid, res.get("count"))
            except Exception as exc:
                logger.warning("Rank snapshot failed for site %s: %s", sid, exc)
    except Exception as exc:
        logger.error("Scheduler job _daily_rank_snapshots_job error: %s", exc)


@app.on_event("startup")
async def _start_scheduler():
    try:
        scheduler.add_job(_daily_rank_snapshots_job, "cron", hour=4, minute=0, id="daily_rank_snapshots", replace_existing=True)
        scheduler.start()
        logger.info("Scheduler started — daily rank snapshots at 04:00 UTC")
    except Exception as exc:
        logger.warning("Scheduler failed to start: %s", exc)
