"""Verify that 'third-party credentials' errors return 400 (not 401),
so the global axios interceptor doesn't sign the user out. Also verify
that true session 401 still works when a bogus Bearer is used."""
import os
import pytest
import requests

if not os.environ.get("REACT_APP_BACKEND_URL"):
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()
                break

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
EMAIL = "demo@logirent.fr"
PASSWORD = "demo1234"
DRAFT_ID = "f10807ff-f05f-44bd-9552-d53711817f98"


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text[:300]
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


def test_publish_facebook_no_meta_returns_400(api_client):
    r = api_client.post(f"{BASE_URL}/api/drafts/{DRAFT_ID}/publish-facebook", json={}, timeout=20)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"
    detail = r.json().get("detail", "")
    assert "Meta" in detail or "connecté" in detail.lower() or "connect" in detail.lower()


def test_publish_gbp_no_google_returns_400(api_client):
    r = api_client.post(f"{BASE_URL}/api/drafts/{DRAFT_ID}/publish-gbp", json={}, timeout=20)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"
    detail = r.json().get("detail", "")
    assert "Google" in detail or "GBP" in detail or "connect" in detail.lower()


def test_gbp_locations_no_google_returns_400(api_client):
    r = api_client.get(f"{BASE_URL}/api/gbp/locations", timeout=20)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"


def test_bogus_bearer_still_returns_401():
    """True session 401 must remain: a garbage Bearer on /api/sites → 401."""
    r = requests.get(
        f"{BASE_URL}/api/sites",
        headers={"Authorization": "Bearer totally.bogus.token"},
        timeout=15,
    )
    assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text[:200]}"
