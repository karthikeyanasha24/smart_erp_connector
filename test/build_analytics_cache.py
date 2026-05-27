#!/usr/bin/env python3
"""
Pre-aggregate ERP sales into small SQL Server cache tables for fast dashboard reads.

Architecture:
  ERP view (VW_MB_POWERBI_SLS_REPORT, etc.)
       → one heavy GROUP BY (this script)
       → analytics_daily_summary + analytics_kpi_cache
       → future: API reads these instead of scanning the full view every time

Uses credentials from backend/.env (never hardcode passwords).

Usage (from project root):
  python test/build_analytics_cache.py
  python test/build_analytics_cache.py --verify-only   # read cache, no rebuild
  python test/build_analytics_cache.py --periods today,mtd,qtd,ytd

Requires: pip install pyodbc python-dotenv (see backend/requirements.txt)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

try:
    import pyodbc
except ImportError:
    print("pyodbc required: pip install pyodbc", file=sys.stderr)
    raise SystemExit(1)

# ─── Config (matches backend/src/config.py defaults) ─────────────────────────

SOURCE_TABLE = os.getenv("SALES_AI_TABLE", "dbo.VW_MB_POWERBI_SLS_REPORT")
DATE_COL = os.getenv("MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN", "XnMemoDate")
BRANCH_COL = os.getenv("SALES_ANALYTICS_BRANCH_DIM", "BranchAlias")
CATEGORY_COL = os.getenv("SALES_ANALYTICS_CATEGORY_DIM", "CategoryShortName")
DEPT_COL = os.getenv("SALES_ANALYTICS_DEPARTMENT_DIM", "DepartmentShortName")
AMT_COL = os.getenv("SALES_ANALYTICS_AMOUNT_COLUMN", "NetAmount")
QTY_COL = os.getenv("SALES_ANALYTICS_QUANTITY_COLUMN", "NetSlsQty")
BILL_MODE = os.getenv("SALES_ANALYTICS_BILL_COUNT_MODE", "rows").lower()
BILL_COL = os.getenv("SALES_ANALYTICS_BILL_COUNT_COLUMN", "BillCount")

SUMMARY_TABLE = "dbo.analytics_daily_summary"
KPI_TABLE = "dbo.analytics_kpi_cache"

DEFAULT_PERIODS = ("today", "mtd", "qtd", "ytd", "last_30d")


def _log(msg: str) -> None:
    print(msg, flush=True)


def _db_credentials() -> Tuple[str, str, str, str, str]:
    server = os.getenv("DB_SERVER") or os.getenv("ERP_DB_HOST", "")
    port = str(os.getenv("DB_PORT") or os.getenv("ERP_DB_PORT", "1433"))
    database = os.getenv("DB_NAME") or os.getenv("ERP_DB_NAME", "")
    user = os.getenv("DB_USER") or os.getenv("ERP_DB_USER", "")
    password = os.getenv("DB_PASSWORD") or os.getenv("ERP_DB_PASSWORD", "")
    if not all([server, database, user, password]):
        raise RuntimeError(
            "Set DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD in backend/.env"
        )
    return server, port, database, user, password


def _odbc_drivers() -> List[str]:
    preferred = os.getenv("ODBC_DRIVER", "")
    installed: List[str] = []
    try:
        installed = list(pyodbc.drivers())
    except Exception:
        pass
    candidates = [
        preferred,
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ]
    out: List[str] = []
    for d in candidates:
        if d and d not in out and (not installed or d in installed):
            out.append(d)
    return out or installed


def connect() -> pyodbc.Connection:
    server, port, database, user, password = _db_credentials()
    last: Optional[Exception] = None
    for driver in _odbc_drivers():
        cs = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server},{port};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            f"Connect Timeout=60;"
            f"TrustServerCertificate=yes;"
            f"Encrypt=no;"
        )
        try:
            conn = pyodbc.connect(cs, timeout=120)
            _log(f"Connected ({driver}) → {database} on {server}:{port}")
            return conn
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Could not connect to SQL Server: {last}") from last


def _bills_expr() -> str:
    if BILL_MODE == "column":
        return f"SUM(CAST([{BILL_COL}] AS BIGINT))"
    return "COUNT(*)"


def _exec(conn: pyodbc.Connection, sql: str, label: str) -> None:
    _log(f"  {label}...")
    t0 = time.perf_counter()
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    _log(f"  {label} done ({time.perf_counter() - t0:.1f}s)")


def _fetch_all(conn: pyodbc.Connection, sql: str) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def create_tables(conn: pyodbc.Connection) -> None:
    _exec(
        conn,
        f"""
        IF OBJECT_ID('{SUMMARY_TABLE}', 'U') IS NULL
        BEGIN
            CREATE TABLE {SUMMARY_TABLE} (
                sales_date DATE NOT NULL,
                branch NVARCHAR(255) NOT NULL,
                category NVARCHAR(255) NOT NULL,
                department NVARCHAR(255) NOT NULL,
                revenue FLOAT NOT NULL DEFAULT 0,
                bills BIGINT NOT NULL DEFAULT 0,
                qty FLOAT NOT NULL DEFAULT 0,
                refreshed_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
            CREATE INDEX IX_ads_date ON {SUMMARY_TABLE} (sales_date);
            CREATE INDEX IX_ads_branch ON {SUMMARY_TABLE} (branch, sales_date);
        END
        """,
        "Ensure analytics_daily_summary",
    )
    _exec(
        conn,
        f"""
        IF OBJECT_ID('{KPI_TABLE}', 'U') IS NULL
        BEGIN
            CREATE TABLE {KPI_TABLE} (
                period VARCHAR(50) NOT NULL PRIMARY KEY,
                sales FLOAT NOT NULL DEFAULT 0,
                bills BIGINT NOT NULL DEFAULT 0,
                qty FLOAT NOT NULL DEFAULT 0,
                avg_bill FLOAT NOT NULL DEFAULT 0,
                updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
        END
        """,
        "Ensure analytics_kpi_cache",
    )


def populate_daily_summary(conn: pyodbc.Connection, *, years_back: int) -> None:
    bills = _bills_expr()
    # One scan of the ERP view — same data the live API aggregates on every request.
    _exec(conn, f"TRUNCATE TABLE {SUMMARY_TABLE};", "Clear analytics_daily_summary")

    insert_sql = f"""
        INSERT INTO {SUMMARY_TABLE} (
            sales_date, branch, category, department,
            revenue, bills, qty, refreshed_at
        )
        SELECT
            CAST([{DATE_COL}] AS DATE) AS sales_date,
            ISNULL(CAST([{BRANCH_COL}] AS NVARCHAR(255)), N'(unknown)') AS branch,
            ISNULL(CAST([{CATEGORY_COL}] AS NVARCHAR(255)), N'(unknown)') AS category,
            ISNULL(CAST([{DEPT_COL}] AS NVARCHAR(255)), N'(unknown)') AS department,
            ISNULL(SUM(CAST([{AMT_COL}] AS FLOAT)), 0) AS revenue,
            {bills} AS bills,
            ISNULL(SUM(CAST([{QTY_COL}] AS FLOAT)), 0) AS qty,
            SYSUTCDATETIME()
        FROM {SOURCE_TABLE} WITH (NOLOCK)
        WHERE [{DATE_COL}] >= DATEFROMPARTS(YEAR(GETDATE()) - {years_back}, 1, 1)
          AND [{DATE_COL}] < DATEADD(day, 1, CAST(GETDATE() AS DATE))
        GROUP BY
            CAST([{DATE_COL}] AS DATE),
            [{BRANCH_COL}],
            [{CATEGORY_COL}],
            [{DEPT_COL}]
        OPTION (MAXDOP 4);
    """
    _exec(conn, insert_sql, f"Populate {SUMMARY_TABLE} from {SOURCE_TABLE}")


def _period_where(period: str) -> str:
    """SQL predicate on analytics_daily_summary.sales_date."""
    p = period.lower()
    if p == "today":
        return "sales_date = CAST(GETDATE() AS DATE)"
    if p == "mtd":
        return (
            "sales_date >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) "
            "AND sales_date <= CAST(GETDATE() AS DATE)"
        )
    if p == "qtd":
        return (
            "sales_date >= DATEFROMPARTS("
            "YEAR(GETDATE()), ((DATEPART(QUARTER, GETDATE()) - 1) * 3) + 1, 1) "
            "AND sales_date <= CAST(GETDATE() AS DATE)"
        )
    if p == "ytd":
        return (
            "sales_date >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1) "
            "AND sales_date <= CAST(GETDATE() AS DATE)"
        )
    if p == "last_30d":
        return "sales_date >= DATEADD(day, -29, CAST(GETDATE() AS DATE))"
    raise ValueError(f"Unknown period: {period}")


def populate_kpi_cache(conn: pyodbc.Connection, periods: List[str]) -> None:
    _exec(conn, f"DELETE FROM {KPI_TABLE};", "Clear analytics_kpi_cache")
    for period in periods:
        where = _period_where(period)
        sql = f"""
            INSERT INTO {KPI_TABLE} (period, sales, bills, qty, avg_bill, updated_at)
            SELECT
                ?,
                ISNULL(SUM(revenue), 0),
                ISNULL(SUM(bills), 0),
                ISNULL(SUM(qty), 0),
                CASE WHEN ISNULL(SUM(bills), 0) = 0 THEN 0
                     ELSE ISNULL(SUM(revenue), 0) / SUM(bills) END,
                SYSUTCDATETIME()
            FROM {SUMMARY_TABLE}
            WHERE {where};
        """
        cur = conn.cursor()
        cur.execute(sql, (period,))
        conn.commit()
        _log(f"  KPI cached: {period}")


def verify(conn: pyodbc.Connection) -> None:
    kpis = _fetch_all(conn, f"SELECT * FROM {KPI_TABLE} ORDER BY period")
    _log("\n── KPI cache (fast dashboard) ──")
    for row in kpis:
        sales_l = (row.get("sales") or 0) / 100_000
        _log(
            f"  {row['period']:10}  sales={sales_l:,.2f} L  "
            f"bills={row.get('bills')}  qty={row.get('qty'):,.0f}  "
            f"avg={row.get('avg_bill'):,.0f}"
        )

    trend = _fetch_all(
        conn,
        f"""
        SELECT TOP 10 sales_date, SUM(revenue) AS revenue, SUM(bills) AS bills
        FROM {SUMMARY_TABLE}
        WHERE sales_date >= DATEADD(day, -30, CAST(GETDATE() AS DATE))
        GROUP BY sales_date
        ORDER BY sales_date DESC
        """,
    )
    _log("\n── Last 10 days (fast chart) ──")
    for row in trend:
        _log(f"  {row['sales_date']}  revenue={row['revenue']:,.0f}  bills={row['bills']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build analytics_daily_summary + analytics_kpi_cache in SQL Server"
    )
    parser.add_argument(
        "--years-back",
        type=int,
        default=2,
        help="How many years of daily rows to load into summary (default 2)",
    )
    parser.add_argument(
        "--periods",
        default=",".join(DEFAULT_PERIODS),
        help=f"Comma-separated KPI periods (default: {','.join(DEFAULT_PERIODS)})",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip rebuild; only print cached KPI + sample trend",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print config and exit",
    )
    args = parser.parse_args()
    periods = [p.strip() for p in args.periods.split(",") if p.strip()]

    _log("FAST DASHBOARD CACHE BUILD")
    _log(f"  source: {SOURCE_TABLE}")
    _log(f"  date={DATE_COL}  amount={AMT_COL}  qty={QTY_COL}  bills={BILL_MODE}")
    _log(f"  dims: branch={BRANCH_COL}  category={CATEGORY_COL}  dept={DEPT_COL}")

    if args.dry_run:
        return 0

    conn = connect()
    try:
        if args.verify_only:
            verify(conn)
            return 0

        t0 = time.perf_counter()
        create_tables(conn)
        populate_daily_summary(conn, years_back=max(0, args.years_back))
        populate_kpi_cache(conn, periods)
        _log(f"\nDone in {time.perf_counter() - t0:.1f}s")
        verify(conn)
        _log(
            "\nNext: wire backend KPI/dashboard to read from "
            f"{KPI_TABLE} / {SUMMARY_TABLE}, or schedule this script nightly."
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
