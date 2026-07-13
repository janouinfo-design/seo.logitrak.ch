"""Test bug fix: Keyword Intelligence JSON truncation error"""
import os
import sys
import time
import json
import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://content-logi-pro.preview.emergentagent.com").rstrip("/")
SITE_ID = "b3bec42d-2117-4f73-93b9-a0adc3b47a38"
EMAIL = "demo@logirent.fr"
PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_repair_json_truncated():
    """Unit: _parse_llm_json on truncated JSON should return dict without exception"""
    from ai_visibility import _parse_llm_json
    truncated = '{"a": [{"b": "c", "d"'
    result = _parse_llm_json(truncated)
    assert isinstance(result, dict)
    assert "a" in result


def test_repair_json_various():
    from ai_visibility import _parse_llm_json, _repair_json
    # Truncated string
    assert isinstance(_parse_llm_json('{"x": "unterminated'), dict)
    # Nested truncation
    r = _parse_llm_json('{"clusters": [{"name": "x", "keywords": [{"kw": "y",')
    assert isinstance(r, dict)
    assert "clusters" in r


def test_keyword_intelligence_end_to_end(headers):
    """Main bug: full KI pipeline must complete without 'Expecting delimiter' error"""
    r = requests.post(f"{BASE_URL}/api/sites/{SITE_ID}/keyword-intelligence", headers=headers, timeout=30)
    assert r.status_code == 200, f"POST failed: {r.status_code} {r.text}"
    job_id = r.json().get("job_id")
    assert job_id, f"No job_id returned: {r.json()}"
    print(f"job_id={job_id}")

    # Poll up to 4 min
    deadline = time.time() + 240
    last = None
    while time.time() < deadline:
        rr = requests.get(f"{BASE_URL}/api/content/jobs/{job_id}", headers=headers, timeout=30)
        assert rr.status_code == 200, f"Poll failed: {rr.status_code} {rr.text}"
        last = rr.json()
        status = last.get("status")
        print(f"status={status}")
        if status == "completed":
            break
        if status == "failed" or status == "error":
            pytest.fail(f"Job failed: {last.get('error') or last}")
        time.sleep(10)
    else:
        pytest.fail(f"Job timed out. Last: {last}")

    assert last["status"] == "completed"
    err = last.get("error") or ""
    assert "Expecting" not in str(err), f"JSON delimiter error still present: {err}"

    result = last.get("result") or {}
    assert result.get("clusters"), f"clusters empty: {list(result.keys())}"
    assert "quick_wins" in result
    assert "content_plan" in result
    assert "competitors" in result
    assert "summary" in result
    print(f"OK - {len(result.get('clusters', []))} clusters")


def test_keyword_intelligence_latest(headers):
    r = requests.get(f"{BASE_URL}/api/sites/{SITE_ID}/keyword-intelligence/latest", headers=headers, timeout=30)
    assert r.status_code == 200, f"Latest failed: {r.status_code} {r.text}"
    data = r.json()
    # Might be wrapped
    report = data.get("report") or data.get("result") or data
    assert report.get("clusters"), f"latest missing clusters: {list(report.keys())}"
    assert "quick_wins" in report
    assert "content_plan" in report
    assert "competitors" in report
    assert "summary" in report
