"""SQL fragments for sales KPIs (row-count vs COUNT(DISTINCT invoice), quantity column)."""

from __future__ import annotations

from src.config import cfg


def quantity_column() -> str:
    return cfg.SALES_ANALYTICS_QUANTITY_COLUMN


def bill_count_case(date_col: str, start_ref: str, end_ref: str) -> str:
    """Conditional aggregate for bills/transactions in a date window.
    Modes:
      rows   -- SUM(CASE ... THEN 1 END)  counts every row (line items)
      column -- COUNT(DISTINCT CASE ... THEN [col] END)  unique invoice numbers
    """
    end_expr = f"DATEADD(day,1,CAST({end_ref} AS DATE))"
    if cfg.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        return (
            f"SUM(CASE WHEN [{date_col}] >= {start_ref} AND [{date_col}] < {end_expr} "
            f"THEN 1 ELSE 0 END)"
        )
    col = cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN
    return (
        f"COUNT(DISTINCT CASE WHEN [{date_col}] >= {start_ref} AND [{date_col}] < {end_expr} "
        f"THEN [{col}] END)"
    )


def transactions_aggregate() -> str:
    """Bill count for KPI cards and GROUP BY trend/chart queries (same definition)."""
    if cfg.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        return "COUNT(*)"
    return f"COUNT(DISTINCT [{cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN}])"


def bills_in_window(window_predicate: str) -> str:
    """Conditional bill aggregate when current and LY share one GROUP BY scan."""
    if cfg.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        return f"SUM(CASE WHEN {window_predicate} THEN 1 ELSE 0 END)"
    col = cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN
    return f"COUNT(DISTINCT CASE WHEN {window_predicate} THEN [{col}] END)"


def trend_transactions_aggregate() -> str:
    """Alias — trend/day-wise bars must match KPI bill totals."""
    return transactions_aggregate()
