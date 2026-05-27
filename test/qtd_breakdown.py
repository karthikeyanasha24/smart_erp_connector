#!/usr/bin/env python3
"""
QTD sales breakdown — list ALL rows for:
  - Period-wise (monthly buckets for QTD — fast SQL, ~3 rows)
  - Branch-wise
  - Category-wise
  - Department-wise

Uses the running API (backend on :3000).

DEFAULT (bundle): /analytics/bundle — branches, trend, categories, kpis (includes QTD qty)
  then departments in a 2nd call. ~2–10s when server cache is warm (same as mtd_breakdown).

  --split: legacy 4+ parallel client HTTP calls (faster cold cache vs bundle semaphore).
  --dashboard: single heavy /analytics/dashboard (YoY period-wise LY column; slow).

Usage:
  python test/qtd_breakdown.py --email you@example.com --password secret
  python test/qtd_breakdown.py --no-departments
  python test/qtd_breakdown.py --split --sequential
  python test/qtd_breakdown.py --timeout 300
  python test/qtd_breakdown.py --wait-warmup   # longer login retries during SQL warmup
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from breakdown_fetch import fetch_fast_bundle
from breakdown_health import ensure_api_reachable

DEFAULT_BASE = os.environ.get("API_BASE_URL", "http://localhost:3000")
DEFAULT_EMAIL = os.environ.get("DASHBOARD_EMAIL", "asha24@gmail.com")
DEFAULT_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
PERIOD = "qtd"
API_TOP_N_MAX = 100
LOGIN_TIMEOUT = 120
LOGIN_MAX_WAIT_S = 600
LOGIN_MAX_WAIT_WARMUP_S = 1200
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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {detail}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Request timed out after {timeout}s: {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}") from exc


def _api_start_hint(base: str) -> str:
    return (
        f"\n  API not reachable at {base.rstrip('/')}\n"
        "  Start the backend in another terminal:\n"
        "    cd backend\n"
        "    npm run dev\n"
        "  Wait for 'Cache warmup complete', then re-run this script."
    )


def _http_with_heartbeat(
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int,
    label: str,
) -> Dict[str, Any]:
    stop = threading.Event()

    def _pulse() -> None:
        t0 = time.perf_counter()
        while not stop.wait(5.0):
            _log(f"       ... {label} ({time.perf_counter() - t0:.0f}s)")

    pulse = threading.Thread(target=_pulse, daemon=True)
    pulse.start()
    try:
        return _http(method, url, token=token, body=body, timeout=timeout)
    finally:
        stop.set()


def _login(
    base: str,
    email: str,
    password: str,
    timeout: int,
    *,
    max_wait: float = LOGIN_MAX_WAIT_S,
) -> str:
    """Retry on timeout while the server is busy (warmup / SQL)."""
    url = f"{base.rstrip('/')}/auth/login"
    body = {"email": email, "password": password}
    deadline = time.monotonic() + max_wait
    attempt = 0
    last_err: Optional[RuntimeError] = None

    while time.monotonic() < deadline:
        attempt += 1
        remaining = int(deadline - time.monotonic())
        req_timeout = min(timeout, max(30, remaining))
        if attempt > 1:
            _log(f"  Login retry {attempt} (timeout {req_timeout}s)...")
        try:
            out = _http_with_heartbeat(
                "POST", url, body=body, timeout=req_timeout, label="logging in"
            )
            token = out.get("access_token")
            if not token:
                raise RuntimeError(f"Login failed: {out}")
            return token
        except RuntimeError as exc:
            last_err = exc
            if "timed out" not in str(exc).lower():
                raise
            if time.monotonic() >= deadline:
                break
            _log("  Login timed out — server likely busy, retrying in 5s...")
            time.sleep(5)

    raise RuntimeError(
        f"Login did not succeed within {int(max_wait)}s. Last error: {last_err}"
    )


def _run_jobs(
    jobs: Dict[str, str],
    token: str,
    timeout: int,
    *,
    sequential: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, float], Dict[str, str]]:
    results: Dict[str, Any] = {}
    timings: Dict[str, float] = {}
    errors: Dict[str, str] = {}

    def _fetch_one(name: str, url: str) -> Tuple[str, Dict[str, Any], float]:
        t0 = time.perf_counter()
        data = _http("GET", url, token=token, timeout=timeout)
        return name, data, (time.perf_counter() - t0) * 1000

    items = list(jobs.items())
    if sequential:
        for i, (name, url) in enumerate(items, 1):
            _log(f"  [{i}/{len(items)}] {name}... (timeout {timeout}s)")
            try:
                n, data, ms = _fetch_one(name, url)
                results[n] = data
                timings[n] = round(ms, 1)
                _log(f"       OK {n} in {ms:.0f} ms")
            except Exception as exc:
                errors[name] = str(exc)
                _log(f"       FAIL {name}: {exc}")
    else:
        _log(f"  Starting {len(items)} requests in parallel (timeout {timeout}s each)...")
        for name in jobs:
            _log(f"       - queued: {name}")
        with ThreadPoolExecutor(max_workers=len(items)) as pool:
            futs = {pool.submit(_fetch_one, n, u): n for n, u in items}
            for fut in as_completed(futs):
                key = futs[fut]
                try:
                    name, data, ms = fut.result()
                    results[name] = data
                    timings[name] = round(ms, 1)
                    _log(f"       OK {name} in {ms:.0f} ms")
                except Exception as exc:
                    errors[key] = str(exc)
                    _log(f"       FAIL {key}: {exc}")

    return results, timings, errors


def _split_jobs(base: str, top_n: int, with_departments: bool) -> Dict[str, str]:
    base = base.rstrip("/")
    n = min(max(top_n, 1), API_TOP_N_MAX)
    jobs = {
        "branches": f"{base}/analytics/branches?period={PERIOD}",
        "trend": f"{base}/analytics/trend?period={PERIOD}",
        "categories": f"{base}/analytics/categories?period={PERIOD}&top_n={n}",
        "kpis": f"{base}/analytics/kpis?period={PERIOD}",
    }
    if with_departments:
        jobs["departments"] = f"{base}/analytics/departments?period={PERIOD}&top_n={n}"
    return jobs


def _http_get_with_heartbeat(
    url: str,
    *,
    token: str,
    timeout: int,
    label: str,
) -> Dict[str, Any]:
    stop = threading.Event()

    def _pulse() -> None:
        t0 = time.perf_counter()
        while not stop.wait(5.0):
            _log(f"       ... {label} ({time.perf_counter() - t0:.0f}s)")

    pulse = threading.Thread(target=_pulse, daemon=True)
    pulse.start()
    try:
        return _http("GET", url, token=token, timeout=timeout)
    finally:
        stop.set()


def _fetch_qtd_bundle(
    base: str,
    token: str,
    *,
    use_bundle: bool = True,
    use_dashboard: bool = False,
    with_departments: bool = True,
    include_kpis: bool = False,
    top_n: int = API_TOP_N_MAX,
    timeout: int = BUNDLE_TIMEOUT,
    sequential: bool = False,
) -> Tuple[Dict[str, Any], str]:
    base = base.rstrip("/")

    if use_dashboard:
        jobs = {"dashboard": f"{base}/analytics/dashboard?period={PERIOD}"}
        if with_departments:
            n = min(max(top_n, 1), API_TOP_N_MAX)
            jobs["departments"] = f"{base}/analytics/departments?period={PERIOD}&top_n={n}"
        mode = "dashboard (single heavy call)"
        results, timings, errors = _run_jobs(jobs, token, timeout, sequential=sequential)
        if "dashboard" not in results:
            raise RuntimeError(f"dashboard fetch failed: {errors}")
        if errors:
            results["_errors"] = errors
        results["_timings_ms"] = timings
        return results, mode

    if use_bundle:
        return fetch_fast_bundle(
            PERIOD,
            base,
            token,
            log=_log,
            http_get=_http_get_with_heartbeat,
            top_n=top_n,
            timeout=timeout,
            with_departments=with_departments,
            include_kpis=include_kpis,
        )

    jobs = _split_jobs(base, top_n, with_departments)
    mode = "split (sequential)" if sequential else "split (parallel)"
    results, timings, errors = _run_jobs(jobs, token, timeout, sequential=sequential)
    missing = {"branches", "trend", "categories"} - set(results.keys())
    if missing:
        raise RuntimeError(f"Required fetches failed: {missing}. Errors: {errors}")
    if errors:
        results["_errors"] = errors
    results["_timings_ms"] = timings
    return results, mode


def _n(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def lakhs(v: float) -> str:
    return f"₹{v / 100_000:,.2f} L"


def _day_label(iso_date: str) -> str:
    try:
        d = datetime.fromisoformat(iso_date[:10])
        return d.strftime("%d-%b")
    except ValueError:
        return iso_date[:10]


def _trend_row_label(t: Dict[str, Any]) -> str:
    if t.get("label"):
        return str(t["label"])
    d = str(t.get("date", ""))
    if len(d) >= 7 and d[4] == "-":
        try:
            return datetime.strptime(d[:7], "%Y-%m").strftime("%b %Y")
        except ValueError:
            pass
    return _day_label(d)


def build_report(raw: Dict[str, Any]) -> Dict[str, Any]:
    dash = raw.get("dashboard") or {}
    kpis = raw.get("kpis") or {}
    api_trend = (raw.get("trend") or {}).get("trend") or []

    summary = dash.get("summary") or {}
    if not summary and kpis:
        rev = kpis.get("revenue") or {}
        txn = kpis.get("transactions") or {}
        qty = kpis.get("quantity") or {}
        summary = {
            "mtd_sales": rev.get("value"),
            "ly_sales": rev.get("prior"),
            "sales_growth_pct": rev.get("growth"),
            "bills": txn.get("value"),
            "quantity": qty.get("value") or 0,
        }

    trend_pts = dash.get("trend") or []
    dash_cats = dash.get("categories") or []
    dash_branches = dash.get("branches") or []

    api_branches = (raw.get("branches") or {}).get("branches") or []
    api_categories = (raw.get("categories") or {}).get("categories") or []
    api_departments = (raw.get("departments") or {}).get("departments") or []

    branches = api_branches if api_branches else [
        {"branch": b.get("name"), "revenue": b.get("revenue"), "transactions": None}
        for b in dash_branches
    ]
    categories = api_categories if api_categories else [
        {
            "category": c.get("name"),
            "revenue": c.get("revenue"),
            "transactions": None,
            "percentage": c.get("percentage"),
        }
        for c in dash_cats
    ]

    if trend_pts:
        daywise = [
            {
                "date": p.get("date"),
                "label": p.get("label"),
                "sales": _n(p.get("current")),
                "sales_lakhs": round(_n(p.get("current")) / 100_000, 4),
                "last_year_sales": _n(p.get("prior")),
                "bills": int(_n(p.get("bills"))),
                "quantity": _n(p.get("quantity")),
            }
            for p in trend_pts
        ]
    else:
        daywise = [
            {
                "date": str(t.get("date", ""))[:10],
                "label": _trend_row_label(t),
                "sales": _n(t.get("revenue")),
                "sales_lakhs": round(_n(t.get("revenue")) / 100_000, 4),
                "last_year_sales": 0,
                "bills": int(_n(t.get("transactions"))),
                "quantity": _n(t.get("quantity")),
            }
            for t in api_trend
        ]

    if not summary.get("mtd_sales") and daywise:
        summary = {
            **summary,
            "mtd_sales": sum(d["sales"] for d in daywise),
            "bills": summary.get("bills") or sum(d["bills"] for d in daywise),
            "quantity": summary.get("quantity") or sum(d["quantity"] for d in daywise),
        }
    elif summary.get("quantity") in (None, 0) and daywise:
        summary = {**summary, "quantity": sum(d["quantity"] for d in daywise)}

    branch_rows = sorted(
        [
            {
                "branch": str(b.get("branch", b.get("name", ""))),
                "sales": _n(b.get("revenue")),
                "sales_lakhs": round(_n(b.get("revenue")) / 100_000, 4),
                "transactions": int(_n(b.get("transactions"))) if b.get("transactions") is not None else None,
            }
            for b in branches
        ],
        key=lambda x: -x["sales"],
    )

    category_rows = sorted(
        [
            {
                "category": str(c.get("category", c.get("name", ""))),
                "sales": _n(c.get("revenue")),
                "sales_lakhs": round(_n(c.get("revenue")) / 100_000, 4),
                "transactions": int(_n(c.get("transactions"))) if c.get("transactions") is not None else None,
                "share_pct": _n(c.get("percentage")),
            }
            for c in categories
        ],
        key=lambda x: -x["sales"],
    )

    department_rows = sorted(
        [
            {
                "department": str(d.get("department", "")),
                "sales": _n(d.get("revenue")),
                "sales_lakhs": round(_n(d.get("revenue")) / 100_000, 4),
                "transactions": int(_n(d.get("transactions"))),
            }
            for d in api_departments
        ],
        key=lambda x: -x["sales"],
    )

    total_sales = _n(summary.get("mtd_sales"))
    period_label = dash.get("period_label") or "Quarter-to-Date"
    date_range = dash.get("date_range")
    if not date_range and daywise:
        date_range = {"start": daywise[0]["date"], "end": daywise[-1]["date"]}

    monthly_trend = bool(
        api_trend
        and not trend_pts
        and len(str(api_trend[0].get("date", ""))) <= 7
    )

    return {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "period": PERIOD,
        "period_label": period_label,
        "date_range": date_range,
        "monthly_trend": monthly_trend,
        "summary": {
            "total_sales": total_sales,
            "total_sales_lakhs": round(total_sales / 100_000, 4),
            "bills": int(_n(summary.get("bills"))),
            "quantity": _n(summary.get("quantity")),
            "ly_sales": _n(summary.get("ly_sales")),
            "sales_growth_pct": summary.get("sales_growth_pct"),
        },
        "daywise": daywise,
        "branch_wise": branch_rows,
        "category_wise": category_rows,
        "department_wise": department_rows,
        "counts": {
            "days": len(daywise),
            "branches": len(branch_rows),
            "categories": len(category_rows),
            "departments": len(department_rows),
        },
        "_timings_ms": raw.get("_timings_ms"),
        "_errors": raw.get("_errors"),
        "_mode": raw.get("_mode"),
    }


def _print_table(title: str, headers: List[str], rows: List[List[str]]) -> None:
    print(f"\n{'=' * 78}")
    print(f"  {title} ({len(rows)} rows)")
    print("=" * 78)
    if not rows:
        print("  (no data)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("-" * (sum(widths) + 2 * (len(headers) - 1)))
    for row in rows:
        print(fmt.format(*row))


def print_report(r: Dict[str, Any]) -> None:
    s = r["summary"]
    dr = r.get("date_range") or {}
    trend_title = "MONTH-WISE SALES" if r.get("monthly_trend") else "DAY-WISE SALES"
    print()
    print("=" * 78)
    print("  QTD SALES BREAKDOWN (Quarter-to-date)")
    print(f"  {r.get('period_label', 'QTD')}  |  {dr.get('start', '?')} to {dr.get('end', '?')}")
    print(f"  Fetched: {r['fetched_at']}")
    if r.get("_timings_ms"):
        print(f"  API timings (ms): {r['_timings_ms']}")
    if r.get("_mode"):
        print(f"  Mode: {r['_mode']}")
    print("=" * 78)
    print(f"\n  TOTAL QTD SALES: {lakhs(s['total_sales'])}  |  Bills: {s['bills']:,}  |  Qty: {s['quantity']:,.0f}")
    if s["total_sales"] > 0 and s["quantity"] == 0:
        print(
            "  ⚠ Qty is 0 — restart backend so KPI+trend return quantity, or use --dashboard."
        )
    if s.get("sales_growth_pct") is not None:
        print(f"  vs last year (same dates): {s['sales_growth_pct']:+.2f}%  (LY {lakhs(s['ly_sales'])})")

    _print_table(
        trend_title,
        ["#", "Period", "Label", "Sales", "Bills", "Qty", "LY Sales"],
        [
            [
                str(i + 1),
                str(d["date"]),
                str(d["label"]),
                lakhs(d["sales"]),
                str(d["bills"]),
                f"{d['quantity']:,.0f}",
                lakhs(d["last_year_sales"]) if d["last_year_sales"] else "—",
            ]
            for i, d in enumerate(r["daywise"])
        ],
    )

    _print_table(
        "BRANCH-WISE SALES (all branches)",
        ["#", "Branch", "Sales", "Bills"],
        [
            [
                str(i + 1),
                row["branch"],
                lakhs(row["sales"]),
                str(row["transactions"]) if row["transactions"] is not None else "—",
            ]
            for i, row in enumerate(r["branch_wise"])
        ],
    )

    _print_table(
        "CATEGORY-WISE SALES (all returned)",
        ["#", "Category", "Sales", "Share %", "Bills"],
        [
            [
                str(i + 1),
                row["category"],
                lakhs(row["sales"]),
                f"{row['share_pct']:.2f}" if row.get("share_pct") else "—",
                str(row["transactions"]) if row["transactions"] is not None else "—",
            ]
            for i, row in enumerate(r["category_wise"])
        ],
    )

    if r["department_wise"]:
        _print_table(
            "DEPARTMENT-WISE SALES (all returned)",
            ["#", "Department", "Sales", "Bills"],
            [
                [
                    str(i + 1),
                    row["department"],
                    lakhs(row["sales"]),
                    str(row["transactions"]),
                ]
                for i, row in enumerate(r["department_wise"])
            ],
        )
    else:
        print(f"\n{'=' * 78}")
        print("  DEPARTMENT-WISE — skipped (re-run without --no-departments)")
        print("=" * 78)

    c = r["counts"]
    period_word = "months" if r.get("monthly_trend") else "days"
    print(f"\n  Totals listed: {c['days']} {period_word} | {c['branches']} branches | "
          f"{c['categories']} categories | {c['departments']} departments")
    if r.get("_errors"):
        print(f"  Warnings: {r['_errors']}")
    print()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="QTD sales: period / branch / category / department lists")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--split", action="store_true",
                        help="Use legacy split parallel client calls instead of /analytics/bundle")
    parser.add_argument("--dashboard", action="store_true",
                        help="Use single /analytics/dashboard (slow; may timeout)")
    parser.add_argument("--sequential", action="store_true",
                        help="With --split: one API at a time (gentler on SQL Server)")
    parser.add_argument("--timeout", type=int, default=BUNDLE_TIMEOUT,
                        help=f"Per-request timeout in seconds (default {BUNDLE_TIMEOUT})")
    parser.add_argument("--login-timeout", type=int, default=LOGIN_TIMEOUT,
                        help=f"Per-attempt login timeout in seconds (default {LOGIN_TIMEOUT})")
    parser.add_argument("--wait-warmup", action="store_true",
                        help="Skip /health blocking; retry login up to 20 min during cache warmup")
    parser.add_argument("--no-departments", action="store_true",
                        help="Skip department breakdown")
    parser.add_argument("--with-kpis", action="store_true",
                        help="Include KPIs in bundle (slower)")
    parser.add_argument("--top-n", type=int, default=API_TOP_N_MAX,
                        help=f"Category/department top_n (max {API_TOP_N_MAX})")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument("-o", "--output", help="Write JSON report to file")
    args = parser.parse_args()

    password = args.password or input(f"Password for {args.email}: ").strip()
    t0 = time.perf_counter()

    _log(f"Checking API at {args.base_url}...")
    health = ensure_api_reachable(
        args.base_url,
        http_get=_http,
        log=_log,
        api_start_hint=_api_start_hint(args.base_url),
        wait_warmup=args.wait_warmup,
    )
    mssql = (health.get("mssql") or {}).get("connected")
    _log(f"  Proceeding | last /health hint: status={health.get('status')} | SQL Server: {mssql}")

    _log(f"Logging in as {args.email}...")
    login_max = LOGIN_MAX_WAIT_WARMUP_S if args.wait_warmup else LOGIN_MAX_WAIT_S
    token = _login(
        args.base_url, args.email, password, args.login_timeout, max_wait=login_max
    )

    raw, mode = _fetch_qtd_bundle(
        args.base_url,
        token,
        use_bundle=not args.split and not args.dashboard,
        use_dashboard=args.dashboard,
        with_departments=not args.no_departments,
        include_kpis=args.with_kpis,
        top_n=args.top_n,
        timeout=args.timeout,
        sequential=args.sequential,
    )
    raw["_mode"] = mode
    _log(f"Done fetching [{mode}]. Building report...")
    report = build_report(raw)
    report["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Wrote {args.output}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif not args.output:
        print_report(report)
    else:
        print_report(report)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except urllib.error.URLError as exc:
        print(f"Cannot reach API: {exc.reason}", file=sys.stderr)
        print(_api_start_hint(DEFAULT_BASE), file=sys.stderr)
        raise SystemExit(1)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
