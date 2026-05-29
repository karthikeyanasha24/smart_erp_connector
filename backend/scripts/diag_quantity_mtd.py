#!/usr/bin/env python3
"""Compare MTD quantity candidates (NetSlsQty vs row count vs AppQty)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.db.mssql import init_mssql, execute_raw, close_mssql
from src.utils.date_utils import resolve_date_range
from src.utils.sql_ref import sql_table


async def main() -> None:
    await init_mssql()
    dr = resolve_date_range("mtd")
    sls = sql_table("dbo.VW_MB_POWERBI_SLS_REPORT")
    app = sql_table("dbo.VW_MB_POWERBI_APP_REPORT")
    dc = "XnMemoDate"

    sql_sls = f"""
        SELECT
            COUNT(*) AS row_count,
            SUM([NetSlsQty]) AS sum_net_sls_qty,
            SUM([NetAmount]) AS sum_net_amount
        FROM {sls} WITH (NOLOCK)
        WHERE [{dc}] >= '{dr.start}'
          AND [{dc}] < DATEADD(day,1,CAST('{dr.end}' AS DATE))
    """
    row = (await execute_raw(sql_sls))["records"][0]
    print(f"MTD {dr.start} .. {dr.end}")
    print("SLS_REPORT (dashboard table):")
    print(f"  row_count (line items)     = {row.get('row_count')}")
    print(f"  SUM(NetSlsQty) units       = {row.get('sum_net_sls_qty')}")
    print(f"  SUM(NetAmount)             = {row.get('sum_net_amount')}")

    sql_app = f"""
        SELECT
            COUNT(*) AS row_count,
            SUM([AppQty]) AS sum_app_qty,
            SUM([BillCount]) AS sum_bill_count,
            SUM([NetAmount]) AS sum_net_amount
        FROM {app} WITH (NOLOCK)
        WHERE [XnDt] >= '{dr.start}'
          AND [XnDt] < DATEADD(day,1,CAST('{dr.end}' AS DATE))
    """
    try:
        app_row = (await execute_raw(sql_app))["records"][0]
        print("APP_REPORT (XnDt filter):")
        print(f"  row_count                  = {app_row.get('row_count')}")
        print(f"  SUM(AppQty)                = {app_row.get('sum_app_qty')}")
        print(f"  SUM(BillCount)             = {app_row.get('sum_bill_count')}")
        print(f"  SUM(NetAmount)             = {app_row.get('sum_net_amount')}")
    except Exception as exc:
        print("APP_REPORT query failed:", exc)

    await close_mssql()


if __name__ == "__main__":
    asyncio.run(main())
