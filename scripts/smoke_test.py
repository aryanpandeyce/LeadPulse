"""Automated deployment & local smoke test runner for LeadPulse (Step A8 & B6).

Usage:
    python scripts/smoke_test.py --backend-url http://localhost:8000 --frontend-url http://localhost:3000
"""

import argparse
import os
import sys
import urllib.error
import urllib.request
import json
from typing import Any


def _http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    expected_status: int = 200,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data_bytes = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        resp_headers = {k.lower(): v for k, v in exc.headers.items()}
        body = json.loads(exc.read().decode("utf-8"))

    if status != expected_status:
        raise AssertionError(
            f"Expected HTTP {expected_status} from {method} {url}, got {status}: {body}"
        )
    return status, body, resp_headers


def run_smoke_tests(backend_url: str, frontend_url: str, agent_password: str) -> None:
    base = backend_url.rstrip("/")
    if base.endswith("/api/v1"):
        api_base = base
    else:
        api_base = f"{base}/api/v1"

    print(f"[Smoke Test] Target Backend API : {api_base}")
    print(f"[Smoke Test] Target Frontend URL: {frontend_url}")

    # 1. GET /api/v1/health
    _, health, h_headers = _http_json(f"{api_base}/health")
    assert health.get("status") == "ok", f"Unexpected /health payload: {health}"
    assert "x-request-id" in h_headers, "Missing X-Request-ID header on /health"
    print("  [PASS] 1/8 GET /api/v1/health -> 200 OK (X-Request-ID present)")

    # 2. GET /api/v1/ready
    _, ready, _ = _http_json(f"{api_base}/ready")
    checks = ready.get("checks", {})
    assert checks.get("database") == "up", f"Database check not up: {ready}"
    assert checks.get("redis") == "up", f"Redis check not up: {ready}"
    print("  [PASS] 2/8 GET /api/v1/ready  -> 200 OK (database=up, redis=up)")

    # 3. POST /api/v1/auth/login
    _, login_body, _ = _http_json(
        f"{api_base}/auth/login",
        method="POST",
        payload={"email": "agent@leadpulse.io", "password": agent_password},
    )
    access_token = login_body.get("access_token")
    assert access_token, "No access_token returned from /auth/login"
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    print("  [PASS] 3/8 POST /api/v1/auth/login (agent@leadpulse.io) -> JWT issued")

    # 4. GET /api/v1/customers?limit=5
    _, cust_body, _ = _http_json(f"{api_base}/customers?limit=5", headers=auth_headers)
    assert len(cust_body.get("data", [])) > 0, "Expected non-empty customers data"
    print(f"  [PASS] 4/8 GET /api/v1/customers?limit=5 -> {len(cust_body['data'])} rows (total={cust_body.get('total')})")

    # 5. GET /api/v1/leads?limit=5
    _, leads_body, _ = _http_json(f"{api_base}/leads?limit=5", headers=auth_headers)
    assert len(leads_body.get("data", [])) > 0, "Expected non-empty leads data"
    assert leads_body.get("next_cursor") is not None, "Expected non-null next_cursor"
    print(f"  [PASS] 5/8 GET /api/v1/leads?limit=5 -> next_cursor={leads_body['next_cursor'][:20]}...")

    # 6. GET /api/v1/kpis
    _, kpis_body, _ = _http_json(f"{api_base}/kpis", headers=auth_headers)
    assert kpis_body.get("source") in ("redis", "materialized_view"), f"Unexpected KPI source: {kpis_body}"
    print(f"  [PASS] 6/8 GET /api/v1/kpis -> source={kpis_body['source']} ({kpis_body.get('query_ms')} ms)")

    # 7. 404 Unified Error Envelope
    _, err_body, err_headers = _http_json(
        f"{api_base}/error-demo?kind=not_found",
        expected_status=404,
    )
    err_obj = err_body.get("error", {})
    assert err_obj.get("code") == "LEAD_NOT_FOUND", f"Unexpected error code: {err_body}"
    assert err_obj.get("request_id"), f"Missing error.request_id: {err_body}"
    assert "x-request-id" in err_headers, "Missing X-Request-ID header on 404 response"
    print(f"  [PASS] 7/8 GET /api/v1/error-demo?kind=not_found -> 404 Unified Envelope (request_id={err_obj['request_id']})")

    # 8. FRONTEND_URL
    req = urllib.request.Request(frontend_url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as f_resp:
        assert f_resp.status == 200, f"Frontend returned HTTP {f_resp.status}"
    print(f"  [PASS] 8/8 GET {frontend_url} -> 200 OK")
    print("[Smoke Test] ALL 8 CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LeadPulse end-to-end smoke tests.")
    parser.add_argument(
        "--backend-url",
        default=os.getenv("BACKEND_URL", "http://localhost:8000"),
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("FRONTEND_URL", "http://localhost:3000"),
        help="Frontend base URL (default: http://localhost:3000)",
    )
    parser.add_argument(
        "--agent-password",
        default=os.getenv("SEED_AGENT_PASSWORD", "Agent@123"),
        help="Agent user password",
    )
    args = parser.parse_args()
    try:
        run_smoke_tests(args.backend_url, args.frontend_url, args.agent_password)
    except Exception as exc:
        print(f"[Smoke Test] FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

