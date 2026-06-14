"""Live DB cross-verify for insights / inventory / customer FAQ queries (#40-50)."""
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
    "High Return / Low Conversion Product Identification",
    "AI-based Alerts for Sudden Sales Drop or Spike",
    "Top Customers based on Purchase Value",
    "New vs Repeat Customer Analysis",
    "Category Contribution % in Total Revenue",
    "Gross Margin Analysis by Department/Category",
    "Inventory Aging Analysis",
    "Dead Stock Identification",
    "Product-wise Sell Through %",
    "Sales Trend Prediction for Upcoming Festivals/Seasons",
    "AI-generated Business Insights and Recommendations",
]


def _sample(recs: list, keys: list[str]) -> str:
    if not recs:
        return ""
    first = recs[0]
    return ", ".join(f"{k}={first.get(k)}" for k in keys if k in first)[:60]


async def main() -> int:
    from src.db.mssql import close_mssql, execute_raw, init_mssql
    from src.utils.date_utils import resolve_date_range

    await init_mssql()
    mtd = resolve_date_range("mtd")
    print(f"MTD window (IST): {mtd.start} -> {mtd.end}\n")
    print(f"{'#':>2}  {'ms':>8}  {'Rows':>8}  {'Template':36}  Notes")
    print("-" * 120)

    failures = 0
    for i, q in enumerate(QUERIES, 1):
        hit = try_faq_template(q)
        if not hit:
            print(f"{i:2}.  {'—':>8}  {'—':>8}  {'NO MATCH':36}  {q[:50]}")
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

            if tid == "high_return_low_conversion_products" and recs:
                notes.append(_sample(recs, ["Itemcode", "ReturnRatePct", "MTDSales"]))
                notes.append(f"flagged={n}")

            elif tid == "sales_spike_drop_alert" and recs:
                row = recs[0]
                notes.append(
                    f"last7={row.get('Last7DayAvg')}, prior7={row.get('Prior7DayAvg')}, "
                    f"alert={row.get('AlertFlag')}"
                )

            elif tid == "top_customers_purchase_value" and recs:
                notes.append(_sample(recs, ["CustomerFirstName", "TotalPurchaseValue", "InvoiceCount"]))
                notes.append(f"top customers={n}")

            elif tid == "new_vs_repeat_customer_analysis" and recs:
                for row in recs[:3]:
                    notes.append(f"{row.get('CustomerType')}={row.get('CustomerCount')}")
                if n > 3:
                    notes.append(f"+{n - 3} more rows")

            elif tid == "category_contribution_percentage" and recs:
                notes.append(_sample(recs, ["Category", "ContributionPct", "Revenue"]))
                notes.append(f"categories={n}")

            elif tid == "gross_margin_by_category" and recs:
                notes.append(_sample(recs, ["Category", "GrossMarginPct", "Revenue"]))
                notes.append(f"rows={n} (category-level)")

            elif tid == "stock_aging_analysis" and recs:
                notes.append(_sample(recs, ["AgingBucket", "ItemCount", "StockValue"]))
                notes.append(f"buckets={n}")

            elif tid == "dead_stock_identification" and recs:
                notes.append(_sample(recs, ["Itemcode", "OnHandQty", "LastSaleDate"]))
                notes.append(f"dead stock items={n}")

            elif tid == "product_sell_through_pct" and recs:
                notes.append(_sample(recs, ["Itemcode", "SellThroughPct", "SoldQty30d"]))
                notes.append(f"items={n}")

            elif tid == "festival_sales_trend_prediction" and recs:
                top = max(recs, key=lambda x: float(x.get("TotalSales") or 0))
                notes.append(f"peak {top.get('MonthStart')} sales={top.get('TotalSales')}")
                notes.append(f"months={n}")

            elif tid == "ai_business_insights_snapshot" and recs:
                metrics = [str(r.get("Metric", r.get(list(r.keys())[0]))) for r in recs[:4]]
                notes.append(" | ".join(metrics))
                notes.append(f"KPI rows={n}")

            print(f"{i:2}.  {ms:8}  {n:8}  {tid:36}  {' | '.join(notes)}")

        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            failures += 1
            print(f"{i:2}.  {ms:8}  {'ERR':>8}  {tid:36}  {str(exc)[:70]}")

    await close_mssql()
    print(f"\nResult: {len(QUERIES) - failures}/{len(QUERIES)} passed live SQL")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
