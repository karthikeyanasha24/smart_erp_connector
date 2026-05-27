"""SQL fragments for sales KPIs (row-count vs BillCount, quantity column)."""

from __future__ import annotations

from src.config import cfg


def quantity_column() -> str:
    return cfg.SALES_ANALYTICS_QUANTITY_COLUMN


def bill_count_case(date_col: str, start_ref: str, end_ref: str) -> str:
    """Conditional aggregate for bills/transactions in a date window.
    Uses < DATEADD(day,1,CAST(end AS DATE)) so datetime columns include all
    same-day transactions (old <= end treated date string as midnight).
    """
    end_expr = f"DATEADD(day,1,CAST({end_ref} AS DATE))"
    if cfg.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        return (
            f"SUM(CASE WHEN [{date_col}] >= {start_ref} AND [{date_col}] < {end_expr} "
            f"THEN 1 ELSE 0 END)"
        )
    col = cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN
    return (
        f"SUM(CASE WHEN [{date_col}] >= {start_ref} AND [{date_col}] < {end_expr} "
        f"THEN [{col}] ELSE 0 END)"
    )


def transactions_aggregate() -> str:
    """Aggregate for GROUP BY charts (line items = rows on SLS_REPORT)."""
    if cfg.SALES_ANALYTICS_BILL_COUNT_MODE == "rows":
        return "COUNT(*)"
    return f"SUM([{cfg.SALES_ANALYTICS_BILL_COUNT_COLUMN}])"
