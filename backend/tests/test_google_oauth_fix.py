"""Tests for Google OAuth redirect_uri_mismatch fix (dual callback route)."""
import os
import requests
from urllib.parse import urlparse, parse_qs

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")
EXPECTED_REDIRECT_URI = "https://content-logi-pro.preview.emergentagent.com/api/google/oauth/callback"


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "demo@logirent.fr", "password": "demo1234"}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def test_google_status_configured():
    token = _login()
    r = requests.get(f"{BASE_URL}/api/google/status", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    # Backend uses server_configured
    assert data.get("server_configured") is True, data
    assert data.get("redirect_uri") == EXPECTED_REDIRECT_URI, data


def test_google_login_returns_correct_redirect_uri():
    token = _login()
    r = requests.get(f"{BASE_URL}/api/google/login", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    url = r.json().get("authorization_url", "")
    assert "accounts.google.com" in url
    q = parse_qs(urlparse(url).query)
    assert q.get("redirect_uri", [""])[0] == EXPECTED_REDIRECT_URI


def test_google_oauth_callback_new_route_400_on_invalid_state():
    r = requests.get(f"{BASE_URL}/api/google/oauth/callback",
                     params={"code": "x", "state": "invalid"}, timeout=15, allow_redirects=False)
    assert r.status_code == 400, f"got {r.status_code}: {r.text[:200]}"


def test_google_callback_legacy_route_400_on_invalid_state():
    r = requests.get(f"{BASE_URL}/api/google/callback",
                     params={"code": "x", "state": "invalid"}, timeout=15, allow_redirects=False)
    assert r.status_code == 400, f"got {r.status_code}: {r.text[:200]}"


def test_other_oauth_status_endpoints_regression():
    token = _login()
    h = {"Authorization": f"Bearer {token}"}
    for path in ["/api/linkedin/status", "/api/meta/status", "/api/gbp/status"]:
        r = requests.get(f"{BASE_URL}{path}", headers=h, timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"


def test_meta_and_gbp_login_return_authorization_url():
    token = _login()
    h = {"Authorization": f"Bearer {token}"}
    for path in ["/api/meta/login", "/api/gbp/login"]:
        r = requests.get(f"{BASE_URL}{path}", headers=h, timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
        assert "authorization_url" in r.json(), r.json()
