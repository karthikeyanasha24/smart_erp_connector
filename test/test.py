#!/usr/bin/env python3
"""
Fetch LIVE dashboard data (not demo/mock) — KPIs, charts, insights, transactions.

Why a run can take ~60s (your case):
  - Each /analytics/dashboard runs 5 heavy SQL queries on cache MISS (remote SQL Server).
  - The script was calling dashboard×2 + kpis + transactions in parallel → 12+ queries at once.
  - Total time = slowest request (~60s), not sum — but parallel load makes each query slower.

Fast path (default --fast):
  - One call: GET /analytics/dashboard?period=mtd (covers KPIs + all charts).
  - Second run with warm server cache: usually under 200ms.

Usage:
  python test.py --email you@example.com --password secret
  python test.py --full               # slower: today + kpis + transactions
  python test.py --timings            # show ms per endpoint

If it looks stuck after the password prompt, the API is still loading (cache warmup).
You will see "... logging in (5s)" / "... dashboard_mtd (10s)" progress lines.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

DEFAULT_BASE = os.environ.get("API_BASE_URL", "http://localhost:3000")
DEFAULT_EMAIL = os.environ.get("DASHBOARD_EMAIL", "asha24@gmail.com")
DEFAULT_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
LOGIN_TIMEOUT = 300
LOGIN_MAX_WAIT_S = 600


def _log(msg: str) -> None:
    print(msg, flush=True)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

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
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {detail}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Request timed out after {timeout}s: {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}") from exc


def _http_with_heartbeat(
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 300,
    label: str,
) -> Dict[str, Any]:
    stop = threading.Event()

    def _pulse() -> None:
        t0 = time.perf_counter()
        while not stop.wait(5.0):
            _log(f"  ... {label} ({time.perf_counter() - t0:.0f}s)")

    pulse = threading.Thread(target=_pulse, daemon=True)
    pulse.start()
    try:
        return _http(method, url, token=token, body=body, timeout=timeout)
    finally:
        stop.set()


def _login(base: str, email: str, password: str, *, timeout: int = LOGIN_TIMEOUT) -> str:
    url = f"{base.rstrip('/')}/auth/login"
    body = {"email": email, "password": password}
    deadline = time.monotonic() + LOGIN_MAX_WAIT_S
    attempt = 0
    last_err: Optional[RuntimeError] = None

    while time.monotonic() < deadline:
        attempt += 1
        remaining = int(deadline - time.monotonic())
        req_timeout = min(timeout, max(30, remaining))
        if attempt > 1:
            _log(f"Login retry {attempt} (timeout {req_timeout}s)...")
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
            _log("Login timed out — server may be warming cache; retrying in 5s...")
            time.sleep(5)

    raise RuntimeError(
        f"Login failed after {LOGIN_MAX_WAIT_S}s. "
        "Wait for 'Cache warmup complete' in the backend terminal, then re-run. "
        f"Last error: {last_err}"
    )


def _fetch_api_parallel(
    base: str,
    token: str,
    *,
    fast: bool = True,
    with_today: bool = False,
    with_kpis: bool = False,
    with_transactions: bool = False,
) -> Dict[str, Any]:
    """
    Parallel HTTP against the running API.

    fast=True  → only dashboard/mtd (1 endpoint, ~5 SQL queries on cold cache).
    fast=False → also today dashboard, kpis, transactions (12+ SQL queries).
    """
    base = base.rstrip("/")
    jobs: Dict[str, str] = {
        "dashboard_mtd": f"{base}/analytics/dashboard?period=mtd",
    }
    if not fast:
        with_today = True
        with_kpis = True
        with_transactions = True
    if with_today:
        jobs["dashboard_today"] = f"{base}/analytics/dashboard?period=today"
    if with_kpis:
        jobs["kpis_mtd"] = f"{base}/analytics/kpis?period=mtd"
    if with_transactions:
        jobs["transactions"] = f"{base}/analytics/transactions?period=mtd&page=1&page_size=80"

    results: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    timings: Dict[str, float] = {}

    def _one(name: str, url: str) -> Tuple[str, Dict[str, Any], float]:
        t0 = time.perf_counter()
        data = _http_with_heartbeat(
            "GET", url, token=token, timeout=300, label=name
        )
        return name, data, (time.perf_counter() - t0) * 1000

    _log(f"Fetching {len(jobs)} endpoint(s) from {base} (cold cache can take 1–10+ min)...")
    with ThreadPoolExecutor(max_workers=max(len(jobs), 1)) as pool:
        futs = {pool.submit(_one, n, u): n for n, u in jobs.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                n, data, ms = fut.result()
                results[n] = data
                timings[n] = round(ms, 1)
                _log(f"  OK {n} in {ms:.0f} ms")
            except Exception as exc:
                errors[name] = str(exc)
                _log(f"  FAIL {name}: {exc}")

    if "dashboard_mtd" not in results:
        raise RuntimeError(f"dashboard/mtd failed — {errors}")
    if errors:
        results["_warnings"] = errors
    results["_timings_ms"] = timings
    return results


# ─── Direct (in-process) fetch ────────────────────────────────────────────────

async def _fetch_direct(*, with_transactions: bool = True) -> Dict[str, Any]:
    os.chdir(BACKEND_DIR)
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    os.environ.setdefault("PYTHONUTF8", "1")

    from src.db.mssql import init_mssql, close_mssql
    from src.analytics.dashboard import get_dashboard
    from src.analytics.kpi import get_home_kpis

    await init_mssql()
    out: Dict[str, Any] = {}
    try:
        tasks = [
            get_dashboard("mtd"),
            get_dashboard("today"),
            get_home_kpis("mtd"),
        ]
        if with_transactions:
            from src.analytics.transactions import get_transactions
            tasks.append(get_transactions("mtd", page=1, page_size=80))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        names = ["dashboard_mtd", "dashboard_today", "kpis_mtd"]
        if with_transactions:
            names.append("transactions")

        for name, res in zip(names, results):
            if isinstance(res, Exception):
                out.setdefault("_warnings", {})[name] = str(res)
                continue
            if name == "kpis_mtd":
                out[name] = {"success": True, "period": "mtd", **res}
            elif name.startswith("dashboard"):
                out[name] = {"success": True, **res}
            else:
                out[name] = {"success": True, **res}

        if "dashboard_mtd" not in out:
            raise RuntimeError(f"Dashboard MTD failed: {out.get('_warnings')}")
    finally:
        await close_mssql()
    return out


# ─── Formatting ───────────────────────────────────────────────────────────────

def _n(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def lakhs(v: float) -> str:
    return f"₹{v / 100_000:,.2f} L"


def rupees(v: float) -> str:
    if v >= 100_000:
        return f"₹{v / 1000:,.1f}K"
    return f"₹{v:,.0f}"


def compact(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))


def growth_str(pct: Optional[float]) -> str:
    if pct is None:
        return "—"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def kpi_metric(block: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not block:
        return {"value": None, "prior": None, "growth_pct": None}
    return {
        "value": _n(block.get("value")),
        "prior": _n(block.get("prior")),
        "growth_pct": block.get("growth"),
    }


def build_insights(
    summary: Dict[str, Any],
    branches: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    insights: List[Dict[str, str]] = []
    g = summary.get("sales_growth_pct")
    sales = _n(summary.get("mtd_sales"))
    ly = _n(summary.get("ly_sales"))
    bills = int(_n(summary.get("bills")))

    if g is not None:
        if g > 5:
            insights.append({
                "type": "trend",
                "impact": "high",
                "title": f"Revenue trending +{g:.1f}% above last year",
                "desc": f"MTD gross sales {lakhs(sales)} vs LY {lakhs(ly)}. Momentum is strong.",
            })
        elif g < 0:
            insights.append({
                "type": "anomaly",
                "impact": "high",
                "title": f"Revenue down {abs(g):.1f}% vs last year",
                "desc": f"MTD {lakhs(sales)} is below LY {lakhs(ly)}. Review branch and category performance.",
            })
        else:
            insights.append({
                "type": "trend",
                "impact": "medium",
                "title": "Revenue tracking in line with last year",
                "desc": f"MTD sales {lakhs(sales)} are close to last year's pace.",
            })

    if branches:
        top = branches[0]
        insights.append({
            "type": "recommendation",
            "impact": "medium",
            "title": f"{top.get('name', '')} leads with {top.get('percentage', 0):.1f}% revenue share",
            "desc": f"Top branch at {lakhs(_n(top.get('revenue')))}.",
        })

    if categories:
        top = categories[0]
        insights.append({
            "type": "trend",
            "impact": "medium",
            "title": f"{top.get('name', '')} drives {top.get('percentage', 0):.1f}% of category mix",
            "desc": f"Category revenue {lakhs(_n(top.get('revenue')))}.",
        })

    if bills > 0 and sales > 0:
        aov = sales / bills
        insights.append({
            "type": "recommendation",
            "impact": "low",
            "title": f"Avg bill value at {rupees(aov)} across {compact(bills)} bills",
            "desc": "Bundle promotions could lift average transaction size.",
        })

    return insights


def assemble_report(raw: Dict[str, Any], elapsed_ms: float, mode: str) -> Dict[str, Any]:
    mtd = raw.get("dashboard_mtd") or {}
    today = raw.get("dashboard_today") or {}
    kpis = raw.get("kpis_mtd") or {}
    txns = raw.get("transactions") or {}
    timings = raw.get("_timings_ms") or {}

    s = mtd.get("summary") or {}
    t_s = today.get("summary") or {}
    trend = mtd.get("trend") or []
    categories = mtd.get("categories") or []
    branches = mtd.get("branches") or []
    records = txns.get("transactions") or []

    sales = _n(s.get("mtd_sales"))
    bills = int(_n(s.get("bills")))
    qty = int(_n(s.get("quantity")))
    customers = s.get("customers")
    aov = sales / bills if bills > 0 else 0.0

    rev_kpi = kpi_metric(kpis.get("revenue"))
    txn_kpi = kpi_metric(kpis.get("transactions"))
    aov_kpi = kpi_metric(kpis.get("avg_order_value"))
    cust_kpi = kpi_metric(kpis.get("customers"))

    revenue_trend = [
        {
            "label": p.get("label"),
            "revenue": _n(p.get("current")),
            "last_year": _n(p.get("prior")),
            "bills": int(_n(p.get("bills"))),
            "quantity": _n(p.get("quantity")),
        }
        for p in trend
    ]

    profit_vs_target = [
        {
            "label": p.get("label"),
            "profit": _n(p.get("current")),
            "target": _n(p.get("prior")),
        }
        for p in trend
    ]

    return {
        "source": "live_api" if mode == "api" else "live_direct",
        "elapsed_ms": round(elapsed_ms, 1),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "welcome": {
            "period_label": mtd.get("period_label"),
            "date_range": mtd.get("date_range"),
        },
        "kpi_strip": {
            "total_revenue": {
                "display": lakhs(sales),
                "raw": sales,
                "growth_pct": s.get("sales_growth_pct"),
                "growth_label": "vs same period last year",
                "period_growth_pct": rev_kpi["growth_pct"],
            },
            "transactions": {
                "display": compact(bills),
                "raw": bills,
                "growth_pct": txn_kpi["growth_pct"],
                "growth_label": "vs prior period",
            },
            "avg_order_value": {
                "display": rupees(aov),
                "raw": aov,
                "growth_pct": aov_kpi["growth_pct"],
            },
            "yoy_growth": {
                "display": growth_str(s.get("sales_growth_pct")),
                "raw": s.get("sales_growth_pct"),
                "note": "YoY from dashboard (not QoQ)",
            },
            "qty_sold": {"display": compact(qty), "raw": qty},
            "customers": {
                "display": compact(_n(customers)) if customers is not None else "—",
                "raw": customers,
                "growth_pct": cust_kpi["growth_pct"],
            },
            "todays_sales": {
                "display": lakhs(_n(t_s.get("mtd_sales"))),
                "bills": int(_n(t_s.get("bills"))),
            },
            "profit_margin": {
                "display": None,
                "note": "Not available in ERP analytics API — UI mock only",
            },
        },
        "performance": {
            "revenue_trend": revenue_trend,
            "category_mix": categories,
            "daily_transactions": [
                {"label": p.get("label"), "bills": int(_n(p.get("bills")))}
                for p in trend[-30:]
            ],
            "branch_comparison": [
                {"branch": b.get("name"), "revenue": _n(b.get("revenue")), "pct": b.get("percentage")}
                for b in branches
            ],
            "qty_vs_transactions": [
                {"label": p.get("label"), "qty": _n(p.get("quantity")), "bills": int(_n(p.get("bills")))}
                for p in trend[-15:]
            ],
            "profit_vs_target": profit_vs_target,
            "profit_vs_target_note": "target = last year (prior); profit = current revenue",
        },
        "ai_insights": build_insights(s, branches, categories),
        "recent_transactions": {
            "total_count": txns.get("total_count", len(records)),
            "page": txns.get("page", 1),
            "total_pages": txns.get("total_pages"),
            "records": records,
        },
        "checksum": mtd.get("checksum"),
        "_warnings": raw.get("_warnings"),
        "_timings_ms": timings,
    }


def print_report(r: Dict[str, Any]) -> None:
    k = r["kpi_strip"]
    p = r["performance"]

    print()
    print("=" * 72)
    print(f"  LIVE DASHBOARD DATA  ({r['source']})  —  {r['elapsed_ms']} ms")
    print(f"  {r['fetched_at']}")
    print("=" * 72)

    print("\n── KPI strip (real data, not demo) ─────────────────────────────────")
    print(f"  Total Revenue      {k['total_revenue']['display']:<16}  YoY {growth_str(k['total_revenue']['growth_pct'])}")
    print(f"  Transactions       {k['transactions']['display']:<16}  Δ  {growth_str(k['transactions']['growth_pct'])}")
    print(f"  Avg Order Value    {k['avg_order_value']['display']:<16}  Δ  {growth_str(k['avg_order_value']['growth_pct'])}")
    print(f"  YoY Growth         {k['yoy_growth']['display']}")
    print(f"  QTY Sold           {k['qty_sold']['display']}")
    print(f"  Customers          {k['customers']['display']:<16}  Δ  {growth_str(k['customers']['growth_pct'])}")
    print(f"  Today's Sales      {k['todays_sales']['display']}  ({k['todays_sales']['bills']} bills)")

    print("\n── Performance ─────────────────────────────────────────────────────")
    print(f"  Revenue trend points:     {len(p['revenue_trend'])}")
    if p["revenue_trend"]:
        last = p["revenue_trend"][-1]
        print(f"    Latest {last['label']}: {lakhs(last['revenue'])} (LY {lakhs(last['last_year'])})")
    print(f"  Categories:               {len(p['category_mix'])}")
    for c in p["category_mix"][:5]:
        print(f"    · {c.get('name')}: {lakhs(_n(c.get('revenue')))} ({c.get('percentage')}%)")
    print(f"  Branches:                 {len(p['branch_comparison'])}")
    for b in p["branch_comparison"][:6]:
        print(f"    · {b['branch']}: {lakhs(b['revenue'])}")

    print("\n── AI insights (computed from live data) ───────────────────────────")
    for i, ins in enumerate(r["ai_insights"], 1):
        print(f"  {i}. [{ins['type']}/{ins['impact']}] {ins['title']}")

    tx = r["recent_transactions"]
    print(f"\n── Recent transactions ({tx['total_count']} total) ─────────────────────")
    for row in tx["records"][:8]:
        print(
            f"  {row.get('id',''):<12} {str(row.get('branch','')):<12} "
            f"{str(row.get('category','')):<14} {rupees(_n(row.get('amount'))):>10}  "
            f"{row.get('date','')}  {row.get('status','')}"
        )
    if tx.get("total_pages"):
        print(f"  Page {tx.get('page')} of {tx.get('total_pages')}")
    if not tx["records"]:
        print("  (no transactions — use API without --skip-transactions or fix SLSXNS view)")

    warnings = r.get("_warnings")
    if warnings:
        print(f"\n  Warnings: {warnings}")

    timings = r.get("_timings_ms")
    if timings:
        print("\n── Per-endpoint timing ─────────────────────────────────────────────")
        for name, ms in sorted(timings.items(), key=lambda x: -x[1]):
            print(f"  {name:<20} {ms:>8.1f} ms")
        print(f"  {'(wall clock includes parallel overlap)':<20}")

    print("\n" + "=" * 72)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch full live dashboard in parallel (fast)")
    parser.add_argument("--mode", choices=("api", "direct"), default="api",
                        help="api=parallel HTTP via warm server cache (fastest); direct=in-process SQL")
    parser.add_argument("--full", action="store_true",
                        help="Slow: also today + kpis + transactions (12+ SQL batches)")
    parser.add_argument("--with-today", action="store_true",
                        help="Also fetch dashboard/today (adds ~1 more heavy SQL batch)")
    parser.add_argument("--with-kpis", action="store_true",
                        help="Also fetch /kpis for period-over-period growth %")
    parser.add_argument("--with-transactions", action="store_true",
                        help="Also fetch transactions (currently 500 on your DB)")
    parser.add_argument("--timings", action="store_true", help="Print per-endpoint ms")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    t0 = time.perf_counter()

    fast = not args.full
    if args.mode == "direct":
        raw = asyncio.run(_fetch_direct(
            with_transactions=args.with_transactions or args.full,
        ))
    else:
        _log(f"API: {args.base_url}")
        password = args.password or input(f"Password for {args.email}: ").strip()
        _log(f"Logging in as {args.email}...")
        token = _login(args.base_url, args.email, password)
        _log("Login OK.")
        raw = _fetch_api_parallel(
            args.base_url,
            token,
            fast=fast,
            with_today=args.with_today or args.full,
            with_kpis=args.with_kpis or args.full,
            with_transactions=args.with_transactions or args.full,
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000
    report = assemble_report(raw, elapsed_ms, args.mode)
    if raw.get("_warnings"):
        report["_warnings"] = raw["_warnings"]

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)
        if not args.timings and report.get("_timings_ms"):
            print("Tip: use --timings to see per-endpoint breakdown.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except urllib.error.URLError as exc:
        print(f"Cannot reach API — is backend running on {DEFAULT_BASE}? {exc.reason}", file=sys.stderr)
        raise SystemExit(1)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
