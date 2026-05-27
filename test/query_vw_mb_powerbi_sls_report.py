#!/usr/bin/env python3
"""
Run a sample query against dbo.VW_MB_POWERBI_SLS_REPORT (same view as backend SALES_AI_TABLE).

Uses backend/.env credentials (DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD, etc.) — same as
test/list_products_db.py.

Default query (your example):
  SELECT TOP 5 * FROM dbo.VW_MB_POWERBI_SLS_REPORT WITH (NOLOCK)
  WHERE XnMemoDate >= '2026-05-01'

Examples:
  python test/query_vw_mb_powerbi_sls_report.py
  python test/query_vw_mb_powerbi_sls_report.py --top 10 --since 2026-05-01
  python test/query_vw_mb_powerbi_sls_report.py --format json

Requires: pip install pyodbc python-dotenv (see backend/requirements.txt)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Sequence, Tuple

_TESTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TESTS_DIR.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"


def _load_dotenv_files() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Install python-dotenv: pip install python-dotenv", file=sys.stderr)
        sys.exit(1)
    for p in (_BACKEND_ROOT / ".env", _PROJECT_ROOT / ".env"):
        if p.is_file():
            load_dotenv(p, override=False)


def _mssql_connection_params() -> Tuple[str, int, str, str, str]:
    server = (os.getenv("DB_SERVER") or os.getenv("ERP_DB_HOST") or "").strip()
    port_s = os.getenv("DB_PORT") or os.getenv("ERP_DB_PORT") or "1433"
    try:
        port = int(port_s)
    except ValueError:
        port = 1433
    database = (os.getenv("DB_NAME") or os.getenv("ERP_DB_NAME") or "").strip()
    user = (os.getenv("DB_USER") or os.getenv("ERP_DB_USER") or "").strip()
    password = os.getenv("DB_PASSWORD") or os.getenv("ERP_DB_PASSWORD") or ""
    return server, port, database, user, password


def _connect_timeout() -> int:
    try:
        return int(os.getenv("DB_CONNECT_TIMEOUT_MS", "60000")) // 1000
    except ValueError:
        return 60


def _request_timeout() -> int:
    try:
        return int(os.getenv("DB_REQUEST_TIMEOUT_MS", "480000")) // 1000
    except ValueError:
        return 480


try:
    import pyodbc
except ImportError:
    print("Install pyodbc: pip install pyodbc", file=sys.stderr)
    sys.exit(1)


def _installed_odbc_drivers() -> List[str]:
    try:
        return list(pyodbc.drivers())
    except Exception:
        return []


def _odbc_drivers_to_try(cfg_driver: str) -> List[str]:
    installed = _installed_odbc_drivers()
    candidates = [
        (cfg_driver or "").strip(),
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]
    ordered: List[str] = []
    for d in candidates:
        if d and d not in ordered and (not installed or d in installed):
            ordered.append(d)
    if not ordered:
        for d in installed:
            if "sql" in d.lower() and d not in ordered:
                ordered.append(d)
        if installed and not ordered:
            ordered = installed[:]
    return ordered


def _build_conn_str(driver: str, server: str, port: int, database: str, user: str, password: str) -> str:
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"Connect Timeout={_connect_timeout()};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no;"
    )


def connect_mssql() -> Tuple[Any, str]:
    server, port, database, user, password = _mssql_connection_params()
    cfg_driver = os.getenv("ODBC_DRIVER") or ""

    missing = [
        n for n, v in [("server", server), ("database", database), ("user", user), ("password", password)] if not v
    ]
    if missing:
        print(
            f"Missing DB env: {', '.join(missing)}. Set them in backend/.env",
            file=sys.stderr,
        )
        sys.exit(2)

    last_exc: BaseException | None = None
    for driver in _odbc_drivers_to_try(cfg_driver):
        try:
            conn = pyodbc.connect(
                _build_conn_str(driver, server, port, database, user, password),
                timeout=_connect_timeout(),
                autocommit=True,
            )
            conn.timeout = _request_timeout()
            return conn, driver
        except Exception as exc:
            last_exc = exc
    print(
        "Could not connect. ODBC drivers:",
        _installed_odbc_drivers(),
        "\nLast error:",
        last_exc,
        file=sys.stderr,
    )
    sys.exit(3)


def _cell_value(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return float(raw)
    if isinstance(raw, (datetime, date)):
        return raw.isoformat()
    if isinstance(raw, bytes):
        return raw.hex()
    return raw


def main() -> None:
    p = argparse.ArgumentParser(description="Sample rows from VW_MB_POWERBI_SLS_REPORT")
    p.add_argument("--top", type=int, default=5, help="TOP N rows (default 5)")
    p.add_argument(
        "--since",
        default="2026-05-01",
        help="Filter XnMemoDate >= this date (YYYY-MM-DD). Default 2026-05-01",
    )
    p.add_argument(
        "--view",
        default="dbo.VW_MB_POWERBI_SLS_REPORT",
        help="Fully qualified view name",
    )
    p.add_argument("--format", choices=("table", "json"), default="table")
    args = p.parse_args()

    _load_dotenv_files()

    # Parameterized: avoids string interpolation; TOP uses int bound in T-SQL
    sql = f"""
SELECT TOP (?)
    *
FROM {args.view} WITH (NOLOCK)
WHERE [XnMemoDate] >= ?
"""
    conn, driver = connect_mssql()
    try:
        cur = conn.cursor()
        cur.execute(sql, args.top, args.since)
        cols: Sequence[str] = [c[0] for c in cur.description or ()]
        rows = cur.fetchall()
    finally:
        conn.close()

    print(f"Connected with driver: {driver}", file=sys.stderr)
    print(f"Rows: {len(rows)} (requested TOP {args.top})\n", file=sys.stderr)

    if args.format == "json":
        out = [
            {cols[i]: _cell_value(row[i]) for i in range(len(cols))}
            for row in rows
        ]
        print(json.dumps(out, indent=2, default=str))
        return

    if not rows:
        print("(no rows)")
        return

    # Fixed-width-ish table (truncate wide cells for terminal)
    widths = [max(len(str(c)), max(len(str(_cell_value(row[i]))[:80]) for row in rows)) for i, c in enumerate(cols)]

    def line(cells: List[str]) -> str:
        parts = [str(cells[i]).ljust(widths[i])[: widths[i] + 2] for i in range(len(cells))]
        return " | ".join(parts)

    print(line(list(cols)))
    print(line(["-" * widths[i] for i in range(len(cols))]))
    for row in rows:
        print(line([str(_cell_value(row[i]))[:120] for i in range(len(cols))]))


if __name__ == "__main__":
    main()
