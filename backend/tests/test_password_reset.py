"""Backend tests for forgot-password / reset-password flow."""
import os
import re
import subprocess
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")
DEMO_EMAIL = "demo@logirent.fr"
DEMO_PWD = "demo1234"


def _tail_log_for_token(email: str, since_ts: float, timeout: float = 8.0):
    """Grep backend err log for PASSWORD RESET LINK containing email; return token or None."""
    deadline = time.time() + timeout
    pattern = re.compile(r"reset-password\?token=([A-Za-z0-9_\-]+)")
    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                ["tail", "-n", "500", "/var/log/supervisor/backend.err.log"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="ignore")
        except Exception:
            out = ""
        # find latest match for this email
        matches = [m for m in pattern.finditer(out)]
        if matches:
            # verify email appears near a match (simple filter)
            lines = out.splitlines()
            for line in reversed(lines):
                if email in line and "reset-password?token=" in line:
                    m = pattern.search(line)
                    if m:
                        return m.group(1)
        time.sleep(0.5)
    return None


def test_login_returns_token_key():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PWD})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data
    assert data["user"]["email"] == DEMO_EMAIL


def test_forgot_password_existing_email():
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": DEMO_EMAIL})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_forgot_password_unknown_email_returns_same_response():
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "nobody-xyz-12345@example.com"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_reset_with_bogus_token_returns_400():
    r = requests.post(
        f"{BASE_URL}/api/auth/reset-password",
        json={"token": "totally-bogus-token-xxx", "new_password": "somepass123"},
    )
    assert r.status_code == 400


def test_reset_short_password_returns_422():
    r = requests.post(
        f"{BASE_URL}/api/auth/reset-password",
        json={"token": "whatever", "new_password": "short"},
    )
    assert r.status_code == 422


def test_full_reset_flow_and_restore_demo_password():
    # 1) trigger forgot for demo
    ts = time.time()
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": DEMO_EMAIL})
    assert r.status_code == 200
    token = _tail_log_for_token(DEMO_EMAIL, ts)
    assert token, "Reset token not found in backend logs"

    # 2) reset to new password
    new_pwd = "NewTestPwd_9!"
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"token": token, "new_password": new_pwd})
    assert r.status_code == 200, r.text

    # 3) old pwd fails
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PWD})
    assert r.status_code == 401

    # 4) new pwd works
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": new_pwd})
    assert r.status_code == 200

    # 5) token reuse -> 400
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"token": token, "new_password": "AnotherPwd_9!"})
    assert r.status_code == 400

    # 6) Restore demo1234
    ts2 = time.time()
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": DEMO_EMAIL})
    assert r.status_code == 200
    token2 = _tail_log_for_token(DEMO_EMAIL, ts2)
    assert token2
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"token": token2, "new_password": DEMO_PWD})
    assert r.status_code == 200

    # 7) demo1234 works again
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PWD})
    assert r.status_code == 200


def test_register_still_works():
    import uuid
    email = f"test-{uuid.uuid4().hex[:8]}@test.fr"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": "testpass123", "full_name": "Test User"},
    )
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert "token" in data
