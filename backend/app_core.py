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
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request
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
    linkedin_post_urn: Optional[str] = None
    linkedin_post_url: Optional[str] = None
    linkedin_posted_at: Optional[str] = None
    facebook_post_id: Optional[str] = None
    facebook_post_url: Optional[str] = None
    facebook_posted_at: Optional[str] = None
    instagram_post_id: Optional[str] = None
    instagram_post_url: Optional[str] = None
    instagram_posted_at: Optional[str] = None
    gbp_post_name: Optional[str] = None
    gbp_post_url: Optional[str] = None
    gbp_posted_at: Optional[str] = None
    cover_image_url: Optional[str] = None
    cover_image_alt: Optional[str] = None
    cover_image_credit: Optional[str] = None
    cover_image_credit_url: Optional[str] = None
    image_query: Optional[str] = None


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


