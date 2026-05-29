"""
KPI Analytics Engine
Computes home-dashboard KPIs: revenue, transactions, avg order value, customers.
All figures include period-over-period comparison with growth rates.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import resolve_date_range, get_comparison_range
from src.utils.sql_ref import sql_table
from src.db.mssql import execute_query
from src.analytics.metrics_sql import bill_count_case, quantity_column


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _growth(current: float, prior: float) -> Optional[float]:
    if prior == 0:
        return None
    return round((current - prior) / prior * 100, 2)


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


# ─── KPI Queries ──────────────────────────────────────────────────────────────

async def _fetch_revenue_kpi(period: str) -> Dict[str, Any]:
    date_range = resolve_date_range(period)
    prior_range = get_comparison_range(period)

    c = cfg
    table = sql_table(c.SALES_AI_TABLE)
    date_col = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN   # XnDt
    amt_col = c.SALES_ANALYTICS_AMOUNT_COLUMN
    curr_txn = bill_count_case(date_col, "@startDate", "@endDate")
    prior_txn = bill_count_case(date_col, "@priorStart", "@priorEnd")
    qty_col = quantity_column()
    end_curr = "DATEADD(day,1,CAST(@endDate AS DATE))"
    end_prior = "DATEADD(day,1,CAST(@priorEnd AS DATE))"

    sql = f"""
        SELECT
            ISNULL(SUM(CASE WHEN [{date_col}] >= @startDate AND [{date_col}] < {end_curr}
                     THEN [{amt_col}] ELSE 0 END), 0) AS CurrentRevenue,
            ISNULL(SUM(CASE WHEN [{date_col}] >= @priorStart AND [{date_col}] < {end_prior}
                     THEN [{amt_col}] ELSE 0 END), 0) AS PriorRevenue,
            ISNULL({curr_txn}, 0) AS CurrentTransactions,
            ISNULL({prior_txn}, 0) AS PriorTransactions,
            ISNULL(SUM(CASE WHEN [{date_col}] >= @startDate AND [{date_col}] < {end_curr}
                     THEN [{qty_col}] ELSE 0 END), 0) AS CurrentQuantity,
            ISNULL(SUM(CASE WHEN [{date_col}] >= @priorStart AND [{date_col}] < {end_prior}
                     THEN [{qty_col}] ELSE 0 END), 0) AS PriorQuantity
        FROM {table} WITH (NOLOCK)
        WHERE [{date_col}] >= @priorStart AND [{date_col}] <= @endDate
        OPTION (RECOMPILE)
    """

    result = await execute_query(
        sql,
        params={
            "startDate": date_range.start,
            "endDate": date_range.end,
            "priorStart": prior_range.start,
            "priorEnd": prior_range.end,
        },
        nolock=True,
        recompile=False,   # Already in SQL
    )

    rows = result["records"]
    row = rows[0] if rows else {}

    curr_rev = _safe_float(row.get("CurrentRevenue"))
    prior_rev = _safe_float(row.get("PriorRevenue"))
    curr_txn = _safe_float(row.get("CurrentTransactions"))
    prior_txn = _safe_float(row.get("PriorTransactions"))
    curr_qty = _safe_float(row.get("CurrentQuantity"))
    prior_qty = _safe_float(row.get("PriorQuantity"))

    avg_order = curr_rev / curr_txn if curr_txn > 0 else 0
    prior_avg = prior_rev / prior_txn if prior_txn > 0 else 0

    return {
        "revenue": {
            "value": curr_rev,
            "prior": prior_rev,
            "growth": _growth(curr_rev, prior_rev),
            "period": date_range.label,
        },
        "transactions": {
            "value": int(curr_txn),
            "prior": int(prior_txn),
            "growth": _growth(curr_txn, prior_txn),
            "period": date_range.label,
        },
        "avg_order_value": {
            "value": round(avg_order, 2),
            "prior": round(prior_avg, 2),
            "growth": _growth(avg_order, prior_avg),
            "period": date_range.label,
        },
        "quantity": {
            "value": int(curr_qty),
            "prior": int(prior_qty),
            "growth": _growth(curr_qty, prior_qty),
            "period": date_range.label,
        },
    }


async def _fetch_customer_kpi(period: str) -> Dict[str, Any]:
    if cfg.ANALYTICS_SKIP_CUSTOMER_COUNT:
        return {"customers": {"value": None, "prior": None, "growth": None, "period": period}}

    date_range = resolve_date_range(period)
    prior_range = get_comparison_range(period)

    c = cfg
    table = sql_table(c.CUSTOMER_VIEW)
    date_col = c.CUSTOMERS_FILTER_DATE_COLUMN   # CreatedOn

    sql = f"""
        SELECT
            COUNT(CASE WHEN CAST([{date_col}] AS DATE) >= @startDate
                            AND CAST([{date_col}] AS DATE) <= @endDate
                       THEN 1 END) AS NewCustomers,
            COUNT(CASE WHEN CAST([{date_col}] AS DATE) >= @priorStart
                            AND CAST([{date_col}] AS DATE) <= @priorEnd
                       THEN 1 END) AS PriorCustomers
        FROM {table} WITH (NOLOCK)
        WHERE CAST([{date_col}] AS DATE) >= @priorStart
          AND CAST([{date_col}] AS DATE) <= @endDate
        OPTION (RECOMPILE)
    """

    result = await execute_query(
        sql,
        params={
            "startDate": date_range.start,
            "endDate": date_range.end,
            "priorStart": prior_range.start,
            "priorEnd": prior_range.end,
        },
        nolock=True,
        recompile=False,
    )

    rows = result["records"]
    row = rows[0] if rows else {}
    curr = _safe_float(row.get("NewCustomers"))
    prior = _safe_float(row.get("PriorCustomers"))

    return {
        "customers": {
            "value": int(curr),
            "prior": int(prior),
            "growth": _growth(curr, prior),
            "period": date_range.label,
        }
    }


# ─── Public API ───────────────────────────────────────────────────────────────

async def get_home_kpis(period: str = "mtd") -> Dict[str, Any]:
    """Returns all home-screen KPIs for the given period — always live from SQL Server."""
    try:
        revenue_task = asyncio.create_task(_fetch_revenue_kpi(period))
        customer_task = asyncio.create_task(_fetch_customer_kpi(period))

        rev_data, cust_data = await asyncio.gather(
            revenue_task,
            customer_task,
            return_exceptions=True,
        )

        result: Dict[str, Any] = {}

        if isinstance(rev_data, dict):
            result.update(rev_data)
        else:
            logger.error("Revenue KPI fetch failed", error=str(rev_data))
            result.update({
                "revenue": None,
                "transactions": None,
                "avg_order_value": None,
                "quantity": None,
            })

        if isinstance(cust_data, dict):
            result.update(cust_data)
        else:
            result["customers"] = None

        return result

    except Exception as exc:
        logger.error("get_home_kpis failed", error=str(exc))
        raise

