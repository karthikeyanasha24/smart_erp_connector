# mtd_sales_month.py
# Fast Month-To-Date sales fetcher
# Source: dbo.VW_MB_POWERBI_APP_REPORT
# Main KPI: SUM(NetAmount)

import os
import time
import pyodbc
import pandas as pd
from datetime import datetime

# ---------------------------------------------------
# DB CONNECTION
# ---------------------------------------------------

SERVER = os.getenv("DB_SERVER")
DATABASE = os.getenv("DB_DATABASE")
USERNAME = os.getenv("DB_USERNAME")
PASSWORD = os.getenv("DB_PASSWORD")

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    "TrustServerCertificate=yes;"
    "MARS_Connection=yes;"
)

# ---------------------------------------------------
# SQL QUERY
# ---------------------------------------------------

QUERY = """
SET NOCOUNT ON;

SELECT
    CAST(XnDt AS DATE) AS SalesDate,
    SUM(NetAmount) AS TotalSales,
    SUM(AppQty) AS TotalQty,
    SUM(BillCount) AS TotalBills
FROM dbo.VW_MB_POWERBI_APP_REPORT WITH (NOLOCK)
WHERE
    XnDt >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
    AND XnDt < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY CAST(XnDt AS DATE)
ORDER BY SalesDate;
"""

# ---------------------------------------------------
# FETCH FUNCTION
# ---------------------------------------------------

def fetch_mtd_sales():
    start = time.time()

    print("Connecting to SQL Server...")

    conn = pyodbc.connect(conn_str)

    # FAST READ
    conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')

    print("Fetching MTD sales data...")

    df = pd.read_sql(QUERY, conn)

    conn.close()

    end = time.time()

    print(f"\nFetched {len(df)} rows")
    print(f"Completed in {round(end - start, 2)} sec\n")

    return df


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

if __name__ == "__main__":
    df = fetch_mtd_sales()

    print(df.head())

    # Save CSV
    file_name = f"mtd_sales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    df.to_csv(file_name, index=False)

    print(f"\nSaved -> {file_name}")