"""
Combined analytics module.

Merges: cache.py, metrics_sql.py, transactions.py, kpi.py, charts.py, dashboard.py, warmup.py
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

from src.config import cfg
from src.db.mssql import execute_query
from src.utils.date_utils import (
    DateRange,
    get_comparison_range,
    get_prior_year_range,
    resolve_custom_range,
    resolve_date_range,
    trend_granularity,
)
from src.utils.logger import logger
from src.utils.sql_ref import sql_table


# =============================================================================
# cache.py
# =============================================================================
"""
Analytics Cache
TTL-based in-memory cache with stale-while-revalidate support.
Used for KPI and chart queries to avoid redundant SQL Server hits.
"""


# ─── Entry ────────────────────────────────────────────────────────────────────

@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl_s: float
    key: str
    hits: int = 0

    @property
    def age_s(self) -> float:
        return time.time() - self.created_at

    @property
    def is_fresh(self) -> bool:
        return self.age_s < self.ttl_s

    @property
    def is_stale_ok(self) -> bool:
        """Stale-while-revalidate: serve for up to N×TTL if fresh data is unavailable."""
        stale_ttl = self.ttl_s * cfg.ANALYTICS_STALE_TTL_MULTIPLIER
        return self.age_s < stale_ttl


# ─── Cache Store ──────────────────────────────────────────────────────────────

class AnalyticsCache:
    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}
        self._stats = {"hits": 0, "misses": 0, "stale_hits": 0}
        self._default_ttl_s = cfg.ANALYTICS_CACHE_TTL_MS / 1000
        self._revalidating: Dict[str, bool] = {}

    def get(self, key: str) -> Tuple[Optional[Any], bool]:
        """
        Returns (value, is_fresh).
        - (value, True)  → fresh hit
        - (value, False) → stale hit (revalidation needed)
        - (None, False)  → miss
        """
        entry = self._store.get(key)
        if entry is None:
            self._stats["misses"] += 1
            return None, False

        entry.hits += 1

        if entry.is_fresh:
            self._stats["hits"] += 1
            return entry.value, True

        if entry.is_stale_ok:
            self._stats["stale_hits"] += 1
            return entry.value, False

        # Expired beyond stale window — delete
        del self._store[key]
        self._stats["misses"] += 1
        return None, False

    def set(self, key: str, value: Any, ttl_s: Optional[float] = None) -> None:
        ttl = ttl_s if ttl_s is not None else self._default_ttl_s
        self._store[key] = CacheEntry(value=value, created_at=time.time(), ttl_s=ttl, key=key)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Delete all keys that start with prefix."""
        to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in to_delete:
            del self._store[k]
        return len(to_delete)

    def clear(self) -> int:
        n = len(self._store)
        self._store.clear()
        return n

    def stats(self) -> Dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"] + self._stats["stale_hits"]
        hit_rate = (self._stats["hits"] / total * 100) if total else 0
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate_pct": round(hit_rate, 1),
            "entries": len(self._store),
        }

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable,
        ttl_s: Optional[float] = None,
    ) -> Any:
        """
        Cache-aside with stale-while-revalidate:
        1. Fresh hit  → return immediately
        2. Stale hit  → return stale, trigger background refresh
        3. Miss       → fetch, cache, return
        """
        value, is_fresh = self.get(key)

        if is_fresh:
            return value

        if value is not None:
            # Stale — return immediately and refresh in background
            if not self._revalidating.get(key):
                self._revalidating[key] = True
                asyncio.create_task(self._background_refresh(key, fetch_fn, ttl_s))
            return value

        # Miss — fetch synchronously
        result = await fetch_fn()
        self.set(key, result, ttl_s)
        return result

    async def _background_refresh(
        self, key: str, fetch_fn: Callable, ttl_s: Optional[float]
    ) -> None:
        try:
            result = await fetch_fn()
            self.set(key, result, ttl_s)
            logger.debug("Cache background refresh complete", key=key)
        except Exception as exc:
            logger.warning("Cache background refresh failed", key=key, error=str(exc))
        finally:
            self._revalidating.pop(key, None)


# ─── Singleton ────────────────────────────────────────────────────────────────

cache = AnalyticsCache()


# =============================================================================
# metrics_sql.py
# =============================================================================
"""SQL fragments for sales KPIs (row-count vs BillCount, quantity column)."""


def quantity_column() -> str:
    return cfg.SALES_ANALYTICS_QUANTITY_COLUMN


def bill_count_case(date_col: str, start_ref: str, end_ref: str) -> str:
    """Conditional aggregate for bills/transactions in a date window."""
    if cfg.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        return (
            f"SUM(CASE WHEN [{date_col}] >= {start_ref} AND [{date_col}] <= {end_ref} "
            f"THEN 1 ELSE 0 END)"
        )
    col = cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN
    return (
        f"SUM(CASE WHEN [{date_col}] >= {start_ref} AND [{date_col}] <= {end_ref} "
        f"THEN [{col}] ELSE 0 END)"
    )


def transactions_aggregate() -> str:
    """Aggregate for GROUP BY charts (line items = rows on SLS_REPORT)."""
    if cfg.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        return "COUNT(*)"
    return f"SUM([{cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN}])"


# =============================================================================
# transactions.py
# =============================================================================
"""
Transactions Data
Paginated, filterable transaction list from VW_MB_POWERBI_SLSXNS_REPORT.
Also provides a summary (totals + sparkline) for the header strip.
"""


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


# ─── Transaction List ─────────────────────────────────────────────────────────

async def get_transactions(
    period: str = "mtd",
    page: int = 1,
    page_size: int = 50,
    branch: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated transaction list from SLSXNS view."""
    dr = resolve_date_range(period)

    # SLSXNS view: CashmemoNo, XnDt, BranchAlias, CategoryShortName,
    #              DepartmentShortName, NetSlsNetAmount, SalesPersonName, etc.
    SLSXNS_VIEW = sql_table("dbo.VW_MB_POWERBI_SLSXNS_REPORT")

    where_clauses = [
        "[XnDt] >= @startDate",
        "[XnDt] < DATEADD(day,1,CAST(@endDate AS DATE))",
    ]
    params: Dict[str, Any] = {
        "startDate": dr.start,
        "endDate": dr.end,
    }

    if branch:
        where_clauses.append("[BranchAlias] = @branch")
        params["branch"] = branch

    if category:
        where_clauses.append("[CategoryShortName] = @category")
        params["category"] = category

    if search:
        where_clauses.append("([CashmemoNo] LIKE @search OR [SalesPersonName] LIKE @search)")
        params["search"] = f"%{search}%"

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * page_size

    # Count query
    count_sql = f"""
        SELECT COUNT(*) AS TotalCount
        FROM {SLSXNS_VIEW} WITH (NOLOCK)
        WHERE {where_sql}
        OPTION (RECOMPILE)
    """

    # Data query with pagination
    data_sql = f"""
        SELECT
            [CashmemoNo]         AS id,
            [XnDt]               AS date,
            [BranchAlias]        AS branch,
            [CategoryShortName]  AS category,
            [DepartmentShortName] AS department,
            [NetSlsNetAmount]    AS amount,
            [SalesPersonName]    AS salesperson
        FROM {SLSXNS_VIEW} WITH (NOLOCK)
        WHERE {where_sql}
        ORDER BY [XnDt] DESC, [CashmemoNo] DESC
        OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
        OPTION (RECOMPILE)
    """

    try:
        count_result = await execute_query(count_sql, params=params, nolock=False, recompile=False)
        total_count = int(_safe_float(count_result["records"][0].get("TotalCount", 0))) if count_result["records"] else 0

        data_result = await execute_query(data_sql, params=params, nolock=False, recompile=False)
        transactions = [
            {
                "id": str(r.get("id", "")),
                "date": str(r.get("date", ""))[:10],
                "branch": str(r.get("branch", "")),
                "category": str(r.get("category", "")),
                "department": str(r.get("department", "")),
                "amount": _safe_float(r.get("amount")),
                "salesperson": str(r.get("salesperson", "")),
                "status": "completed",  # SLSXNS = completed transactions
            }
            for r in data_result["records"]
        ]

        return {
            "transactions": transactions,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total_count + page_size - 1) // page_size),
            "period": period,
            "period_label": dr.label,
        }
    except Exception as exc:
        logger.error("transactions_fetch_failed", error=str(exc))
        raise


# ─── Transaction Summary (header KPIs) ───────────────────────────────────────

async def get_transaction_summary(period: str = "mtd") -> Dict[str, Any]:
    """Header summary: total revenue, total transactions, avg ticket, success rate."""
    cache_key = f"txn:summary:{period}"

    async def _fetch() -> Dict[str, Any]:
        dr = resolve_date_range(period)
        SLSXNS_VIEW = sql_table("dbo.VW_MB_POWERBI_SLSXNS_REPORT")

        # Also get prior period for growth
        # Simple: compare current vs prior of same length
        summary_sql = f"""
            SELECT
                SUM([NetSlsNetAmount]) AS TotalRevenue,
                COUNT(DISTINCT [CashmemoNo]) AS TotalTransactions,
                AVG([NetSlsNetAmount]) AS AvgTicket
            FROM {SLSXNS_VIEW} WITH (NOLOCK)
            WHERE [XnDt] >= @startDate
              AND [XnDt] < DATEADD(day,1,CAST(@endDate AS DATE))
            OPTION (RECOMPILE)
        """
        result = await execute_query(
            summary_sql,
            params={"startDate": dr.start, "endDate": dr.end},
            nolock=False, recompile=False,
        )
        row = result["records"][0] if result["records"] else {}
        return {
            "total_revenue": _safe_float(row.get("TotalRevenue")),
            "total_transactions": int(_safe_float(row.get("TotalTransactions"))),
            "avg_ticket": _safe_float(row.get("AvgTicket")),
            "success_rate": 100.0,  # SLSXNS = completed transactions only
            "period": period,
            "period_label": dr.label,
        }

    return await cache.get_or_fetch(cache_key, _fetch)


# =============================================================================
# kpi.py
# =============================================================================
"""
KPI Analytics Engine
Computes home-dashboard KPIs: revenue, transactions, avg order value, customers.
All figures include period-over-period comparison with growth rates.
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _growth(current: float, prior: float) -> Optional[float]:
    if prior == 0:
        return None
    return round((current - prior) / prior * 100, 2)


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

    sql = f"""
        SELECT
            ISNULL(SUM(CASE WHEN [{date_col}] >= @startDate AND [{date_col}] <= @endDate
                     THEN [{amt_col}] ELSE 0 END), 0) AS CurrentRevenue,
            ISNULL(SUM(CASE WHEN [{date_col}] >= @priorStart AND [{date_col}] <= @priorEnd
                     THEN [{amt_col}] ELSE 0 END), 0) AS PriorRevenue,
            ISNULL({curr_txn}, 0) AS CurrentTransactions,
            ISNULL({prior_txn}, 0) AS PriorTransactions
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
    """
    Returns all home-screen KPIs for the given period.
    Results are cached; stale data is served while a background refresh runs.
    """
    cache_key = f"kpi:v2:{period}"

    async def _fetch() -> Dict[str, Any]:
        try:
            # Run revenue and customer KPIs concurrently
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
                result.update({"revenue": None, "transactions": None, "avg_order_value": None})

            if isinstance(cust_data, dict):
                result.update(cust_data)
            else:
                result["customers"] = None

            return result

        except Exception as exc:
            logger.error("get_home_kpis failed", error=str(exc))
            raise

    return await cache.get_or_fetch(cache_key, _fetch)


# =============================================================================
# charts.py
# =============================================================================
"""
Charts Data Engine — date-filter bug fixed 2026-05-26.
All WHERE clauses use < DATEADD(day,1,CAST(@endDate AS DATE)) instead of
<= @endDate to correctly include same-day datetime values.
"""


# ─── Revenue Trend ────────────────────────────────────────────────────────────

async def get_revenue_trend(period: str = "last_30d") -> List[Dict[str, Any]]:
    cache_key = f"chart:trend:v2:{period}"

    async def _fetch() -> List[Dict[str, Any]]:
        dr = resolve_date_range(period)
        c = cfg
        dc = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
        sql = f"""
            SELECT
                CAST([{dc}] AS DATE) AS TransactionDate,
                SUM([{c.SALES_ANALYTICS_AMOUNT_COLUMN}]) AS Revenue,
                {transactions_aggregate()} AS Transactions
            FROM {sql_table(c.SALES_AI_TABLE)} WITH (NOLOCK)
            WHERE [{dc}] >= @startDate
              AND [{dc}] < DATEADD(day,1,CAST(@endDate AS DATE))
            GROUP BY CAST([{dc}] AS DATE)
            ORDER BY TransactionDate ASC
            OPTION (RECOMPILE)
        """
        result = await execute_query(sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False)
        return [
            {
                "date": str(r.get("TransactionDate", "")),
                "revenue": _safe_float(r.get("Revenue")),
                "transactions": int(_safe_float(r.get("Transactions"))),
            }
            for r in result["records"]
        ]

    return await cache.get_or_fetch(cache_key, _fetch)


# ─── Category Breakdown ───────────────────────────────────────────────────────

async def get_category_breakdown(period: str = "mtd", top_n: Optional[int] = None) -> List[Dict[str, Any]]:
    n = min(top_n or cfg.ANALYTICS_TOP_N, cfg.ANALYTICS_TOP_N_MAX)
    cache_key = f"chart:category:v2:{period}:{n}"

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

    return await cache.get_or_fetch(cache_key, _fetch)


# ─── Branch Bar Chart ─────────────────────────────────────────────────────────

async def get_branch_chart(period: str = "mtd") -> List[Dict[str, Any]]:
    cache_key = f"chart:branch:v2:{period}"

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

    return await cache.get_or_fetch(cache_key, _fetch)


# ─── Department Breakdown ─────────────────────────────────────────────────────

async def get_department_chart(period: str = "mtd", top_n: Optional[int] = None) -> List[Dict[str, Any]]:
    n = min(top_n or cfg.ANALYTICS_TOP_N, cfg.ANALYTICS_TOP_N_MAX)
    cache_key = f"chart:department:v2:{period}:{n}"

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
            GROUP BY [{c.SALES_ANALYTICS_DEPARTMENT_DIM}]
            ORDER BY Revenue DESC
            OPTION (RECOMPILE)
        """
        result = await execute_query(sql, params={"startDate": dr.start, "endDate": dr.end}, nolock=False, recompile=False)
        return [
            {
                "department": str(r.get("Department", "")),
                "revenue": _safe_float(r.get("Revenue")),
                "transactions": int(_safe_float(r.get("Transactions"))),
            }
            for r in result["records"]
        ]

    return await cache.get_or_fetch(cache_key, _fetch)


# ─── Top Salespersons ─────────────────────────────────────────────────────────

async def get_top_salespersons(period: str = "mtd", top_n: int = 10) -> List[Dict[str, Any]]:
    n = min(top_n, cfg.ANALYTICS_TOP_N_MAX)
    cache_key = f"chart:salesperson:v2:{period}:{n}"

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

    return await cache.get_or_fetch(cache_key, _fetch)


# ─── Hourly Heatmap ───────────────────────────────────────────────────────────

async def get_hourly_heatmap(period: str = "last_30d") -> List[Dict[str, Any]]:
    cache_key = f"chart:heatmap:v2:{period}"

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

    return await cache.get_or_fetch(cache_key, _fetch)


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


# =============================================================================
# dashboard.py
# =============================================================================
"""
Sales analytics dashboard — summary KPIs, YoY trend, contribution breakdown, checksum.
"""


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
        OPTION (RECOMPILE)
    """
    result = await execute_query(
        sql,
        params={
            "startDate": dr.start,
            "endDate": dr.end,
            "lyStart": ly_dr.start,
            "lyEnd": ly_dr.end,
        },
        nolock=False,
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
    sql = f"""
        SELECT COUNT(DISTINCT CustomerId) AS Cnt
        FROM {sql_table(c.SALES_VIEW)} WITH (NOLOCK)
        WHERE [{c.SALES_FILTER_DATE_COLUMN}] >= @startDate
          AND [{c.SALES_FILTER_DATE_COLUMN}] < DATEADD(day,1,CAST(@endDate AS DATE))
        OPTION (RECOMPILE)
    """
    try:
        result = await execute_query(
            sql,
            params={"startDate": dr.start, "endDate": dr.end},
            nolock=True,
            recompile=False,
        )
        cnt = int(_safe_float(result["records"][0].get("Cnt") if result["records"] else 0))
        logger.info("👥 customers counted", date_range=f"{dr.start} → {dr.end}", customers=cnt)
        return cnt
    except Exception as exc:
        logger.warning("⚠️  customer count failed", error=str(exc))
        return None


async def _query_trend(dr: DateRange, ly_dr: DateRange, granularity: str) -> List[Dict[str, Any]]:
    from datetime import date as dt

    c = cfg
    table = sql_table(c.SALES_AI_TABLE)
    date_col = c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
    amt_col = c.SALES_ANALYTICS_AMOUNT_COLUMN
    qty_col = quantity_column()
    bills_agg = transactions_aggregate()

    if granularity == "month":
        period_expr = f"FORMAT([{date_col}], 'yyyy-MM')"
        label_expr = f"FORMAT([{date_col}], 'MMM yyyy')"
    else:
        period_expr = f"CAST([{date_col}] AS DATE)"
        label_expr = f"FORMAT(CAST([{date_col}] AS DATE), 'dd-MMM')"

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

    curr_res = await execute_query(
        sql_curr,
        params={"startDate": dr.start, "endDate": dr.end},
        nolock=False,
        recompile=False,
    )
    ly_res = await execute_query(
        sql_ly,
        params={"lyStart": ly_dr.start, "lyEnd": ly_dr.end},
        nolock=False,
        recompile=False,
    )

    ly_map: Dict[str, float] = {}
    for r in ly_res["records"]:
        key = str(r.get("PeriodKey", ""))[:10]
        if granularity == "month" and len(key) >= 7:
            ly_map[key[5:7]] = _safe_float(r.get("Revenue"))
        else:
            try:
                d = dt.fromisoformat(key)
                ly_map[d.isoformat()] = _safe_float(r.get("Revenue"))
            except ValueError:
                ly_map[key] = _safe_float(r.get("Revenue"))

    points: List[Dict[str, Any]] = []
    for r in curr_res["records"]:
        key = str(r.get("PeriodKey", ""))[:10]
        label = str(r.get("Label", key))
        if granularity == "month" and len(key) >= 7:
            prior = ly_map.get(key[5:7], 0)
        else:
            try:
                d = dt.fromisoformat(key)
                prior = ly_map.get(d.replace(year=d.year - 1).isoformat(), 0)
            except ValueError:
                prior = ly_map.get(key, 0)
        points.append({
            "label": label,
            "date": key,
            "current": _safe_float(r.get("Revenue")),
            "prior": prior,
            "bills": int(_safe_float(r.get("Bills"))),
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
        OPTION (RECOMPILE)
    """
    result = await execute_query(
        sql,
        params={"startDate": dr.start, "endDate": dr.end},
        nolock=False,
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
) -> Dict[str, Any]:
    cache_key = f"dashboard:v4:{period}:{start_date}:{end_date}"

    logger.info("🔍 dashboard requested", period=period, cache_key=cache_key)

    async def _fetch() -> Dict[str, Any]:
        logger.info("💾 cache miss — querying SQL Server", period=period)
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
        summary = await _query_summary(dr, ly_dr)
        customers = await _query_customers(dr)
        trend = await _query_trend(dr, ly_dr, gran)
        categories = await _query_contribution(dr, "category", cfg.ANALYTICS_TOP_N_MAX)
        branches = await _query_contribution(dr, "branch", cfg.ANALYTICS_TOP_N_MAX)

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

    return await cache.get_or_fetch(cache_key, _fetch)


# =============================================================================
# warmup.py
# =============================================================================
"""
Cache Warmup Engine
Pre-populates the analytics cache on startup and periodically thereafter.
This ensures the first user request gets fast cached data, not a cold SQL Server hit.
"""


# ─── Warmup Tasks ─────────────────────────────────────────────────────────────

async def _run_warmup_task(name: str, fn: Callable[[], Coroutine[Any, Any, Any]]) -> None:
    try:
        await fn()
        logger.debug("Cache warmed", key=name)
    except Exception as exc:
        logger.warning("Cache warmup task failed", task=name, error=str(exc))
    finally:
        # Pause between queries to avoid hammering SQL Server on startup
        await asyncio.sleep(cfg.ANALYTICS_WARMUP_PAUSE_MS / 1000)


async def warmup_all() -> None:
    """Run all warmup tasks sequentially (respecting the pause between each).

    Priority order:
    1. Dashboard (mtd) — what the home page loads immediately
    2. Dashboard (qtd, ytd, last_6m) — Analytics page period tabs
    3. KPI + chart breakdowns for mtd and last_30d
    """
    tasks: List[tuple[str, Callable]] = []

    # Phase 1: Dashboard endpoint — highest priority (what useDashboard() calls)
    for period in ["mtd", "last_30d", "qtd", "ytd", "last_6m"]:
        tasks.append((f"dashboard:{period}", lambda p=period: get_dashboard(p)))

    # Phase 2: KPI + chart breakdowns for mtd and last_30d
    for period in ["mtd", "last_30d"]:
        tasks.extend([
            (f"kpi:{period}", lambda p=period: get_home_kpis(p)),
            (f"trend:{period}", lambda p=period: get_revenue_trend(p)),
            (f"category:{period}", lambda p=period: get_category_breakdown(p)),
            (f"branch:{period}", lambda p=period: get_branch_chart(p)),
            (f"department:{period}", lambda p=period: get_department_chart(p)),
            (f"salesperson:{period}", lambda p=period: get_top_salespersons(p)),
        ])

    logger.info("Starting cache warmup", task_count=len(tasks))

    for name, fn in tasks:
        await _run_warmup_task(name, fn)

    stats = cache.stats()
    logger.info("Cache warmup complete", **stats)


# ─── Background Warmer ────────────────────────────────────────────────────────

_warmer_task: asyncio.Task | None = None


async def start_background_warmer() -> None:
    """
    Starts a background task that re-warms the cache at the configured interval.
    Typically called once at application startup.
    """
    global _warmer_task

    if not cfg.ANALYTICS_WARMUP:
        logger.info("Cache warmup disabled")
        return

    async def _loop() -> None:
        # Initial warmup on startup
        await warmup_all()

        interval_s = cfg.ANALYTICS_WARMUP_INTERVAL_MS / 1000
        logger.info("Cache warmer scheduled", interval_s=interval_s)

        while True:
            await asyncio.sleep(interval_s)
            logger.info("Scheduled cache re-warm triggered")
            await warmup_all()

    _warmer_task = asyncio.create_task(_loop())
    logger.info("Background cache warmer started")


async def stop_background_warmer() -> None:
    global _warmer_task
    if _warmer_task and not _warmer_task.done():
        _warmer_task.cancel()
        try:
            await _warmer_task
        except asyncio.CancelledError:
            pass
    _warmer_task = None
    logger.info("Background cache warmer stopped")
