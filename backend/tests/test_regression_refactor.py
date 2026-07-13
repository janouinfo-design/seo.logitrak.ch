"""Full backend regression test after 16-module refactor.

Covers every route module: auth, sites, drafts, agents, workflows, notifications,
workspace/billing, social (meta/gbp/linkedin/google) status + login URLs,
performance, rank-tracking, dashboard stats, audits history, calendar,
business-profile, ai-visibility latest, competitor latest, saved keywords,
draft HTML export, draft generate-image (503 expected).
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

EMAIL = "demo@logirent.fr"
PASSWORD = "demo1234"
SITE_ID = "b3bec42d-2117-4f73-93b9-a0adc3b47a38"
DRAFT_ID = "f10807ff-f05f-44bd-9552-d53711817f98"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


def _get(path, h, **kw):
    return requests.get(f"{API}{path}", headers=h, timeout=kw.get("timeout", 30))


# ---------- AUTH ----------
def test_auth_me(h):
    r = _get("/auth/me", h)
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


def test_auth_login_bad():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": "wrong"}, timeout=15)
    assert r.status_code in (400, 401)


# ---------- SITES ----------
def test_sites_list(h):
    r = _get("/sites", h)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1
    assert any(s["id"] == SITE_ID for s in data)


def test_site_get(h):
    r = _get(f"/sites/{SITE_ID}", h)
    assert r.status_code == 200
    assert r.json()["id"] == SITE_ID


# ---------- DRAFTS ----------
def test_drafts_list(h):
    r = _get("/drafts", h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_draft_get(h):
    r = _get(f"/drafts/{DRAFT_ID}", h)
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == DRAFT_ID
    # image_query field should exist per PRD
    assert "image_query" in d or "cover_image_url" in d


def test_draft_export_html(h):
    r = _get(f"/drafts/{DRAFT_ID}/export.html", h)
    assert r.status_code == 200
    html = r.text
    # og:image and figure cover should be present when a cover exists
    assert "og:image" in html
    assert "<figure" in html or "cover" in html.lower()


def test_draft_generate_image_503(h):
    r = requests.post(f"{API}/drafts/{DRAFT_ID}/generate-image", headers=h, timeout=30)
    # Expected 503 (no Pexels key)
    assert r.status_code == 503, f"expected 503 got {r.status_code}: {r.text[:200]}"


# ---------- AGENTS OVERVIEW ----------
def test_agents_overview_no_site(h):
    r = _get("/agents/overview", h)
    assert r.status_code == 200
    d = r.json()
    for k in ("seo", "geo", "content", "social"):
        assert k in d


def test_agents_overview_with_site(h):
    r = _get(f"/agents/overview?site_id={SITE_ID}", h)
    assert r.status_code == 200


# ---------- WORKFLOWS ----------
def test_workflows_list(h):
    r = _get("/workflows", h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_workflow_crud_and_run(h):
    payload = {
        "name": "TEST_regression_wf",
        "site_id": SITE_ID,
        "trigger_type": "no_publication",
        "trigger_params": {"days": 1},
        "actions": ["notify"],
        "enabled": True,
    }
    r = requests.post(f"{API}/workflows", headers=h, json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    wf = r.json()
    wf_id = wf["id"]

    # Trigger a run
    rr = requests.post(f"{API}/workflows/{wf_id}/run", headers=h, timeout=60)
    assert rr.status_code == 200, rr.text
    body = rr.json()
    assert body.get("fired") is True
    assert any(a.get("action") == "notify" and a.get("ok") for a in body.get("actions_results", []))

    # cleanup
    d = requests.delete(f"{API}/workflows/{wf_id}", headers=h, timeout=15)
    assert d.status_code in (200, 204)


# ---------- NOTIFICATIONS ----------
def test_notifications(h):
    r = _get("/notifications", h)
    assert r.status_code == 200
    data = r.json()
    lst = data["notifications"] if isinstance(data, dict) else data
    assert isinstance(lst, list)
    if lst:
        nid = lst[0]["id"]
        rr = requests.post(f"{API}/notifications/read", headers=h, json={"ids": [nid]}, timeout=15)
        assert rr.status_code == 200


# ---------- WORKSPACE + BILLING ----------
def test_workspace_current(h):
    r = _get("/workspace", h)
    assert r.status_code == 200


def test_billing_plans(h):
    r = _get("/billing/plans", h)
    assert r.status_code == 200
    plans = r.json()
    assert isinstance(plans, (list, dict))


# ---------- INTEGRATION STATUS + LOGIN URLs ----------
@pytest.mark.parametrize("path", ["/meta/status", "/gbp/status", "/linkedin/status", "/google/status"])
def test_integration_status(h, path):
    r = _get(path, h)
    assert r.status_code == 200


def test_meta_login_url(h):
    r = _get("/meta/login", h)
    # Should return a redirect URL or 200 with url payload
    assert r.status_code in (200, 302, 307)


def test_gbp_login_url(h):
    r = _get("/gbp/login", h)
    assert r.status_code in (200, 302, 307)


# ---------- PERFORMANCE + RANK ----------
def test_site_performance(h):
    r = _get(f"/sites/{SITE_ID}/performance", h)
    assert r.status_code == 200


def test_site_rank_tracking(h):
    r = _get(f"/sites/{SITE_ID}/rank-tracking", h)
    assert r.status_code == 200


# ---------- DASHBOARD ----------
def test_dashboard_stats(h):
    r = _get("/dashboard/stats", h)
    assert r.status_code == 200


# ---------- AUDITS HISTORY ----------
def test_site_audits(h):
    r = _get(f"/sites/{SITE_ID}/audits", h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- CALENDAR ----------
def test_calendar(h):
    r = _get(f"/calendar?site_id={SITE_ID}", h)
    assert r.status_code == 200


# ---------- BUSINESS PROFILE ----------
def test_business_profile(h):
    r = _get(f"/sites/{SITE_ID}/business-profile", h)
    assert r.status_code in (200, 404)  # 404 if none saved yet


# ---------- AI VISIBILITY latest ----------
def test_ai_visibility_latest(h):
    r = _get(f"/sites/{SITE_ID}/ai-visibility/latest", h)
    assert r.status_code in (200, 404)


# ---------- COMPETITORS latest ----------
def test_competitor_latest(h):
    r = _get(f"/sites/{SITE_ID}/competitor-analysis/latest", h)
    assert r.status_code in (200, 404)


# ---------- SAVED KEYWORDS ----------
def test_saved_keywords(h):
    r = _get(f"/keywords/saved?site_id={SITE_ID}", h)
    assert r.status_code == 200
