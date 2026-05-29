"""
Charts Data Engine — date-filter bug fixed 2026-05-26.
All WHERE clauses use < DATEADD(day,1,CAST(@endDate AS DATE)) instead of
<= @endDate to correctly include same-day datetime values.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import resolve_date_range, trend_granularity
from src.utils.sql_ref import sql_table
from src.db.mssql import execute_query
from src.analytics.metrics_sql import transactions_aggregate, quantity_column


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0




# ─── Revenue Trend ────────────────────────────────────────────────────────────

async def get_revenue_trend(period: str = "last_30d") -> List[Dict[str, Any]]:
    gran = trend_granularity(period)

    async def _fetch() -> List[Dict[str, Any]]:
        dr = resolve_date_range(period)
        c = cfg
        dc = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
        amt = c.SALES_ANALYTICS_AMOUNT_COLUMN
        qty = quantity_column()

        if gran == "month":
            period_expr = f"FORMAT([{dc}], 'yyyy-MM')"
            label_expr = f"FORMAT([{dc}], 'MMM yyyy')"
            sql = f"""
                SELECT
                    {period_expr} AS PeriodKey,
                    MIN({label_expr}) AS Label,
                    SUM([{amt}]) AS Revenue,
                    {transactions_aggregate()} AS Transactions,
                    SUM([{qty}]) AS Quantity
                FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
                WHERE [{dc}] >= @startDate
                  AND [{dc}] < DATEADD(day,1,CAST(@endDate AS DATE))
                GROUP BY {period_expr}
                ORDER BY PeriodKey ASC
                OPTION (RECOMPILE)
            """
            result = await execute_query(
                sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False,
            )
            return [
                {
                    "date": str(r.get("PeriodKey", "")),
                    "label": str(r.get("Label", r.get("PeriodKey", ""))),
                    "revenue": _safe_float(r.get("Revenue")),
                    "transactions": int(_safe_float(r.get("Transactions"))),
                    "quantity": int(_safe_float(r.get("Quantity"))),
                }
                for r in result["records"]
            ]

        sql = f"""
            SELECT
                CAST([{dc}] AS DATE) AS TransactionDate,
                SUM([{amt}]) AS Revenue,
                {transactions_aggregate()} AS Transactions,
                SUM([{qty}]) AS Quantity
            FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
            WHERE [{dc}] >= @startDate
              AND [{dc}] < DATEADD(day,1,CAST(@endDate AS DATE))
            GROUP BY CAST([{dc}] AS DATE)
            ORDER BY TransactionDate ASC
            OPTION (RECOMPILE)
        """
        result = await execute_query(
            sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False,
        )
        return [
            {
                "date": str(r.get("TransactionDate", "")),
                "label": str(r.get("TransactionDate", ""))[:10],
                "revenue": _safe_float(r.get("Revenue")),
                "transactions": int(_safe_float(r.get("Transactions"))),
                "quantity": int(_safe_float(r.get("Quantity"))),
            }
            for r in result["records"]
        ]

    return await _fetch()


# ─── Category Breakdown ───────────────────────────────────────────────────────

async def get_category_breakdown(period: str = "mtd", top_n: Optional[int] = None) -> List[Dict[str, Any]]:
    n = min(top_n or cfg.ANALYTICS_TOP_N, cfg.ANALYTICS_TOP_N_MAX)

    async def _fetch() -> List[Dict[str, Any]]:
        dr = resolve_date_range(period)
        c = cfg
        dc = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
        sql = f"""
            SELECT TOP {n}
                [{c.SALES_ANALYTICS_CATEGORY_DIM}] AS Category,
                SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) AS Revenue,
                {transactions_aggregate()} AS Transactions,
                CAST(
                    SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) * 100.0
                    / SUM(SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}])) OVER ()
                    AS DECIMAL(10,2)
                ) AS Percentage
            FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
            WHERE [{dc}] >= @startDate
              AND [{dc}] < DATEADD(day,1,CAST(@endDate AS DATE))
            GROUP BY [{c.SALES_ANALYTICS_CATEGORY_DIM}]
            ORDER BY Revenue DESC
            OPTION (RECOMPILE)
        """
        result = await execute_query(sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False)
        return [
            {
                "category": str(r.get("Category", "")),
                "revenue": _safe_float(r.get("Revenue")),
                "transactions": int(_safe_float(r.get("Transactions"))),
                "percentage": _safe_float(r.get("Percentage")),
            }
            for r in result["records"]
        ]

    return await _fetch()


# ─── Branch Bar Chart ─────────────────────────────────────────────────────────

async def get_branch_chart(period: str = "mtd") -> List[Dict[str, Any]]:

    async def _fetch() -> List[Dict[str, Any]]:
        dr = resolve_date_range(period)
        c = cfg
        dc = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
        sql = f"""
            SELECT
                [{c.SALES_ANALYTICS_BRANCH_DIM}] AS Branch,
                SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) AS Revenue,
                {transactions_aggregate()} AS Transactions
            FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
            WHERE [{dc}] >= @startDate
              AND [{dc}] < DATEADD(day,1,CAST(@endDate AS DATE))
            GROUP BY [{c.SALES_ANALYTICS_BRANCH_DIM}]
            ORDER BY Revenue DESC
            OPTION (RECOMPILE)
        """
        result = await execute_query(sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False)
        return [
            {
                "branch": str(r.get("Branch", "")),
                "revenue": _safe_float(r.get("Revenue")),
                "transactions": int(_safe_float(r.get("Transactions"))),
            }
            for r in result["records"]
        ]

    return await _fetch()


# ─── Department Breakdown ─────────────────────────────────────────────────────

async def get_department_chart(period: str = "mtd", top_n: Optional[int] = None) -> List[Dict[str, Any]]:
    n = min(top_n or cfg.ANALYTICS_TOP_N, cfg.ANALYTICS_TOP_N_MAX)

    async def _fetch() -> List[Dict[str, Any]]:
        dr = resolve_date_range(period)
        c = cfg
        dc = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
        sql = f"""
            SELECT TOP {n}
                [{c.SALES_ANALYTICS_DEPARTMENT_DIM}] AS Department,
                SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) AS Revenue,
                {transactions_aggregate()} AS Transactions
            FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
            WHERE [{dc}] >= @startDate
              AND [{dc}] < DATEADD(day,1,CAST(@endDate AS DATE))
              AND NULLIF(LTRIM(RTRIM(CAST([{c.SALES_ANALYTICS_DEPARTMENT_DIM}] AS NVARCHAR(200)))), '') IS NOT NULL
            GROUP BY [{c.SALES_ANALYTICS_DEPARTMENT_DIM}]
            HAVING SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) > 0
            ORDER BY Revenue DESC
            OPTION (RECOMPILE)
        """
        result = await execute_query(sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False)
        rows: List[Dict[str, Any]] = []
        for r in result["records"]:
            name = str(r.get("Department", "")).strip()
            if not name:
                continue
            rows.append({
                "department": name,
                "revenue": _safe_float(r.get("Revenue")),
                "transactions": int(_safe_float(r.get("Transactions"))),
            })
        if rows:
            logger.info("Department chart loaded", period=period, count=len(rows))
        else:
            logger.warning("Department chart returned no rows", period=period, table=c.SALES_AI_TABLE)
        return rows

    return await _fetch()


# ─── Top Salespersons ─────────────────────────────────────────────────────────

async def get_top_salespersons(period: str = "mtd", top_n: int = 10) -> List[Dict[str, Any]]:
    n = min(top_n, cfg.ANALYTICS_TOP_N_MAX)

    async def _fetch() -> List[Dict[str, Any]]:
        dr = resolve_date_range(period)
        c = cfg
        sql = f"""
            SELECT TOP {n}
                SalesPersonName,
                BranchAlias AS Branch,
                SUM([{c.SALESPERSON_AMOUNT_COLUMN}]) AS Revenue,
                COUNT(DISTINCT CashmemoNo) AS Transactions
            FROM {sql_table(c.SALESPERSON_TOPN_VIEW)} WITH (NOLOCK)
            WHERE [{c.SALESPERSON_DATE_COLUMN}] >= @startDate
              AND [{c.SALESPERSON_DATE_COLUMN}] < DATEADD(day,1,CAST(@endDate AS DATE))
            GROUP BY SalesPersonName, BranchAlias
            ORDER BY Revenue DESC
            OPTION (RECOMPILE)
        """
        result = await execute_query(sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False)
        return [
            {
                "name": str(r.get("SalesPersonName", "")),
                "branch": str(r.get("Branch", "")),
                "revenue": _safe_float(r.get("Revenue")),
                "transactions": int(_safe_float(r.get("Transactions"))),
            }
            for r in result["records"]
        ]

    return await _fetch()


# ─── Hourly Heatmap ───────────────────────────────────────────────────────────

async def get_hourly_heatmap(period: str = "last_30d") -> List[Dict[str, Any]]:

    async def _fetch() -> List[Dict[str, Any]]:
        dr = resolve_date_range(period)
        c = cfg
        dc = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
        sql = f"""
            SELECT
                DATEPART(HOUR, [{dc}]) AS HourOfDay,
                DATEPART(WEEKDAY, [{dc}]) AS DayOfWeek,
                SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) AS Revenue,
                {transactions_aggregate()} AS Transactions
            FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
            WHERE [{dc}] >= @startDate
              AND [{dc}] < DATEADD(day,1,CAST(@endDate AS DATE))
            GROUP BY DATEPART(HOUR, [{dc}]), DATEPART(WEEKDAY, [{dc}])
            ORDER BY DayOfWeek, HourOfDay
            OPTION (RECOMPILE)
        """
        result = await execute_query(sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False)
        day_names = ["", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        return [
            {
                "hour": int(_safe_float(r.get("HourOfDay"))),
                "day": day_names[int(_safe_float(r.get("DayOfWeek")))],
                "day_num": int(_safe_float(r.get("DayOfWeek"))),
                "revenue": _safe_float(r.get("Revenue")),
                "transactions": int(_safe_float(r.get("Transactions"))),
            }
            for r in result["records"]
        ]

    return await _fetch()


# ─── Branch Detail ────────────────────────────────────────────────────────────

async def get_branch_detail(branch_alias: str, period: str = "last_14d") -> Dict[str, Any]:
    dr = resolve_date_range(period)
    c = cfg
    dc = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN

    trend_sql = f"""
        SELECT
            CAST([{dc}] AS DATE) AS TransactionDate,
            SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) AS Revenue,
            COUNT(*) AS Transactions
        FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
        WHERE [{dc}] >= @startDate
          AND [{dc}] < DATEADD(day,1,CAST(@endDate AS DATE))
          AND [{c.SALES_ANALYTICS_BRANCH_DIM}] = @branch
        GROUP BY CAST([{dc}] AS DATE)
        ORDER BY TransactionDate ASC
        OPTION (RECOMPILE)
    """

    result = await execute_query(
        trend_sql,
        params={"startDate": dr.start, "endDate": dr.end, "branch": branch_alias},
        nolock=False, recompile=False,
    )
    trend = [
        {
            "date": str(r.get("TransactionDate", "")),
            "revenue": _safe_float(r.get("Revenue")),
            "transactions": int(_safe_float(r.get("Transactions"))),
        }
        for r in result["records"]
    ]

    total_rev = sum(d["revenue"] for d in trend)
    total_txn = sum(d["transactions"] for d in trend)

    return {
        "branch": branch_alias,
        "period": period,
        "period_label": dr.label,
        "total_revenue": total_rev,
        "total_transactions": total_txn,
        "avg_daily_revenue": total_rev / max(len(trend), 1),
        "trend": trend,
    }
