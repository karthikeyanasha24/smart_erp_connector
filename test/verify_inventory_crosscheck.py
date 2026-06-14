"""Cross-check formulas for inventory/forecast templates vs raw SQL."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

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


async def main() -> None:
    from src.db.mssql import close_mssql, execute_raw, init_mssql

    await init_mssql()

    # 1) Monthly APP revenue — last 6 complete months (for MoM + forecast)
    monthly = await execute_raw("""
    SELECT
        DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
        SUM(s.[NetAmount]) AS Revenue,
        COUNT(DISTINCT s.[Itemcode]) AS DistinctItemcodes
    FROM dbo.VW_MB_POWERBI_APP_REPORT s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND s.[XnDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
    GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
    ORDER BY MonthStart
    """)
    print("=== APP_REPORT monthly (complete months only) ===")
    rows = monthly.get("records") or []
    revs = []
    for r in rows:
        rev = float(r["Revenue"] or 0)
        revs.append(rev)
        print(f"  {r['MonthStart']}: INR {rev:,.0f}  items={r['DistinctItemcodes']}")

    if len(revs) >= 3:
        avg3 = sum(revs[-3:]) / 3
        print(f"\n  Manual avg last 3 months: INR {avg3:,.2f}")
        print(f"  (months: {[str(r['MonthStart']) for r in rows[-3:]]})")

    # 2) Compare dashboard-aligned monthly (SALESPERSON)
    monthly_sp = await execute_raw("""
    SELECT
        DATEFROMPARTS(YEAR(sp.[CashmemoDt]), MONTH(sp.[CashmemoDt]), 1) AS MonthStart,
        SUM(sp.[SalesNetAmount]) AS Revenue
    FROM dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID sp WITH (NOLOCK)
    WHERE sp.[CashmemoDt] >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND sp.[CashmemoDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
    GROUP BY DATEFROMPARTS(YEAR(sp.[CashmemoDt]), MONTH(sp.[CashmemoDt]), 1)
    ORDER BY MonthStart
    """)
    print("\n=== SALESPERSON monthly (dashboard-aligned) ===")
    sp_rows = monthly_sp.get("records") or []
    for r in sp_rows:
        print(f"  {r['MonthStart']}: INR {float(r['Revenue'] or 0):,.0f}")
    if len(sp_rows) >= 3:
        sp_avg = sum(float(r["Revenue"] or 0) for r in sp_rows[-3:]) / 3
        print(f"\n  Manual avg last 3 months (dashboard): INR {sp_avg:,.2f}")

    # 3) Template outputs
    print("\n=== Template outputs (top rows) ===")
    for q in QUERIES:
        hit = try_faq_template(q)
        if not hit:
            print(f"NO MATCH: {q}")
            continue
        tid = hit["template_id"]
        r = await execute_raw(hit["sql"])
        recs = r.get("records") or []
        print(f"\n{tid} ({len(recs)} rows)")
        for row in recs[:3]:
            print(f"  {row}")

    # 4) APP item coverage last 30d
    cov = await execute_raw("""
    SELECT
        COUNT(DISTINCT s.[Itemcode]) AS ItemsWithSales30d,
        SUM(s.[AppQty]) AS TotalQty30d
    FROM dbo.VW_MB_POWERBI_APP_REPORT s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE))
      AND s.[Itemcode] IS NOT NULL
    """)
    stock = await execute_raw("""
    SELECT COUNT(DISTINCT pm.[Itemcode]) AS StockItems
    FROM dbo.VW_MB_POWERBI_STOCK_REPORT st WITH (NOLOCK)
    INNER JOIN dbo.VW_MB_POWERBI_PRODUCT_MASTER pm WITH (NOLOCK) ON pm.[ItemId] = st.[ItemId]
    WHERE st.[StockQty] > 0 AND pm.[Itemcode] IS NOT NULL
    """)
    c = (cov.get("records") or [{}])[0]
    s = (stock.get("records") or [{}])[0]
    print("\n=== Data coverage gap ===")
    print(f"  Stock items (qty>0): {s.get('StockItems')}")
    print(f"  APP items with sales last 30d: {c.get('ItemsWithSales30d')}")
    print(f"  Total AppQty sold last 30d: {c.get('TotalQty30d')}")

    await close_mssql()


if __name__ == "__main__":
    asyncio.run(main())
