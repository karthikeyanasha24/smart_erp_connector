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
    """Exact bill count for KPI summary cards — COUNT(DISTINCT invoice)."""
    if cfg.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        return "COUNT(*)"
    return f"COUNT(DISTINCT [{cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN}])"


def trend_transactions_aggregate() -> str:
    """Fast COUNT(*) for trend chart GROUP BY queries.
    Always uses row count for speed -- COUNT(DISTINCT) over months of daily groups
    is 10-50x slower and causes timeouts. Trend bars show approximate volume;
    exact invoice count is shown on the KPI summary card via bill_count_case().
    """
    return "COUNT(*)"
