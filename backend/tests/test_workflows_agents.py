"""Backend tests: agents/overview, workflows CRUD/run, notifications."""
import os
import pytest
import requests

def _load_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)

_load_frontend_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
EMAIL = "demo@logirent.fr"
PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def site_id(headers):
    r = requests.get(f"{BASE}/sites", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    sites = r.json()
    assert len(sites) > 0, "Expected at least one site"
    return sites[0]["id"]


# --- Agents Overview ---
class TestAgentsOverview:
    def test_overview_with_site(self, headers, site_id):
        r = requests.get(f"{BASE}/agents/overview", params={"site_id": site_id}, headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("seo", "geo", "content", "social"):
            assert k in data, f"missing {k}"
        # SEO
        seo = data["seo"]
        assert "audit" in seo and "saved_keywords" in seo and "gsc_connected" in seo
        assert "tracked_keywords" in seo and "rank_drops" in seo
        assert isinstance(seo["rank_drops"], list)
        # GEO
        assert "report" in data["geo"] and "actions" in data["geo"]
        # Content
        c = data["content"]
        assert "pending" in c and "published" in c and "quota" in c
        assert "used" in c["quota"] and "limit" in c["quota"]
        # Social
        s = data["social"]
        assert "networks" in s and "connected_count" in s and "total_posts" in s
        for net in ("linkedin", "facebook", "instagram", "gbp"):
            assert net in s["networks"], f"missing network {net}"
            assert "connected" in s["networks"][net]

    def test_overview_no_site(self, headers):
        r = requests.get(f"{BASE}/agents/overview", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(("seo", "geo", "content", "social")).issubset(data.keys())


# --- Workflows CRUD + Run + Notifications ---
class TestWorkflows:
    created_ids = []

    def test_create_no_actions_400(self, headers, site_id):
        r = requests.post(f"{BASE}/workflows", headers=headers, json={
            "site_id": site_id, "name": "TEST_bad", "trigger_type": "no_publication",
            "trigger_params": {"days": 1}, "actions": []
        }, timeout=30)
        assert r.status_code == 400

    def test_create_invalid_site_404(self, headers):
        r = requests.post(f"{BASE}/workflows", headers=headers, json={
            "site_id": "nonexistent-site-xyz", "name": "TEST_bad2",
            "trigger_type": "no_publication", "trigger_params": {"days": 1},
            "actions": ["notify"]
        }, timeout=30)
        assert r.status_code == 404

    def test_create_notify_and_run_no_publication(self, headers, site_id):
        r = requests.post(f"{BASE}/workflows", headers=headers, json={
            "site_id": site_id, "name": "TEST_no_pub_notify",
            "trigger_type": "no_publication", "trigger_params": {"days": 1},
            "actions": ["notify"]
        }, timeout=30)
        assert r.status_code == 200, r.text
        wf = r.json()
        assert wf["id"] and wf["enabled"] is True
        TestWorkflows.created_ids.append(wf["id"])

        # Run - should fire true (no publication in 1 day) and create a notification
        rr = requests.post(f"{BASE}/workflows/{wf['id']}/run", headers=headers, timeout=60)
        assert rr.status_code == 200, rr.text
        res = rr.json()
        assert res["fired"] is True, res
        actions = res.get("actions_results", [])
        assert any(a["action"] == "notify" and a["ok"] for a in actions), res

    def test_create_rank_drop_run(self, headers, site_id):
        r = requests.post(f"{BASE}/workflows", headers=headers, json={
            "site_id": site_id, "name": "TEST_rank_drop",
            "trigger_type": "rank_drop", "trigger_params": {"threshold": 3},
            "actions": ["notify"]
        }, timeout=30)
        assert r.status_code == 200
        wf = r.json()
        TestWorkflows.created_ids.append(wf["id"])
        rr = requests.post(f"{BASE}/workflows/{wf['id']}/run", headers=headers, timeout=60)
        assert rr.status_code == 200
        res = rr.json()
        # Preview has no rank_snapshots history → fired False with explicit reason
        assert res["fired"] is False
        assert "historique" in res["reason"].lower() or "search console" in res["reason"].lower()

    def test_create_ai_visibility_drop_run(self, headers, site_id):
        r = requests.post(f"{BASE}/workflows", headers=headers, json={
            "site_id": site_id, "name": "TEST_ai_vis",
            "trigger_type": "ai_visibility_drop", "trigger_params": {"threshold": 5},
            "actions": ["notify"]
        }, timeout=30)
        assert r.status_code == 200
        wf = r.json()
        TestWorkflows.created_ids.append(wf["id"])
        rr = requests.post(f"{BASE}/workflows/{wf['id']}/run", headers=headers, timeout=60)
        assert rr.status_code == 200
        res = rr.json()
        # Depending on # of ai_visibility_reports; assert message meaningful
        assert "reason" in res and len(res["reason"]) > 0

    def test_list_workflows(self, headers, site_id):
        r = requests.get(f"{BASE}/workflows", params={"site_id": site_id}, headers=headers, timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        ids = {w["id"] for w in items}
        for cid in TestWorkflows.created_ids:
            assert cid in ids

    def test_patch_workflow(self, headers):
        wid = TestWorkflows.created_ids[0]
        r = requests.patch(f"{BASE}/workflows/{wid}", headers=headers,
                           json={"enabled": False, "name": "TEST_no_pub_notify_v2"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is False
        assert r.json()["name"] == "TEST_no_pub_notify_v2"

    def test_patch_other_user_wf_404(self, headers):
        r = requests.patch(f"{BASE}/workflows/bogus-workflow-id-xyz", headers=headers,
                           json={"enabled": False}, timeout=30)
        assert r.status_code == 404

    def test_run_audit_action(self, headers, site_id):
        r = requests.post(f"{BASE}/workflows", headers=headers, json={
            "site_id": site_id, "name": "TEST_audit_action",
            "trigger_type": "no_publication", "trigger_params": {"days": 1},
            "actions": ["run_audit"]
        }, timeout=30)
        assert r.status_code == 200
        wf = r.json()
        TestWorkflows.created_ids.append(wf["id"])
        rr = requests.post(f"{BASE}/workflows/{wf['id']}/run", headers=headers, timeout=180)
        assert rr.status_code == 200, rr.text
        res = rr.json()
        assert res["fired"] is True
        actions = res.get("actions_results", [])
        audit_res = next((a for a in actions if a["action"] == "run_audit"), None)
        assert audit_res is not None
        assert audit_res["ok"] is True, audit_res
        assert "score" in audit_res["detail"].lower() or "audit" in audit_res["detail"].lower()

    # --- Notifications ---
    def test_notifications_list_and_read(self, headers):
        r = requests.get(f"{BASE}/notifications", params={"unread_only": "true"}, headers=headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "notifications" in data and "unread_count" in data
        assert isinstance(data["notifications"], list)

        # Mark read without ids/all -> 400
        rr = requests.post(f"{BASE}/notifications/read", headers=headers, json={}, timeout=30)
        assert rr.status_code == 400

        # Mark selective if any exist
        if data["notifications"]:
            first_id = data["notifications"][0]["id"]
            rr = requests.post(f"{BASE}/notifications/read", headers=headers, json={"ids": [first_id]}, timeout=30)
            assert rr.status_code == 200
            assert rr.json().get("updated", 0) >= 1

        # Mark all as read
        rr = requests.post(f"{BASE}/notifications/read", headers=headers, json={"all": True}, timeout=30)
        assert rr.status_code == 200

        # Verify unread_count = 0
        r2 = requests.get(f"{BASE}/notifications", params={"unread_only": "true"}, headers=headers, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["unread_count"] == 0

    def test_zzz_cleanup(self, headers):
        # Cleanup TEST_ workflows created here
        for wid in TestWorkflows.created_ids:
            requests.delete(f"{BASE}/workflows/{wid}", headers=headers, timeout=30)
        # Verify one is deleted -> 404
        if TestWorkflows.created_ids:
            r = requests.delete(f"{BASE}/workflows/{TestWorkflows.created_ids[0]}", headers=headers, timeout=30)
            assert r.status_code == 404
