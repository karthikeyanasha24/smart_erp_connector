#!/usr/bin/env python3
"""
Today's sales — standalone diagnostic script (direct SQL Server).

Does not start the backend or call the HTTP API unless you pass --api.

Loads DB credentials from backend/.env (same as list_transactions_db.py).

Usage:
  python test/todays_sales.py
  python test/todays_sales.py --branches 10
  python test/todays_sales.py --api
  python test/todays_sales.py --api --base https://smart-erp-backend-aa9k.onrender.com

Requires: pip install pyodbc python-dotenv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ENV = _PROJECT_ROOT / "backend" / ".env"

_APP = "dbo.VW_MB_POWERBI_APP_REPORT"
_SLS = "dbo.VW_MB_POWERBI_SLSXNS_REPORT"
_SLS_DATA = "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Install python-dotenv: pip install python-dotenv", file=sys.stderr)
        sys.exit(1)
    if _BACKEND_ENV.is_file():
        load_dotenv(_BACKEND_ENV)
    else:
        print(f"Missing {_BACKEND_ENV}", file=sys.stderr)
        sys.exit(2)


def _fmt_money(v: Any) -> str:
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f}"


def _row_dict(cursor, row) -> Dict[str, Any]:
    cols = [d[0] for d in cursor.description]
    out: Dict[str, Any] = {}
    for i, c in enumerate(cols):
        val = row[i]
        if isinstance(val, Decimal):
            val = float(val)
        out[c] = val
    return out


# ─── pyodbc (minimal, same pattern as list_transactions_db.py) ───────────────

def _connect() -> Tuple[Any, str]:
    try:
        import pyodbc
    except ImportError:
        print("Install pyodbc: pip install pyodbc", file=sys.stderr)
        sys.exit(1)

    server = (os.getenv("DB_SERVER") or os.getenv("ERP_DB_HOST") or "").strip()
    port = int(os.getenv("DB_PORT") or os.getenv("ERP_DB_PORT") or "1433")
    database = (os.getenv("DB_NAME") or os.getenv("ERP_DB_NAME") or "").strip()
    user = (os.getenv("DB_USER") or os.getenv("ERP_DB_USER") or "").strip()
    password = os.getenv("DB_PASSWORD") or os.getenv("ERP_DB_PASSWORD") or ""
    if not all([server, database, user, password]):
        print("Set DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD in backend/.env", file=sys.stderr)
        sys.exit(2)

    timeout = int(os.getenv("DB_CONNECT_TIMEOUT_MS", "60000")) // 1000
    drivers = [
        (os.getenv("ODBC_DRIVER") or "").strip(),
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ]
    installed = set(pyodbc.drivers())
    last: Optional[BaseException] = None
    for drv in drivers:
        if not drv or (installed and drv not in installed):
            continue
        cs = (
            f"DRIVER={{{drv}}};SERVER={server},{port};DATABASE={database};"
            f"UID={user};PWD={password};Connect Timeout={timeout};"
            "TrustServerCertificate=yes;Encrypt=no;"
        )
        try:
            conn = pyodbc.connect(cs, timeout=timeout, autocommit=True)
            conn.timeout = int(os.getenv("DB_REQUEST_TIMEOUT_MS", "120000")) // 1000
            return conn, drv
        except Exception as exc:
            last = exc
    print(f"SQL connect failed: {last}", file=sys.stderr)
    sys.exit(3)


def _query(conn, sql: str) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(sql)
    return [_row_dict(cur, r) for r in cur.fetchall()]


def _fetch_db_sales(branch_top: int) -> Dict[str, Any]:
    conn, driver = _connect()
    print(f"Connected via {driver}")
    print(f"Server date (SQL): ", end="")
    server_today = _query(conn, "SELECT CAST(GETDATE() AS DATE) AS Today")[0]["Today"]
    print(server_today)
    print()

    results: Dict[str, Any] = {"server_today": str(server_today), "local_today": date.today().isoformat()}

    # 1) APP_REPORT — dashboard default (NetAmount + XnDt)
    app = _query(
        conn,
        f"""
        SELECT
            CAST(SUM(s.[NetAmount]) AS decimal(18,2)) AS Revenue,
            COUNT(DISTINCT s.[XnNo]) AS Bills,
            CAST(SUM(s.[AppQty]) AS decimal(18,2)) AS Quantity
        FROM {_APP} s WITH (NOLOCK)
        WHERE CAST(s.[XnDt] AS DATE) = CAST(GETDATE() AS DATE)
        """,
    )[0]
    results["app_report"] = app
    print("-- VW_MB_POWERBI_APP_REPORT (XnDt = today) --")
    print(f"  Revenue:   {_fmt_money(app.get('Revenue'))}")
    print(f"  Bills:     {int(app.get('Bills') or 0):,}")
    print(f"  Quantity:  {_fmt_money(app.get('Quantity'))}")
    print()

    # 2) SLSXNS — line-level net sales (FAQ / transactions source)
    sls = _query(
        conn,
        f"""
        SELECT
            CAST(SUM(T.[NetSlsNetAmount]) AS decimal(18,2)) AS Revenue,
            COUNT(DISTINCT T.[XnNo]) AS Bills,
            CAST(SUM(T.[NetSlsQty]) AS decimal(18,2)) AS Quantity,
            COUNT(*) AS LineRows
        FROM {_SLS} T WITH (NOLOCK)
        WHERE CAST(T.[XnDt] AS DATE) = CAST(GETDATE() AS DATE)
        """,
    )[0]
    results["slsxns"] = sls
    print("-- VW_MB_POWERBI_SLSXNS_REPORT (XnDt = today) --")
    print(f"  Revenue:   {_fmt_money(sls.get('Revenue'))}")
    print(f"  Bills:     {int(sls.get('Bills') or 0):,}")
    print(f"  Quantity:  {_fmt_money(sls.get('Quantity'))}")
    print(f"  Lines:     {int(sls.get('LineRows') or 0):,}")
    print()

    # 3) SLS_DATA_WITHOUT_ITEMID — CashmemoDt (alternate config path)
    cash = _query(
        conn,
        f"""
        SELECT
            CAST(SUM(sp.[SalesNetAmount]) AS decimal(18,2)) AS Revenue,
            COUNT(DISTINCT sp.[CashmemoNo]) AS Bills
        FROM {_SLS_DATA} sp WITH (NOLOCK)
        WHERE CAST(sp.[CashmemoDt] AS DATE) = CAST(GETDATE() AS DATE)
        """,
    )[0]
    results["sls_data_cashmemo"] = cash
    print("-- VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID (CashmemoDt = today) --")
    print(f"  Revenue:   {_fmt_money(cash.get('Revenue'))}")
    print(f"  Bills:     {int(cash.get('Bills') or 0):,}")
    print()

    if branch_top > 0:
        branches = _query(
            conn,
            f"""
            SELECT TOP ({branch_top})
                T.[BranchAlias] AS Branch,
                CAST(SUM(T.[NetSlsNetAmount]) AS decimal(18,2)) AS Revenue,
                COUNT(DISTINCT T.[XnNo]) AS Bills
            FROM {_SLS} T WITH (NOLOCK)
            WHERE CAST(T.[XnDt] AS DATE) = CAST(GETDATE() AS DATE)
              AND T.[BranchAlias] IS NOT NULL
            GROUP BY T.[BranchAlias]
            ORDER BY Revenue DESC
            """,
        )
        results["top_branches"] = branches
        print(f"-- Top {branch_top} branches today (SLSXNS) --")
        for i, b in enumerate(branches, 1):
            print(f"  {i:2}. {b.get('Branch','?'):12}  {_fmt_money(b.get('Revenue')):>14}  bills={int(b.get('Bills') or 0)}")
        print()

    conn.close()
    return results


def _fetch_api(base: str, email: str, password: str) -> None:
    import urllib.error
    import urllib.request

    base = base.rstrip("/")
    login_body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{base}/auth/login",
        data=login_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            token = json.loads(resp.read()).get("access_token")
    except urllib.error.HTTPError as exc:
        print(f"Login failed: {exc.read().decode()[:300]}", file=sys.stderr)
        sys.exit(4)
    if not token:
        print("No access_token in login response", file=sys.stderr)
        sys.exit(4)

    url = f"{base}/analytics/dashboard?period=today"
    req2 = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req2, timeout=180) as resp:
        data = json.loads(resp.read())

    summary = data.get("summary") or {}
    dr = data.get("date_range") or {}
    print("-- API /analytics/dashboard?period=today --")
    print(f"  Period:    {data.get('period_label', 'today')}")
    print(f"  Range:     {dr.get('start')} → {dr.get('end')}")
    print(f"  Revenue:   {_fmt_money(summary.get('mtd_sales'))}")
    print(f"  LY sales:  {_fmt_money(summary.get('ly_sales'))}")
    print(f"  Growth %:  {summary.get('sales_growth_pct')}")
    print(f"  Bills:     {summary.get('bills')}")
    print(f"  Quantity:  {summary.get('quantity')}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Today's sales from ERP (standalone SQL)")
    parser.add_argument("--branches", type=int, default=5, help="Top N branches (0 = skip)")
    parser.add_argument("--api", action="store_true", help="Also fetch /analytics/dashboard?period=today")
    parser.add_argument("--base", default=os.getenv("API_BASE_URL", "http://localhost:3000"))
    parser.add_argument("--email", default=os.getenv("DASHBOARD_EMAIL", os.getenv("APP_LOGIN_EMAIL", "")))
    parser.add_argument("--password", default=os.getenv("DASHBOARD_PASSWORD", os.getenv("APP_LOGIN_PASSWORD", "")))
    parser.add_argument("--json", action="store_true", help="Print raw result JSON (DB only)")
    args = parser.parse_args()

    _load_env()
    print("SmarterP - Today's sales\n")
    data = _fetch_db_sales(max(0, args.branches))
    if args.json:
        print(json.dumps(data, indent=2, default=str))

    if args.api:
        if not args.email or not args.password:
            print("--api skipped: set --email/--password or DASHBOARD_EMAIL/PASSWORD in env", file=sys.stderr)
        else:
            _fetch_api(args.base, args.email, args.password)


if __name__ == "__main__":
    main()
