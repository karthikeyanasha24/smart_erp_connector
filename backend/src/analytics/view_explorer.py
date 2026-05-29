"""
ERP view catalog + paginated row browser (whitelist-only dynamic SQL).

Performance:
  - Fetch page rows FIRST (user sees data quickly).
  - Dimension / master views skip full COUNT(*) (avoids 10+ minute scans).
  - Fact views use a capped count (TOP hard_cap+1) instead of scanning the whole view.
  - Not queued behind dashboard warmup (see analytics route).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.analytics.cache import cache
from src.config import cfg
from src.db.mssql import execute_query
from src.utils.logger import logger
from src.utils.sql_ref import sql_table

_CATALOG_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "data" / "view_catalog.json",
    Path(__file__).resolve().parents[3] / "test" / "erp_semantic_layer.json",
]

_VIEW_CACHE_TTL_S = 600.0  # 10 min — dimension pages are small and stable


@lru_cache()
def _load_catalog() -> Dict[str, Any]:
    for path in _CATALOG_CANDIDATES:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {
                "database": raw.get("database", ""),
                "view_categories": raw.get("view_categories") or {},
                "views": raw.get("views") or {},
            }
    return {"database": "", "view_categories": {}, "views": {}}


def _view_entry(view_key: str) -> Dict[str, Any]:
    views = _load_catalog().get("views") or {}
    entry = views.get(view_key)
    if not entry or not entry.get("fqn"):
        raise ValueError(f"Unknown view key '{view_key}'")
    return entry


def _is_dimension(entry: Dict[str, Any]) -> bool:
    grain = (entry.get("grain") or "").lower()
    purpose = (entry.get("purpose") or "").lower()
    if grain in ("dimension", "master", "lookup"):
        return True
    if "master" in purpose and "transaction" not in purpose:
        return True
    return False


def _select_list(entry: Dict[str, Any]) -> str:
    display = entry.get("display_cols")
    if isinstance(display, list) and display:
        return ", ".join(f"[{str(c)}]" for c in display)
    return "*"


def _order_clause(entry: Dict[str, Any], select_list: str) -> str:
    for key in ("branch_col", "date_col"):
        col = entry.get(key)
        if col:
            return f"ORDER BY [{col}]"
    display = entry.get("display_cols")
    if isinstance(display, list) and display:
        return f"ORDER BY [{display[0]}]"
    return "ORDER BY (SELECT NULL)"


def _align_rows(columns: List[str], records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Match row keys to column names (ODBC/pymssql casing differences)."""
    if not columns or not records:
        return records
    out: List[Dict[str, Any]] = []
    for row in records:
        lower_map = {str(k).lower(): k for k in row.keys()}
        aligned: Dict[str, Any] = {}
        for col in columns:
            if col in row:
                aligned[col] = row[col]
            else:
                src = lower_map.get(col.lower())
                aligned[col] = row[src] if src is not None else None
        out.append(aligned)
    return out


async def _capped_row_count(table: str, hard_cap: int) -> Tuple[int, int, bool]:
    """
    Count rows up to hard_cap+1. Returns (total_count_for_ui, total_raw_estimate, capped).
    """
    probe = hard_cap + 1
    sql = f"""
        SELECT COUNT(1) AS Total FROM (
            SELECT TOP ({probe}) 1 AS _x FROM {table} WITH (NOLOCK)
        ) AS bounded
    """
    res = await execute_query(sql, nolock=False, recompile=False)
    raw = int((res.get("records") or [{}])[0].get("Total") or 0)
    if raw > hard_cap:
        return hard_cap, raw, True
    return raw, raw, False


async def _fetch_page_rows(
    table: str,
    entry: Dict[str, Any],
    offset: int,
    limit: int,
) -> Tuple[List[Dict[str, Any]], List[str], int]:
    select_list = _select_list(entry)
    order_sql = _order_clause(entry, select_list)
    data_sql = f"""
        SELECT {select_list}
        FROM {table} WITH (NOLOCK)
        {order_sql}
        OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY
    """
    data_res = await execute_query(
        data_sql,
        params={"offset": offset, "limit": limit},
        nolock=False,
        recompile=False,
    )
    records = data_res.get("records") or []
    columns = list(records[0].keys()) if records else []

    if not columns and offset == 0:
        probe = await execute_query(
            f"SELECT TOP 1 {select_list} FROM {table} WITH (NOLOCK)",
            nolock=False,
            recompile=False,
        )
        probe_rows = probe.get("records") or []
        if probe_rows:
            columns = list(probe_rows[0].keys())

    records = _align_rows(columns, records)
    duration = int(data_res.get("duration") or 0)
    return records, columns, duration


def list_catalog_views() -> Dict[str, Any]:
    catalog = _load_catalog()
    views = catalog.get("views") or {}
    items: List[Dict[str, Any]] = []
    for key, meta in sorted(views.items(), key=lambda kv: (kv[1].get("catalog_no") or 999, kv[0])):
        fqn = str(meta.get("fqn") or "")
        short = fqn.split(".")[-1] if fqn else key
        items.append({
            "key": key,
            "fqn": fqn,
            "short_name": short,
            "catalog_no": meta.get("catalog_no"),
            "purpose": meta.get("purpose") or "",
            "grain": meta.get("grain") or "",
            "column_count": meta.get("column_count"),
            "date_col": meta.get("date_col"),
            "amount_col": meta.get("amount_col"),
            "branch_col": meta.get("branch_col"),
            "note": meta.get("note"),
        })
    return {
        "database": catalog.get("database") or cfg.mssql_database,
        "view_count": len(items),
        "views": items,
        "categories": catalog.get("view_categories") or {},
    }


async def fetch_view_page(
    view_key: str,
    page: int = 1,
    page_size: int = 50,
    skip_count: Optional[bool] = None,
) -> Dict[str, Any]:
    entry = _view_entry(view_key)
    fqn = str(entry["fqn"])
    table = sql_table(fqn)
    dimension = _is_dimension(entry)
    if skip_count is None:
        skip_count = dimension

    page = max(1, int(page))
    page_size = max(5, min(int(page_size), 500))
    offset = (page - 1) * page_size
    hard_cap = max(1_000, int(cfg.DATASET_HARD_CAP))

    cache_key = f"view:v2:{view_key}:{page}:{page_size}:sc={int(skip_count)}"
    cached, fresh = cache.get(cache_key)
    if fresh and cached is not None:
        return cached

    records, columns, duration_ms = await _fetch_page_rows(table, entry, offset, page_size)
    has_more = len(records) >= page_size

    total_raw: Optional[int] = None
    capped = False
    if skip_count:
        # Pagination without full scan: show rows now, approximate totals.
        if has_more:
            total_count = page * page_size + 1
            total_pages = page + 1
        else:
            total_count = offset + len(records)
            total_pages = max(1, page)
        total_raw = total_count
    else:
        total_count, total_raw, capped = await _capped_row_count(table, hard_cap)
        total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count else 1

    payload = {
        "view_key": view_key,
        "fqn": fqn,
        "short_name": fqn.split(".")[-1],
        "purpose": entry.get("purpose") or "",
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_raw": total_raw,
        "total_pages": total_pages,
        "capped": capped,
        "hard_cap": hard_cap,
        "columns": columns,
        "rows": records,
        "duration_ms": duration_ms,
        "count_skipped": skip_count,
        "has_more": has_more,
    }

    ttl = _VIEW_CACHE_TTL_S if dimension else min(_VIEW_CACHE_TTL_S, 120.0)
    cache.set(cache_key, payload, ttl_s=ttl)
    logger.info(
        "view_page_loaded",
        view=view_key,
        page=page,
        rows=len(records),
        count_skipped=skip_count,
        duration_ms=duration_ms,
    )
    return payload
