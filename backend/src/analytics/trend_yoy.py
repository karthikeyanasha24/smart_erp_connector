"""
YoY revenue trend — single SQL scan for current + prior year daily/monthly buckets.
Used by charts.get_revenue_trend.
"""

from __future__ import annotations

from datetime import date as date_type, datetime as datetime_type
from typing import Any, Dict, List

from src.config import cfg
from src.db.mssql import execute_query
from src.utils.sql_ref import sql_table
from src.analytics.metrics_sql import quantity_column
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
    "mtd", "qtd", "ytd", "last_6m", "last_30d", "last_7d", "last_14d", "last_90d",
})


async def fetch_revenue_trend_yoy(period: str) -> List[Dict[str, Any]]:
    """Chart rows: date, label, revenue, prior, transactions, quantity."""
    dr = resolve_date_range(period)
    ly_dr = get_prior_year_range(period)
    gran = trend_granularity(period)

    c = cfg
    table = sql_table(c.SALES_AI_TABLE)
    date_col = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
    amt_col = c.SALES_ANALYTICS_AMOUNT_COLUMN
    qty_col = quantity_column()
    end_curr = "DATEADD(day,1,CAST(@endDate AS DATE))"
    end_ly = "DATEADD(day,1,CAST(@lyEnd AS DATE))"
    curr_win = f"[{date_col}] >= @startDate AND [{date_col}] < {end_curr}"
    ly_win = f"[{date_col}] >= @lyStart AND [{date_col}] < {end_ly}"

    if c.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        bills_expr = f"SUM(CASE WHEN {curr_win} THEN 1 ELSE 0 END)"
    else:
        bc = c.SALES_ANALYTICS_BILL_COUNT_COLUMN
        bills_expr = f"SUM(CASE WHEN {curr_win} THEN [{bc}] ELSE 0 END)"

    if gran == "month":
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
            if gran == "month" and len(key) >= 7:
                ly_map[key[5:7]] = ly_val
            else:
                ly_map[key] = ly_val

    rows: List[Dict[str, Any]] = []
    for r in result["records"]:
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
