"""
Transactions Data
Paginated, filterable transaction list from VW_MB_POWERBI_SLSXNS_REPORT.
Also provides a summary (totals + sparkline) for the header strip.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import resolve_date_range
from src.utils.sql_ref import sql_table
from src.db.mssql import execute_query
from src.analytics.cache import cache


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


# ─── Transaction List ─────────────────────────────────────────────────────────

def _transactions_catalog_select_sql() -> str:
    """Column layout aligned with test/list_transactions_db.py (default / non-legacy)."""
    id_expr = (
        "COALESCE(NULLIF(LTRIM(RTRIM(CAST(ISNULL(T.[XnNo],'') AS NVARCHAR(510)))), ''), "
        "CAST(ISNULL(T.[XnId],'') AS NVARCHAR(510))) AS id"
    )
    return f"""
            {id_expr},
            T.[XnDt]               AS date,
            T.[BranchAlias]        AS branch,
            T.[CategoryShortName]  AS category,
            T.[DepartmentShortName] AS department,
            T.[NetSlsNetAmount]    AS amount,
            CAST(N'' AS NVARCHAR(510)) AS salesperson,
            CAST(T.[XnId] AS NVARCHAR(510)) AS xn_id,
            T.[XnNo]               AS xn_no,
            T.[Itemcode]           AS itemcode,
            T.[NetSlsQty]          AS quantity
    """


def _transactions_legacy_select_sql() -> str:
    """Older builds: CashmemoNo + SalesPersonName (see test/list_transactions_db.py --legacy)."""
    return """
            [CashmemoNo]         AS id,
            [XnDt]               AS date,
            [BranchAlias]        AS branch,
            [CategoryShortName]  AS category,
            [DepartmentShortName] AS department,
            [NetSlsNetAmount]    AS amount,
            ISNULL([SalesPersonName], N'') AS salesperson,
            CAST([XnId] AS NVARCHAR(510)) AS xn_id,
            [XnNo]               AS xn_no,
            [Itemcode]           AS itemcode,
            [NetSlsQty]          AS quantity
    """


def _transactions_where_clause(
    branch: Optional[str],
    category: Optional[str],
    search: Optional[str],
    legacy_search: bool,
) -> tuple[str, Dict[str, Any]]:
    where_clauses = [
        "[XnDt] >= @startDate",
        "[XnDt] < DATEADD(day,1,CAST(@endDate AS DATE))",
    ]
    params: Dict[str, Any] = {}

    if branch:
        where_clauses.append("[BranchAlias] = @branch")
        params["branch"] = branch

    if category:
        where_clauses.append("[CategoryShortName] = @category")
        params["category"] = category

    if search and search.strip():
        pat = f"%{search.strip()}%"
        if legacy_search:
            where_clauses.append("([CashmemoNo] LIKE @search OR [SalesPersonName] LIKE @search)")
        else:
            where_clauses.append(
                "("
                "[XnNo] LIKE @search "
                "OR CAST([XnId] AS NVARCHAR(510)) LIKE @search "
                "OR [Itemcode] LIKE @search"
                ")"
            )
        params["search"] = pat

    return " AND ".join(where_clauses), params


def _row_to_transaction(r: Dict[str, Any]) -> Dict[str, Any]:
    raw = r.get("date")
    if hasattr(raw, "isoformat"):
        date_s = raw.isoformat()[:10]
    else:
        date_s = str(raw or "")[:10]

    qty = r.get("quantity")
    return {
        "id": str(r.get("id") or ""),
        "date": date_s,
        "branch": str(r.get("branch") or ""),
        "category": str(r.get("category") or ""),
        "department": str(r.get("department") or ""),
        "amount": _safe_float(r.get("amount")),
        "salesperson": str(r.get("salesperson") or ""),
        "xn_id": str(r.get("xn_id") or "") if r.get("xn_id") is not None else None,
        "xn_no": str(r.get("xn_no") or "") if r.get("xn_no") is not None else None,
        "itemcode": str(r.get("itemcode") or "") if r.get("itemcode") is not None else None,
        "quantity": int(_safe_float(qty)) if qty is not None else None,
        "status": "completed",
    }


async def get_transactions(
    period: str = "mtd",
    page: int = 1,
    page_size: int = 50,
    branch: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated line-level list from SLSXNS (matches test/list_transactions_db.py defaults).

    Page 1 with no filters is cached on the backend so the Transactions page loads
    instantly (< 20 ms) on every navigation after the first warmup.
    """
    # ── Fast path: serve page-1 / no-filter requests from cache ──────────────
    is_cacheable = (page == 1 and not branch and not category and not search)
    if is_cacheable:
        _cache_key = f"txn:list:v1:{period}:{page_size}"
        _cached, _ = cache.get(_cache_key)
        if _cached is not None:
            return _cached

    dr = resolve_date_range(period)
    SLSXNS_VIEW = sql_table("dbo.VW_MB_POWERBI_SLSXNS_REPORT")

    base_range = {"startDate": dr.start, "endDate": dr.end}

    async def run_catalog() -> Dict[str, Any]:
        where_sql, filt = _transactions_where_clause(branch, category, search, legacy_search=False)
        params = {**base_range, **filt}

        offset = (page - 1) * page_size
        sel = _transactions_catalog_select_sql().strip()
        order_sql = "ORDER BY T.[XnDt] DESC, T.[XnNo] DESC, T.[XnId] DESC"

        count_sql = f"""
            SELECT COUNT_BIG(*) AS TotalCount
            FROM {SLSXNS_VIEW} T WITH (NOLOCK)
            WHERE {where_sql}
            OPTION (RECOMPILE)
        """
        data_sql = f"""
            SELECT {sel}
            FROM {SLSXNS_VIEW} T WITH (NOLOCK)
            WHERE {where_sql}
            {order_sql}
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
            OPTION (RECOMPILE)
        """

        count_result = await execute_query(count_sql, params=params, nolock=False, recompile=False)
        total_count = int(_safe_float(count_result["records"][0].get("TotalCount", 0))) if count_result["records"] else 0

        data_result = await execute_query(data_sql, params=params, nolock=False, recompile=False)
        return {"total_count": total_count, "records": data_result["records"]}

    async def run_legacy() -> Dict[str, Any]:
        where_sql, filt = _transactions_where_clause(branch, category, search, legacy_search=True)
        params = {**base_range, **filt}
        offset = (page - 1) * page_size
        sel = _transactions_legacy_select_sql().strip()
        order_sql = "ORDER BY [XnDt] DESC, [CashmemoNo] DESC"

        count_sql = f"""
            SELECT COUNT_BIG(*) AS TotalCount
            FROM {SLSXNS_VIEW} WITH (NOLOCK)
            WHERE {where_sql}
            OPTION (RECOMPILE)
        """
        data_sql = f"""
            SELECT {sel}
            FROM {SLSXNS_VIEW} WITH (NOLOCK)
            WHERE {where_sql}
            {order_sql}
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
            OPTION (RECOMPILE)
        """

        count_result = await execute_query(count_sql, params=params, nolock=False, recompile=False)
        total_count = int(_safe_float(count_result["records"][0].get("TotalCount", 0))) if count_result["records"] else 0

        data_result = await execute_query(data_sql, params=params, nolock=False, recompile=False)
        return {"total_count": total_count, "records": data_result["records"]}

    try:
        pack = await run_catalog()
    except Exception as exc:
        logger.warning("transactions_catalog_mode_failed_fallback_legacy", error=str(exc))
        pack = await run_legacy()

    transactions = [_row_to_transaction(r) for r in pack["records"]]
    total_count = pack["total_count"]

    result: Dict[str, Any] = {
        "transactions": transactions,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total_count + page_size - 1) // page_size),
        "period": period,
        "period_label": dr.label,
    }

    # ── Write to cache for page-1 / no-filter requests ─────────────────────
    if is_cacheable:
        cache.set(_cache_key, result)  # type: ignore[possibly-undefined]
        logger.debug("Transaction list cached", key=_cache_key, rows=len(transactions))

    return result


# ─── Transaction Summary (header KPIs) ───────────────────────────────────────

async def get_transaction_summary(period: str = "mtd") -> Dict[str, Any]:
    """Header summary: total revenue, total transactions, avg ticket, success rate."""
    cache_key = f"txn:summary:v2:{period}"

    async def _fetch() -> Dict[str, Any]:
        dr = resolve_date_range(period)
        SLSXNS_VIEW = sql_table("dbo.VW_MB_POWERBI_SLSXNS_REPORT")

        # Also get prior period for growth
        # Simple: compare current vs prior of same length
        # Line-item grain (consistent with pagination count and list_transactions_db.py).
        summary_sql = f"""
            SELECT
                SUM([NetSlsNetAmount]) AS TotalRevenue,
                COUNT_BIG(*) AS TotalTransactions,
                CASE WHEN COUNT_BIG(*) > 0
                    THEN SUM([NetSlsNetAmount]) / CAST(COUNT_BIG(*) AS FLOAT)
                    ELSE 0
                END AS AvgTicket
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
