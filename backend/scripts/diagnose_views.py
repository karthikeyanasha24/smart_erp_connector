"""
Diagnose SLS_REPORT and APP_REPORT — find correct date columns and data.
Run: python scripts/diagnose_views.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.mssql import init_mssql, execute_query


VIEWS = [
    "VW_MB_POWERBI_SLS_REPORT",
    "VW_MB_POWERBI_APP_REPORT",
]


async def main():
    await init_mssql()

    for view in VIEWS:
        print(f"\n{'='*60}")
        print(f"VIEW: dbo.{view}")
        print('='*60)

        # 1. List all columns
        cols_sql = """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = @view
            ORDER BY ORDINAL_POSITION
        """
        res = await execute_query(cols_sql, params={"view": view})
        cols = res["records"]
        date_cols = [r["COLUMN_NAME"] for r in cols if r["DATA_TYPE"] in ("date","datetime","datetime2","smalldatetime")]
        print(f"\nAll columns ({len(cols)}):")
        for r in cols:
            marker = " ← DATE" if r["COLUMN_NAME"] in date_cols else ""
            print(f"  {r['COLUMN_NAME']:40s} {r['DATA_TYPE']}{marker}")

        if not date_cols:
            print("  (no date columns found)")
            continue

        # 2. For each date column, check min/max and MTD row count
        print(f"\nDate column diagnostics:")
        for dc in date_cols:
            try:
                diag_sql = f"""
                    SELECT
                        MIN([{dc}]) AS MinDate,
                        MAX([{dc}]) AS MaxDate,
                        COUNT(*) AS TotalRows,
                        SUM(CASE WHEN [{dc}] >= '2026-05-01' AND [{dc}] < '2026-05-30' THEN 1 ELSE 0 END) AS MTD_Rows
                    FROM dbo.[{view}] WITH (NOLOCK)
                """
                r2 = await execute_query(diag_sql)
                rec = r2["records"][0] if r2["records"] else {}
                print(f"\n  [{dc}]")
                print(f"    Min={rec.get('MinDate')}  Max={rec.get('MaxDate')}")
                print(f"    TotalRows={rec.get('TotalRows')}  MTD_Rows(May 2026)={rec.get('MTD_Rows')}")
            except Exception as e:
                print(f"\n  [{dc}] ERROR: {e}")

        # 3. Sample 3 rows to see actual values
        try:
            sample_sql = f"SELECT TOP 3 * FROM dbo.[{view}] WITH (NOLOCK)"
            s = await execute_query(sample_sql)
            if s["records"]:
                print(f"\nSample row keys: {list(s['records'][0].keys())}")
        except Exception as e:
            print(f"\nSample error: {e}")

asyncio.run(main())
