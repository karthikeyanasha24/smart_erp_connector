"""
ERP view catalog + paginated row browser (whitelist-only dynamic SQL).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import cfg
from src.db.mssql import execute_query
from src.utils.sql_ref import sql_table

_CATALOG_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "data" / "view_catalog.json",
    Path(__file__).resolve().parents[3] / "test" / "erp_semantic_layer.json",
]


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
) -> Dict[str, Any]:
    entry = _view_entry(view_key)
    fqn = str(entry["fqn"])
    table = sql_table(fqn)

    page = max(1, int(page))
    page_size = max(5, min(int(page_size), 500))
    offset = (page - 1) * page_size
    hard_cap = max(1_000, int(cfg.DATASET_HARD_CAP))

    count_sql = f"SELECT COUNT(1) AS Total FROM {table} WITH (NOLOCK)"
    count_res = await execute_query(count_sql, nolock=False, recompile=False)
    total_raw = int((count_res.get("records") or [{}])[0].get("Total") or 0)
    total_count = min(total_raw, hard_cap)

    data_sql = f"""
        SELECT *
        FROM {table} WITH (NOLOCK)
        ORDER BY (SELECT NULL)
        OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY
    """
    data_res = await execute_query(
        data_sql,
        params={"offset": offset, "limit": page_size},
        nolock=False,
        recompile=False,
    )
    records = data_res.get("records") or []
    columns = list(records[0].keys()) if records else []

    if not columns and page == 1:
        probe = await execute_query(
            f"SELECT TOP 1 * FROM {table} WITH (NOLOCK)",
            nolock=False,
            recompile=False,
        )
        probe_rows = probe.get("records") or []
        if probe_rows:
            columns = list(probe_rows[0].keys())

    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count else 1

    return {
        "view_key": view_key,
        "fqn": fqn,
        "short_name": fqn.split(".")[-1],
        "purpose": entry.get("purpose") or "",
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_raw": total_raw,
        "total_pages": total_pages,
        "capped": total_raw > hard_cap,
        "hard_cap": hard_cap,
        "columns": columns,
        "rows": records,
        "duration_ms": int(data_res.get("duration") or 0),
    }
