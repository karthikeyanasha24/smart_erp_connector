"""
Sales analytics dashboard — summary KPIs, YoY trend, contribution breakdown, checksum.
"""

from __future__ import annotations

import asyncio
import time as _time
from datetime import date as date_type, datetime as datetime_type
from typing import Any, Dict, List, Optional

from src.config import cfg
from src.db.mssql import execute_query
from src.utils.sql_ref import sql_table
from src.analytics.metrics_sql import bill_count_case, quantity_column, transactions_aggregate
from src.analytics.cache import cache
from src.utils.logger import logger
from src.utils.date_utils import (
    resolve_date_range,
    resolve_custom_range,
    get_prior_year_range,
    trend_granularity,
    period_cache_key,
    today_ist,
    DateRange,
)


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _period_key(raw: Any) -> str:
    """Normalize SQL PeriodKey (date/datetime/str) to YYYY-MM-DD for YoY joins."""
    if raw is None:
        return ""
    if isinstance(raw, datetime_type):
        return raw.date().isoformat()
    if isinstance(raw, date_type):
        return raw.isoformat()
    s = str(raw).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    try:
        return datetime_type.fromisoformat(s.replace("Z", "+00:00")[:26]).date().isoformat()
    except ValueError:
        return s[:10]


def _prior_year_day_key(day_key: str) -> str:
    d = date_type.fromisoformat(day_key)
    return d.replace(year=d.year - 1).isoformat()


def _period_range(period: str, start_date: Optional[str], end_date: Optional[str]) -> DateRange:
    if period == "custom" and start_date and end_date:
        return resolve_custom_range(start_date, end_date)
    return resolve_date_range(period)


async def _query_summary(dr: DateRange, ly_dr: DateRange) -> Dict[str, Any]:
    c = cfg
    table = sql_table(c.SALES_AI_TABLE)
    date_col = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
    amt_col = c.SALES_ANALYTICS_AMOUNT_COLUMN
    qty_col = quantity_column()
    bills_expr = bill_count_case(date_col, "@startDate", "@endDate")

    sql = f"""
        SELECT
            ISNULL(SUM(CASE WHEN [{date_col}] >= @startDate
                                 AND [{date_col}] < DATEADD(day,1,CAST(@endDate AS DATE))
                THEN [{amt_col}] ELSE 0 END), 0) AS CurrentSales,
            ISNULL(SUM(CASE WHEN [{date_col}] >= @lyStart
                                 AND [{date_col}] < DATEADD(day,1,CAST(@lyEnd AS DATE))
                THEN [{amt_col}] ELSE 0 END), 0) AS LYSales,
            ISNULL({bills_expr}, 0) AS Bills,
            ISNULL(SUM(CASE WHEN [{date_col}] >= @startDate
                                 AND [{date_col}] < DATEADD(day,1,CAST(@endDate AS DATE))
                THEN [{qty_col}] ELSE 0 END), 0) AS Quantity
        FROM {table} WITH (NOLOCK)
        WHERE [{date_col}] >= @lyStart
          AND [{date_col}] < DATEADD(day,1,CAST(@endDate AS DATE))
    """
    result = await execute_query(
        sql,
        params={
            "startDate": dr.start,
            "endDate": dr.end,
            "lyStart": ly_dr.start,
            "lyEnd": ly_dr.end,
        },
        nolock=True,
        recompile=False,
    )
    row = result["records"][0] if result["records"] else {}
    curr = _safe_float(row.get("CurrentSales"))
    ly = _safe_float(row.get("LYSales"))
    growth = round((curr - ly) / ly * 100, 2) if ly else None
    qty = _safe_float(row.get("Quantity"))
    bills = int(_safe_float(row.get("Bills")))

    logger.info(
        "📊 summary computed",
        date_range=f"{dr.start} → {dr.end}",
        current_sales_L=round(curr / 100_000, 2),
        ly_sales_L=round(ly / 100_000, 2),
        growth_pct=growth,
        quantity=int(qty),
        bills=bills,
    )

    return {
        "mtd_sales": curr,
        "ly_sales": ly,
        "sales_growth_pct": growth,
        "quantity": qty,
        "bills": bills,
    }


async def _query_customers(dr: DateRange) -> Optional[int]:
    if cfg.ANALYTICS_SKIP_CUSTOMER_COUNT:
        return None
    c = cfg
    table = sql_table(c.SALES_AI_TABLE)
    date_col = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
    sql = f"""
        SELECT COUNT(DISTINCT [CustomerId]) AS Cnt
        FROM {table} WITH (NOLOCK)
        WHERE [{date_col}] >= @startDate
          AND [{date_col}] < DATEADD(day,1,CAST(@endDate AS DATE))
    """
    try:
        result = await execute_query(
            sql,
            params={"startDate": dr.start, "endDate": dr.end},
            nolock=True,
            recompile=False,
        )
        rows = result.get("records") or []
        if not rows:
            return None
        row = rows[0]
        raw = row.get("Cnt")
        if raw is None and isinstance(row, dict):
            raw = row.get("cnt")
        # Missing cell / ODBC alias mismatch → None (don't coerce to 0)
        if raw is None:
            logger.warning("⚠️  customer count row missing Cnt", sample_keys=list(row.keys())[:8])
            return None
        cnt = int(_safe_float(raw))
        logger.info("👥 customers counted", date_range=f"{dr.start} → {dr.end}", customers=cnt)
        return cnt
    except Exception as exc:
        logger.warning("⚠️  customer count failed", error=str(exc))
        return None


async def _query_trend(dr: DateRange, ly_dr: DateRange, granularity: str) -> List[Dict[str, Any]]:
    """Single table scan for current + prior-year trend (was two separate queries)."""
    c = cfg
    table = sql_table(c.SALES_AI_TABLE)
    date_col = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
    amt_col = c.SALES_ANALYTICS_AMOUNT_COLUMN
    qty_col = quantity_column()
    end_curr = "DATEADD(day,1,CAST(@endDate AS DATE))"
    end_ly = "DATEADD(day,1,CAST(@lyEnd AS DATE))"
    curr_win = f"[{date_col}] >= @startDate AND [{date_col}] < {end_curr}"
    ly_win = f"[{date_col}] >= @lyStart AND [{date_col}] < {end_ly}"

    # Trend chart: always COUNT(*) — fast; exact invoice count is on KPI card
    bills_expr = f"SUM(CASE WHEN {curr_win} THEN 1 ELSE 0 END)"

    if granularity == "month":
        period_expr = f"FORMAT([{date_col}], 'yyyy-MM')"
        label_expr = f"FORMAT([{date_col}], 'MMM yyyy')"
    else:
        period_expr = f"CAST([{date_col}] AS DATE)"
        label_expr = f"FORMAT(CAST([{date_col}] AS DATE), 'dd-MMM')"

    sql = f"""
        SELECT
            {period_expr} AS PeriodKey,
            MIN({label_expr}) AS Label,
            SUM(CASE WHEN {curr_win} THEN [{amt_col}] ELSE 0 END) AS Revenue,
            SUM(CASE WHEN {ly_win} THEN [{amt_col}] ELSE 0 END) AS PriorRevenue,
            {bills_expr} AS Bills,
            SUM(CASE WHEN {curr_win} THEN [{qty_col}] ELSE 0 END) AS Quantity
        FROM {table} WITH (NOLOCK)
        WHERE [{date_col}] >= @lyStart
          AND [{date_col}] < {end_curr}
        GROUP BY {period_expr}
        ORDER BY PeriodKey ASC
    """
    result = await execute_query(
        sql,
        params={
            "startDate": dr.start,
            "endDate": dr.end,
            "lyStart": ly_dr.start,
            "lyEnd": ly_dr.end,
        },
        nolock=True,
        recompile=False,
    )

    ly_map: Dict[str, float] = {}
    for r in result["records"]:
        key = _period_key(r.get("PeriodKey"))
        ly_val = _safe_float(r.get("PriorRevenue"))
        if ly_val > 0:
            if granularity == "month" and len(key) >= 7:
                ly_map[key[5:7]] = ly_val
            else:
                ly_map[key] = ly_val

    points: List[Dict[str, Any]] = []
    for r in result["records"]:
        curr = _safe_float(r.get("Revenue"))
        bills = int(_safe_float(r.get("Bills")))
        if curr == 0 and bills == 0:
            continue
        key = _period_key(r.get("PeriodKey"))
        label = str(r.get("Label", key))
        if granularity == "month" and len(key) >= 7:
            prior = ly_map.get(key[5:7], 0)
        elif key:
            try:
                prior = ly_map.get(_prior_year_day_key(key), 0)
            except ValueError:
                prior = ly_map.get(key, 0)
        else:
            prior = 0
        points.append({
            "label": label,
            "date": key,
            "current": curr,
            "prior": prior,
            "bills": bills,
            "quantity": _safe_float(r.get("Quantity")),
        })
    return points


async def _query_contribution(dr: DateRange, dim: str, limit: int = 50) -> List[Dict[str, Any]]:
    c = cfg
    col = c.SALES_ANALYTICS_CATEGORY_DIM if dim == "category" else c.SALES_ANALYTICS_BRANCH_DIM
    sql = f"""
        SELECT TOP {limit}
            [{col}] AS Name,
            SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) AS Revenue
        FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
        WHERE [{c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN}] >= @startDate
          AND [{c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN}] < DATEADD(day,1,CAST(@endDate AS DATE))
        GROUP BY [{col}]
        ORDER BY Revenue DESC
    """
    result = await execute_query(
        sql,
        params={"startDate": dr.start, "endDate": dr.end},
        nolock=True,
        recompile=False,
    )
    rows = result["records"]
    total = sum(_safe_float(r.get("Revenue")) for r in rows) or 1
    return [
        {
            "name": str(r.get("Name", "")),
            "revenue": _safe_float(r.get("Revenue")),
            "percentage": round(_safe_float(r.get("Revenue")) / total * 100, 2),
        }
        for r in rows
    ]


async def get_dashboard(
    period: str = "mtd",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    # When MTD and Today cover the same date (1st of month), share a single cache key
    # so both periods always return identical data and can't diverge.
    effective_period = period
    if period == "mtd" and period != "custom":
        _today_ist = today_ist()
        _today_str = _today_ist.isoformat()
        _som = _today_ist.replace(day=1).isoformat()
        if _som == _today_str:
            effective_period = "today"   # alias: mtd == today on the 1st

    # Custom-range dashboards are not cached (date params vary).
    cache_key = period_cache_key("dashboard:v3", effective_period) if effective_period != "custom" else None

    # ── _fetch is defined first so the _bg closure can always access it ──
    async def _fetch() -> Dict[str, Any]:
        logger.info("querying SQL Server", period=period)
        dr = _period_range(period, start_date, end_date)
        ly_dr = get_prior_year_range(
            "custom" if period == "custom" else period,
        )
        if period == "custom" and start_date and end_date:
            from datetime import date as dt
            s = dt.fromisoformat(start_date[:10])
            e = dt.fromisoformat(end_date[:10])
            ly_dr = DateRange(
                s.replace(year=s.year - 1).isoformat(),
                e.replace(year=e.year - 1).isoformat(),
                "Last Year (same range)",
                "ly_custom",
            )

        gran = trend_granularity(period if period != "custom" else "mtd")
        top_n = cfg.ANALYTICS_TOP_N_MAX

        summary, customers, trend, categories, branches = await asyncio.gather(
            _query_summary(dr, ly_dr),
            _query_customers(dr),
            _query_trend(dr, ly_dr, gran),
            _query_contribution(dr, "category", top_n),
            _query_contribution(dr, "branch", top_n),
        )

        trend_sum = sum(p["current"] for p in trend)
        checksum_match = abs(trend_sum - summary["mtd_sales"]) < max(1, summary["mtd_sales"] * 0.001)

        logger.info(
            "✅ dashboard ready",
            period=period,
            date_range=f"{dr.start} → {dr.end}",
            sales_L=round(summary["mtd_sales"] / 100_000, 2),
            ly_L=round(summary["ly_sales"] / 100_000, 2),
            growth_pct=summary["sales_growth_pct"],
            bills=summary["bills"],
            quantity=int(summary["quantity"]),
            customers=customers,
            trend_points=len(trend),
            categories=len(categories),
            branches=len(branches),
            checksum_ok=checksum_match,
        )

        return {
            "period": period,
            "period_label": dr.label,
            "granularity": gran,
            "date_range": {"start": dr.start, "end": dr.end},
            "ly_range": {"start": ly_dr.start, "end": ly_dr.end},
            "fetched_at": _time.time(),   # Unix timestamp of actual SQL Server fetch
            "summary": {
                **summary,
                "customers": customers,
            },
            "trend": trend,
            "categories": categories,
            "branches": branches,
            "checksum": {
                "trend_total": trend_sum,
                "summary_total": summary["mtd_sales"],
                "match": checksum_match,
            },
        }

    # ── Cache read (after _fetch is defined so _bg closure works) ──
    if cache_key and not force_refresh:
        cached, is_fresh = cache.get(cache_key)
        if cached is not None:
            logger.debug("🔍 dashboard cache hit", period=period, fresh=is_fresh)
            if not is_fresh:
                async def _bg() -> None:
                    try:
                        fresh = await _fetch()
                        cache.set(cache_key, fresh)
                        # Also write alias key when effective_period differs (day-1 mtd/today sync)
                        if effective_period != period:
                            cache.set(period_cache_key("dashboard:v3", period), fresh)
                        logger.info("🔄 dashboard bg-refresh done", period=period)
                    except Exception as exc:
                        logger.warning("🔄 dashboard bg-refresh failed", period=period, error=str(exc))
                asyncio.create_task(_bg())
            return cached
    elif cache_key and force_refresh:
        cache.delete(cache_key)
        if effective_period != period:
            cache.delete(period_cache_key("dashboard:v3", period))
        logger.info("🔄 dashboard force-refresh", period=period)

    logger.info("🔍 dashboard requested", period=period)
    result = await _fetch()
    if cache_key:
        cache.set(cache_key, result)
        # Also populate the original period key when aliased (mtd on day 1 → also writes today)
        if effective_period != period:
            cache.set(period_cache_key("dashboard:v3", period), result)
    return result
