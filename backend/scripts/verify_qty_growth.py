"""
Diagnostic script: compare NetSlsQty vs AppQty for MTD, and verify growth %.
Run from backend/ directory:
    python scripts/verify_qty_growth.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.mssql import init_mssql, execute_query
from src.utils.date_utils import resolve_date_range, get_prior_year_range


async def main():
    await init_mssql()

    dr    = resolve_date_range("mtd")
    ly_dr = get_prior_year_range("mtd")

    print(f"\nCurrent MTD : {dr.start}  →  {dr.end}")
    print(f"Prior Year  : {ly_dr.start}  →  {ly_dr.end}")
    print("=" * 60)

    # ── 1. SLS_REPORT quantities ──────────────────────────────────
    sls_sql = """
        SELECT
            SUM(CASE WHEN [XnDt] >= @start AND [XnDt] < DATEADD(day,1,CAST(@end AS DATE))
                THEN [NetSlsQty] ELSE 0 END) AS MTD_NetSlsQty,
            SUM(CASE WHEN [XnDt] >= @ly_start AND [XnDt] < DATEADD(day,1,CAST(@ly_end AS DATE))
                THEN [NetSlsQty] ELSE 0 END) AS LY_NetSlsQty,
            SUM(CASE WHEN [XnDt] >= @start AND [XnDt] < DATEADD(day,1,CAST(@end AS DATE))
                THEN [NetAmount] ELSE 0 END) AS MTD_NetAmount,
            SUM(CASE WHEN [XnDt] >= @ly_start AND [XnDt] < DATEADD(day,1,CAST(@ly_end AS DATE))
                THEN [NetAmount] ELSE 0 END) AS LY_NetAmount,
            COUNT(DISTINCT CASE WHEN [XnDt] >= @start AND [XnDt] < DATEADD(day,1,CAST(@end AS DATE))
                THEN [CashmemoNo] END) AS MTD_Bills_Distinct,
            SUM(CASE WHEN [XnDt] >= @start AND [XnDt] < DATEADD(day,1,CAST(@end AS DATE))
                THEN 1 ELSE 0 END) AS MTD_LineItems
        FROM dbo.VW_MB_POWERBI_SLS_REPORT WITH (NOLOCK)
    """
    sls = await execute_query(sls_sql, params={
        "start": dr.start, "end": dr.end,
        "ly_start": ly_dr.start, "ly_end": ly_dr.end,
    })
    r = sls["records"][0] if sls["records"] else {}

    mtd_sls_qty  = float(r.get("MTD_NetSlsQty") or 0)
    ly_sls_qty   = float(r.get("LY_NetSlsQty") or 0)
    mtd_amt      = float(r.get("MTD_NetAmount") or 0)
    ly_amt       = float(r.get("LY_NetAmount") or 0)
    sls_growth   = ((mtd_amt - ly_amt) / ly_amt * 100) if ly_amt else None

    print(f"\n[VW_MB_POWERBI_SLS_REPORT]")
    print(f"  MTD NetSlsQty   : {mtd_sls_qty:>12,.0f}  ← dashboard shows this as 'MTD Qty'")
    print(f"  LY  NetSlsQty   : {ly_sls_qty:>12,.0f}")
    print(f"  MTD NetAmount   : ₹{mtd_amt/100_000:>10,.2f} L")
    print(f"  LY  NetAmount   : ₹{ly_amt/100_000:>10,.2f} L")
    print(f"  Revenue Growth  : {sls_growth:>10.1f}%  ← dashboard shows this as Growth")
    print(f"  MTD BillCount   : {r.get('MTD_Bills_Distinct'):>12,}  (distinct CashmemoNo)")
    print(f"  MTD Line Items  : {r.get('MTD_LineItems'):>12,}  (row count)")

    # ── 2. APP_REPORT quantities ──────────────────────────────────
    app_sql = """
        SELECT
            SUM(CASE WHEN [XnDt] >= @start AND [XnDt] < DATEADD(day,1,CAST(@end AS DATE))
                THEN [AppQty] ELSE 0 END) AS MTD_AppQty,
            SUM(CASE WHEN [XnDt] >= @ly_start AND [XnDt] < DATEADD(day,1,CAST(@ly_end AS DATE))
                THEN [AppQty] ELSE 0 END) AS LY_AppQty,
            SUM(CASE WHEN [XnDt] >= @start AND [XnDt] < DATEADD(day,1,CAST(@end AS DATE))
                THEN [NetSlsNetAmount] ELSE 0 END) AS MTD_NetSlsNetAmount,
            SUM(CASE WHEN [XnDt] >= @ly_start AND [XnDt] < DATEADD(day,1,CAST(@ly_end AS DATE))
                THEN [NetSlsNetAmount] ELSE 0 END) AS LY_NetSlsNetAmount,
            SUM(CASE WHEN [XnDt] >= @start AND [XnDt] < DATEADD(day,1,CAST(@end AS DATE))
                THEN [BillCount] ELSE 0 END) AS MTD_BillCount
        FROM dbo.VW_MB_POWERBI_APP_REPORT WITH (NOLOCK)
    """
    app = await execute_query(app_sql, params={
        "start": dr.start, "end": dr.end,
        "ly_start": ly_dr.start, "ly_end": ly_dr.end,
    })
    a = app["records"][0] if app["records"] else {}

    mtd_app_qty   = float(a.get("MTD_AppQty") or 0)
    ly_app_qty    = float(a.get("LY_AppQty") or 0)
    mtd_app_amt   = float(a.get("MTD_NetSlsNetAmount") or 0)
    ly_app_amt    = float(a.get("LY_NetSlsNetAmount") or 0)
    app_growth    = ((mtd_app_amt - ly_app_amt) / ly_app_amt * 100) if ly_app_amt else None

    print(f"\n[VW_MB_POWERBI_APP_REPORT]")
    print(f"  MTD AppQty           : {mtd_app_qty:>12,.0f}  ← Power BI 'SalesQuantity'")
    print(f"  LY  AppQty           : {ly_app_qty:>12,.0f}")
    print(f"  MTD NetSlsNetAmount  : ₹{mtd_app_amt/100_000:>10,.2f} L")
    print(f"  LY  NetSlsNetAmount  : ₹{ly_app_amt/100_000:>10,.2f} L")
    print(f"  Revenue Growth       : {app_growth:>10.1f}%  ← Power BI growth")
    print(f"  MTD BillCount        : {a.get('MTD_BillCount'):>12,.0f}")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"  Quantity  — SLS NetSlsQty : {mtd_sls_qty:>10,.0f}")
    print(f"  Quantity  — APP AppQty    : {mtd_app_qty:>10,.0f}  ← Power BI uses this")
    print(f"  Growth    — SLS view      : {sls_growth:>9.1f}%")
    print(f"  Growth    — APP view      : {app_growth:>9.1f}%")
    print(f"\n  ➤ Dashboard currently uses SLS_REPORT (NetSlsQty + NetAmount)")
    print(f"  ➤ Power BI  uses APP_REPORT (AppQty + NetSlsNetAmount)")
    print(f"  ➤ To match Power BI: switch SALES_ANALYTICS_QUANTITY_COLUMN=AppQty")
    print(f"                  and SALES_AI_TABLE=dbo.VW_MB_POWERBI_APP_REPORT")
    print(f"                  and SALES_ANALYTICS_AMOUNT_COLUMN=NetSlsNetAmount")

asyncio.run(main())
