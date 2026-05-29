"""
Product catalog (item master) + top sellers by revenue from SLS_REPORT.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import resolve_date_range, get_prior_year_range
from src.utils.sql_ref import sql_table
from src.db.mssql import execute_query


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _json_cell(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.hex()
    if isinstance(v, str):
        return v.strip()
    return v


def _serialize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({k: _json_cell(v) for k, v in r.items()})
    return out


def _product_label_expr() -> str:
    """Best-effort readable label from line-level sales rows.

    VW_MB_POWERBI_SLS_REPORT does NOT have an ItemName column.
    Use Itemcode as the human-readable label (it's the product code);
    fall back to ItemId (numeric) if Itemcode is blank.
    """
    # VW_MB_POWERBI_SLS_REPORT confirmed columns (from schema_index):
    # ArticleNo, ItemId, DepartmentShortName, CategoryShortName, SupplierAlias, etc.
    # Use ArticleNo as the human-readable product code; fall back to ItemId.
    return (
        "ISNULL("
        "NULLIF(LTRIM(RTRIM(CAST(ISNULL(T.[ArticleNo],'') AS NVARCHAR(512)))),''), "
        "CAST(T.[ItemId] AS NVARCHAR(100))"
        ")"
    )


async def fetch_product_catalog(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    limit = max(5, min(int(limit), 500))
    offset = max(0, min(int(offset), 500_000))

    return await _fetch_product_catalog_raw(search, limit, offset)


async def _fetch_product_catalog_raw(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    view = sql_table(cfg.PRODUCT_MASTER_VIEW)
    like = None
    where_extra = ""
    params: Dict[str, Any] = {}

    if search and search.strip():
        q = search.strip()[:120]
        like = f"%{q}%"
        where_extra = """
          AND (
            [ItemId] LIKE @like
            OR [Itemcode] LIKE @like
            OR [ArticleNo] LIKE @like
            OR ISNULL([SupplierName],'') LIKE @like
            OR ISNULL([SupplierAlias],'') LIKE @like
            OR ISNULL([DepartmentShortName],'') LIKE @like
            OR ISNULL([CategoryShortName],'') LIKE @like
          )
        """
        params["like"] = like

    count_sql = f"""
        SELECT
            COUNT(1) AS Total,
            COUNT(DISTINCT NULLIF(LTRIM(RTRIM([DepartmentShortName])), '')) AS Departments,
            COUNT(DISTINCT NULLIF(LTRIM(RTRIM([CategoryShortName])), '')) AS Categories,
            COUNT(DISTINCT NULLIF(LTRIM(RTRIM([SupplierName])), '')) AS Suppliers
        FROM {view} WITH (NOLOCK)
        WHERE 1=1 {where_extra}
        OPTION (RECOMPILE)
    """

    data_sql = f"""
        SELECT
            [ItemId],
            [Itemcode],
            [DepartmentShortName],
            [CategoryShortName],
            [ArticleNo],
            [SupplierAlias],
            [SupplierName],
            CAST([ItemMRP] AS FLOAT) AS ItemMRP,
            CAST([PurchasePrice] AS FLOAT) AS PurchasePrice
        FROM {view} WITH (NOLOCK)
        WHERE 1=1 {where_extra}
        ORDER BY [ItemId]
        OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY
        OPTION (RECOMPILE)
    """
    params_data = dict(params)
    params_data["offset"] = offset
    params_data["limit"] = limit

    count_res = await execute_query(count_sql, params=params or None, nolock=False, recompile=False)
    agg = count_res["records"][0] if count_res["records"] else {}

    rows_res = await execute_query(data_sql, params=params_data, nolock=False, recompile=False)

    return {
        "success": True,
        "total_count": int(_safe_float(agg.get("Total"))),
        "distinct_departments": int(_safe_float(agg.get("Departments"))),
        "distinct_categories": int(_safe_float(agg.get("Categories"))),
        "distinct_suppliers": int(_safe_float(agg.get("Suppliers"))),
        "offset": offset,
        "limit": limit,
        "products": _serialize_rows(rows_res["records"]),
    }


async def fetch_top_products(period: str = "mtd", top_n: int = 15) -> List[Dict[str, Any]]:
    n = max(5, min(int(top_n), 80))

    async def _fetch() -> List[Dict[str, Any]]:
        dr = resolve_date_range(period)
        lyr = get_prior_year_range(period)
        c = cfg
        # Use item-level view (has ItemId/ItemName) — SALES_ITEMS_AI_TABLE is SLS_REPORT
        dc  = c.SALES_ITEMS_DATE_COLUMN
        tbl = sql_table(c.SALES_ITEMS_AI_TABLE)
        amt = c.SALES_ITEMS_AMOUNT_COLUMN
        qty = c.SALES_ITEMS_QUANTITY_COLUMN
        lbl = _product_label_expr()

        sql_cur_plain = f"""
            SELECT TOP ({n})
                T.[ItemId] AS ItemId,
                MAX({lbl}) AS Label,
                SUM([{amt}]) AS Revenue,
                SUM([{qty}]) AS Quantity
            FROM {tbl} T WITH (NOLOCK)
            WHERE T.[{dc}] >= @startDate
              AND T.[{dc}] < DATEADD(day, 1, CAST(@endDate AS DATE))
            GROUP BY T.[ItemId]
            ORDER BY SUM([{amt}]) DESC
            OPTION (RECOMPILE)
        """

        try:
            cur = await execute_query(
                sql_cur_plain,
                params={"startDate": dr.start, "endDate": dr.end},
                nolock=False,
                recompile=False,
            )
            records = cur["records"]
        except Exception as exc:
            logger.warning("top products primary query failed", error=str(exc))
            records = []

        if not records:
            fb_sql = f"""
                SELECT TOP ({n})
                    T.[ItemId] AS ItemId,
                    CAST(T.[ItemId] AS NVARCHAR(100)) AS Label,
                    SUM([{amt}]) AS Revenue,
                    SUM([{qty}]) AS Quantity
                FROM {tbl} T WITH (NOLOCK)
                WHERE T.[{dc}] >= @startDate
                  AND T.[{dc}] < DATEADD(day, 1, CAST(@endDate AS DATE))
                GROUP BY T.[ItemId]
                ORDER BY SUM([{amt}]) DESC
                OPTION (RECOMPILE)
            """
            try:
                cur_fb = await execute_query(
                    fb_sql,
                    params={"startDate": dr.start, "endDate": dr.end},
                    nolock=False,
                    recompile=False,
                )
                records = cur_fb["records"]
            except Exception as exc:
                logger.warning("top products fallback failed", error=str(exc))
                records = []

        if not records:
            return []

        ids = [str(r.get("ItemId") or "") for r in records if r.get("ItemId") is not None]
        id_list = "', '".join(x.replace("'", "''") for x in ids if x)

        ly_map: Dict[str, float] = {}
        if id_list:
            ly_sql = f"""
                SELECT
                    T.[ItemId] AS ItemId,
                    SUM([{amt}]) AS Revenue
                FROM {tbl} T WITH (NOLOCK)
                WHERE T.[{dc}] >= @startDate
                  AND T.[{dc}] < DATEADD(day, 1, CAST(@endDate AS DATE))
                  AND CAST(T.[ItemId] AS NVARCHAR(128)) IN ('{id_list}')
                GROUP BY T.[ItemId]
                OPTION (RECOMPILE)
            """
            try:
                ly = await execute_query(
                    ly_sql,
                    params={"startDate": lyr.start, "endDate": lyr.end},
                    nolock=False,
                    recompile=False,
                )
                for r in ly["records"]:
                    k = str(r.get("ItemId", ""))
                    ly_map[k] = _safe_float(r.get("Revenue"))
            except Exception as exc:
                logger.warning("top products LY revenue skipped", error=str(exc))

        total_rev = sum(_safe_float(r.get("Revenue")) for r in records) or 1.0
        out: List[Dict[str, Any]] = []
        for r in records[:n]:
            item_id = str(r.get("ItemId", "") or "")
            rev = _safe_float(r.get("Revenue"))
            qty = int(_safe_float(r.get("Quantity")))
            pct = round((rev / total_rev) * 10000) / 100
            ly = ly_map.get(item_id, 0.0)
            growth: Optional[float]
            if ly > 0:
                growth = round(((rev - ly) / ly) * 10000) / 100
            elif rev > 0 and ly <= 0:
                growth = None
            else:
                growth = 0.0

            out.append(
                {
                    "item_id": item_id,
                    "label": str(r.get("Label") or item_id),
                    "revenue": rev,
                    "quantity": qty,
                    "growth_pct": growth,
                    "share_pct": pct,
                }
            )
        return out

    try:
        return await _fetch()
    except Exception as exc:
        logger.warning("fetch_top_products failed", error=str(exc))
        try:
            return await _fetch()
        except Exception:
            return []
