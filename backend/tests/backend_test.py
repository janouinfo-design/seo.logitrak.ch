"""LOGI SEO Booster - Backend integration tests (pytest).

Covers auth, sites CRUD, Wix mock fallback, audit, content generation (Claude 4.5),
drafts CRUD + versions/rollback, publish (Wix unavailable path), publish-logs,
performance (mocked), dashboard stats.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

UNIQUE = uuid.uuid4().hex[:8]
EMAIL = f"test_{UNIQUE}@logitest.fr"
PASSWORD = "testpass123"
FULL_NAME = "Test User"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth(session):
    """Register a fresh user and return token + user_id."""
    r = session.post(f"{API}/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "full_name": FULL_NAME
    }, timeout=20)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    assert data["user"]["email"] == EMAIL
    return data


@pytest.fixture(scope="session")
def auth_headers(auth):
    return {"Authorization": f"Bearer {auth['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def site_id(session, auth_headers):
    payload = {
        "label": "Logirent",
        "name": "Logirent Test",
        "wix_site_id": "test-site-id-12345",
        "wix_account_id": "test-account-id-67890",
        "wix_api_key": "IST.test-fake-api-key-for-mvp",
        "base_url": "https://www.logirent.fr",
    }
    r = session.post(f"{API}/sites", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "wix_api_key" not in d  # raw key MUST NOT be returned
    assert d["has_api_key"] is True
    assert d["label"] == "Logirent"
    return d["id"]


# ---- Auth ----
class TestAuth:
    def test_health(self, session):
        r = session.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_register_duplicate_409(self, session, auth):
        r = session.post(f"{API}/auth/register", json={
            "email": EMAIL, "password": PASSWORD, "full_name": FULL_NAME
        }, timeout=20)
        assert r.status_code == 409

    def test_login_success(self, session, auth):
        r = session.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
        assert r.status_code == 200
        assert "token" in r.json()

    def test_login_wrong_password(self, session, auth):
        r = session.post(f"{API}/auth/login", json={"email": EMAIL, "password": "wrong"}, timeout=20)
        assert r.status_code == 401

    def test_me(self, session, auth_headers):
        r = session.get(f"{API}/auth/me", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == EMAIL

    def test_me_no_token(self, session):
        r = session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401


# ---- Sites CRUD ----
class TestSites:
    def test_list_sites(self, session, auth_headers, site_id):
        r = session.get(f"{API}/sites", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        sites = r.json()
        ids = [s["id"] for s in sites]
        assert site_id in ids
        for s in sites:
            assert "wix_api_key" not in s

    def test_get_site(self, session, auth_headers, site_id):
        r = session.get(f"{API}/sites/{site_id}", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["id"] == site_id

    def test_patch_site(self, session, auth_headers, site_id):
        r = session.patch(f"{API}/sites/{site_id}", json={"name": "Logirent Test Updated"},
                          headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["name"] == "Logirent Test Updated"
        # verify persistence
        r2 = session.get(f"{API}/sites/{site_id}", headers=auth_headers, timeout=10)
        assert r2.json()["name"] == "Logirent Test Updated"

    def test_other_user_cannot_access(self, session, site_id):
        # register a second user
        email2 = f"other_{uuid.uuid4().hex[:8]}@logitest.fr"
        r = session.post(f"{API}/auth/register", json={
            "email": email2, "password": "pass1234", "full_name": "Other"
        }, timeout=20)
        assert r.status_code == 200
        token2 = r.json()["token"]
        h2 = {"Authorization": f"Bearer {token2}"}
        r = session.get(f"{API}/sites/{site_id}", headers=h2, timeout=10)
        assert r.status_code == 404


# ---- Wix pages/blog (mock fallback) ----
class TestWixIntegration:
    def test_pages_fallback_to_mock(self, session, auth_headers, site_id):
        r = session.get(f"{API}/sites/{site_id}/pages", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        pages = r.json()["pages"]
        assert len(pages) == 5

    def test_blog_posts_fallback(self, session, auth_headers, site_id):
        r = session.get(f"{API}/sites/{site_id}/blog-posts", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        assert "posts" in r.json()


# ---- Audit ----
class TestAudit:
    def test_run_audit(self, session, auth_headers, site_id):
        r = session.post(f"{API}/sites/{site_id}/audit", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert 0 <= d["score"] <= 100
        assert d["total_pages"] == 5
        assert isinstance(d["issues"], list) and len(d["issues"]) > 0
        for i in d["issues"]:
            assert i["severity"] in ("high", "medium", "low")
        assert set(d["summary"].keys()) == {"high", "medium", "low"}

    def test_audit_history(self, session, auth_headers, site_id):
        r = session.get(f"{API}/sites/{site_id}/audits", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert len(r.json()) >= 1


# ---- AI content generation (Claude Sonnet 4.5) ----
class TestContentGen:
    def test_generate_article(self, session, auth_headers, site_id):
        payload = {
            "site_id": site_id,
            "content_type": "article",
            "topic": "Conseils pour louer un appartement à Paris",
            "keywords": ["location appartement Paris", "bail locatif"],
            "city": "Paris",
            "tone": "professionnel",
            "target_length": "court",
        }
        r = session.post(f"{API}/content/generate", json=payload,
                         headers=auth_headers, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["title"]
        assert d["meta_title"]
        assert d["meta_description"]
        assert d["body_markdown"]
        assert isinstance(d["keywords"], list)
        assert isinstance(d["faq"], list)
        assert d["status"] == "draft"
        # save for later use
        pytest.draft_id = d["id"]


# ---- Drafts CRUD ----
class TestDrafts:
    def test_list_drafts(self, session, auth_headers, site_id):
        r = session.get(f"{API}/drafts?site_id={site_id}", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_get_draft(self, session, auth_headers):
        did = getattr(pytest, "draft_id", None)
        if not did:
            pytest.skip("no draft created")
        r = session.get(f"{API}/drafts/{did}", headers=auth_headers, timeout=10)
        assert r.status_code == 200

    def test_patch_draft_creates_version(self, session, auth_headers):
        did = getattr(pytest, "draft_id", None)
        if not did:
            pytest.skip("no draft created")
        r = session.patch(f"{API}/drafts/{did}", json={"title": "Nouveau titre"},
                          headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["title"] == "Nouveau titre"
        # versions
        rv = session.get(f"{API}/drafts/{did}/versions", headers=auth_headers, timeout=10)
        assert rv.status_code == 200
        versions = rv.json()["versions"]
        assert len(versions) >= 1
        pytest.version_id = versions[0]["id"]

    def test_rollback(self, session, auth_headers):
        did = getattr(pytest, "draft_id", None)
        vid = getattr(pytest, "version_id", None)
        if not did or not vid:
            pytest.skip("no version available")
        r = session.post(f"{API}/drafts/{did}/rollback/{vid}", headers=auth_headers, timeout=10)
        assert r.status_code == 200


# ---- Publish (Wix unavailable expected) ----
class TestPublish:
    def test_publish_wix_unavailable(self, session, auth_headers):
        did = getattr(pytest, "draft_id", None)
        if not did:
            pytest.skip("no draft created")
        r = session.post(f"{API}/drafts/{did}/publish", json={"publish_immediately": False},
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Wix call fails (fake key) → wix_draft_id None, status 'ready'
        assert d["wix_draft_id"] is None
        assert d["status"] == "ready"

    def test_publish_logs(self, session, auth_headers, site_id):
        r = session.get(f"{API}/publish-logs?site_id={site_id}", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        logs = r.json()["logs"]
        assert len(logs) >= 1
        assert logs[0]["status"] == "wix_unavailable"
        assert logs[0]["wix_draft_id"] is None


# ---- Performance (mocked) ----
class TestPerformance:
    def test_performance(self, session, auth_headers, site_id):
        r = session.get(f"{API}/sites/{site_id}/performance", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["mocked"] is True
        assert len(d["daily"]) == 28
        assert len(d["keywords"]) >= 1
        assert "recommendations" in d


# ---- Dashboard stats ----
class TestDashboard:
    def test_stats(self, session, auth_headers):
        r = session.get(f"{API}/dashboard/stats", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["sites"] >= 1
        assert d["drafts"] >= 1
        assert d["last_audit"] is not None
        assert "score" in d["last_audit"]


# ---- Cleanup site at the end ----
class TestZCleanup:
    def test_delete_draft(self, session, auth_headers):
        did = getattr(pytest, "draft_id", None)
        if not did:
            pytest.skip("no draft")
        r = session.delete(f"{API}/drafts/{did}", headers=auth_headers, timeout=10)
        assert r.status_code == 200

    def test_delete_site(self, session, auth_headers, site_id):
        r = session.delete(f"{API}/sites/{site_id}", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        r2 = session.get(f"{API}/sites/{site_id}", headers=auth_headers, timeout=10)
        assert r2.status_code == 404
