"""Live DB cross-verify for customer / peak hours / festival / region / basket FAQ queries."""
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
    "Customer Repeat Purchase Analysis",
    "Peak Sales Hours / Peak Billing Time Analysis",
    "Festival vs Non-Festival Sales Comparison",
    "Region Wise Sales Performance Comparison",
    "Supplier Contribution % in Overall Sales",
    "Average Basket Size by Store",
    "Average Invoice Value Trend Analysis",
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

            if tid == "customer_repeat_purchase_analysis" and recs:
                notes.append(_sample(recs, ["VisitCount", "CustomerCount", "AvgSpendPerCustomer"]))
                repeat = sum(
                    int(x.get("CustomerCount") or 0)
                    for x in recs
                    if int(x.get("VisitCount") or 0) > 1
                )
                notes.append(f"repeat buyers (2+ visits)={repeat}")

            elif tid == "peak_sales_hours_not_supported" and recs:
                peak = recs[0]
                notes.append(
                    f"peak hour={peak.get('SaleHour')}, "
                    f"sales={peak.get('MTDSales')}, bills={peak.get('Bills')}"
                )
                notes.append(f"hours with data={n}")

            elif tid == "festival_vs_non_festival_sales" and recs:
                festive = [x for x in recs if "Festive" in str(x.get("SeasonTag", ""))]
                notes.append(_sample(recs, ["CalendarMonth", "SeasonTag", "AvgMonthlyRevenue"]))
                notes.append(f"months={n}, festive-tagged={len(festive)}")

            elif tid == "region_wise_sales_performance" and recs:
                notes.append(_sample(recs, ["Region", "MTDSales", "Bills"]))
                notes.append(f"regions={n}")

            elif tid == "supplier_contribution_percentage" and recs:
                top = recs[0]
                notes.append(
                    f"top: {top.get('SupplierName')} "
                    f"{float(top.get('ContributionPct') or 0):.2f}%"
                )
                notes.append(f"suppliers={n}")

            elif tid == "average_basket_size_by_store" and recs:
                notes.append(_sample(recs, ["Store", "ATS", "MTDSales"]))
                notes.append(f"stores={n}")

            elif tid == "average_invoice_value_trend" and recs:
                notes.append(_sample(recs, ["MonthStart", "AvgInvoiceValue", "InvoiceCount"]))
                notes.append(
                    f"{recs[0].get('MonthStart')} .. {recs[-1].get('MonthStart')}"
                )

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
