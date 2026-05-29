#!/usr/bin/env python3
"""
Cross-verify MTD sales growth % (app ~29.4% vs stakeholder ~32%).

Usage:
  python backend/scripts/diag_growth_mtd.py
  python backend/scripts/diag_growth_mtd.py --ref-date 2026-05-29
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.config import cfg
from src.db.mssql import init_mssql, execute_raw, close_mssql
from src.utils.date_utils import resolve_date_range, get_prior_year_range, get_comparison_range
from src.utils.sql_ref import sql_table


def _growth(curr: float, ly: float) -> Optional[float]:
    if ly == 0:
        return None
    return round((curr - ly) / ly * 100, 2)


def _lakhs(v: float) -> float:
    return round(v / 100_000, 2)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref-date", default=None)
    args = parser.parse_args()
    ref = date.fromisoformat(args.ref_date) if args.ref_date else date.today()

    await init_mssql()

    dr = resolve_date_range("mtd", ref)
    ly_dr = get_prior_year_range("mtd", ref)
    cmp_dr = get_comparison_range("mtd", ref)

    tbl = sql_table(cfg.SALES_AI_TABLE)
    dc = cfg.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN
    amt = cfg.SALES_ANALYTICS_AMOUNT_COLUMN

    ly_m = date.fromisoformat(ly_dr.start)
    ly_full_end = date(ly_m.year, ly_m.month, monthrange(ly_m.year, ly_m.month)[1]).isoformat()

    prev_m_end = date.fromisoformat(dr.start) - timedelta(days=1)
    prev_m_start = prev_m_end.replace(day=1).isoformat()

    # One round-trip: all windows
    sql = f"""
        SELECT
          ISNULL(SUM(CASE WHEN [{dc}] >= '{dr.start}' AND [{dc}] < DATEADD(day,1,'{dr.end}')
              THEN [{amt}] END), 0) AS cy_mtd,
          ISNULL(SUM(CASE WHEN [{dc}] >= '{ly_dr.start}' AND [{dc}] < DATEADD(day,1,'{ly_dr.end}')
              THEN [{amt}] END), 0) AS ly_same_dates,
          ISNULL(SUM(CASE WHEN [{dc}] >= '{ly_m.replace(day=1).isoformat()}'
              AND [{dc}] < DATEADD(day,1,'{ly_full_end}') THEN [{amt}] END), 0) AS ly_full_may,
          ISNULL(SUM(CASE WHEN [{dc}] >= '{cmp_dr.start}' AND [{dc}] < DATEADD(day,1,'{cmp_dr.end}')
              THEN [{amt}] END), 0) AS kpi_cmp_window,
          ISNULL(SUM(CASE WHEN [{dc}] >= '{prev_m_start}' AND [{dc}] < DATEADD(day,1,'{prev_m_end.isoformat()}')
              THEN [{amt}] END), 0) AS prior_month_full
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= '{ly_dr.start}'
          AND [{dc}] < DATEADD(day,1,'{dr.end}')
    """
    row = (await execute_raw(sql))["records"][0]
    cy = float(row["cy_mtd"])
    ly_same = float(row["ly_same_dates"])
    ly_full = float(row["ly_full_may"])
    kpi_ly = float(row["kpi_cmp_window"])
    prior_month = float(row["prior_month_full"])

    print(f"Reference: {ref.isoformat()}  |  {cfg.SALES_AI_TABLE}  |  {dc}  |  {amt}")
    print(f"CY MTD:          {dr.start} .. {dr.end}")
    print(f"LY (dashboard):  {ly_dr.start} .. {ly_dr.end}")
    print(f"KPI compare win: {cmp_dr.start} .. {cmp_dr.end} ({cmp_dr.label})")
    print("=" * 72)

    scenarios = [
        ("Dashboard YoY (same dates)", cy, ly_same),
        ("Full May LY (entire month)", cy, ly_full),
        ("KPI get_comparison_range", cy, kpi_ly),
        ("Full prior month (April)", cy, prior_month),
    ]
    for label, c, l in scenarios:
        g = _growth(c, l)
        print(
            f"{label:<32}  CY {_lakhs(c):>8} L  LY {_lakhs(l):>8} L  growth {g:+.2f}%"
            if g is not None
            else f"{label:<32}  CY {_lakhs(c):>8} L  LY {_lakhs(l):>8} L  growth n/a",
            flush=True,
        )

    print()
    g_app = _growth(cy, ly_same)
    print(f"App-style growth (A): {g_app}%")
    for target in (29.4, 32.0, 32):
        need_ly = cy / (1 + target / 100)
        print(
            f"  For exactly {target}% need LY = {_lakhs(need_ly)} L  "
            f"(delta vs dashboard LY: {_lakhs(ly_same - need_ly):+.2f} L)",
            flush=True,
        )

    await close_mssql()


if __name__ == "__main__":
    asyncio.run(main())
