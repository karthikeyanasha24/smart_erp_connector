"""
Schema Router — reads src/schema_index.json and returns direct column/table
mappings for each business concept without scanning the DB at runtime.

Usage:
    from src.analytics.schema_router import route

    r = route("sales_main")
    # → {"view": "dbo.VW_MB_POWERBI_APP_REPORT", "date_col": "XnDt", ...}

    r = route("today_sales")   # same as sales_main, date filter = today
    r = route("stock")
    r = route("product_master")

The index is built once by:
    python scripts/build_schema_index.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

_INDEX_PATH = Path(__file__).parent.parent / "schema_index.json"
_index: Optional[Dict[str, Any]] = None


def _load() -> Dict[str, Any]:
    global _index
    if _index is None:
        if not _index_path_exists():
            raise FileNotFoundError(
                f"schema_index.json not found at {_INDEX_PATH}. "
                "Run: python scripts/build_schema_index.py"
            )
        with open(_INDEX_PATH, encoding="utf-8") as f:
            _index = json.load(f)
    return _index


def _index_path_exists() -> bool:
    return _INDEX_PATH.exists()


def available() -> bool:
    """True if schema_index.json exists and is loadable."""
    try:
        _load()
        return True
    except Exception:
        return False


def route(concept: str) -> Dict[str, Any]:
    """Return routing dict for a business concept. Raises KeyError if not found."""
    idx = _load()
    routing = idx.get("routing", {})
    if concept not in routing:
        raise KeyError(f"Concept '{concept}' not in schema_index routing. "
                       f"Available: {list(routing.keys())}")
    return dict(routing[concept])


def route_or_none(concept: str) -> Optional[Dict[str, Any]]:
    try:
        return route(concept)
    except Exception:
        return None


def view_columns(view_name: str) -> Dict[str, str]:
    """Return {column_name: data_type} for a view."""
    idx = _load()
    ve = idx.get("views", {}).get(view_name, {})
    return dict(ve.get("columns", {}))


def view_concepts(view_name: str) -> Dict[str, str]:
    """Return {concept: column_name} for a view."""
    idx = _load()
    ve = idx.get("views", {}).get(view_name, {})
    return dict(ve.get("concepts", {}))


def best_date_column(view_name: str) -> Optional[str]:
    idx = _load()
    ve = idx.get("views", {}).get(view_name, {})
    return ve.get("best_date_column")


def generated_at() -> Optional[str]:
    try:
        return _load().get("generated_at")
    except Exception:
        return None


def reload() -> None:
    """Force reload from disk (useful after rebuild)."""
    global _index
    _index = None
    _load()


# ── Config auto-patch ─────────────────────────────────────────────────────────

def patch_config_from_index() -> bool:
    """
    Reads the schema_index routing and overwrites cfg.SALES_AI_TABLE,
    cfg.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN, etc. at startup.

    Returns True if patch was applied, False if index not available.
    This lets the app self-configure without manual .env edits.
    """
    if not available():
        return False

    r = route_or_none("sales_main")
    if not r:
        return False

    try:
        from src.config import cfg  # late import to avoid circular
        cfg.SALES_AI_TABLE                           = r["view"]
        cfg.ANALYTICS_BASE_TABLE                     = r["view"]
        cfg.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN = r["date_col"]
        cfg.SALES_ANALYTICS_AMOUNT_COLUMN            = r["amount_col"]
        cfg.SALES_ANALYTICS_QUANTITY_COLUMN          = r["quantity_col"]
        if r.get("bill_count_col"):
            cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN    = r["bill_count_col"]
            cfg.SALES_ANALYTICS_BILL_COUNT_MODE      = "column"
        else:
            cfg.SALES_ANALYTICS_BILL_COUNT_MODE      = "rows"
        cfg.SALES_ANALYTICS_BRANCH_DIM               = r.get("branch_col", cfg.SALES_ANALYTICS_BRANCH_DIM)
        cfg.SALES_ANALYTICS_CATEGORY_DIM             = r.get("category_col", cfg.SALES_ANALYTICS_CATEGORY_DIM)
        cfg.SALES_ANALYTICS_DEPARTMENT_DIM           = r.get("department_col", cfg.SALES_ANALYTICS_DEPARTMENT_DIM)
        # Keep item-level view on SLS_REPORT (has ItemId/ItemName) — not overridden by schema_index
        # cfg.SALES_ITEMS_AI_TABLE stays at its .env value (dbo.VW_MB_POWERBI_SLS_REPORT)
        return True
    except Exception:
        return False
