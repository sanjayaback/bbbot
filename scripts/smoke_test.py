"""Post-deployment smoke test for DocuQuery.

Usage:
  python scripts/smoke_test.py https://docuquery-api.example.com

Optional authenticated check:
  DOCUQUERY_ACCESS_TOKEN=... python scripts/smoke_test.py https://docuquery-api.example.com
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def request(base: str, path: str, token: str | None = None) -> tuple[int, object]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{base.rstrip('/')}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body: object = json.loads(raw)
        except Exception:
            body = raw
        return exc.code, body


def check(label: str, status: int, body: object, expected: set[int]) -> bool:
    ok = status in expected
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: HTTP {status}")
    if not ok:
        print(json.dumps(body, indent=2, default=str))
    return ok


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    token = os.getenv("DOCUQUERY_ACCESS_TOKEN")
    passed = True

    status, body = request(base, "/health")
    passed &= check("process health", status, body, {200})

    status, body = request(base, "/ready")
    passed &= check("database + redis readiness", status, body, {200})

    status, body = request(base, "/api/public-config")
    passed &= check("public configuration", status, body, {200})

    if token:
        status, body = request(base, "/api/workspaces", token)
        passed &= check("authenticated workspace bootstrap", status, body, {200})
    else:
        print("[SKIP] authenticated workspace check (set DOCUQUERY_ACCESS_TOKEN)")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
