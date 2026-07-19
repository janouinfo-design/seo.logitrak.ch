"""
Backend tests for iteration_17:
- Admin panel endpoints (/api/admin/*)
- Workspace invite flow + RBAC enforcement (/api/team/*, /api/workspace/*)
Runs against public REACT_APP_BACKEND_URL.
"""
import os
import time
import uuid
import re
import pytest
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "contact@logitrak.ch"
ADMIN_PWD = "AdminTest2026!"
DEMO_EMAIL = "demo@logirent.fr"
DEMO_PWD = "demo1234"


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PWD)


@pytest.fixture(scope="session")
def demo_token():
    return _login(DEMO_EMAIL, DEMO_PWD)


# ---- 1. Login & is_admin resolution ----
def test_login_admin_is_admin_true(admin_token):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("is_admin") is True, data


def test_login_demo_is_admin_false(demo_token):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(demo_token), timeout=30)
    assert r.status_code == 200
    assert r.json().get("is_admin") is False


# ---- 2. /api/admin/overview ----
def test_admin_overview_ok(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/overview", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ["total_users", "total_sites", "total_drafts", "drafts_this_month",
              "published_drafts", "revenue_eur", "plan_distribution"]:
        assert k in data, f"missing key {k} in {data}"


def test_admin_overview_forbidden_for_demo(demo_token):
    r = requests.get(f"{BASE_URL}/api/admin/overview", headers=_h(demo_token), timeout=30)
    assert r.status_code == 403


# ---- 3. /api/admin/users ----
def test_admin_users_ok(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/users", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
    body = r.json()
    users = body.get("users") if isinstance(body, dict) else body
    assert isinstance(users, list) and len(users) > 0
    u = users[0]
    for k in ["id", "email", "full_name", "created_at", "plan", "is_admin",
              "articles_this_month", "sites_count"]:
        assert k in u, f"missing key {k} in user object {u}"


def test_admin_users_forbidden_for_demo(demo_token):
    r = requests.get(f"{BASE_URL}/api/admin/users", headers=_h(demo_token), timeout=30)
    assert r.status_code == 403


# ---- 4. PATCH admin plan change ----
def test_admin_patch_demo_plan_pro_then_free(admin_token, demo_token):
    body = requests.get(f"{BASE_URL}/api/admin/users", headers=_h(admin_token)).json()
    users = body.get("users") if isinstance(body, dict) else body
    demo_user = next(u for u in users if u["email"] == DEMO_EMAIL)
    uid = demo_user["id"]

    # -> pro
    r = requests.patch(f"{BASE_URL}/api/admin/users/{uid}/plan",
                       headers=_h(admin_token), json={"plan": "pro"}, timeout=30)
    assert r.status_code == 200, r.text

    w = requests.get(f"{BASE_URL}/api/workspace", headers=_h(demo_token)).json()
    assert w.get("plan") == "pro", w
    limit = (w.get("usage") or {}).get("articles_limit")
    assert limit == 50, f"expected 50 for pro, got {limit} in {w}"

    # -> free (cleanup)
    r = requests.patch(f"{BASE_URL}/api/admin/users/{uid}/plan",
                       headers=_h(admin_token), json={"plan": "free"}, timeout=30)
    assert r.status_code == 200


# ---- 5. Invitation flow ----
INVITE_EMAIL = f"testeur.equipe+{uuid.uuid4().hex[:6]}@example.com"
_invite_state = {}


def test_invite_create(admin_token):
    r = requests.post(f"{BASE_URL}/api/team/invites",
                      headers=_h(admin_token),
                      json={"email": INVITE_EMAIL, "role": "editor"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    link = data.get("invite_link") or data.get("link") or ""
    assert "/register?invite=" in link, data
    m = re.search(r"invite=([A-Za-z0-9_\-]+)", link)
    assert m
    _invite_state["token"] = m.group(1)
    _invite_state["email"] = INVITE_EMAIL


def test_invite_info_public():
    tok = _invite_state["token"]
    r = requests.get(f"{BASE_URL}/api/team/invite-info", params={"token": tok}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("valid") is True
    assert d.get("email") == INVITE_EMAIL
    assert d.get("role") == "editor"
    assert d.get("workspace_name")


def test_invite_register_new_user():
    tok = _invite_state["token"]
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": INVITE_EMAIL, "full_name": "Testeur Equipe",
        "password": "Test12345!", "invite_token": tok,
    }, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("token")
    _invite_state["member_token"] = data["token"]


def test_new_member_me_shows_role_and_acting():
    mt = _invite_state["member_token"]
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(mt), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("workspace_role") == "editor", d
    assert d.get("acting_workspace_name"), d


def test_admin_team_members_lists_new_member(admin_token):
    r = requests.get(f"{BASE_URL}/api/team/members", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    members = body.get("members") if isinstance(body, dict) else body
    match = [m for m in members if m.get("email") == INVITE_EMAIL]
    assert match, f"member {INVITE_EMAIL} not in {members}"
    assert match[0].get("role") == "editor"
    _invite_state["member_id"] = match[0].get("id") or match[0].get("member_id") or match[0].get("user_id")


# ---- 6. RBAC ----
def test_editor_can_get_drafts():
    mt = _invite_state["member_token"]
    r = requests.get(f"{BASE_URL}/api/drafts", headers=_h(mt), timeout=30)
    assert r.status_code == 200


def test_editor_forbidden_on_post_sites():
    mt = _invite_state["member_token"]
    r = requests.post(f"{BASE_URL}/api/sites", headers=_h(mt),
                      json={"name": "x", "label": "Autre", "url": "https://x.com"}, timeout=30)
    assert r.status_code == 403, r.text
    assert "Éditeur" in r.text or "editeur" in r.text.lower()


def test_admin_downgrade_to_viewer(admin_token):
    mid = _invite_state["member_id"]
    r = requests.patch(f"{BASE_URL}/api/team/members/{mid}",
                       headers=_h(admin_token), json={"role": "viewer"}, timeout=30)
    assert r.status_code == 200, r.text


def test_viewer_blocked_on_post():
    mt = _invite_state["member_token"]
    # Try POST /api/drafts (write op) → should be blocked as viewer
    r = requests.post(f"{BASE_URL}/api/drafts", headers=_h(mt),
                      json={"site_id": "x", "topic": "test", "language": "fr"}, timeout=30)
    assert r.status_code == 403, r.text
    assert "Lecteur" in r.text or "lecteur" in r.text.lower()


def test_viewer_can_still_get_drafts():
    mt = _invite_state["member_token"]
    r = requests.get(f"{BASE_URL}/api/drafts", headers=_h(mt), timeout=30)
    assert r.status_code == 200


# ---- 7. Workspace switch ----
def test_memberships_lists_two_workspaces():
    mt = _invite_state["member_token"]
    r = requests.get(f"{BASE_URL}/api/workspace/memberships", headers=_h(mt), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    lst = body.get("memberships") if isinstance(body, dict) else body
    assert isinstance(lst, list) and len(lst) >= 2
    own = [x for x in lst if x.get("is_own")]
    active = [x for x in lst if x.get("active")]
    assert own, lst
    assert active, lst
    _invite_state["own_ws"] = own[0].get("workspace_id") or own[0].get("id")


def test_switch_to_own_workspace():
    mt = _invite_state["member_token"]
    ws = _invite_state["own_ws"]
    r = requests.post(f"{BASE_URL}/api/workspace/switch",
                      headers=_h(mt), json={"workspace_id": ws}, timeout=30)
    assert r.status_code == 200, r.text
    me = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(mt)).json()
    # In own workspace, workspace_role should be null/absent
    assert not me.get("workspace_role"), me


# ---- 8. Cleanup: remove member ----
def test_admin_delete_member(admin_token):
    mid = _invite_state["member_id"]
    r = requests.delete(f"{BASE_URL}/api/team/members/{mid}", headers=_h(admin_token), timeout=30)
    assert r.status_code in (200, 204), r.text
    body = requests.get(f"{BASE_URL}/api/team/members", headers=_h(admin_token)).json()
    members = body.get("members") if isinstance(body, dict) else body
    assert not [m for m in members if m.get("email") == INVITE_EMAIL]


# ---- 9. Regression ----
def test_regression_demo_endpoints(demo_token):
    for path in ["/api/sites", "/api/drafts", "/api/workspace"]:
        r = requests.get(f"{BASE_URL}{path}", headers=_h(demo_token), timeout=30)
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text}"
    w = requests.get(f"{BASE_URL}/api/workspace", headers=_h(demo_token)).json()
    assert w.get("plan") == "free"
    limit = (w.get("usage") or {}).get("articles_limit")
    assert limit == 5, w
