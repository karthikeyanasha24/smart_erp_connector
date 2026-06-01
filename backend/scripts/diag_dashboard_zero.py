"""Quick diag: which view/column has MTD data."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.db.mssql import init_mssql, execute_raw, close_mssql
from src.utils.date_utils import resolve_date_range


async def probe(label: str, sql: str) -> None:
    try:
        r = await execute_raw(sql)
        print(f"{label}: {r['records'][0]}")
    except Exception as e:
        print(f"{label}: ERROR {e}")


async def main() -> None:
    await init_mssql()
    dr = resolve_date_range("mtd")
    ly = resolve_date_range("mtd")  # noqa — use get_prior_year_range in app
    print(f"MTD window: {dr.start} -> {dr.end}\n")

    start, end = dr.start, dr.end
    end_excl = f"DATEADD(day,1,CAST('{end}' AS DATE))"

    queries = [
        (
            "SLS_WITHOUT_ITEMID / CashmemoDt (current auto-config)",
            f"""
            SELECT COUNT(*) AS rows, ISNULL(SUM(SalesNetAmount),0) AS rev
            FROM dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID WITH (NOLOCK)
            WHERE CashmemoDt >= '{start}' AND CashmemoDt < {end_excl}
            """,
        ),
        (
            "SLS_WITHOUT_ITEMID date range",
            f"""
            SELECT MIN(CashmemoDt) AS min_dt, MAX(CashmemoDt) AS max_dt, COUNT(*) AS total_rows
            FROM dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID WITH (NOLOCK)
            """,
        ),
        (
            "APP_REPORT / XnDt MTD",
            f"""
            SELECT COUNT(*) AS rows, ISNULL(SUM(NetAmount),0) AS rev, ISNULL(SUM(BillCount),0) AS bills
            FROM dbo.VW_MB_POWERBI_APP_REPORT WITH (NOLOCK)
            WHERE XnDt >= '{start}' AND XnDt < {end_excl}
            """,
        ),
        (
            "APP_REPORT / XnDt date range",
            f"""
            SELECT MIN(XnDt) AS min_dt, MAX(XnDt) AS max_dt, COUNT(*) AS total_rows
            FROM dbo.VW_MB_POWERBI_APP_REPORT WITH (NOLOCK)
            """,
        ),
        (
            "APP_REPORT May full month",
            f"""
            SELECT COUNT(*) AS rows, ISNULL(SUM(NetAmount),0) AS rev
            FROM dbo.VW_MB_POWERBI_APP_REPORT WITH (NOLOCK)
            WHERE XnDt >= '2026-05-01' AND XnDt < '2026-06-01'
            """,
        ),
    ]

    for label, sql in queries:
        await probe(label, sql)

    await close_mssql()


if __name__ == "__main__":
    asyncio.run(main())
