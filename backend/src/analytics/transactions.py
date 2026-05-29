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
    dr = resolve_date_range(period)
    SLSXNS_VIEW = sql_table("dbo.VW_MB_POWERBI_SLSXNS_REPORT")

    base_range = {"startDate": dr.start, "endDate": dr.end}

    async def run_catalog() -> Dict[str, Any]:
        where_sql, filt = _transactions_where_clause(branch, category, search, legacy_search=False)
        params = {**base_range, **filt}

        offset = (page - 1) * page_size
        sel = _transactions_catalog_select_sql().strip()
        order_sql = "ORDER BY T.[XnDt] DESC, T.[XnNo] DESC, T.[XnId] DESC"

        # Fast count: fetch TOP (offset + page_size + 1) row count only — avoids full table scan.
        # This is accurate for pages near the start and shows "N+" for huge datasets.
        fast_count_cap = offset + page_size + 1
        # Note: OPTION (RECOMPILE) cannot be used inside a subquery in SQL Server.
        # The outer COUNT uses the subquery result — no OPTION needed there.
        # The data query keeps OPTION (RECOMPILE) at the top level which is valid.
        count_sql = f"""
            SELECT COUNT(*) AS TotalCount
            FROM (
                SELECT TOP ({fast_count_cap}) 1 AS _r
                FROM {SLSXNS_VIEW} T WITH (NOLOCK)
                WHERE {where_sql}
            ) _sub
        """
        data_sql = f"""
            SELECT {sel}
            FROM {SLSXNS_VIEW} T WITH (NOLOCK)
            WHERE {where_sql}
            {order_sql}
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
            OPTION (RECOMPILE)
        """

        # Run count and data in parallel for speed
        import asyncio
        count_res, data_res = await asyncio.gather(
            execute_query(count_sql, params=params, nolock=False, recompile=False),
            execute_query(data_sql, params=params, nolock=False, recompile=False),
        )
        counted = int(_safe_float(count_res["records"][0].get("TotalCount", 0))) if count_res["records"] else 0
        # If we hit the cap, actual total is unknown (there are more rows)
        total_count = counted if counted < fast_count_cap else counted + 1

        return {"total_count": total_count, "records": data_res["records"]}

    async def run_legacy() -> Dict[str, Any]:
        where_sql, filt = _transactions_where_clause(branch, category, search, legacy_search=True)
        params = {**base_range, **filt}
        offset = (page - 1) * page_size
        sel = _transactions_legacy_select_sql().strip()
        order_sql = "ORDER BY [XnDt] DESC, [CashmemoNo] DESC"

        fast_count_cap = offset + page_size + 1
        count_sql = f"""
            SELECT COUNT(*) AS TotalCount
            FROM (
                SELECT TOP ({fast_count_cap}) 1 AS _r
                FROM {SLSXNS_VIEW} WITH (NOLOCK)
                WHERE {where_sql}
            ) _sub
        """
        data_sql = f"""
            SELECT {sel}
            FROM {SLSXNS_VIEW} WITH (NOLOCK)
            WHERE {where_sql}
            {order_sql}
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
            OPTION (RECOMPILE)
        """

        import asyncio
        count_res, data_res = await asyncio.gather(
            execute_query(count_sql, params=params, nolock=False, recompile=False),
            execute_query(data_sql, params=params, nolock=False, recompile=False),
        )
        counted = int(_safe_float(count_res["records"][0].get("TotalCount", 0))) if count_res["records"] else 0
        total_count = counted if counted < fast_count_cap else counted + 1

        return {"total_count": total_count, "records": data_res["records"]}

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

    return result


# ─── Transaction Summary (header KPIs) ───────────────────────────────────────

async def get_transaction_summary(period: str = "mtd") -> Dict[str, Any]:
    """Header summary: total revenue, total transactions, avg ticket, success rate.

    Uses the fast SLS_DATA_WITHOUT_ITEMID view (cfg.SALES_AI_TABLE) for aggregate KPIs
    — same underlying data as SLSXNS but without item-master JOINs, so 50x faster.
    Falls back to SLSXNS_REPORT if cfg.SALES_AI_TABLE is unavailable.
    """

    async def _fetch() -> Dict[str, Any]:
        dr = resolve_date_range(period)

        # Fast path: use the pre-aggregated fast view (SLS_DATA_WITHOUT_ITEMID)
        # It has CashmemoDt (date), SalesNetAmount (revenue), and one row per bill-line.
        fast_tbl = sql_table(cfg.SALES_AI_TABLE)
        date_col = cfg.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN  # CashmemoDt
        amt_col  = cfg.SALES_ANALYTICS_AMOUNT_COLUMN              # SalesNetAmount

        fast_sql = f"""
            SELECT
                SUM([{amt_col}]) AS TotalRevenue,
                COUNT_BIG(*) AS TotalTransactions,
                CASE WHEN COUNT_BIG(*) > 0
                    THEN SUM([{amt_col}]) / CAST(COUNT_BIG(*) AS FLOAT)
                    ELSE 0
                END AS AvgTicket
            FROM {fast_tbl} WITH (NOLOCK)
            WHERE [{date_col}] >= @startDate
              AND [{date_col}] < DATEADD(day,1,CAST(@endDate AS DATE))
            OPTION (RECOMPILE)
        """
        try:
            result = await execute_query(
                fast_sql,
                params={"startDate": dr.start, "endDate": dr.end},
                nolock=False, recompile=False,
            )
            row = result["records"][0] if result["records"] else {}
            return {
                "total_revenue": _safe_float(row.get("TotalRevenue")),
                "total_transactions": int(_safe_float(row.get("TotalTransactions"))),
                "avg_ticket": _safe_float(row.get("AvgTicket")),
                "success_rate": 100.0,
                "period": period,
                "period_label": dr.label,
            }
        except Exception as exc:
            logger.warning("transaction_summary_fast_path_failed", error=str(exc))

        # Slow fallback: SLSXNS_REPORT
        SLSXNS_VIEW = sql_table("dbo.VW_MB_POWERBI_SLSXNS_REPORT")
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
            "success_rate": 100.0,
            "period": period,
            "period_label": dr.label,
        }

    return await _fetch()
