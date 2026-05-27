"""Diagnose MTD aggregates across sales views."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.db.mssql import init_mssql, execute_raw, close_mssql
from src.utils.date_utils import resolve_date_range
from src.utils.sql_ref import sql_table


async def q(label: str, sql: str) -> None:
    try:
        r = await execute_raw(sql)
        print(f"\n=== {label} ===")
        for row in r["records"]:
            print(row)
    except Exception as e:
        print(f"\n=== {label} FAILED ===", e)


async def main() -> None:
    await init_mssql()
    dr = resolve_date_range("mtd")
    print("MTD range:", dr.start, "to", dr.end)

    app = sql_table("dbo.VW_MB_POWERBI_APP_REPORT")
    slsxns = sql_table("dbo.VW_MB_POWERBI_SLSXNS_REPORT")
    sls = sql_table("dbo.VW_MB_POWERBI_SLS_REPORT")

    await q(
        "APP_REPORT date range",
        f"SELECT MIN(XnDt) AS MinDt, MAX(XnDt) AS MaxDt, COUNT(*) AS Rows FROM {app}",
    )
    await q(
        "APP_REPORT MTD",
        f"""
        SELECT COUNT(*) AS Rows,
               SUM(NetAmount) AS NetAmount,
               SUM(BillCount) AS SumBillCount,
               SUM(AppQty) AS SumAppQty,
               COUNT(DISTINCT XnNo) AS DistinctBills
        FROM {app}
        WHERE XnDt >= '{dr.start}' AND XnDt <= '{dr.end} 23:59:59'
        """,
    )
    await q(
        "SLSXNS MTD NetSlsNetAmount",
        f"""
        SELECT COUNT(*) AS Rows,
               SUM(NetSlsNetAmount) AS NetSlsNetAmount,
               COUNT(DISTINCT CashmemoNo) AS DistinctBills,
               SUM(NetSlsQty) AS Qty
        FROM {slsxns}
        WHERE XnDt >= '{dr.start}' AND XnDt <= '{dr.end} 23:59:59'
        """,
    )
    await q(
        "SLS_REPORT MTD",
        f"""
        SELECT COUNT(*) AS Rows, SUM(NetAmount) AS NetAmount
        FROM {sls}
        WHERE XnMemoDate >= '{dr.start}' AND XnMemoDate <= '{dr.end} 23:59:59'
        """,
    )
    await q(
        "APP May 2025 (LY window)",
        f"""
        SELECT COUNT(*) AS Rows, SUM(NetAmount) AS NetAmount, SUM(BillCount) AS SumBillCount
        FROM {app}
        WHERE XnDt >= '2025-05-01' AND XnDt <= '2025-05-25 23:59:59'
        """,
    )

    await close_mssql()


if __name__ == "__main__":
    asyncio.run(main())
