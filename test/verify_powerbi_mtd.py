#!/usr/bin/env python3
"""
Cross-verify Power BI MBZ dashboard KPIs against SQL Server.

Default window: 2026-05-01 .. 2026-05-29 (matches PBI slicer in screenshot).
Optional --as-of-ist: cap May 29 at 15:00 IST (09:30 UTC) for snapshot checks.

Usage:
  python test/verify_powerbi_mtd.py
  python test/verify_powerbi_mtd.py --as-of-ist "2026-05-29 15:00:00"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from list_transactions_db import _load_dotenv_files, connect_mssql  # noqa: E402
from mtd_breakdown import AnalyticsEnv, _execute_sql, _safe_float, sql_table  # noqa: E402

# Power BI screenshot (May 29 ~3pm IST)
PBI = {
    "sales_L": 2824.60,
    "qty_K": 115.224,
    "invoices_K": 50.591,
    "clients_K": 35.0,
    "suppliers": 247,
}


def _lakhs(v: float) -> float:
    return round(v / 100_000, 2)


def _thousands(v: float) -> float:
    return round(v / 1000, 3)


def _diff(label: str, got: float, want: float, *, unit: str = "") -> str:
    d = round(got - want, 3)
    pct = round(d / want * 100, 2) if want else 0
    mark = "OK" if abs(pct) <= 1.0 else "DIFF"
    return f"  {label:<22} got={got}{unit}  pbi={want}{unit}  delta={d:+} ({pct:+.2f}%) [{mark}]"


def _query_bundle(
    conn: Any,
    *,
    tbl: str,
    dc: str,
    start: str,
    end_date: str,
    end_exclusive: Optional[str],
    amt: str,
    qty: str,
    bill_mode: str,
) -> Dict[str, float]:
    """One scan: sales, qty, bills, suppliers, distinct docs."""
    if end_exclusive:
        end_pred = f"[{dc}] < CAST(? AS DATETIME)"
        end_param = end_exclusive
    else:
        end_pred = f"[{dc}] < DATEADD(day,1,CAST(? AS DATE))"
        end_param = end_date

    if bill_mode == "column":
        bills_expr = "ISNULL(SUM([BillCount]), 0)"
        distinct_docs = "COUNT(DISTINCT [XnNo])"
    else:
        bills_expr = "COUNT(*)"
        distinct_docs = "NULL"

    sql = f"""
        SELECT
          ISNULL(SUM([{amt}]), 0) AS sales,
          ISNULL(SUM([{qty}]), 0) AS quantity,
          {bills_expr} AS bills,
          COUNT(DISTINCT [SupplierAlias]) AS suppliers,
          {distinct_docs} AS distinct_xnno
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= CAST(? AS DATE)
          AND {end_pred}
    """
    params: Tuple[Any, ...] = (start, end_param)
    rows = _execute_sql(conn, sql, params)
    row = rows[0] if rows else {}
    return {
        "sales": _safe_float(row.get("sales")),
        "quantity": _safe_float(row.get("quantity")),
        "bills": _safe_float(row.get("bills")),
        "suppliers": _safe_float(row.get("suppliers")),
        "distinct_xnno": _safe_float(row.get("distinct_xnno")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-05-01")
    parser.add_argument("--end", default="2026-05-29")
    parser.add_argument(
        "--as-of-ist",
        default=None,
        help='Cap end at datetime, e.g. "2026-05-29 15:00:00" (IST if DB stores local time)',
    )
    args = parser.parse_args()

    _load_dotenv_files()
    env = AnalyticsEnv.from_os()

    scenarios: List[Tuple[str, str, str, str, str, str]] = [
        (
            "APP_REPORT (PBI primary view)",
            "dbo.VW_MB_POWERBI_APP_REPORT",
            "XnDt",
            "NetAmount",
            "AppQty",
            "column",
        ),
        (
            "SLS_REPORT (item-level)",
            "dbo.VW_MB_POWERBI_SLS_REPORT",
            "XnMemoDate",
            "NetAmount",
            "NetSlsQty",
            "rows",
        ),
    ]

    conn, driver = connect_mssql()
    try:
        conn.timeout = 1200
    except Exception:
        pass

    print(f"Connected: {driver}")
    print(f"Window: {args.start} .. {args.end}")
    if args.as_of_ist:
        print(f"As-of cap (IST): {args.as_of_ist}")
    print(f"Power BI targets: sales={PBI['sales_L']}L qty={PBI['qty_K']}K "
          f"invoices={PBI['invoices_K']}K suppliers={PBI['suppliers']}")
    print("=" * 72)

    end_exclusive = args.as_of_ist if args.as_of_ist else None

    for label, view, dc, amt, qty, bill_mode in scenarios:
        tbl = sql_table(view)
        try:
            m = _query_bundle(
                conn,
                tbl=tbl,
                dc=dc,
                start=args.start,
                end_date=args.end,
                end_exclusive=end_exclusive,
                amt=amt,
                qty=qty,
                bill_mode=bill_mode,
            )
        except Exception as exc:
            print(f"\n== {label} ==\n  ERROR: {exc}")
            continue

        sales_l = _lakhs(m["sales"])
        qty_k = _thousands(m["quantity"])
        bills_k = _thousands(m["bills"])
        inv_distinct_k = _thousands(m["distinct_xnno"])

        print(f"\n== {label} ==")
        print(f"  {dc} | {amt} | qty={qty} | bills={bill_mode}")
        print(_diff("Sales", sales_l, PBI["sales_L"], unit=" L"))
        print(_diff("SalesQuantity", qty_k, PBI["qty_K"], unit=" K"))
        print(_diff("Unique Invoices (sum BillCount)", bills_k, PBI["invoices_K"], unit=" K"))
        print(_diff("Unique Invoices (distinct XnNo)", inv_distinct_k, PBI["invoices_K"], unit=" K"))
        print(_diff("Distinct Supplier", m["suppliers"], PBI["suppliers"], unit=""))

        # YoY growth for sales (same-date LY)
        ly_start = date.fromisoformat(args.start).replace(year=2025).isoformat()
        ly_end = date.fromisoformat(args.end).replace(year=2025).isoformat()
        ly_sql = f"""
            SELECT ISNULL(SUM([{amt}]), 0) AS ly_sales
            FROM {tbl} WITH (NOLOCK)
            WHERE [{dc}] >= ? AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        """
        ly_row = _execute_sql(conn, ly_sql, (ly_start, ly_end))[0]
        ly_sales = _safe_float(ly_row.get("ly_sales"))
        if ly_sales:
            g = round((m["sales"] - ly_sales) / ly_sales * 100, 2)
            print(f"  YoY growth (same dates LY): {g}%  (LY sales {_lakhs(ly_sales)} L)")

    try:
        conn.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
