"""Tests for GitHub 403 graceful error handling (iteration 16).

Focus:
- test_github_connection returns proper French HTTPException on invalid token / missing config
- publish_draft_to_github returns 400 with French message when GitHub not configured
- Static verification of _GITHUB_403_MSG and raise sites in routes_publish.py
- Regression: /api/sites, /api/drafts, /api/publish-logs work with the demo user.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@logirent.fr"
DEMO_PWD = "demo1234"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PWD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert "token" in data and "user" in data
    return data["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def test_site(auth):
    """Create a test url_crawl site (no github config yet)."""
    payload = {
        "site_type": "url_crawl",
        "name": "TEST_gh403_site",
        "label": "Autre",
        "base_url": "https://example.com",
    }
    r = requests.post(f"{API}/sites", json=payload, headers=auth, timeout=15)
    assert r.status_code == 200, f"create site failed: {r.status_code} {r.text[:200]}"
    site = r.json()
    yield site
    # cleanup
    requests.delete(f"{API}/sites/{site['id']}", headers=auth, timeout=10)


# --- Static code review ------------------------------------------------------
class TestStaticCode:
    def test_source_contains_expected_constants_and_raises(self):
        with open("/app/backend/routes_publish.py", "r", encoding="utf-8") as f:
            src = f.read()
        # 1. _GITHUB_403_MSG present and mentions "Contents : Read and write"
        assert "_GITHUB_403_MSG" in src
        # capture the whole tuple-string block up to the closing paren at start-of-line
        m = re.search(r"_GITHUB_403_MSG\s*=\s*\((.*?)^\)", src, re.DOTALL | re.MULTILINE)
        assert m, "_GITHUB_403_MSG definition not found"
        msg_block = m.group(1)
        assert "Contents" in msg_block and "Read and write" in msg_block, \
            f"_GITHUB_403_MSG should mention 'Contents : Read and write', got: {msg_block[:200]}"

        # 2. _github_put_file raises HTTPException(403, _GITHUB_403_MSG) on status 403 and 404
        put_fn = re.search(r"async def _github_put_file\([\s\S]+?(?=\nasync def |\ndef |\n@api)", src)
        assert put_fn, "_github_put_file not found"
        put_body = put_fn.group(0)
        assert "resp.status_code == 403" in put_body
        assert "HTTPException(403, _GITHUB_403_MSG" in put_body
        assert "resp.status_code == 404" in put_body

        # 3. _github_get_file_sha raises HTTPException(403) on 403  (note: current code raises 502 — verify actual)
        sha_fn = re.search(r"async def _github_get_file_sha\([\s\S]+?(?=\nasync def |\ndef |\n@api)", src)
        assert sha_fn, "_github_get_file_sha not found"

        # 4. test_github_connection checks permissions.push and raises 403 with 'ÉCRITURE'
        tc = re.search(r"async def test_github_connection\([\s\S]+?(?=\nasync def |\ndef |\n@api)", src)
        assert tc, "test_github_connection not found"
        tc_body = tc.group(0)
        assert "permissions" in tc_body and "push" in tc_body
        assert "ÉCRITURE" in tc_body, "test_github_connection should mention 'ÉCRITURE' in the 403 message"

    def test_github_get_file_sha_raises_403(self):
        """Task requires _github_get_file_sha to raise HTTPException(403) on 403."""
        with open("/app/backend/routes_publish.py", "r", encoding="utf-8") as f:
            src = f.read()
        sha_fn = re.search(r"async def _github_get_file_sha\([\s\S]+?(?=\nasync def |\ndef |\n@api)", src)
        body = sha_fn.group(0)
        # Currently code raises HTTPException(502, ...) for anything non-200/404.
        # The spec says it should raise 403 on 403.
        has_403 = "resp.status_code == 403" in body and "HTTPException(403" in body
        assert has_403, "_github_get_file_sha does NOT explicitly handle 403 → should raise HTTPException(403, _GITHUB_403_MSG)"


# --- Live API tests ----------------------------------------------------------
class TestGithubEndpoints:
    def test_test_github_no_config(self, auth, test_site):
        """No github_token/owner/repo → 400 with French config message."""
        r = requests.post(f"{API}/sites/{test_site['id']}/test-github", headers=auth, timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", "")
        assert "Configurez d'abord github_token" in detail, f"got detail: {detail}"

    def test_test_github_invalid_token(self, auth, test_site):
        """Patch site with fake token → GitHub returns 401 → endpoint returns 400 'Token GitHub invalide ou expiré.'."""
        patch = {
            "github_token": "ghp_faketoken123456789ABCDEF",
            "github_owner": "octocat",
            "github_repo": "Hello-World",
            "github_branch": "master",
        }
        pr = requests.patch(f"{API}/sites/{test_site['id']}", json=patch, headers=auth, timeout=15)
        assert pr.status_code == 200, f"patch failed: {pr.status_code} {pr.text[:200]}"

        r = requests.post(f"{API}/sites/{test_site['id']}/test-github", headers=auth, timeout=30)
        assert r.status_code == 400, f"expected 400 for invalid token, got {r.status_code}: {r.text[:400]}"
        detail = r.json().get("detail", "")
        assert "Token GitHub invalide ou expiré" in detail, f"got detail: {detail}"

    def test_publish_github_no_config(self, auth, test_site):
        """POST /api/drafts/{id}/publish-github when site has no gh config → 400 with French message.

        Create a draft first, then remove github fields, then try to publish.
        """
        # Clear github fields on site
        requests.patch(f"{API}/sites/{test_site['id']}", json={
            "github_token": "", "github_owner": "", "github_repo": ""
        }, headers=auth, timeout=15)

        # Create a draft via direct DB seed would need internals; use content endpoint if available.
        # Simplest: create draft through the drafts collection is not exposed publicly.
        # Try listing drafts and use one for this site; otherwise skip if no draft available.
        dr = requests.get(f"{API}/drafts", headers=auth, timeout=15)
        assert dr.status_code == 200
        drafts_payload = dr.json()
        drafts = drafts_payload if isinstance(drafts_payload, list) else drafts_payload.get("drafts", [])

        # find a draft belonging to any site owned by user; publish-github checks the draft's own site config
        # We need to test with a draft whose site has no github config → use test_site's drafts (none exist likely)
        # Instead, use the first available draft — its own site may already have config, so this test may not
        # be deterministic. Fallback: test with a random UUID → returns 404 "Brouillon introuvable".
        # For "no github config" test we need a draft on test_site. Let's create one via generate-content endpoint if any.
        # Skip if we cannot easily seed a draft; still assert 404 path for random id.
        r404 = requests.post(f"{API}/drafts/nonexistent-draft-id-xyz/publish-github", headers=auth, timeout=15)
        assert r404.status_code == 404, f"expected 404 for missing draft, got {r404.status_code}"

        # Now try to find a draft that belongs to test_site (may be none). If found, test 400 path.
        candidate = None
        for d in drafts:
            if d.get("site_id") == test_site["id"]:
                candidate = d
                break
        if not candidate:
            pytest.skip("No draft on test_site to test publish-github 400 path; static check + 404 covered.")
        r = requests.post(f"{API}/drafts/{candidate['id']}/publish-github", headers=auth, timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", "")
        assert "GitHub n'est pas configuré" in detail or "Configurez" in detail


# --- Regression --------------------------------------------------------------
class TestRegression:
    def test_list_sites(self, auth):
        r = requests.get(f"{API}/sites", headers=auth, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_drafts(self, auth):
        r = requests.get(f"{API}/drafts", headers=auth, timeout=15)
        assert r.status_code == 200

    def test_publish_logs(self, auth):
        r = requests.get(f"{API}/publish-logs", headers=auth, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "logs" in body and isinstance(body["logs"], list)
