"""Tests for Google OAuth scope fix:
- GOOGLE_SCOPES uses canonical https://www.googleapis.com/auth/userinfo.email (not 'email' shortcut)
- OAUTHLIB_RELAX_TOKEN_SCOPE=1 in process env after import routes_google
- No regression on PKCE
- Callback does not surface 'Scope has changed' nor 'Missing code verifier'
"""
import os
import sys
import hashlib
from urllib.parse import urlparse, parse_qs

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")

DEMO_EMAIL = "demo@logirent.fr"
DEMO_PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _qparams(url):
    return parse_qs(urlparse(url).query)


# --- Scope fix ---

def test_authorization_url_uses_canonical_userinfo_email(headers):
    r = requests.get(f"{BASE_URL}/api/google/login", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    url = r.json()["authorization_url"]
    q = _qparams(url)
    scope = q.get("scope", [""])[0]
    tokens = scope.split(" ")
    assert "https://www.googleapis.com/auth/webmasters.readonly" in tokens, f"scope missing webmasters.readonly: {scope}"
    assert "https://www.googleapis.com/auth/analytics.readonly" in tokens, f"scope missing analytics.readonly: {scope}"
    assert "openid" in tokens, f"scope missing openid: {scope}"
    assert "https://www.googleapis.com/auth/userinfo.email" in tokens, f"scope missing canonical userinfo.email: {scope}"
    # Ensure the bare 'email' shortcut is NOT present as a standalone scope token
    assert "email" not in tokens, f"scope should not contain the bare 'email' shortcut: {scope}"


def test_oauthlib_relax_token_scope_env_set():
    # Import routes_google in-process; it should setdefault OAUTHLIB_RELAX_TOKEN_SCOPE=1
    sys.path.insert(0, "/app/backend")
    # Ensure the flag isn't pre-set by test env
    os.environ.pop("OAUTHLIB_RELAX_TOKEN_SCOPE", None)
    import importlib
    if "routes_google" in sys.modules:
        importlib.reload(sys.modules["routes_google"])
    else:
        import routes_google  # noqa: F401
    assert os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE") == "1"


# --- PKCE non-regression ---

def test_pkce_still_present(headers):
    r = requests.get(f"{BASE_URL}/api/google/login", headers=headers, timeout=15)
    assert r.status_code == 200
    url = r.json()["authorization_url"]
    q = _qparams(url)
    assert q.get("code_challenge", [None])[0] is not None
    assert q.get("code_challenge_method", [None])[0] == "S256"
    assert q.get("state", [None])[0]


def test_callback_no_scope_changed_nor_missing_verifier(headers):
    r = requests.get(f"{BASE_URL}/api/google/login", headers=headers, timeout=15)
    assert r.status_code == 200
    url = r.json()["authorization_url"]
    state = _qparams(url).get("state", [None])[0]
    assert state

    cb = requests.get(
        f"{BASE_URL}/api/google/oauth/callback",
        params={"code": "fakecode", "state": state},
        timeout=20,
        allow_redirects=False,
    )
    assert cb.status_code == 400, f"expected 400, got {cb.status_code}: {cb.text}"
    body = cb.text
    assert "Scope has changed" not in body, f"Scope regression: {body}"
    assert "Missing code verifier" not in body, f"PKCE regression: {body}"
    assert "Échec d'échange du code OAuth" in body


# --- Quick regressions ---

def test_google_status(headers):
    r = requests.get(f"{BASE_URL}/api/google/status", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json().get("server_configured") is True


def test_auth_login_demo():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200
    assert "token" in r.json()


def test_agents_overview(headers):
    r = requests.get(f"{BASE_URL}/api/agents/overview", headers=headers, timeout=20)
    assert r.status_code == 200
