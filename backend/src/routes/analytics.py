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
GET /analytics/views                — List all ERP views from semantic catalog
GET /analytics/views/query          — Paginate rows from a whitelisted ERP view
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
from src.analytics.view_explorer import fetch_view_page, list_catalog_views
from src.analytics.concurrency import run_analytics_sql
from src.analytics.dashboard import get_dashboard
from src.db.mssql import check_mssql_health
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
        logger.error("Dashboard fetch failed", period=period, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))



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
        logger.error("KPI fetch failed", period=period, error=str(exc))
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

    try:
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
        return payload
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
    n = max(5, min(int(top_n), 80))
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
    overall = mssql.get("connected", False)
    return {
        "success": overall,
        "status": "healthy" if overall else "degraded",
        "mssql": mssql,
        "mode": "live",
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


# ─── View catalog / data explorer ────────────────────────────────────────────

@router.get("/views")
async def views_catalog(
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all whitelisted ERP views from the semantic catalog."""
    try:
        data = list_catalog_views()
        return {"success": True, **data}
    except Exception as exc:
        logger.error("views_catalog_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/views/query")
async def views_query(
    view: str = Query(..., description="View key from catalog"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    skip_count: Optional[bool] = Query(
        None,
        description="Skip row count (fast). Default: auto for dimension/master views.",
    ),
    user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    """Paginate rows from a whitelisted ERP view."""
    try:
        # Do not use run_analytics_sql — view browse must not queue behind dashboard warmup.
        data = await fetch_view_page(view, page, page_size, skip_count=skip_count)
        return {"success": True, **data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("views_query_failed", view=view, page=page, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

