#!/usr/bin/env python3
"""
Compute and compare growth % for:
  - MTD YoY (CY MTD vs LY same dates)
  - App KPI comparison window growth (as defined by backend get_comparison_range("mtd"))

Outputs numeric values only (no currency symbols) to avoid Windows encoding issues.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _growth(curr: float, prior: float) -> Optional[float]:
    if prior == 0:
        return None
    return round((curr - prior) / prior * 100, 2)


def _lakhs(v: float) -> float:
    return round(v / 100_000, 2)


def _compute_windows(ref: date) -> Dict[str, Tuple[str, str]]:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "backend"))
    # Imported late after sys.path tweak
    from src.utils.date_utils import get_comparison_range, resolve_date_range  # noqa: E402

    dr = resolve_date_range("mtd", ref)
    cy = (dr.start, dr.end)

    ly_start = date.fromisoformat(dr.start).replace(year=date.fromisoformat(dr.start).year - 1)
    ly_end = date.fromisoformat(dr.end).replace(year=date.fromisoformat(dr.end).year - 1)
    ly = (ly_start.isoformat(), ly_end.isoformat())

    prior = get_comparison_range("mtd", ref)
    kpi_prior = (prior.start, prior.end)
    return {"cy": cy, "ly": ly, "kpi_prior": kpi_prior}


def _run_sums(
    conn: Any,
    *,
    view_fqn: str,
    date_col: str,
    amt_col: str,
    cy: Tuple[str, str],
    ly: Tuple[str, str],
    kpi_prior: Tuple[str, str],
) -> Dict[str, float]:
    # Keep WHERE bounded so SQL Server can filter efficiently.
    where_start = ly[0]
    where_end = cy[1]

    sql = f"""
        SELECT
          ISNULL(SUM(CASE WHEN [{date_col}] >= ? AND [{date_col}] < DATEADD(day,1,CAST(? AS DATE))
              THEN [{amt_col}] ELSE 0 END), 0) AS cy_sum,
          ISNULL(SUM(CASE WHEN [{date_col}] >= ? AND [{date_col}] < DATEADD(day,1,CAST(? AS DATE))
              THEN [{amt_col}] ELSE 0 END), 0) AS ly_sum,
          ISNULL(SUM(CASE WHEN [{date_col}] >= ? AND [{date_col}] < DATEADD(day,1,CAST(? AS DATE))
              THEN [{amt_col}] ELSE 0 END), 0) AS kpi_prior_sum
        FROM {view_fqn} WITH (NOLOCK)
        WHERE [{date_col}] >= ?
          AND [{date_col}] < DATEADD(day,1,CAST(? AS DATE))
    """

    params = (
        cy[0],
        cy[1],
        ly[0],
        ly[1],
        kpi_prior[0],
        kpi_prior[1],
        where_start,
        where_end,
    )

    # _execute_sql is a small pyodbc helper already used in other test scripts.
    from mtd_breakdown import _execute_sql  # noqa: E402

    rows = _execute_sql(conn, sql, params)
    row = rows[0] if rows else {}
    return {
        "cy": _safe_float(row.get("cy_sum")),
        "ly": _safe_float(row.get("ly_sum")),
        "kpi_prior": _safe_float(row.get("kpi_prior_sum")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref-date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--no-kpi",
        action="store_true",
        help="Skip KPI prior-window computation (faster).",
    )
    args = parser.parse_args()

    ref = date.fromisoformat(args.ref_date) if args.ref_date else date.today()

    # Reuse same SQL Server connection settings as the backend.
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "test"))
    from list_transactions_db import _load_dotenv_files, connect_mssql  # noqa: E402

    _load_dotenv_files()
    conn, driver = connect_mssql()
    try:
        try:
            conn.timeout = 1200
        except Exception:
            pass
        print(f"Connected via {driver}")

        windows = _compute_windows(ref)
        cy = windows["cy"]
        ly = windows["ly"]
        kpi_prior = windows["kpi_prior"]

        # Two possible mappings (stakeholder might be using a different one):
        # - SLS_REPORT + NetAmount (what our earlier dashboard-matching run used)
        # - APP_REPORT + NetSlsNetAmount (what backend/.env indicates in this repo)
        mappings = [
            ("SLS_REPORT(NetAmount, XnMemoDate)", "dbo.VW_MB_POWERBI_SLS_REPORT", "XnMemoDate", "NetAmount"),
            ("APP_REPORT(NetSlsNetAmount, XnDt)", "dbo.VW_MB_POWERBI_APP_REPORT", "XnDt", "NetSlsNetAmount"),
        ]

        for label, view_fqn, date_col, amt_col in mappings:
            sums = _run_sums(
                conn,
                view_fqn=view_fqn,
                date_col=date_col,
                amt_col=amt_col,
                cy=cy,
                ly=ly,
                kpi_prior=kpi_prior,
            )
            cy_v = sums["cy"]
            ly_v = sums["ly"]
            kpi_v = sums["kpi_prior"]

            yoy = _growth(cy_v, ly_v)
            print(f"\n== {label} ==")
            print(f"CY MTD   [{cy[0]}..{cy[1]}] = {_lakhs(cy_v)} L")
            print(f"LY same  [{ly[0]}..{ly[1]}] = {_lakhs(ly_v)} L")
            print(f"YoY growth_pct = {yoy}")

            if not args.no_kpi:
                kpi_g = _growth(cy_v, kpi_v)
                print(f"KPI prior [{kpi_prior[0]}..{kpi_prior[1]}] = {_lakhs(kpi_v)} L")
                print(f"KPI growth_pct = {kpi_g}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

