"""Distinct customer count for a period — uses fast SALES_AI_TABLE (not slow SALES_VIEW)."""

from __future__ import annotations

from typing import Optional

from src.config import cfg
from src.db.mssql import execute_query
from src.utils.date_utils import resolve_date_range
from src.utils.sql_ref import sql_table
from src.utils.logger import logger


def _safe_int(val) -> Optional[int]:
    try:
        if val is None:
            return None
        return int(float(val))
    except (TypeError, ValueError):
        return None


async def get_customer_count(period: str) -> Optional[int]:
    """
    COUNT(DISTINCT CustomerId) on the same fast view as KPIs/charts.
    Much faster than COUNT on dbo.VwAISalesData used by full dashboard.
    """
    if cfg.ANALYTICS_SKIP_CUSTOMER_COUNT:
        return None

    dr = resolve_date_range(period)
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
        cnt = _safe_int(row.get("Cnt") or row.get("cnt"))
        if cnt is None:
            return None
        logger.info(
            "customers counted (fast view)",
            period=period,
            customers=cnt,
            date_range=f"{dr.start} → {dr.end}",
        )
        return cnt
    except Exception as exc:
        logger.warning("customer_count_failed", period=period, error=str(exc))
        return None
