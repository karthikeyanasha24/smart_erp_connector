"""Live DB cross-verify for product / supplier / store FREQUENT_AI_QUERIES."""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from nlq_faq_sql import try_faq_template

QUERIES = [
    "Most Selling Product in the Current Month or Year",
    "Least Selling Product in the Current Month or Year",
    "Which Supplier has the Highest Sales in the Current Month?",
    "Which Supplier has the Lowest Sales in the Current Month?",
    "Top 10 Performing Stores based on Growth %",
    "Bottom 10 Performing Stores based on Sales Decline",
]


def _sample(recs: list, keys: list[str]) -> str:
    if not recs:
        return ""
    first = recs[0]
    return ", ".join(f"{k}={first.get(k)}" for k in keys if k in first)[:65]


async def main() -> int:
    from src.db.mssql import close_mssql, execute_raw, init_mssql
    from src.utils.date_utils import resolve_date_range

    await init_mssql()
    mtd = resolve_date_range("mtd")
    print(f"MTD window (IST): {mtd.start} -> {mtd.end}\n")
    print(f"{'#':>2}  {'ms':>7}  {'Rows':>7}  {'Template':36}  Notes")
    print("-" * 115)

    failures = 0
    for i, q in enumerate(QUERIES, 1):
        hit = try_faq_template(q)
        if not hit:
            print(f"{i:2}.  {'—':>7}  {'—':>7}  {'NO MATCH':36}  {q[:55]}")
            failures += 1
            continue

        tid = hit.get("template_id", "?")
        t0 = time.perf_counter()
        try:
            r = await execute_raw(hit["sql"])
            ms = int((time.perf_counter() - t0) * 1000)
            recs = r.get("records") or []
            n = len(recs)
            notes: list[str] = []

            if n == 0:
                notes.append("EMPTY")
                failures += 1
            else:
                notes.append("OK")

            if tid == "most_selling_product_mtd" and recs:
                notes.append(_sample(recs, ["Itemcode", "MTDQtySold", "MTDSales"]))
                notes.append("sorted by qty (MTD only, not full year)")

            elif tid == "least_selling_product_mtd" and recs:
                notes.append(_sample(recs, ["Itemcode", "MTDSales", "MTDQty"]))
                notes.append(f"bottom {n} products with sales>0")

            elif tid == "highest_supplier_sales_mtd" and recs:
                notes.append(_sample(recs, ["SupplierName", "Revenue"]))

            elif tid == "lowest_supplier_sales_mtd" and recs:
                notes.append(_sample(recs, ["SupplierName", "MTDSales"]))
                if recs and n > 1:
                    notes.append(f"lowest among {n} suppliers with sales")

            elif tid == "top_stores_by_growth_pct" and recs:
                notes.append(_sample(recs, ["Store", "GrowthPct", "MTDSales"]))
                notes.append(f"top {n} stores")

            elif tid == "bottom_stores_sales_decline" and recs:
                notes.append(_sample(recs, ["Store", "SalesDecline", "DeclinePct"]))
                notes.append(f"declining stores={n}")

            print(f"{i:2}.  {ms:7}  {n:7}  {tid:36}  {' | '.join(notes)}")

        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            failures += 1
            print(f"{i:2}.  {ms:7}  {'ERR':>7}  {tid:36}  {str(exc)[:70]}")

    await close_mssql()
    print(f"\nResult: {len(QUERIES) - failures}/{len(QUERIES)} passed live SQL")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
