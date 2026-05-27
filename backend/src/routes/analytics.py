"""
Analytics Routes
GET /analytics/kpis                 — Home KPIs
GET /analytics/trend                — Revenue trend
GET /analytics/categories           — Category breakdown
GET /analytics/branches             — Branch bar chart
GET /analytics/departments          — Department breakdown
GET /analytics/products/catalog    — Paginated item master (VW_MB_POWERBI_PRODUCT_MASTER)
GET /analytics/products/top        — Top sellers by revenue for a period (+ YoY growth)
GET /analytics/heatmap              — Hourly heatmap
GET /analytics/bundle               — Fast parallel split (branches+trend+categories+kpis)
GET /analytics/branches/{alias}     — Branch detail + trend
GET /analytics/health               — DB health check
POST /analytics/cache/clear         — Clear cache (admin)
GET /analytics/cache/stats          — Cache stats (admin)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from src.analytics.kpi import get_home_kpis
from src.analytics.charts import (
    get_revenue_trend,
    get_category_breakdown,
    get_branch_chart,
    get_department_chart,
    get_top_salespersons,
    get_hourly_heatmap,
    get_branch_detail,
)
from src.analytics.products_catalog import fetch_product_catalog, fetch_top_products
from src.analytics.transactions import get_transactions, get_transaction_summary
from src.analytics.concurrency import run_analytics_sql
from src.analytics.dashboard import get_dashboard
from src.analytics.cache import cache
from src.analytics.cache_prime import (
    assemble_bundle_from_chart_caches,
    prime_chart_caches_from_bundle,
)
from src.db.mssql import check_mssql_health
from src.db.postgres import check_pg_health
from src.middleware.auth import get_current_user, require_permission, require_roles
from src.auth.jwt import TokenPayload
from src.utils.logger import logger

router = APIRouter(prefix="/analytics", tags=["analytics"])

_VALID_PERIODS = {
    "today", "yesterday", "mtd", "ytd", "qtd",
    "last_7d", "last_14d", "last_30d", "last_90d",
    "last_180d", "last_6m", "last_365d",
    "last_month", "last_quarter", "last_year", "custom",
}


def _validate_period(period: str) -> str:
    if period not in _VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"Invalid period '{period}'. Valid: {sorted(_VALID_PERIODS)}")
    return period


# ─── Sales Dashboard (summary + YoY trend + contribution) ───────────────────

@router.get("/dashboard")
async def sales_dashboard(
    period: str = Query(default="mtd"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="custom period requires start_date and end_date")
    else:
        _validate_period(period)
    try:
        data = await get_dashboard(period, start_date, end_date)
        return {"success": True, **data}
    except Exception as exc:
        logger.error("Dashboard fetch failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Snapshot (instant cached data — zero SQL Server latency) ────────────────

@router.get("/snapshot")
async def analytics_snapshot(
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns the most-recent cached dashboard data from memory/PostgreSQL.
    NEVER touches SQL Server — always responds in < 20 ms.

    Call this on every page load to get instant data while the background
    refresh (regular /analytics/dashboard + /analytics/kpis) runs in parallel.

    The frontend should:
      1. GET /analytics/snapshot  →  paint dashboard immediately
      2. GET /analytics/kpis (background)  →  update KPI chips when ready
      3. GET /analytics/dashboard (background)  →  update charts when ready
    """
    # ── Probe the in-memory cache for all known key variants ─────────────────
    # Older backend versions used v3/v4; current is v4 for kpis and v7 for dashboard.
    _kpi_candidates_mtd   = ["kpi:v4:mtd",   "kpi:v3:mtd",   "kpi:v2:mtd"]
    _kpi_candidates_today = ["kpi:v4:today",  "kpi:v3:today"]
    _kpi_candidates_qtd   = ["kpi:v4:qtd",   "kpi:v3:qtd"]
    _kpi_candidates_ytd   = ["kpi:v4:ytd",   "kpi:v3:ytd"]
    _kpi_candidates_last6m = ["kpi:v4:last_6m", "kpi:v3:last_6m"]

    def _bundle_with_departments(period: str):
        return _first(
            [f"bundle:v2:{period}:{n}:d1:k1" for n in [100, 50, 30]]
            + [f"bundle:v2:{period}:{n}:d0:k1" for n in [100, 50, 30]]
        )

    def _departments_cached(period: str):
        b = _bundle_with_departments(period)
        if b and b.get("departments"):
            return b["departments"]
        return _first([f"chart:department:v2:{period}:{n}" for n in [100, 50, 30]])
    _dash_candidates_mtd  = [
        "dashboard:v7:mtd:None:None",
        "dashboard:v4:mtd:None:None",
    ]
    _dash_candidates_today = [
        "dashboard:v7:today:None:None",
        "dashboard:v4:today:None:None",
    ]
    # All other analytics periods — probed directly (warmed in Phase 3)
    _dash_candidates_qtd    = ["dashboard:v7:qtd:None:None",    "dashboard:v4:qtd:None:None"]
    _dash_candidates_ytd    = ["dashboard:v7:ytd:None:None",    "dashboard:v4:ytd:None:None"]
    _dash_candidates_last6m = ["dashboard:v7:last_6m:None:None","dashboard:v4:last_6m:None:None"]
    # Bundle fallback keys for each period (fast lean charts without dashboard YoY)
    def _bundle_candidates(period: str) -> List[str]:
        return [f"bundle:v2:{period}:{n}:d0:k0" for n in [100, 50, 30]] + \
               [f"bundle:v2:{period}:{n}:d0:k1" for n in [100, 50, 30]]
    # Bundle keys can also give us MTD data (branches + trend + categories)
    _bundle_candidates_mtd = _bundle_candidates("mtd")
    _bundle_candidates_today = [
        f"bundle:v2:today:{n}:d0:k0" for n in [100, 50, 30]
    ]
    _trend_candidates_today = ["chart:trend:v4:today:day", "chart:trend:v3:today:day"]

    def _first(keys: List[str]):
        for k in keys:
            val, _ = cache.get(k)
            if val is not None:
                return val
        return None

    def _map_bundle_trend(raw_trend: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for t in raw_trend or []:
            d = str(t.get("date", ""))[:10]
            out.append({
                "date": d,
                "label": str(t.get("label") or d)[:10],
                "current": float(t.get("revenue") or t.get("current") or 0),
                "prior": float(t.get("prior") or 0),
                "bills": int(t.get("transactions") or t.get("bills") or 0),
                "quantity": float(t.get("quantity") or 0),
            })
        return out

    def _summary_from_trend_point(pt: Dict[str, Any]) -> Dict[str, Any]:
        rev = float(pt.get("revenue") or pt.get("current") or 0)
        bills = int(pt.get("transactions") or pt.get("bills") or 0)
        qty = float(pt.get("quantity") or 0)
        return {
            "mtd_sales": rev,
            "ly_sales": float(pt.get("prior") or 0),
            "sales_growth_pct": None,
            "bills": bills,
            "quantity": qty,
            "customers": None,
        }

    def _today_dashboard_from_trend_rows(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not rows:
            return None
        from datetime import date as _date
        today_s = _date.today().isoformat()
        pt = None
        for t in rows:
            if str(t.get("date", ""))[:10] == today_s:
                pt = t
                break
        if pt is None:
            last = rows[-1]
            if str(last.get("date", ""))[:10] != today_s:
                return None
            pt = last
        mapped = _map_bundle_trend([pt])
        summary = _summary_from_trend_point(pt)
        return {
            "success": True,
            "period": "today",
            "period_label": "Today",
            "granularity": "day",
            "summary": summary,
            "trend": mapped,
            "categories": [],
            "branches": [],
            "checksum": None,
            "_source": "trend_derived",
        }

    mtd_kpis      = _first(_kpi_candidates_mtd)
    today_kpis    = _first(_kpi_candidates_today)
    qtd_kpis      = _first(_kpi_candidates_qtd)
    ytd_kpis      = _first(_kpi_candidates_ytd)
    last6m_kpis   = _first(_kpi_candidates_last6m)
    mtd_dashboard = _first(_dash_candidates_mtd)
    today_dash    = _first(_dash_candidates_today)

    # Fall back to bundle data when individual dashboard cache is cold
    if mtd_dashboard is None:
        bundle = _first(_bundle_candidates_mtd)
        if bundle:
            mapped_trend = _map_bundle_trend(bundle.get("trend") or [])
            mtd_dashboard = {
                "success": True,
                "period": "mtd",
                "period_label": "Month-to-Date",
                "granularity": "day",
                "summary": None,
                "trend": mapped_trend,
                "categories": [
                    {"name": c.get("category", ""), "revenue": c.get("revenue", 0), "percentage": c.get("percentage", 0)}
                    for c in (bundle.get("categories") or [])
                ],
                "branches": [
                    {"name": b.get("branch", ""), "revenue": b.get("revenue", 0), "percentage": 0}
                    for b in (bundle.get("branches") or [])
                ],
                "checksum": None,
                "_source": "bundle",
            }

    if today_dash is None:
        bundle_today = _first(_bundle_candidates_today)
        if bundle_today:
            rows = bundle_today.get("trend") or []
            today_dash = _today_dashboard_from_trend_rows(rows)

    if today_dash is None:
        trend_today = _first(_trend_candidates_today)
        if trend_today:
            today_dash = _today_dashboard_from_trend_rows(trend_today)

    if today_dash is None and mtd_dashboard:
        today_dash = _today_dashboard_from_trend_rows(mtd_dashboard.get("trend") or [])

    if today_kpis is None and today_dash and today_dash.get("summary"):
        s = today_dash["summary"]
        today_kpis = {
            "revenue": {"value": s.get("mtd_sales", 0), "prior": s.get("ly_sales", 0), "growth": s.get("sales_growth_pct"), "period": "Today"},
            "transactions": {"value": s.get("bills", 0), "prior": 0, "growth": None, "period": "Today"},
            "quantity": {"value": s.get("quantity", 0), "prior": 0, "growth": None, "period": "Today"},
        }

    # ── Additional analytics periods (QTD / YTD / Last-6M) ──────────────────
    # Read from memory cache — returns None if backend hasn't warmed these yet.
    # Frontend uses these to seed analytics-page:{period} cache for instant tab switching.
    qtd_dashboard   = _first(_dash_candidates_qtd)
    ytd_dashboard   = _first(_dash_candidates_ytd)
    last6m_dashboard = _first(_dash_candidates_last6m)
    # Fallback to bundle keys for lean (no YoY) data
    if qtd_dashboard is None:
        _b = _first(_bundle_candidates("qtd"))
        if _b:
            mapped = _map_bundle_trend(_b.get("trend") or [])
            qtd_dashboard = {
                "success": True, "period": "qtd", "period_label": "Quarter-to-Date",
                "granularity": "day", "summary": None,
                "trend": mapped,
                "categories": [{"name": c.get("category",""), "revenue": c.get("revenue",0), "percentage": c.get("percentage",0)} for c in (_b.get("categories") or [])],
                "branches": [{"name": b.get("branch",""), "revenue": b.get("revenue",0), "percentage": 0} for b in (_b.get("branches") or [])],
                "checksum": None, "_source": "bundle",
            }
    if ytd_dashboard is None:
        _b = _first(_bundle_candidates("ytd"))
        if _b:
            mapped = _map_bundle_trend(_b.get("trend") or [])
            ytd_dashboard = {
                "success": True, "period": "ytd", "period_label": "Year-to-Date",
                "granularity": "month", "summary": None,
                "trend": mapped,
                "categories": [{"name": c.get("category",""), "revenue": c.get("revenue",0), "percentage": c.get("percentage",0)} for c in (_b.get("categories") or [])],
                "branches": [{"name": b.get("branch",""), "revenue": b.get("revenue",0), "percentage": 0} for b in (_b.get("branches") or [])],
                "checksum": None, "_source": "bundle",
            }
    if last6m_dashboard is None:
        _b = _first(_bundle_candidates("last_6m"))
        if _b:
            mapped = _map_bundle_trend(_b.get("trend") or [])
            last6m_dashboard = {
                "success": True, "period": "last_6m", "period_label": "Last 6 Months",
                "granularity": "month", "summary": None,
                "trend": mapped,
                "categories": [{"name": c.get("category",""), "revenue": c.get("revenue",0), "percentage": c.get("percentage",0)} for c in (_b.get("categories") or [])],
                "branches": [{"name": b.get("branch",""), "revenue": b.get("revenue",0), "percentage": 0} for b in (_b.get("branches") or [])],
                "checksum": None, "_source": "bundle",
            }

    # ── Transactions page 1 (instant load for Transactions page) ─────────────
    # Look for the cached first-page transaction list (page_size=12 matches the UI default).
    _txn_list_keys_mtd = [
        "txn:list:v1:mtd:12",
        "txn:list:v1:mtd:50",
    ]
    _txn_list_keys_today = [
        "txn:list:v1:today:12",
        "txn:list:v1:today:50",
    ]
    txn_summary_keys_mtd = ["txn:summary:v2:mtd", "txn:summary:v1:mtd"]
    txn_list_mtd   = _first(_txn_list_keys_mtd)
    txn_list_today = _first(_txn_list_keys_today)
    txn_summary_mtd = _first(txn_summary_keys_mtd)

    departments_mtd    = _departments_cached("mtd")
    departments_today  = _departments_cached("today")
    departments_qtd    = _departments_cached("qtd")
    departments_ytd    = _departments_cached("ytd")
    departments_last6m = _departments_cached("last_6m")

    has_data = bool(
        mtd_kpis or mtd_dashboard or today_kpis or today_dash
        or qtd_dashboard or ytd_dashboard or last6m_dashboard
    )

    return {
        "success": True,
        "has_data": has_data,
        "source": "memory_cache",
        "mtd_dashboard": mtd_dashboard,
        "mtd_kpis": mtd_kpis,
        "today_kpis": today_kpis,
        "today_dashboard": today_dash,
        "qtd_kpis": qtd_kpis,
        "ytd_kpis": ytd_kpis,
        "last6m_kpis": last6m_kpis,
        "qtd_dashboard": qtd_dashboard,
        "ytd_dashboard": ytd_dashboard,
        "last6m_dashboard": last6m_dashboard,
        "departments_mtd": departments_mtd,
        "departments_today": departments_today,
        "departments_qtd": departments_qtd,
        "departments_ytd": departments_ytd,
        "departments_last6m": departments_last6m,
        "txn_list_mtd": txn_list_mtd,
        "txn_list_today": txn_list_today,
        "txn_summary_mtd": txn_summary_mtd,
        "cache_stats": cache.stats(),
    }


# ─── KPIs ─────────────────────────────────────────────────────────────────────

@router.get("/kpis")
async def home_kpis(
    period: str = Query(default="mtd"),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    try:
        data = await get_home_kpis(period)
        return {"success": True, "period": period, **data}
    except Exception as exc:
        logger.error("KPI fetch failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Fast bundle (one HTTP round-trip; server-side parallel SQL + cache) ─────

@router.get("/bundle")
async def analytics_bundle(
    period: str = Query(default="mtd"),
    top_n: int = Query(default=100, ge=1, le=100),
    include_departments: bool = Query(default=False),
    include_kpis: bool = Query(default=False),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Single request that runs branches, trend, categories, (optional) kpis and departments
    in parallel on the server — same data as test/*_breakdown.py split mode, less HTTP overhead.
    Whole response is cached (repeat calls ~instant when warm).
    """
    _validate_period(period)
    n = top_n
    cache_key = f"bundle:v2:{period}:{n}:d{int(include_departments)}:k{int(include_kpis)}"

    async def _fetch_bundle() -> Dict[str, Any]:
        specs: List[Tuple[str, Any]] = [
            ("branches", get_branch_chart(period)),
            ("trend", get_revenue_trend(period)),
            ("categories", get_category_breakdown(period, n)),
        ]
        if include_kpis:
            specs.append(("kpis", get_home_kpis(period)))
        if include_departments:
            specs.append(("departments", get_department_chart(period, n)))

        timings_ms: Dict[str, float] = {}
        errors: Dict[str, str] = {}
        payload: Dict[str, Any] = {"success": True, "period": period}

        async def _timed(name: str, coro: Any) -> Tuple[str, Any, float]:
            t0 = time.perf_counter()
            try:
                data = await run_analytics_sql(coro)
                return name, data, round((time.perf_counter() - t0) * 1000, 1)
            except Exception as exc:
                return name, exc, round((time.perf_counter() - t0) * 1000, 1)

        results = await asyncio.gather(*[_timed(name, coro) for name, coro in specs])

        for name, outcome, ms in results:
            timings_ms[name] = ms
            if isinstance(outcome, Exception):
                errors[name] = str(outcome)
                logger.warning("Bundle partial failure", period=period, key=name, error=str(outcome))
                continue
            if name == "kpis":
                payload["kpis"] = outcome
            elif name == "trend":
                payload["trend"] = outcome
            else:
                payload[name] = outcome

        if errors:
            payload["errors"] = errors
        payload["timings_ms"] = timings_ms

        required = {"branches", "trend", "categories"}
        missing = required - {k for k in required if k in payload}
        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"Bundle missing required keys: {sorted(missing)}. Errors: {errors}",
            )
        prime_chart_caches_from_bundle(period, payload, top_n=n)
        return payload

    try:
        composed = assemble_bundle_from_chart_caches(
            period, n, include_kpis=include_kpis, include_departments=include_departments
        )
        if composed is not None:
            data: Dict[str, Any] = {
                "success": True,
                "period": period,
                **composed,
                "timings_ms": {"source": "chart_cache_compose"},
            }
            cache.set(cache_key, data)
            prime_chart_caches_from_bundle(period, data, top_n=n)
            return data

        data = await cache.get_or_fetch(cache_key, _fetch_bundle)
        prime_chart_caches_from_bundle(period, data, top_n=n)
        return data
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Bundle fetch failed", period=period, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ─── Charts ───────────────────────────────────────────────────────────────────

@router.get("/trend")
async def revenue_trend(
    period: str = Query(default="last_30d"),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    data = await get_revenue_trend(period)
    return {"success": True, "period": period, "trend": data}


@router.get("/categories")
async def category_breakdown(
    period: str = Query(default="mtd"),
    top_n: int = Query(default=10, ge=1, le=100),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    data = await get_category_breakdown(period, top_n)
    return {"success": True, "period": period, "categories": data}


@router.get("/branches")
async def branch_chart(
    period: str = Query(default="mtd"),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    data = await get_branch_chart(period)
    return {"success": True, "period": period, "branches": data}


@router.get("/departments")
async def department_chart(
    period: str = Query(default="mtd"),
    top_n: int = Query(default=10, ge=1, le=100),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    data = await get_department_chart(period, top_n)
    return {"success": True, "period": period, "departments": data}


@router.get("/salespersons")
async def top_salespersons(
    period: str = Query(default="mtd"),
    top_n: int = Query(default=10, ge=1, le=50),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    data = await get_top_salespersons(period, top_n)
    return {"success": True, "period": period, "salespersons": data}


@router.get("/products/catalog")
async def product_catalog_api(
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=5, le=500),
    offset: int = Query(default=0, ge=0),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        data = await run_analytics_sql(fetch_product_catalog(search=search, limit=limit, offset=offset))
        return data
    except Exception as exc:
        logger.error("product_catalog_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/products/top")
async def top_products_api(
    period: str = Query(default="mtd"),
    top_n: int = Query(default=15, ge=5, le=80),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    try:
        items = await run_analytics_sql(fetch_top_products(period, top_n))
        return {"success": True, "period": period, "products": items}
    except Exception as exc:
        logger.error("top_products_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/heatmap")
async def hourly_heatmap(
    period: str = Query(default="last_30d"),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    data = await get_hourly_heatmap(period)
    return {"success": True, "period": period, "heatmap": data}


# ─── Branch Detail ────────────────────────────────────────────────────────────

@router.get("/branches/{branch_alias}")
async def branch_detail(
    branch_alias: str,
    period: str = Query(default="last_14d"),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    data = await get_branch_detail(branch_alias, period)
    return {"success": True, **data}


# ─── Health Check ─────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    mssql = await check_mssql_health()
    pg: Dict[str, Any] = {}
    try:
        pg = await check_pg_health()
    except Exception as exc:
        pg = {"connected": False, "error": str(exc)}

    overall = mssql.get("connected", False)
    return {
        "success": overall,
        "status": "healthy" if overall else "degraded",
        "mssql": mssql,
        "postgres": pg,
        "cache": cache.stats(),
    }


# ─── Transactions ────────────────────────────────────────────────────────────

@router.get("/transactions/summary")
async def transaction_summary(
    period: str = Query(default="mtd"),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    try:
        data = await get_transaction_summary(period)
        return {"success": True, **data}
    except Exception as exc:
        logger.error("transaction_summary_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/transactions")
async def transactions_list(
    period: str = Query(default="mtd"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    branch: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    _validate_period(period)
    try:
        data = await run_analytics_sql(get_transactions(period, page, page_size, branch, category, search))
        return {"success": True, **data}
    except Exception as exc:
        logger.error("transactions_list_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Cache Admin ──────────────────────────────────────────────────────────────

@router.post("/cache/clear", dependencies=[Depends(require_roles("admin"))])
async def clear_cache(prefix: Optional[str] = None) -> Dict[str, Any]:
    if prefix:
        n = cache.invalidate_prefix(prefix)
        return {"success": True, "cleared": n, "prefix": prefix}
    n = cache.clear()
    return {"success": True, "cleared": n}


@router.get("/cache/stats", dependencies=[Depends(require_roles("admin", "manager"))])
async def cache_stats() -> Dict[str, Any]:
    return {"success": True, "cache": cache.stats()}
