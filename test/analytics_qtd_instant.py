#!/usr/bin/env python3
"""
Analytics QTD tab — same API path the UI uses after the instant-toggle fix.

Simulates Analytics.tsx when you click QTD:
  1. Lean GET /analytics/bundle?period=qtd&include_departments=false&include_kpis=false
  2. (optional) GET /analytics/departments + /analytics/dashboard in parallel

When step 1 is <15s, the Analytics page should paint KPIs/charts immediately on QTD toggle
(if this script was run once or backend cache is warm).

Usage:
  python test/analytics_qtd_instant.py --email you@example.com --password secret
  python test/analytics_qtd_instant.py --email you@example.com --password secret --full
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from breakdown_health import ensure_api_reachable

DEFAULT_BASE = os.environ.get("API_BASE_URL", "http://localhost:3000")
PERIOD = "qtd"
TOP_N = 100
LOGIN_TIMEOUT = 120
BUNDLE_TIMEOUT = 300


def _log(msg: str) -> None:
    print(msg, flush=True)


def _http(
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 180,
) -> Dict[str, Any]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _login(base: str, email: str, password: str) -> str:
    out = _http(
        "POST",
        f"{base.rstrip('/')}/auth/login",
        body={"email": email, "password": password},
        timeout=LOGIN_TIMEOUT,
    )
    token = out.get("access_token")
    if not token:
        raise RuntimeError(f"Login failed: {out}")
    return token


def _sum_trend_revenue(trend: list) -> float:
    return sum(float(p.get("revenue") or 0) for p in trend)


def main() -> int:
    parser = argparse.ArgumentParser(description="QTD analytics UI path timing")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--email", default=os.environ.get("DASHBOARD_EMAIL", "asha24@gmail.com"))
    parser.add_argument("--password", default=os.environ.get("DASHBOARD_PASSWORD", ""))
    parser.add_argument("--full", action="store_true", help="Also fetch departments + dashboard (background in UI)")
    parser.add_argument("--timeout", type=int, default=BUNDLE_TIMEOUT)
    args = parser.parse_args()

    password = args.password or input(f"Password for {args.email}: ").strip()
    base = args.base_url.rstrip("/")

    _log(f"Checking API at {base}...")
    ensure_api_reachable(
        base,
        http_get=_http,
        log=_log,
        api_start_hint="\n  Start backend: cd backend && python main.py",
        wait_warmup=True,
    )

    _log(f"Logging in as {args.email}...")
    token = _login(base, args.email, password)

    lean_url = (
        f"{base}/analytics/bundle?period={PERIOD}&top_n={TOP_N}"
        f"&include_departments=false&include_kpis=false"
    )
    _log(f"\n[UI phase 1] Lean bundle (instant paint path)\n  GET {lean_url}")
    t0 = time.perf_counter()
    bundle = _http("GET", lean_url, token=token, timeout=args.timeout)
    ms1 = (time.perf_counter() - t0) * 1000

    trend = bundle.get("trend") or []
    branches = bundle.get("branches") or []
    categories = bundle.get("categories") or []
    rev = _sum_trend_revenue(trend)

    _log(f"  OK in {ms1:.0f} ms")
    _log(f"  trend points: {len(trend)}  branches: {len(branches)}  categories: {len(categories)}")
    _log(f"  revenue (from trend sum): ₹{rev / 100_000:,.2f} L")
    if bundle.get("timings_ms"):
        _log(f"  server timings_ms: {bundle['timings_ms']}")

    if ms1 > 20_000:
        _log("\n  ⚠ Slow — wait for 'Cache warmup complete' in backend, then re-run.")
        _log("  Second run should be ~2–15s (then Analytics QTD tab is instant).")
    else:
        _log("\n  ✓ Fast enough — Analytics QTD toggle should show data right away when this cache is warm.")

    if args.full:
        _log("\n[UI phase 2] Background enrich (departments + YoY dashboard)")
        t1 = time.perf_counter()
        dept_url = f"{base}/analytics/departments?period={PERIOD}&top_n={TOP_N}"
        dash_url = f"{base}/analytics/dashboard?period={PERIOD}"
        dept = _http("GET", dept_url, token=token, timeout=args.timeout)
        dash = _http("GET", dash_url, token=token, timeout=args.timeout)
        ms2 = (time.perf_counter() - t1) * 1000
        s = dash.get("summary") or {}
        _log(f"  OK in {ms2:.0f} ms (parallel-ish)")
        _log(f"  departments: {len(dept.get('departments') or [])}")
        _log(f"  dashboard sales: ₹{(float(s.get('mtd_sales') or 0) / 100_000):,.2f} L")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
