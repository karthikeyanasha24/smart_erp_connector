"""Live DB cross-verify for discount / ranking / forecast / target FAQ queries."""
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
    "Discount Impact on Sales Performance",
    "Store Ranking based on Sales, ATS, and Customer Count",
    "Product Recommendation based on Customer Buying Pattern",
    "AI-based Demand Forecasting by Store and Category",
    "Daily Sales Target vs Achievement Tracking",
    "Weather/Festival Impact on Sales Trend",
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
    print(f"{'#':>2}  {'ms':>8}  {'Rows':>7}  {'Template':36}  Notes")
    print("-" * 118)

    failures = 0
    for i, q in enumerate(QUERIES, 1):
        hit = try_faq_template(q)
        if not hit:
            print(f"{i:2}.  {'—':>8}  {'—':>7}  {'NO MATCH':36}  {q[:52]}")
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

            if tid == "discount_impact_sales" and recs:
                notes.append(_sample(recs, ["Category", "ImpliedDiscountPct", "NetSales"]))
                notes.append(f"categories={n}")

            elif tid == "store_ranking_sales_ats_customers" and recs:
                notes.append(_sample(recs, ["Store", "MTDSales", "ATS", "UniqueCustomers"]))
                notes.append(f"stores ranked={n}")

            elif tid == "product_recommendation_customer" and recs:
                notes.append(_sample(recs, ["Itemcode", "RepeatBuyerCount", "RevenueFromRepeatBuyers"]))
                notes.append(f"recommended items={n}")

            elif tid == "demand_forecast_store_category" and recs:
                notes.append(_sample(recs, ["Store", "Category", "ForecastNextMonthRevenue"]))
                notes.append(f"store x category pairs={n}")

            elif tid == "daily_sales_target_achievement" and recs:
                notes.append(_sample(recs, ["SaleDate", "DaySales", "AchievementPct"]))
                notes.append(f"trading days={n}")

            elif tid in ("weather_festival_impact_sales", "festival_vs_non_festival_sales") and recs:
                notes.append(_sample(recs, ["CalendarMonth", "SeasonTag", "AvgMonthlyRevenue"]))
                notes.append(f"months={n} (Oct/Nov=festive proxy)")

            elif tid == "festival_sales_trend_prediction" and recs:
                top = max(recs, key=lambda x: float(x.get("TotalSales") or 0))
                notes.append(f"peak month {top.get('MonthStart')} sales={top.get('TotalSales')}")
                notes.append(f"months={n}")

            print(f"{i:2}.  {ms:8}  {n:7}  {tid:36}  {' | '.join(notes)}")

        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            failures += 1
            print(f"{i:2}.  {ms:8}  {'ERR':>7}  {tid:36}  {str(exc)[:72]}")

    await close_mssql()
    print(f"\nResult: {len(QUERIES) - failures}/{len(QUERIES)} passed live SQL")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
