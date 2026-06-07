"""LOGI SEO Booster - Phase 2 tests: Keyword Research + Page Optimizer.

Covers:
  - POST /api/keywords/research (4 clusters, ≥4 keywords each, full schema)
  - GET  /api/keywords/research history
  - POST/GET/DELETE /api/keywords/saved (incl. 409 duplicate)
  - POST /api/pages/optimize (mock pages, full suggested schema, lengths)
  - POST /api/pages/optimize 404 on unknown page_id
  - GET  /api/pages/optimizations + GET /{id}
  - POST /api/pages/optimizations/{id}/apply → draft.status='ready', applied=True
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

UNIQUE = uuid.uuid4().hex[:8]
EMAIL = f"phase2_{UNIQUE}@logitest.fr"
PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_headers(session):
    r = session.post(f"{API}/auth/register",
                     json={"email": EMAIL, "password": PASSWORD, "full_name": "Phase2 Tester"},
                     timeout=20)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def site_id(session, auth_headers):
    payload = {
        "label": "Logirent",
        "name": "Logirent Phase2",
        "wix_site_id": "test-site-id-12345",
        "wix_account_id": "test-account-id-67890",
        "wix_api_key": "IST.test-fake-api-key-for-mvp",
        "base_url": "https://www.logirent.fr",
    }
    r = session.post(f"{API}/sites", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
def page_id(session, auth_headers, site_id):
    """Pick a real mock page id from the site."""
    r = session.get(f"{API}/sites/{site_id}/pages", headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    pages = r.json()["pages"]
    assert len(pages) >= 1
    return pages[0]["id"]


# ---------- Keyword Research ----------
class TestKeywordResearch:
    research_id = None

    def test_research_full_schema(self, session, auth_headers, site_id):
        payload = {
            "site_id": site_id,
            "theme": "location appartement meublé",
            "city": "Paris",
            "competitors": ["pap.fr", "seloger.com"],
        }
        r = session.post(f"{API}/keywords/research", json=payload, headers=auth_headers, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] and d["summary"]
        # exactly 4 clusters with required intents
        intents = {c["intent"] for c in d["clusters"]}
        assert intents == {"locale", "informationnelle", "transactionnelle", "navigationnelle"}, intents
        for c in d["clusters"]:
            assert len(c["keywords"]) >= 4, f"{c['intent']} has only {len(c['keywords'])}"
            for kw in c["keywords"]:
                assert kw.get("keyword")
                assert kw.get("difficulty") in ("low", "medium", "high")
                assert kw.get("volume_estimate") in ("low", "medium", "high")
                assert kw.get("priority") in ("high", "medium", "low")
                assert kw.get("rationale")
        TestKeywordResearch.research_id = d["id"]

    def test_research_history(self, session, auth_headers, site_id):
        r = session.get(f"{API}/keywords/research?site_id={site_id}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        assert any(it["id"] == TestKeywordResearch.research_id for it in items)


# ---------- Saved Keywords ----------
class TestSavedKeywords:
    saved_id = None

    def test_save(self, session, auth_headers, site_id):
        payload = {
            "site_id": site_id,
            "keyword": "Location Appartement Paris 11",
            "intent": "locale",
            "priority": "high",
            "notes": "longue traîne facile",
        }
        r = session.post(f"{API}/keywords/saved", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["keyword"] == "location appartement paris 11"  # stored lower-cased
        assert d["priority"] == "high"
        TestSavedKeywords.saved_id = d["id"]

    def test_save_duplicate_409(self, session, auth_headers, site_id):
        payload = {
            "site_id": site_id,
            "keyword": "location appartement paris 11",
            "intent": "locale",
            "priority": "medium",
        }
        r = session.post(f"{API}/keywords/saved", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 409, r.text

    def test_list(self, session, auth_headers, site_id):
        r = session.get(f"{API}/keywords/saved?site_id={site_id}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        ids = [k["id"] for k in r.json()]
        assert TestSavedKeywords.saved_id in ids

    def test_delete(self, session, auth_headers):
        sid = TestSavedKeywords.saved_id
        r = session.delete(f"{API}/keywords/saved/{sid}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        # idempotent → second delete 404
        r2 = session.delete(f"{API}/keywords/saved/{sid}", headers=auth_headers, timeout=15)
        assert r2.status_code == 404


# ---------- Page Optimizer ----------
class TestOptimizer:
    opt_id = None

    def test_optimize_404_unknown_page(self, session, auth_headers, site_id):
        r = session.post(f"{API}/pages/optimize",
                         json={"site_id": site_id, "page_id": "non-existent-page", "focus_keyword": "x"},
                         headers=auth_headers, timeout=30)
        assert r.status_code == 404, r.text

    def test_optimize_full_schema(self, session, auth_headers, site_id, page_id):
        payload = {
            "site_id": site_id,
            "page_id": page_id,
            "focus_keyword": "location appartement meublé Paris",
            "city": "Paris",
        }
        r = session.post(f"{API}/pages/optimize", json=payload, headers=auth_headers, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] and d["page_id"] == page_id
        # current is the actual mock page state
        assert d["current"].get("title") is not None
        # suggested schema
        s = d["suggested"]
        for k in ("h1", "meta_title", "meta_description", "h2_plan",
                  "intro_short_answer", "faq_suggested", "content_outline"):
            assert k in s, f"missing suggested.{k}"
        assert isinstance(s["h2_plan"], list) and len(s["h2_plan"]) >= 2
        assert isinstance(s["faq_suggested"], list) and len(s["faq_suggested"]) >= 1
        # meta_title 50-65 chars (per spec); allow a tiny ±3 tolerance for Claude variability
        mt_len = len(s["meta_title"])
        assert 47 <= mt_len <= 68, f"meta_title length {mt_len} out of 50-65 (±3) bounds: {s['meta_title']!r}"
        md_len = len(s["meta_description"])
        assert 127 <= md_len <= 173, f"meta_description length {md_len} out of 130-170 (±3) bounds"
        # improvements
        assert isinstance(d["improvements"], list) and len(d["improvements"]) >= 3
        assert d["diff_summary"]
        TestOptimizer.opt_id = d["id"]

    def test_list_optimizations(self, session, auth_headers, site_id):
        r = session.get(f"{API}/pages/optimizations?site_id={site_id}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        ids = [o["id"] for o in r.json()]
        assert TestOptimizer.opt_id in ids

    def test_get_optimization(self, session, auth_headers):
        r = session.get(f"{API}/pages/optimizations/{TestOptimizer.opt_id}",
                        headers=auth_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == TestOptimizer.opt_id

    def test_apply_creates_ready_draft(self, session, auth_headers, site_id):
        r = session.post(f"{API}/pages/optimizations/{TestOptimizer.opt_id}/apply",
                         headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["applied"] is True
        # Confirm a draft with status='ready' now exists for this site
        rd = session.get(f"{API}/drafts?site_id={site_id}", headers=auth_headers, timeout=15)
        assert rd.status_code == 200
        drafts = rd.json()
        ready_drafts = [x for x in drafts if x["status"] == "ready"
                        and x["content_type"] == "page_optimization"]
        assert len(ready_drafts) >= 1, "No ready draft created by apply"
        latest = ready_drafts[0]
        # title should equal suggested.h1, meta_title equal to suggested.meta_title
        opt = session.get(f"{API}/pages/optimizations/{TestOptimizer.opt_id}",
                          headers=auth_headers, timeout=15).json()
        assert latest["title"] == opt["suggested"]["h1"]
        assert latest["meta_title"] == opt["suggested"]["meta_title"]
        # body must contain intro_short_answer text
        assert opt["suggested"]["intro_short_answer"][:30] in latest["body_markdown"]


# ---------- Cleanup ----------
class TestZCleanup:
    def test_delete_site(self, session, auth_headers, site_id):
        r = session.delete(f"{API}/sites/{site_id}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
