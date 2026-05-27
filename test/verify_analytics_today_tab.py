#!/usr/bin/env python3
"""
Verify Analytics "Today" tab data path — same APIs the React app uses after the
useAnalytics.ts fix (bundle first → UI paints, dashboard/departments enrich later).

Usage:
  python test/verify_analytics_today_tab.py --email you@example.com --password secret
  python test/verify_analytics_today_tab.py --email ... --password ... --compare-mtd

Pass = Today bundle returns in < 30s with non-zero revenue (when cache warm: < 5s).
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import date as dt
from typing import Any, Dict, Optional, Tuple

from breakdown_health import ensure_api_reachable

DEFAULT_BASE = os.environ.get("API_BASE_URL", "http://localhost:3000")
DEFAULT_EMAIL = os.environ.get("DASHBOARD_EMAIL", "asha24@gmail.com")
DEFAULT_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
API_TOP_N = 100
BUNDLE_SLOW_S = 30


def _log(msg: str) -> None:
    print(msg, flush=True)


def _http(
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Timeout after {timeout}s: {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}") from exc


def _login(base: str, email: str, password: str) -> str:
    out = _http(
        "POST",
        f"{base.rstrip('/')}/auth/login",
        body={"email": email, "password": password},
        timeout=120,
    )
    token = out.get("access_token")
    if not token:
        raise RuntimeError(f"Login failed: {out}")
    return token


def _bundle_url(base: str, period: str) -> str:
    return (
        f"{base.rstrip('/')}/analytics/bundle"
        f"?period={period}&top_n={API_TOP_N}&include_departments=false&include_kpis=true"
    )


def _probe_bundle(
    base: str,
    token: str,
    period: str,
) -> Tuple[bool, float, Dict[str, Any]]:
    """Phase 1 only — this is what unblocks the Analytics UI spinner now."""
    stop = threading.Event()

    def _pulse() -> None:
        t0 = time.perf_counter()
        while not stop.wait(5.0):
            _log(f"    ... bundle/{period} ({time.perf_counter() - t0:.0f}s)")

    threading.Thread(target=_pulse, daemon=True).start()
    t0 = time.perf_counter()
    try:
        data = _http("GET", _bundle_url(base, period), token=token, timeout=300)
    finally:
        stop.set()
    ms = (time.perf_counter() - t0) * 1000
    kpis = data.get("kpis") or {}
    rev = float((kpis.get("revenue") or {}).get("value") or 0)
    ok = rev > 0 or len(data.get("branches") or []) > 0
    return ok, ms, {
        "revenue": rev,
        "branches": len(data.get("branches") or []),
        "categories": len(data.get("categories") or []),
        "trend": len(data.get("trend") or []),
        "timings_ms": data.get("timings_ms"),
        "source": (data.get("timings_ms") or {}).get("source"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Today tab bundle (Analytics page phase 1)")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--compare-mtd", action="store_true", help="Also time MTD bundle")
    args = parser.parse_args()

    password = args.password or input(f"Password for {args.email}: ").strip()
    _log(f"Verify Analytics Today tab | {args.base_url} | date {dt.today().isoformat()}\n")

    ensure_api_reachable(
        args.base_url,
        http_get=_http,
        log=_log,
        api_start_hint="\n  Start: cd backend && python main.py",
    )
    token = _login(args.base_url, args.email, password)
    _log("Login OK.\n")

    periods = ["today"]
    if args.compare_mtd:
        periods.append("mtd")

    all_ok = True
    for period in periods:
        _log(f"── {period.upper()} (phase-1 bundle — paints Analytics tab) ──")
        try:
            ok, ms, info = _probe_bundle(args.base_url, token, period)
            fast = ms < BUNDLE_SLOW_S * 1000
            _log(
                f"    {'PASS' if ok and fast else 'WARN' if ok else 'FAIL'} "
                f"in {ms:.0f} ms | revenue=₹{info['revenue']/100_000:,.2f} L "
                f"| branches={info['branches']} | cache={info.get('source')}"
            )
            if not ok:
                all_ok = False
                _log("    → No sales data — tab may look empty.")
            elif not fast:
                _log(f"    → Slow (>{BUNDLE_SLOW_S}s). Open MTD in browser once to warm cache, then retry.")
        except RuntimeError as exc:
            all_ok = False
            _log(f"    FAIL: {exc}")

    _log("\n── Expected in browser (after frontend fix) ──")
    _log("  • Toggle Today → KPIs/charts appear when bundle finishes (~2s warm).")
    _log("  • YoY chart may still load briefly (phase 2 dashboard); page no longer spins forever.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
