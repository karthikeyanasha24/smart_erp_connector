"""Quick SLS_REPORT MTD + LY aggregates."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.db.mssql import init_mssql, execute_raw, close_mssql
from src.utils.date_utils import resolve_date_range, get_prior_year_range
from src.utils.sql_ref import sql_table


async def main() -> None:
    await init_mssql()
    dr = resolve_date_range("mtd")
    ly = get_prior_year_range("mtd")
    sls = sql_table("dbo.VW_MB_POWERBI_SLS_REPORT")
    for label, start, end in [
        ("MTD", dr.start, dr.end),
        ("LY", ly.start, ly.end),
    ]:
        sql = f"""
        SELECT COUNT(*) AS Rows,
               SUM(NetAmount) AS NetAmount,
               SUM(NetSlsQty) AS Qty
        FROM {sls}
        WHERE XnMemoDate >= '{start}' AND XnMemoDate <= '{end} 23:59:59'
        """
        r = await execute_raw(sql)
        print(label, r["records"][0])
    await close_mssql()


if __name__ == "__main__":
    asyncio.run(main())
