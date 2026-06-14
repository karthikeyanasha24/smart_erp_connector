"""Live DB cross-verify for top 5 FREQUENT_AI_QUERIES."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from nlq_faq_sql import try_faq_template

QUERIES = [
    "Store Wise MTD Sales, Unique Customer Count, ATS",
    "Department Wise MTD Sales, Unique Customer Count, ATS",
    "Category Wise MTD Sales, Unique Customer Count, ATS",
    "Month-wise Sales Comparison since Apr'24",
    "Last 5 Years Sales Analysis at Department and Category Level",
]


async def main() -> int:
    from src.db.mssql import close_mssql, execute_raw, init_mssql
    from src.utils.date_utils import resolve_date_range

    await init_mssql()
    mtd = resolve_date_range("mtd")
    print(f"MTD window (IST): {mtd.start} -> {mtd.end}\n")
    print(f"{'#':>2}  {'Rows':>7}  {'Template':36}  Status / notes")
    print("-" * 100)

    failures = 0
    mtd_totals: list[float] = []

    for i, q in enumerate(QUERIES, 1):
        hit = try_faq_template(q)
        if not hit:
            print(f"{i:2}.  {'—':>7}  {'NO MATCH':36}  {q[:55]}")
            failures += 1
            continue

        tid = hit.get("template_id", "?")
        try:
            r = await execute_raw(hit["sql"])
            recs = r.get("records") or []
            n = len(recs)
            notes: list[str] = []

            if n == 0:
                notes.append("EMPTY — no rows")
                failures += 1
            else:
                notes.append("OK")
                first = recs[0]
                sample_keys = list(first.keys())[:3]
                notes.append(
                    "sample: "
                    + ", ".join(f"{k}={first[k]}" for k in sample_keys)[:50]
                )

            if tid in (
                "store_mtd_sales_customers_ats",
                "department_mtd_sales_customers_ats",
                "category_mtd_sales_customers_ats",
            ):
                total = sum(float(x.get("MTDSales") or 0) for x in recs)
                mtd_totals.append(total)
                notes.append(f"sum(MTDSales)={total:,.2f}")

            if tid == "monthly_sales_since_apr_2024" and recs:
                notes.append(
                    f"months {recs[0].get('MonthLabel')} .. {recs[-1].get('MonthLabel')}"
                )
                notes.append(
                    f"sum={sum(float(x.get('TotalSales') or 0) for x in recs):,.0f}"
                )

            if tid == "five_year_sales_dept_category" and recs:
                months = {str(x.get("MonthStart"))[:7] for x in recs}
                notes.append(f"{len(months)} distinct months, {n} dept×cat rows")

            print(f"{i:2}.  {n:7}  {tid:36}  {' | '.join(notes)}")

        except Exception as exc:
            failures += 1
            print(f"{i:2}.  {'ERR':>7}  {tid:36}  {str(exc)[:70]}")

    if len(mtd_totals) == 3:
        spread = max(mtd_totals) - min(mtd_totals)
        pct = (spread / max(mtd_totals) * 100) if max(mtd_totals) else 0
        print()
        print("MTD total cross-check (store vs dept vs category):")
        print(f"  Store:      {mtd_totals[0]:,.2f}")
        print(f"  Department: {mtd_totals[1]:,.2f}")
        print(f"  Category:   {mtd_totals[2]:,.2f}")
        if pct > 1:
            print(
                f"  NOTE: totals differ by {pct:.2f}% — expected because "
                "line-level dept/category splits can double-count vs store rollup."
            )
        else:
            print("  Totals align within 1%.")

    await close_mssql()
    print(f"\nResult: {len(QUERIES) - failures}/{len(QUERIES)} passed live SQL")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
