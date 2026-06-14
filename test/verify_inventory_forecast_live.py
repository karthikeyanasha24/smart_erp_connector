"""Live DB cross-verify for inventory / forecast FREQUENT_AI_QUERIES (#18-24)."""
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
    "Which Products are Growing Fastest Month-over-Month?",
    "Which Categories are Showing Negative Growth Trends?",
    "Predict Next Month Sales using AI Forecasting",
    "Expected Stock Requirement for Next 30 Days",
    "Potential Stock-Out Products Prediction",
    "Slow-Moving Inventory Identification",
    "Fast-Moving Inventory Identification",
]


def _sample(recs: list, keys: list[str]) -> str:
    if not recs:
        return ""
    first = recs[0]
    return ", ".join(f"{k}={first.get(k)}" for k in keys if k in first)[:60]


async def main() -> int:
    from src.db.mssql import close_mssql, execute_raw, init_mssql

    await init_mssql()
    print(f"{'#':>2}  {'ms':>7}  {'Rows':>7}  {'Template':36}  Notes")
    print("-" * 110)

    failures = 0
    for i, q in enumerate(QUERIES, 1):
        hit = try_faq_template(q)
        if not hit:
            print(f"{i:2}.  {'—':>7}  {'—':>7}  {'NO MATCH':36}  {q[:50]}")
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
                if tid != "predict_next_month_sales":
                    failures += 1
            else:
                notes.append("OK")

            if tid == "products_fastest_mom_growth" and recs:
                notes.append(_sample(recs, ["Itemcode", "MoMGrowthPct", "LatestRevenue"]))
                top = recs[0].get("MoMGrowthPct")
                notes.append(f"top MoM%={top}")

            elif tid == "categories_negative_growth_trends" and recs:
                notes.append(_sample(recs, ["Category", "MoMGrowthPct"]))
                notes.append(f"{n} declining categories")

            elif tid == "predict_next_month_sales" and recs:
                row = recs[0]
                notes.append(
                    f"forecast {row.get('ForecastMonthStart')}: "
                    f"INR {float(row.get('ForecastRevenue') or 0):,.0f}"
                )
                notes.append(str(row.get("ForecastMethod", ""))[:40])

            elif tid == "expected_stock_requirement_30_days" and recs:
                notes.append(_sample(recs, ["Itemcode", "ExpectedQtyNext30Days"]))
                notes.append(f"items={n}")

            elif tid == "potential_stockout_prediction" and recs:
                notes.append(_sample(recs, ["Itemcode", "OnHandQty", "QtyNeeded7Days"]))
                notes.append(f"at-risk items={n}")

            elif tid == "slow_moving_inventory_identification" and recs:
                notes.append(_sample(recs, ["Itemcode", "OnHandQty", "SoldQty30d"]))
                notes.append(f"slow movers={n}")

            elif tid == "fast_moving_inventory_identification" and recs:
                notes.append(_sample(recs, ["Itemcode", "SoldQty30d", "DaysOfStockLeft"]))
                notes.append(f"fast movers={n}")

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
