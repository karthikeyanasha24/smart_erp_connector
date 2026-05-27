#!/usr/bin/env python3
"""
Analytics tab probe — mirrors the browser (src/hooks/useAnalytics.ts prefetchAnalyticsPage).

Why Today/QTD/YTD can spin while MTD feels instant:
  Phase 1: GET /analytics/bundle?period=…  (fast when cache warm)
  Phase 2: GET /analytics/departments + GET /analytics/dashboard  (in parallel)
  The UI waits for BOTH phases. If dashboard?period=today hangs, the tab loads forever
  even when bundle already returned good data.

This script does NOT change the app — it only measures the same HTTP calls.

Usage (from project root or test/):
  python test/analytics_today_probe.py --email you@example.com --password secret
  python test/analytics_today_probe.py --email ... --password ... --compare-mtd
  python test/analytics_today_probe.py --period today
  python test/analytics_today_probe.py --period qtd --compare-mtd
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import date as dt
from typing import Any, Dict, List, Optional, Tuple

from breakdown_health import ensure_api_reachable

DEFAULT_BASE = os.environ.get("API_BASE_URL", "http://localhost:3000")
DEFAULT_EMAIL = os.environ.get("DASHBOARD_EMAIL", "asha24@gmail.com")
DEFAULT_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
API_TOP_N = 100
REQUEST_TIMEOUT = 300
LOGIN_TIMEOUT = 120

# Same set as useAnalytics.ts PERIODS_WITH_YOY_DASHBOARD
PERIODS_WITH_YOY_DASHBOARD = frozenset(
    {"mtd", "today", "yesterday", "qtd", "ytd", "last_6m"}
)


def _log(msg: str) -> None:
    print(msg, flush=True)


def _http(
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = REQUEST_TIMEOUT,
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
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {detail}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Timed out after {timeout}s: {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}") from exc


def _login(base: str, email: str, password: str) -> str:
    url = f"{base.rstrip('/')}/auth/login"
    body = {"email": email, "password": password}
    out = _http("POST", url, body=body, timeout=LOGIN_TIMEOUT)
    token = out.get("access_token")
    if not token:
        raise RuntimeError(f"Login failed: {out}")
    return token


def _get_with_heartbeat(
    url: str,
    *,
    token: str,
    timeout: int,
    label: str,
) -> Tuple[Dict[str, Any], float]:
    stop = threading.Event()

    def _pulse() -> None:
        t0 = time.perf_counter()
        while not stop.wait(5.0):
            _log(f"       ... {label} ({time.perf_counter() - t0:.0f}s)")

    threading.Thread(target=_pulse, daemon=True).start()
    t0 = time.perf_counter()
    try:
        return _http("GET", url, token=token, timeout=timeout), (time.perf_counter() - t0) * 1000
    finally:
        stop.set()


def _n(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _lakhs(v: float) -> str:
    return f"₹{v / 100_000:,.2f} L"


def _bundle_url(base: str, period: str) -> str:
    """Exact query string the React app uses (useAnalytics prefetchAnalyticsPage)."""
    return (
        f"{base.rstrip('/')}/analytics/bundle"
        f"?period={period}&top_n={API_TOP_N}"
        f"&include_departments=false&include_kpis=true"
    )


def _departments_url(base: str, period: str) -> str:
    return f"{base.rstrip('/')}/analytics/departments?period={period}&top_n={API_TOP_N}"


def _dashboard_url(base: str, period: str) -> str:
    return f"{base.rstrip('/')}/analytics/dashboard?period={period}"


def _summarize_bundle(data: Dict[str, Any]) -> Dict[str, Any]:
    kpis = data.get("kpis") or {}
    rev = _n((kpis.get("revenue") or {}).get("value"))
    return {
        "revenue": rev,
        "trend_pts": len(data.get("trend") or []),
        "categories": len(data.get("categories") or []),
        "branches": len(data.get("branches") or []),
        "bundle_errors": data.get("errors") or {},
        "timings_ms": data.get("timings_ms") or {},
    }


def _summarize_dashboard(data: Dict[str, Any]) -> Dict[str, Any]:
    summary = data.get("summary") or {}
    sales = _n(summary.get("mtd_sales", summary.get("current_sales")))
    return {
        "sales": sales,
        "bills": _n(summary.get("bills")),
        "qty": _n(summary.get("quantity")),
        "trend_pts": len(data.get("trend") or []),
        "yoy_pts": len(data.get("yoyTrend") or data.get("yoy_trend") or []),
        "date_range": data.get("date_range") or {},
    }


def _page_would_show(bundle_step: Dict[str, Any], dash: Optional[Dict[str, Any]]) -> bool:
    """Rough check: would buildAnalyticsPageData have non-empty charts?"""
    if _n(bundle_step.get("revenue")) > 0:
        return True
    if _n(bundle_step.get("trend_pts")) > 0 or _n(bundle_step.get("categories")) > 0:
        return True
    if dash:
        d = _summarize_dashboard(dash)
        if d["sales"] > 0 or d["trend_pts"] > 0:
            return True
    return False


def probe_analytics_tab(
    base: str,
    token: str,
    period: str,
    *,
    timeout: int = REQUEST_TIMEOUT,
) -> Dict[str, Any]:
    """
    Same sequence as prefetchAnalyticsPage in useAnalytics.ts.
    Returns timings + payloads summary + errors.
    """
    base = base.rstrip("/")
    out: Dict[str, Any] = {"period": period, "steps": {}, "errors": {}}
    needs_dash = period in PERIODS_WITH_YOY_DASHBOARD

    _log(f"\n{'=' * 72}")
    _log(f"  Period: {period.upper()}  (YoY dashboard: {'yes' if needs_dash else 'no'})")
    _log(f"{'=' * 72}")

    # Phase 1 — bundle (UI can paint after this if it didn't wait for phase 2)
    _log("\n  Phase 1 — /analytics/bundle (same as Analytics.tsx first paint path)")
    try:
        data, ms = _get_with_heartbeat(
            _bundle_url(base, period),
            token=token,
            timeout=timeout,
            label=f"bundle/{period}",
        )
        out["steps"]["bundle"] = {"ms": round(ms, 1), **_summarize_bundle(data)}
        _log(f"       OK bundle in {ms:.0f} ms | revenue={_lakhs(out['steps']['bundle']['revenue'])} "
             f"| trend={out['steps']['bundle']['trend_pts']} "
             f"| categories={out['steps']['bundle']['categories']} "
             f"| branches={out['steps']['bundle']['branches']}")
        if out["steps"]["bundle"].get("bundle_errors"):
            _log(f"       bundle partial errors: {out['steps']['bundle']['bundle_errors']}")
    except Exception as exc:
        out["errors"]["bundle"] = str(exc)
        _log(f"       FAIL bundle: {exc}")

    # Phase 2 — departments + dashboard (UI chartLoading stays true until this finishes)
    _log("\n  Phase 2 — departments + dashboard in parallel (this is what blocks the spinner)")
    dept_ms = dash_ms = 0.0
    dept_data: Optional[Dict[str, Any]] = None
    dash_data: Optional[Dict[str, Any]] = None

    def _fetch_dept() -> Tuple[str, float, Dict[str, Any]]:
        d, ms = _get_with_heartbeat(
            _departments_url(base, period),
            token=token,
            timeout=timeout,
            label=f"departments/{period}",
        )
        return "departments", ms, d

    def _fetch_dash() -> Tuple[str, float, Dict[str, Any]]:
        d, ms = _get_with_heartbeat(
            _dashboard_url(base, period),
            token=token,
            timeout=timeout,
            label=f"dashboard/{period}",
        )
        return "dashboard", ms, d

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs: List[Tuple[str, concurrent.futures.Future]] = [
            ("departments", pool.submit(_fetch_dept)),
        ]
        if needs_dash:
            jobs.append(("dashboard", pool.submit(_fetch_dash)))
        for label, fut in jobs:
            try:
                name, ms, data = fut.result()
                if name == "departments":
                    dept_ms, dept_data = ms, data
                    n = len(data.get("departments") or [])
                    out["steps"]["departments"] = {"ms": round(ms, 1), "rows": n}
                    _log(f"       OK departments in {ms:.0f} ms | rows={n}")
                else:
                    dash_ms, dash_data = ms, data
                    s = _summarize_dashboard(data)
                    out["steps"]["dashboard"] = {"ms": round(ms, 1), **s}
                    _log(f"       OK dashboard in {ms:.0f} ms | sales={_lakhs(s['sales'])} "
                         f"| yoy_pts={s['yoy_pts']}")
            except Exception as exc:
                out["errors"][label] = str(exc)
                _log(f"       FAIL {label}: {exc}")

    phase2_ms = max(dept_ms, dash_ms) if needs_dash else dept_ms
    out["phase2_wall_ms"] = round(phase2_ms, 1)
    out["total_wall_ms"] = round(
        out.get("steps", {}).get("bundle", {}).get("ms", 0) + phase2_ms,
        1,
    )
    out["ui_would_paint_after_bundle"] = "bundle" in out.get("steps", {})
    out["ui_spinner_until_phase2"] = needs_dash or True
    bundle_step = out.get("steps", {}).get("bundle") or {}
    out["page_has_data"] = _page_would_show(bundle_step, dash_data)

    # Verdict
    _log("\n  --- Verdict ---")
    if out["errors"]:
        _log(f"  FAIL: {list(out['errors'].keys())} — Analytics tab will error or spin.")
    elif not out.get("page_has_data"):
        _log("  WARN: All endpoints OK but revenue/charts empty — tab may look blank.")
    else:
        _log(f"  OK: Data present. Total ~{out['total_wall_ms']:.0f} ms "
             f"(phase2 wall {out['phase2_wall_ms']:.0f} ms).")

    if needs_dash and "dashboard" in out.get("steps", {}):
        b_ms = out["steps"]["bundle"]["ms"]
        d_ms = out["steps"]["dashboard"]["ms"]
        if d_ms > b_ms * 3 and d_ms > 30_000:
            _log(f"  LIKELY UI BOTTLENECK: dashboard ({d_ms:.0f} ms) >> bundle ({b_ms:.0f} ms).")
            _log("  The page keeps chartLoading=true until dashboard returns (see useAnalytics.ts).")

    yoy = out.get("steps", {}).get("dashboard", {}).get("yoy_pts", 0)
    if needs_dash and yoy == 0 and bundle_step.get("trend_pts", 0) <= 1:
        _log("  NOTE: dashboard returned yoy_pts=0 and bundle has ≤1 trend point — YoY chart may look empty in UI.")

    return out


def _compare_table(mtd: Dict[str, Any], other: Dict[str, Any], other_label: str) -> None:
    _log(f"\n{'#' * 72}")
    _log(f"  MTD vs {other_label.upper()} — what the Analytics page waits for")
    _log(f"{'#' * 72}")

    def _row(label: str, key: str) -> None:
        m = mtd.get("steps", {}).get(key, {})
        o = other.get("steps", {}).get(key, {})
        m_ms = m.get("ms", "—")
        o_ms = o.get("ms", "—")
        _log(f"  {label:<14}  MTD: {m_ms!s:>10} ms   {other_label}: {o_ms!s:>10} ms")

    _row("bundle", "bundle")
    _row("departments", "departments")
    _row("dashboard", "dashboard")
    _log(f"  {'phase2 wall':<14}  MTD: {mtd.get('phase2_wall_ms', '—'):>10}    "
         f"{other_label}: {other.get('phase2_wall_ms', '—'):>10}")
    _log(f"  {'total':<14}  MTD: {mtd.get('total_wall_ms', '—'):>10}    "
         f"{other_label}: {other.get('total_wall_ms', '—'):>10}")

    if other.get("errors"):
        _log(f"\n  {other_label} errors: {other['errors']}")
        _log(f"  → Fix these before the {other_label} tab can behave like MTD.")

    m_b = mtd.get("steps", {}).get("bundle", {}).get("revenue", 0)
    o_b = other.get("steps", {}).get("bundle", {}).get("revenue", 0)
    _log(f"\n  bundle revenue   MTD {_lakhs(m_b)}   {other_label} {_lakhs(o_b)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Analytics page API path (bundle + departments + dashboard)",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument(
        "--period",
        default="today",
        help="Period to probe (default: today)",
    )
    parser.add_argument(
        "--compare-mtd",
        action="store_true",
        help="Also run MTD and print side-by-side timings",
    )
    parser.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT)
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    password = args.password or input(f"Password for {args.email}: ").strip()

    _log(f"Analytics tab probe | API {args.base_url} | calendar today {dt.today().isoformat()}")
    _log("Mirrors: src/hooks/useAnalytics.ts → prefetchAnalyticsPage()\n")

    ensure_api_reachable(
        args.base_url,
        http_get=_http,
        log=_log,
        api_start_hint="\n  Start backend: cd backend && python main.py",
    )

    _log(f"Logging in as {args.email}...")
    token = _login(args.base_url, args.email, password)
    _log("Login OK.\n")

    report: Dict[str, Any] = {"fetched_at": dt.today().isoformat(), "runs": {}}

    if args.compare_mtd:
        _log("Compare order: TODAY first (fast), then MTD (slow on cold SQL cache).\n")
        report["runs"][args.period] = probe_analytics_tab(
            args.base_url, token, args.period, timeout=args.timeout
        )
        _log(
            "\n  MTD bundle can take 1–4 min on cold cache; "
            "reload Analytics (MTD tab) first for instant MTD.\n"
        )
        report["runs"]["mtd"] = probe_analytics_tab(
            args.base_url, token, "mtd", timeout=args.timeout
        )
        _compare_table(report["runs"]["mtd"], report["runs"][args.period], args.period)
    else:
        report["runs"][args.period] = probe_analytics_tab(
            args.base_url, token, args.period, timeout=args.timeout
        )

    if args.json:
        print(json.dumps(report, indent=2, default=str))

    return 0 if not any(r.get("errors") for r in report["runs"].values()) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
