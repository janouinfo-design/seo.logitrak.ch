"""Tests for Meta (FB/Instagram) + Google Business Profile OAuth & publishing endpoints.

Preview keys are FAKE — only URL generation and error paths are tested.
"""
import os
import pytest
import requests
from urllib.parse import urlparse, parse_qs

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@logirent.fr"
DEMO_PASSWORD = "demo1234"
DRAFT_ID = "f10807ff-f05f-44bd-9552-d53711817f98"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- Meta status/login ---
class TestMetaStatus:
    def test_meta_status(self, headers):
        r = requests.get(f"{API}/meta/status", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["server_configured"] is True
        assert d["connected"] is False
        assert d["pages"] == []

    def test_meta_login_url(self, headers):
        r = requests.get(f"{API}/meta/login", headers=headers, timeout=15)
        assert r.status_code == 200
        url = r.json()["authorization_url"]
        assert url.startswith("https://www.facebook.com/v21.0/dialog/oauth")
        q = parse_qs(urlparse(url).query)
        assert "client_id" in q and q["client_id"][0]
        assert "redirect_uri" in q
        assert "state" in q and len(q["state"][0]) > 20  # JWT
        assert "pages_manage_posts" in q["scope"][0]
        assert "instagram_content_publish" in q["scope"][0]

    def test_meta_callback_invalid_state(self):
        r = requests.get(f"{API}/meta/oauth/callback", params={"code": "x", "state": "invalid"},
                         timeout=15, allow_redirects=False)
        assert r.status_code == 400


# --- GBP status/login ---
class TestGBPStatus:
    def test_gbp_status(self, headers):
        r = requests.get(f"{API}/gbp/status", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["server_configured"] is True
        assert d["connected"] is False

    def test_gbp_login_url(self, headers):
        r = requests.get(f"{API}/gbp/login", headers=headers, timeout=15)
        assert r.status_code == 200
        url = r.json()["authorization_url"]
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
        q = parse_qs(urlparse(url).query)
        assert "business.manage" in q["scope"][0]
        assert q["access_type"][0] == "offline"
        assert q["prompt"][0] == "consent"
        assert len(q["state"][0]) > 20

    def test_gbp_callback_invalid_state(self):
        r = requests.get(f"{API}/gbp/oauth/callback", params={"code": "x", "state": "invalid"},
                         timeout=15, allow_redirects=False)
        assert r.status_code == 400


# --- Publish error paths (not connected) ---
class TestPublishErrors:
    def test_publish_facebook_not_connected(self, headers):
        r = requests.post(f"{API}/drafts/{DRAFT_ID}/publish-facebook", headers=headers, json={}, timeout=20)
        assert r.status_code == 401
        assert "Meta" in r.text or "meta" in r.text.lower()

    def test_publish_instagram_no_image(self, headers):
        r = requests.post(f"{API}/drafts/{DRAFT_ID}/publish-instagram", headers=headers, json={}, timeout=20)
        assert r.status_code == 400
        assert "image" in r.text.lower()

    def test_publish_instagram_with_image_not_connected(self, headers):
        r = requests.post(f"{API}/drafts/{DRAFT_ID}/publish-instagram", headers=headers,
                          json={"image_url": "https://x.com/a.jpg"}, timeout=20)
        assert r.status_code == 401

    def test_publish_gbp_not_connected(self, headers):
        r = requests.post(f"{API}/drafts/{DRAFT_ID}/publish-gbp", headers=headers, json={}, timeout=20)
        assert r.status_code == 401
        assert "Google" in r.text or "google" in r.text.lower()

    def test_gbp_locations_not_connected(self, headers):
        r = requests.get(f"{API}/gbp/locations", headers=headers, timeout=15)
        assert r.status_code == 401


# --- Disconnect (idempotent) ---
class TestDisconnect:
    def test_meta_disconnect(self, headers):
        r = requests.post(f"{API}/meta/disconnect", headers=headers, json={}, timeout=15)
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_gbp_disconnect(self, headers):
        r = requests.post(f"{API}/gbp/disconnect", headers=headers, json={}, timeout=15)
        assert r.status_code == 200
        assert r.json() == {"ok": True}


# --- Regression ---
class TestRegression:
    def test_linkedin_status_still_works(self, headers):
        r = requests.get(f"{API}/linkedin/status", headers=headers, timeout=15)
        assert r.status_code == 200
        assert "connected" in r.json()

    def test_get_draft_pydantic_ok(self, headers):
        r = requests.get(f"{API}/drafts/{DRAFT_ID}", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == DRAFT_ID
        # New optional fields present or absent — no validation error
        for k in ["facebook_post_id", "instagram_post_id", "gbp_post_name"]:
            assert k in d or True  # tolerate missing
