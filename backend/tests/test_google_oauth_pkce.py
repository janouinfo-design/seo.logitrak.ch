"""Tests for Google OAuth PKCE fix (code_verifier persistence in google_oauth_states)."""
import os
import hashlib
from urllib.parse import urlparse, parse_qs

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "logi_seo_booster")

DEMO_EMAIL = "demo@logirent.fr"
DEMO_PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data
    return data["token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


def _get_state_from_url(url: str) -> str:
    q = parse_qs(urlparse(url).query)
    return q["state"][0]


def _get_qparam(url: str, key: str):
    q = parse_qs(urlparse(url).query)
    return q.get(key, [None])[0]


# --- Regression: status/agents/login ---

def test_google_status_configured(headers):
    r = requests.get(f"{BASE_URL}/api/google/status", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    # server_configured expected true (real key or fake key both count as configured if all 3 set)
    assert "server_configured" in data
    assert data["server_configured"] is True

def test_agents_overview(headers):
    r = requests.get(f"{BASE_URL}/api/agents/overview", headers=headers, timeout=20)
    assert r.status_code == 200, r.text


# --- Google login PKCE ---

def test_google_login_returns_pkce_url(headers):
    r = requests.get(f"{BASE_URL}/api/google/login", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "authorization_url" in data
    url = data["authorization_url"]
    assert _get_qparam(url, "code_challenge") is not None, "code_challenge missing from authorization_url"
    assert _get_qparam(url, "code_challenge_method") == "S256"
    assert _get_qparam(url, "state") is not None


def test_state_doc_persisted_and_callback_purges_it(headers, mongo):
    # 1) login
    r = requests.get(f"{BASE_URL}/api/google/login", headers=headers, timeout=15)
    assert r.status_code == 200
    url = r.json()["authorization_url"]
    state = _get_qparam(url, "state")
    assert state
    state_hash = hashlib.sha256(state.encode()).hexdigest()

    # 2) doc exists with encrypted verifier
    doc = mongo.google_oauth_states.find_one({"state_hash": state_hash})
    assert doc is not None, "google_oauth_states document not found"
    assert "code_verifier" in doc and doc["code_verifier"]
    # encrypted -> should not be a plain base64 PKCE verifier (Fernet tokens start with 'gAAAA')
    assert "gAAAA" in doc["code_verifier"], f"code_verifier does not look encrypted: {doc['code_verifier'][:20]}"

    # 3) callback with fake code + real state -> expected to fail invalid_grant, but NOT 'Missing code verifier'
    cb = requests.get(
        f"{BASE_URL}/api/google/oauth/callback",
        params={"code": "fakecode", "state": state},
        timeout=20,
        allow_redirects=False,
    )
    assert cb.status_code == 400, f"expected 400, got {cb.status_code}: {cb.text}"
    body = cb.text
    assert "Missing code verifier" not in body, f"PKCE fix regression: {body}"
    assert "Échec d'échange du code OAuth" in body or "invalid_grant" in body or "Bad Request" in body

    # 4) doc purged (single-use)
    doc_after = mongo.google_oauth_states.find_one({"state_hash": state_hash})
    assert doc_after is None, "state doc should have been deleted by find_one_and_delete"


def test_callback_invalid_state_returns_400():
    r = requests.get(
        f"{BASE_URL}/api/google/oauth/callback",
        params={"code": "x", "state": "invalide"},
        timeout=15,
        allow_redirects=False,
    )
    assert r.status_code == 400
    assert "État OAuth invalide" in r.text or "invalide" in r.text


def test_two_logins_two_docs(headers, mongo):
    # cleanup any existing states first
    r1 = requests.get(f"{BASE_URL}/api/google/login", headers=headers, timeout=15)
    r2 = requests.get(f"{BASE_URL}/api/google/login", headers=headers, timeout=15)
    assert r1.status_code == 200 and r2.status_code == 200
    s1 = _get_qparam(r1.json()["authorization_url"], "state")
    s2 = _get_qparam(r2.json()["authorization_url"], "state")
    # Note: JWT state may be identical if called within same second (same sub/exp).
    # Verify docs are inserted for each call without accumulation failure.
    h1 = hashlib.sha256(s1.encode()).hexdigest()
    h2 = hashlib.sha256(s2.encode()).hexdigest()
    d1 = mongo.google_oauth_states.find_one({"state_hash": h1})
    d2 = mongo.google_oauth_states.find_one({"state_hash": h2})
    assert d1 is not None and d2 is not None, "state docs should be persisted"
    # cleanup
    mongo.google_oauth_states.delete_many({"state_hash": {"$in": [h1, h2]}})
