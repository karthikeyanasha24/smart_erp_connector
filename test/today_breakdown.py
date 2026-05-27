#!/usr/bin/env python3
"""
TODAY sales breakdown — diagnose why 'today' tab keeps loading.

Tests the same API endpoints the Analytics page uses for period='today',
reports what data comes back (or doesn't), and flags the exact failure point.

Usage:
  python test/today_breakdown.py
  python test/today_breakdown.py --password secret
  python test/today_breakdown.py --verbose        # show full JSON responses
  python test/today_breakdown.py --timeout 120
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date as dt
from typing import Any, Dict, List, Optional, Tuple

from breakdown_health import ensure_api_reachable

# ─── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_BASE     = os.environ.get("API_BASE_URL",    "http://localhost:3000")
DEFAULT_EMAIL    = os.environ.get("DASHBOARD_EMAIL", "asha24@gmail.com")
DEFAULT_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
PERIOD           = "today"
LOGIN_TIMEOUT    = 45
DEFAULT_TIMEOUT  = 180   # per-request timeout in seconds

TODAY = dt.today().isoformat()   # e.g. "2026-05-26"

# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(msg, flush=True)


def _http(
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}  ←  {detail}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Timed out after {timeout}s: {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}") from exc


def _api_start_hint(base: str) -> str:
    return (
        f"\n  Start the backend: cd backend && python main.py\n"
        f"  Wait for 'Cache warmup complete', then re-run."
    )


def _login(base: str, email: str, password: str, timeout: int = LOGIN_TIMEOUT) -> str:
    url = f"{base.rstrip('/')}/auth/login"
    body = {"email": email, "password": password}
    deadline = time.monotonic() + 600
    last_err: Optional[RuntimeError] = None
    while time.monotonic() < deadline:
        try:
            out = _http("POST", url, body=body, timeout=timeout)
            token = out.get("access_token")
            if not token:
                raise RuntimeError(f"Login failed: {out}")
            return token
        except RuntimeError as exc:
            last_err = exc
            if "timed out" not in str(exc).lower() or time.monotonic() >= deadline:
                raise
            _log("  Login timed out — retrying in 5s...")
            time.sleep(5)
    raise RuntimeError(f"Login failed after 600s: {last_err}")


def _fetch_with_heartbeat(url: str, *, token: str, timeout: int, label: str) -> Tuple[Dict[str, Any], float]:
    """Fetch a URL with a background heartbeat logger. Returns (data, elapsed_ms)."""
    stop = threading.Event()

    def _pulse():
        t0 = time.perf_counter()
        while not stop.wait(5.0):
            _log(f"       … {label} ({time.perf_counter() - t0:.0f}s elapsed)")

    threading.Thread(target=_pulse, daemon=True).start()
    t0 = time.perf_counter()
    try:
        data = _http("GET", url, token=token, timeout=timeout)
        return data, (time.perf_counter() - t0) * 1000
    finally:
        stop.set()


# ─── Fetch all today endpoints ────────────────────────────────────────────────

ENDPOINTS: List[Tuple[str, str]] = [
    # (name, url_suffix)
    ("kpis",        f"/analytics/kpis?period={PERIOD}"),
    ("trend",       f"/analytics/trend?period={PERIOD}"),
    ("categories",  f"/analytics/categories?period={PERIOD}&top_n=100"),
    ("branches",    f"/analytics/branches?period={PERIOD}"),
    ("bundle",      f"/analytics/bundle?period={PERIOD}&top_n=100&include_departments=false&include_kpis=true"),
    ("dashboard",   f"/analytics/dashboard?period={PERIOD}"),
]


def fetch_all(base: str, token: str, timeout: int, sequential: bool = False) -> Dict[str, Any]:
    """Fetch all today endpoints in parallel (or sequentially) and return results."""
    base = base.rstrip("/")
    jobs = {name: base + suffix for name, suffix in ENDPOINTS}
    results: Dict[str, Any]      = {}
    timings: Dict[str, float]    = {}
    errors:  Dict[str, str]      = {}

    def _one(name: str, url: str) -> Tuple[str, Dict[str, Any], float]:
        data, ms = _fetch_with_heartbeat(url, token=token, timeout=timeout, label=name)
        return name, data, ms

    if sequential:
        for name, url in jobs.items():
            _log(f"\n  ▶ {name}  ({url})")
            try:
                n, data, ms = _one(name, url)
                results[n] = data
                timings[n] = round(ms, 1)
                _log(f"    ✓ OK  {ms:.0f} ms")
            except Exception as exc:
                errors[name] = str(exc)
                _log(f"    ✗ FAIL  {exc}")
    else:
        _log(f"\n  Starting {len(jobs)} requests in parallel (timeout {timeout}s each) …")
        for n in jobs:
            _log(f"    queued: {n}")
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futs = {pool.submit(_one, n, u): n for n, u in jobs.items()}
            for fut in as_completed(futs):
                key = futs[fut]
                try:
                    name, data, ms = fut.result()
                    results[name] = data
                    timings[name] = round(ms, 1)
                    _log(f"    ✓ {name}  {ms:.0f} ms")
                except Exception as exc:
                    errors[key] = str(exc)
                    _log(f"    ✗ {key}: {exc}")

    return {"results": results, "timings": timings, "errors": errors}


# ─── Interpret & display ──────────────────────────────────────────────────────

def _n(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_lakhs(v: float) -> str:
    return f"₹{v / 100_000:,.2f} L"


def _check_kpis(data: Dict[str, Any]) -> None:
    rev = data.get("revenue") or {}
    txn = data.get("transactions") or {}
    qty = data.get("quantity") or {}
    _log(f"\n  {'─'*60}")
    _log("  KPIs endpoint  /analytics/kpis?period=today")
    _log(f"  {'─'*60}")
    _log(f"  Revenue  value={_fmt_lakhs(_n(rev.get('value')))}  prior={_fmt_lakhs(_n(rev.get('prior')))}  growth={rev.get('growth')}%")
    _log(f"  Txns     value={_n(txn.get('value')):.0f}         prior={_n(txn.get('prior')):.0f}")
    _log(f"  Qty      value={_n(qty.get('value')):.0f}         prior={_n(qty.get('prior')):.0f}")
    if _n(rev.get("value")) == 0:
        _log("  ⚠  Revenue is ZERO — today may have no sales yet, or the date filter is wrong")
    else:
        _log("  ✓  Revenue is non-zero")


def _check_trend(data: Dict[str, Any]) -> None:
    pts = data.get("trend") or []
    _log(f"\n  {'─'*60}")
    _log("  Trend endpoint  /analytics/trend?period=today")
    _log(f"  {'─'*60}")
    _log(f"  Points returned: {len(pts)}")
    if pts:
        total = sum(_n(p.get("revenue", p.get("current", 0))) for p in pts)
        _log(f"  Total revenue across points: {_fmt_lakhs(total)}")
        for p in pts[:5]:
            _log(f"    date={p.get('date','')}  rev={_fmt_lakhs(_n(p.get('revenue', p.get('current',0))))}  bills={_n(p.get('transactions', p.get('bills',0))):.0f}")
        if len(pts) > 5:
            _log(f"    … and {len(pts)-5} more")
    else:
        _log("  ⚠  EMPTY trend — no data points returned for today")


def _check_categories(data: Dict[str, Any]) -> None:
    cats = data.get("categories") or []
    _log(f"\n  {'─'*60}")
    _log("  Categories endpoint  /analytics/categories?period=today")
    _log(f"  {'─'*60}")
    _log(f"  Categories returned: {len(cats)}")
    if cats:
        total = sum(_n(c.get("revenue", 0)) for c in cats)
        _log(f"  Total revenue: {_fmt_lakhs(total)}")
        for c in cats[:6]:
            pct = _n(c.get("percentage", 0))
            _log(f"    {c.get('name',''):<20}  {_fmt_lakhs(_n(c.get('revenue',0)))}  {pct:.2f}%")
    else:
        _log("  ⚠  EMPTY categories")


def _check_bundle(data: Dict[str, Any]) -> None:
    _log(f"\n  {'─'*60}")
    _log("  Bundle endpoint  /analytics/bundle?period=today")
    _log(f"  {'─'*60}")
    kpis   = data.get("kpis") or {}
    cats   = data.get("categories") or []
    trend  = data.get("trend") or []
    branches = data.get("branches") or []
    timings  = data.get("timings_ms") or {}
    errors   = data.get("errors") or {}
    rev_val = _n((kpis.get("revenue") or {}).get("value", 0))
    _log(f"  kpis.revenue.value = {_fmt_lakhs(rev_val)}")
    _log(f"  categories:  {len(cats)} rows")
    _log(f"  trend:       {len(trend)} points")
    _log(f"  branches:    {len(branches)} rows")
    _log(f"  server timings: {timings}")
    if errors:
        _log(f"  ⚠  bundle errors: {errors}")
    if rev_val == 0 and not cats and not trend:
        _log("  ⚠  Bundle returned ALL ZEROS / empty — this is the root cause of the loading spinner")
    elif rev_val == 0:
        _log("  ⚠  Revenue is zero but some sub-data present — partial issue")
    else:
        _log("  ✓  Bundle has non-zero data")


def _check_dashboard(data: Dict[str, Any]) -> None:
    _log(f"\n  {'─'*60}")
    _log("  Dashboard endpoint  /analytics/dashboard?period=today")
    _log(f"  {'─'*60}")
    summary = data.get("summary") or {}
    sales   = _n(summary.get("mtd_sales", summary.get("current_sales", 0)))
    bills   = _n(summary.get("bills", 0))
    qty     = _n(summary.get("quantity", 0))
    growth  = summary.get("sales_growth_pct")
    dr      = data.get("date_range") or {}
    _log(f"  date_range: {dr}")
    _log(f"  summary.sales   = {_fmt_lakhs(sales)}")
    _log(f"  summary.bills   = {bills:.0f}")
    _log(f"  summary.qty     = {qty:.0f}")
    _log(f"  summary.growth  = {growth}%")
    trend   = data.get("trend") or []
    cats    = data.get("categories") or []
    _log(f"  trend points:   {len(trend)}")
    _log(f"  categories:     {len(cats)}")
    if sales == 0:
        _log("  ⚠  Sales is ZERO in dashboard summary")
    else:
        _log("  ✓  Dashboard summary has non-zero sales")


def diagnose(fetch_result: Dict[str, Any], verbose: bool = False) -> None:
    results = fetch_result["results"]
    timings = fetch_result["timings"]
    errors  = fetch_result["errors"]

    _log(f"\n{'═'*64}")
    _log(f"  TODAY ({TODAY}) — API RESPONSE DIAGNOSIS")
    _log(f"{'═'*64}")

    _log(f"\n  Timings (ms): {timings}")
    if errors:
        _log(f"\n  ⚠  ERRORS:")
        for k, v in errors.items():
            _log(f"    {k}: {v}")

    if "kpis" in results:
        _check_kpis(results["kpis"])

    if "trend" in results:
        _check_trend(results["trend"])

    if "categories" in results:
        _check_categories(results["categories"])

    if "bundle" in results:
        _check_bundle(results["bundle"])

    if "dashboard" in results:
        _check_dashboard(results["dashboard"])

    # ── Root cause summary ────────────────────────────────────────────────────
    _log(f"\n{'═'*64}")
    _log("  ROOT CAUSE SUMMARY")
    _log(f"{'═'*64}")

    kpi_rev = _n(((results.get("kpis") or {}).get("revenue") or {}).get("value", 0))
    bundle  = results.get("bundle") or {}
    b_rev   = _n(((bundle.get("kpis") or {}).get("revenue") or {}).get("value", 0))
    b_cats  = len(bundle.get("categories") or [])
    b_trend = len(bundle.get("trend") or [])

    if errors:
        _log(f"\n  ✗  {len(errors)} endpoint(s) failed: {list(errors.keys())}")
        _log("     → Fix the failing endpoints first. Check backend logs for SQL errors.")

    if kpi_rev == 0 and b_rev == 0:
        _log(f"\n  ✗  ALL revenue is ZERO for today ({TODAY})")
        _log("     Possible causes:")
        _log("     1. No sales recorded yet today (it's early in the day)")
        _log("     2. The SQL date filter still has the old bug  (< instead of <= or wrong DATEADD)")
        _log("     3. Backend cache is serving stale zeros — try restarting the backend")
        _log("     4. The DB date column timezone is UTC and today in UTC is yesterday locally")
    elif b_cats == 0 and b_trend == 0 and b_rev > 0:
        _log(f"\n  ⚠  KPIs have revenue ({_fmt_lakhs(b_rev)}) but bundle returned no trend/categories")
        _log("     → The bundle endpoint is missing sub-queries for 'today' period")
        _log("     → Check backend analytics/all.py or analytics/bundle route for 'today' handling")
    elif b_rev > 0:
        _log(f"\n  ✓  Data is present: {_fmt_lakhs(b_rev)} revenue today")
        if "bundle" in errors or "kpis" in errors:
            _log("     ✗  But some endpoints failed — frontend may time out waiting")
        else:
            _log("     → The data IS available. The frontend loading issue is likely:")
            _log("       a) Frontend SWR/cache serving stale empty state for 'today'")
            _log("       b) Frontend waiting on a slow endpoint before rendering")
            _log("       c) The bundle endpoint takes too long for today (cold cache)")
            _log("       Recommendation: clear browser localStorage (smerp_c:*) and reload")

    if verbose:
        _log(f"\n{'─'*64}")
        _log("  VERBOSE — Full JSON responses")
        _log(f"{'─'*64}")
        for name, data in results.items():
            _log(f"\n  [{name}]")
            _log(json.dumps(data, indent=2, ensure_ascii=False)[:3000])

    _log("")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Diagnose 'today' period data for the Analytics page")
    parser.add_argument("--base-url",  default=DEFAULT_BASE)
    parser.add_argument("--email",     default=DEFAULT_EMAIL)
    parser.add_argument("--password",  default=DEFAULT_PASSWORD)
    parser.add_argument("--timeout",   type=int, default=DEFAULT_TIMEOUT,
                        help=f"Per-request timeout in seconds (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--sequential", action="store_true",
                        help="Fetch endpoints one at a time instead of in parallel")
    parser.add_argument("--verbose",   action="store_true",
                        help="Print full JSON responses")
    parser.add_argument("--json",      action="store_true",
                        help="Write full results to today_results.json")
    args = parser.parse_args()

    password = args.password or input(f"Password for {args.email}: ").strip()

    _log(f"\nChecking API at {args.base_url} …")
    health = ensure_api_reachable(
        args.base_url,
        http_get=_http,
        log=_log,
        api_start_hint=_api_start_hint(args.base_url),
    )
    mssql = (health.get("mssql") or {}).get("connected")
    _log(f"  Proceeding | status={health.get('status')} | SQL Server: {mssql}")
    if not mssql:
        _log("  ⚠  SQL Server is NOT connected — all queries will return zeros/errors")

    _log(f"\nLogging in as {args.email} …")
    token = _login(args.base_url, args.email, password)
    _log(f"  ✓ Logged in  (today = {TODAY})")

    t0     = time.perf_counter()
    result = fetch_all(args.base_url, token, args.timeout, sequential=args.sequential)
    result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    if args.json:
        out_path = "today_results.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result["results"], f, indent=2, ensure_ascii=False)
        _log(f"\nWrote full JSON → {out_path}")

    diagnose(result, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"\nUnexpected error: {exc}", file=sys.stderr)
        raise SystemExit(1)
