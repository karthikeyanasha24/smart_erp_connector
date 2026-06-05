"""
YoY revenue trend — two parallel SQL scans (current + LY), each covering only its
own date window. Faster than one combined 18-month scan on unindexed views.
Used by charts.get_revenue_trend.
"""

from __future__ import annotations

import asyncio
from datetime import date as date_type, datetime as datetime_type
from typing import Any, Dict, List

from src.config import cfg
from src.db.mssql import execute_query
from src.utils.sql_ref import sql_table
from src.analytics.metrics_sql import quantity_column, transactions_aggregate
from src.utils.date_utils import resolve_date_range, get_prior_year_range, trend_granularity


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _period_key(raw: Any) -> str:
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


YOY_TREND_PERIODS = frozenset({
    "today", "mtd", "qtd", "ytd", "last_6m", "last_30d", "last_7d", "last_14d", "last_90d",
})


async def fetch_revenue_trend_yoy(period: str) -> List[Dict[str, Any]]:
    """Chart rows: date, label, revenue, prior, transactions, quantity.

    Uses two separate SQL scans (current + LY) run in parallel, each scaning only
    its own date window. This is faster than the old single 18-month combined scan
    because SQL Server can build a tighter range seek per query.
    """
    dr = resolve_date_range(period)
    ly_dr = get_prior_year_range(period)
    gran = trend_granularity(period)

    c = cfg
    table = sql_table(c.SALES_AI_TABLE)
    date_col = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
    amt_col = c.SALES_ANALYTICS_AMOUNT_COLUMN
    qty_col = quantity_column()

    if gran == "month":
        period_expr = f"FORMAT([{date_col}], 'yyyy-MM')"
        label_expr = f"FORMAT([{date_col}], 'MMM yyyy')"
    else:
        period_expr = f"CAST([{date_col}] AS DATE)"
        label_expr = f"FORMAT(CAST([{date_col}] AS DATE), 'dd-MMM')"

    bills_agg = transactions_aggregate()

    # Current period query — only scans the current window
    sql_curr = f"""
        SELECT
            {period_expr} AS PeriodKey,
            MIN({label_expr}) AS Label,
            SUM([{amt_col}]) AS Revenue,
            {bills_agg} AS Bills,
            SUM([{qty_col}]) AS Quantity
        FROM {table} WITH (NOLOCK)
        WHERE [{date_col}] >= @startDate
          AND [{date_col}] < DATEADD(day,1,CAST(@endDate AS DATE))
        GROUP BY {period_expr}
        ORDER BY PeriodKey ASC
        OPTION (RECOMPILE)
    """

    # Prior year query — only scans the LY window (same length, 1 year earlier)
    sql_ly = f"""
        SELECT
            {period_expr} AS PeriodKey,
            SUM([{amt_col}]) AS Revenue
        FROM {table} WITH (NOLOCK)
        WHERE [{date_col}] >= @lyStart
          AND [{date_col}] < DATEADD(day,1,CAST(@lyEnd AS DATE))
        GROUP BY {period_expr}
        ORDER BY PeriodKey ASC
        OPTION (RECOMPILE)
    """

    # Run both in parallel — each scans only its own date window
    curr_result, ly_result = await asyncio.gather(
        execute_query(
            sql_curr,
            params={"startDate": dr.start, "endDate": dr.end},
            nolock=True,
            recompile=False,  # Already in SQL
        ),
        execute_query(
            sql_ly,
            params={"lyStart": ly_dr.start, "lyEnd": ly_dr.end},
            nolock=True,
            recompile=False,
        ),
    )

    # Build LY lookup: month-number (for monthly gran) or shifted date (for daily gran)
    ly_map: Dict[str, float] = {}
    for r in ly_result["records"]:
        key = _period_key(r.get("PeriodKey"))
        ly_val = _safe_float(r.get("Revenue"))
        if ly_val > 0:
            if gran == "month" and len(key) >= 7:
                ly_map[key[5:7]] = ly_val   # month number "01".."12"
            else:
                ly_map[key] = ly_val        # ISO date of LY day

    rows: List[Dict[str, Any]] = []
    for r in curr_result["records"]:
        curr = _safe_float(r.get("Revenue"))
        bills = int(_safe_float(r.get("Bills")))
        if curr == 0 and bills == 0:
            continue
        key = _period_key(r.get("PeriodKey"))
        label = str(r.get("Label", key))
        if gran == "month" and len(key) >= 7:
            prior = ly_map.get(key[5:7], 0)
        elif key:
            try:
                prior = ly_map.get(_prior_year_day_key(key), 0)
            except ValueError:
                prior = ly_map.get(key, 0)
        else:
            prior = 0
        rows.append({
            "date": key,
            "label": label if gran == "month" else (label or key[:10]),
            "revenue": curr,
            "prior": prior,
            "transactions": bills,
            "quantity": int(_safe_float(r.get("Quantity"))),
        })
    return rows
