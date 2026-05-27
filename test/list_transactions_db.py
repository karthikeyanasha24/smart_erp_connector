#!/usr/bin/env python3
"""
List sales transactions from SQL Server using the same connection settings as the backend.

Loads credentials from backend/.env (preferred) or the project-root .env:
  DB_SERVER / ERP_DB_HOST
  DB_PORT / ERP_DB_PORT (default 1433)
  DB_NAME / ERP_DB_NAME
  DB_USER / ERP_DB_USER
  DB_PASSWORD / ERP_DB_PASSWORD
  ODBC_DRIVER (optional; ODBC 18 / 17 / legacy drivers are tried automatically)

Default column names follow backend/schema_catalog.txt (XnNo, XnId, …). If your database
exposes CashmemoNo / SalesPersonName like some API samples, pass --legacy.

Filtering:
  • --period: same presets as the app (mtd, today, ytd, qtd, last_7d, last_30d, …).
  • --start-date / --end-date: overrides --period when both provided (YYYY-MM-DD).
  • --branch / --category: exact match (optional).
  • --search: LIKE on CashmemoNo and SalesPersonName (matches API behavior).

Output: table / JSON / CSV to stdout or --output FILE.

Examples:
  python test/list_transactions_db.py --period mtd --top 50
  python test/list_transactions_db.py --start-date 2026-05-01 --end-date 2026-05-26
  python test/list_transactions_db.py --period today --format json --json-pretty
  python test/list_transactions_db.py --branch MAIN --category SHIRTS --search INV
  python test/list_transactions_db.py --columns all --top 100 -o txs.csv --format csv
  python test/list_transactions_db.py --count-only --period mtd

Requires: pip install pyodbc python-dotenv (see backend/requirements.txt)
SQL Server ODBC driver 17 or 18 must be installed on this machine.

This script does not modify the database and does not call the HTTP API.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

# ─── Locate .env ───────────────────────────────────────────────────────────────

_TESTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TESTS_DIR.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"


def _load_dotenv_files() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Install python-dotenv: pip install python-dotenv", file=sys.stderr)
        sys.exit(1)

    paths = [_BACKEND_ROOT / ".env", _PROJECT_ROOT / ".env"]
    for p in paths:
        if p.is_file():
            load_dotenv(p, override=False)


# ─── Date range — aligned with backend/src/utils/date_utils.py (standalone copy)

@dataclass
class DateRange:
    start: str
    end: str
    label: str
    period: str


def _fmt(d: date) -> str:
    return d.isoformat()


def _start_of_month(d: date) -> date:
    return d.replace(day=1)


def _end_of_month(d: date) -> date:
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    return d.replace(month=d.month + 1, day=1) - timedelta(days=1)


def _start_of_year(d: date) -> date:
    return d.replace(month=1, day=1)


def _get_quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1


def _start_of_quarter(d: date) -> date:
    q = _get_quarter(d)
    return d.replace(month=(q - 1) * 3 + 1, day=1)


def resolve_date_range(period: str, ref_date: date | None = None) -> DateRange:
    """Same presets as backend `resolve_date_range` (subset sufficient for CLI)."""
    today = ref_date or date.today()
    today_str = _fmt(today)
    lower = re.sub(r"[\s_\-]+", "_", period.lower().strip())

    if lower == "today":
        return DateRange(today_str, today_str, "Today", "today")

    if lower == "yesterday":
        y = today - timedelta(days=1)
        return DateRange(_fmt(y), _fmt(y), "Yesterday", "yesterday")

    if lower in ("mtd", "month_to_date", "this_month"):
        return DateRange(_fmt(_start_of_month(today)), today_str, "Month-to-Date", "mtd")

    if lower in ("ytd", "year_to_date", "this_year"):
        return DateRange(_fmt(_start_of_year(today)), today_str, "Year-to-Date", "ytd")

    if lower in ("qtd", "quarter_to_date", "this_quarter"):
        return DateRange(_fmt(_start_of_quarter(today)), today_str, "Quarter-to-Date", "qtd")

    if lower in ("last_7d", "last_7_days", "past_week"):
        return DateRange(_fmt(today - timedelta(days=6)), today_str, "Last 7 Days", "last_7d")

    if lower in ("last_30d", "last_30_days", "past_month"):
        return DateRange(_fmt(today - timedelta(days=29)), today_str, "Last 30 Days", "last_30d")

    if lower in ("last_90d", "last_90_days", "last_quarter_rolling"):
        return DateRange(_fmt(today - timedelta(days=89)), today_str, "Last 90 Days", "last_90d")

    if lower in ("last_month", "previous_month"):
        lm = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        return DateRange(_fmt(lm), _fmt(_end_of_month(lm)), "Last Month", "last_month")

    if lower in ("last_year", "previous_year"):
        ly = today.replace(year=today.year - 1, month=1, day=1)
        ly_end = today.replace(year=today.year - 1, month=12, day=31)
        return DateRange(_fmt(ly), _fmt(ly_end), "Last Year", "last_year")

    if lower in ("last_6m", "last_6_months", "last_180d"):
        return DateRange(_fmt(today - timedelta(days=179)), today_str, "Last 6 Months", "last_180d")

    return DateRange(_fmt(_start_of_month(today)), today_str, "Month-to-Date", "mtd")


def resolve_custom_range(start: str, end: str) -> DateRange:
    s = date.fromisoformat(start.strip()[:10])
    e = date.fromisoformat(end.strip()[:10])
    if e < s:
        s, e = e, s
    return DateRange(_fmt(s), _fmt(e), f"{_fmt(s)} to {_fmt(e)}", "custom")


# ─── MSSQL env + pyodbc (same pattern as test/list_products_db.py) ──────────────


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


def connect_mssql() -> Tuple[pyodbc.Connection, str]:
    server, port, database, user, password = _mssql_connection_params()
    cfg_driver = os.getenv("ODBC_DRIVER") or ""

    missing = [n for n, v in [("server", server), ("database", database), ("user", user), ("password", password)] if not v]
    if missing:
        print(
            f"Missing DB env vars: {', '.join(missing)}. "
            "Set them in backend/.env (same as backend uses).",
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
    installed = _installed_odbc_drivers()
    print(
        "Could not connect to SQL Server. Installed ODBC drivers: "
        f"{installed or 'none'}\nLast error: {last_exc}",
        file=sys.stderr,
    )
    sys.exit(3)


DEFAULT_VIEW = "dbo.VW_MB_POWERBI_SLSXNS_REPORT"

# Column sets: schema_catalog.txt lists XnNo, XnId, XnDt, … — not CashmemoNo / SalesPersonName.
# Some ERP builds add those aliases; use --legacy when your view matches the REST API verbatim.

LEGACY_API_COLUMNS = (
    "[CashmemoNo] AS id, "
    "[XnDt] AS txn_date, "
    "[BranchAlias] AS branch, "
    "[CategoryShortName] AS category, "
    "[DepartmentShortName] AS department, "
    "[NetSlsNetAmount] AS net_amount, "
    "[SalesPersonName] AS salesperson"
)

EXTENDED_LEGACY_TAIL = ", [XnId] AS xn_id, [XnNo] AS xn_no, [Itemcode] AS itemcode, [NetSlsQty] AS net_qty"

DEFAULT_CATALOG_COLUMNS = (
    "COALESCE(NULLIF(LTRIM(RTRIM(CAST(ISNULL([XnNo],'') AS NVARCHAR(510)))), ''), "
    "CAST(ISNULL([XnId],'') AS NVARCHAR(510))) AS id, "
    "[XnDt] AS txn_date, "
    "[BranchAlias] AS branch, "
    "[CategoryShortName] AS category, "
    "[DepartmentShortName] AS department, "
    "[NetSlsNetAmount] AS net_amount, "
    "CAST(N'' AS NVARCHAR(510)) AS salesperson"
)

EXTENDED_CATALOG_TAIL = ", [XnId] AS xn_id, [XnNo] AS xn_no, [Itemcode] AS itemcode, [NetSlsQty] AS net_qty"


def _cell_value(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return float(raw)
    if isinstance(raw, datetime):
        return raw.isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    if isinstance(raw, bytes):
        return raw.hex()
    return raw


def _rows_to_serializable(rows: List[pyodbc.Row], colnames: Sequence[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        rec: Dict[str, Any] = {}
        for i, name in enumerate(colnames):
            rec[name] = _cell_value(row[i])
        out.append(rec)
    return out


def _print_json(records: List[Dict[str, Any]], pretty: bool, stream: Any) -> None:
    if pretty:
        print(json.dumps(records, indent=2, ensure_ascii=False), file=stream)
    else:
        print(json.dumps(records, ensure_ascii=False), file=stream)


def _print_csv(records: List[Dict[str, Any]], stream: Any) -> None:
    if not records:
        print("(no rows)", file=sys.stderr)
        return
    w = csv.DictWriter(stream, fieldnames=list(records[0].keys()), extrasaction="ignore")
    w.writeheader()
    for r in records:
        flat = {k: "" if v is None else str(v) for k, v in r.items()}
        w.writerow(flat)


def _print_tabular(records: List[Dict[str, Any]], max_col_width: int, stream: Any) -> None:
    if not records:
        print("(no rows)", file=sys.stderr)
        return
    cols = list(records[0].keys())

    def fmt(val: Any) -> str:
        if val is None:
            return ""
        s = str(val).replace("\n", " ").replace("\r", "")
        if len(s) > max_col_width:
            return s[: max_col_width - 1] + "…"
        return s

    str_rows = [[fmt(r.get(c)) for c in cols] for r in records]
    widths = [len(c) for c in cols]
    for sr in str_rows:
        for i, cell in enumerate(sr):
            widths[i] = max(widths[i], len(cell))
    widths = [min(w, max_col_width) for w in widths]

    sep = " | "
    header = sep.join(col.ljust(widths[i]) for i, col in enumerate(cols))
    print(header, file=stream)
    print(sep.join("-" * widths[i] for i in range(len(cols))), file=stream)
    for sr in str_rows:
        print(sep.join(sr[i][: widths[i]].ljust(widths[i]) for i in range(len(sr))), file=stream)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch transaction rows from SQL Server (SLSXNS view) and print to the terminal.",
    )
    ap.add_argument(
        "--view",
        default=DEFAULT_VIEW,
        help=f"Fully qualified view name (default: {DEFAULT_VIEW})",
    )
    ap.add_argument(
        "--period",
        default="mtd",
        metavar="KEY",
        help="Date preset: mtd, today, yesterday, ytd, qtd, last_7d, last_30d, last_90d, last_month, last_year …",
    )
    ap.add_argument(
        "--start-date",
        default="",
        metavar="YYYY-MM-DD",
        help="Inclusive start date (requires --end-date); overrides --period",
    )
    ap.add_argument(
        "--end-date",
        default="",
        metavar="YYYY-MM-DD",
        help="Inclusive end date (requires --start-date); overrides --period",
    )
    ap.add_argument(
        "--columns",
        choices=("minimal", "extended", "all"),
        default="minimal",
        help="minimal/default columns; extended = +XnNo/XnId/Itemcode/NetSlsQty; all = SELECT *",
    )
    ap.add_argument("--top", type=int, default=100, metavar="N", help="Max rows (latest first); default 100")
    ap.add_argument(
        "--legacy",
        action="store_true",
        help="Use CashmemoNo/SalesPersonName + legacy ORDER/search (when your view matches old API dumps)",
    )
    ap.add_argument("--branch", default="", metavar="NAME", help="Filter BranchAlias = value")
    ap.add_argument("--category", default="", metavar="NAME", help="Filter CategoryShortName = value")
    ap.add_argument(
        "--search",
        default="",
        metavar="TEXT",
        help="Substring LIKE: legacy → CashmemoNo/SalesPersonName; default → XnNo/XnId/Itemcode",
    )
    ap.add_argument(
        "--count-only",
        action="store_true",
        help="Only print COUNT(*) for the filtered range (stderr: driver + SQL info)",
    )
    ap.add_argument(
        "--format",
        choices=("table", "json", "csv"),
        default="table",
        help="Output format (ignored with --count-only)",
    )
    ap.add_argument("--json-pretty", action="store_true", help="Pretty JSON when --format json")
    ap.add_argument("--max-col-width", type=int, default=28, metavar="W", help="Truncate width in table mode")
    ap.add_argument("-o", "--output", default="", metavar="FILE", help="Write results to FILE instead of stdout")

    args = ap.parse_args()
    top_n = max(1, min(args.top, 1_000_000))

    _load_dotenv_files()

    if args.start_date.strip() and args.end_date.strip():
        dr = resolve_custom_range(args.start_date, args.end_date)
    elif args.start_date.strip() or args.end_date.strip():
        print("Provide both --start-date and --end-date, or omit both to use --period.", file=sys.stderr)
        sys.exit(2)

    else:
        dr = resolve_date_range(args.period.strip())

    if args.columns != "minimal" and args.view.strip().lower() != DEFAULT_VIEW.lower():
        print(
            f"Warning: --columns {args.columns!r} assumes columns exist on {DEFAULT_VIEW}. "
            "If the query fails, use --columns all or the default view.",
            file=sys.stderr,
        )

    where_parts = [
        "[XnDt] >= CAST(? AS DATE)",
        "[XnDt] < DATEADD(day, 1, CAST(? AS DATE))",
    ]
    params: List[Any] = [dr.start, dr.end]

    if args.branch.strip():
        where_parts.append("[BranchAlias] = ?")
        params.append(args.branch.strip())

    if args.category.strip():
        where_parts.append("[CategoryShortName] = ?")
        params.append(args.category.strip())

    if args.search.strip():
        pat = f"%{args.search.strip().replace('[', '[[]').replace('%', '[%]').replace('_', '[_]')}%"
        if args.legacy:
            where_parts.append("([CashmemoNo] LIKE ? OR [SalesPersonName] LIKE ?)")
            params.extend([pat, pat])
        else:
            where_parts.append(
                "([XnNo] LIKE ? OR CAST([XnId] AS NVARCHAR(510)) LIKE ? OR [Itemcode] LIKE ?)"
            )
            params.extend([pat, pat, pat])

    where_sql = " AND ".join(where_parts)

    legacy = args.legacy
    if legacy:
        col_min, col_ext = LEGACY_API_COLUMNS, LEGACY_API_COLUMNS + EXTENDED_LEGACY_TAIL
        order_sql = "ORDER BY [XnDt] DESC, [CashmemoNo] DESC"
    else:
        col_min, col_ext = DEFAULT_CATALOG_COLUMNS, DEFAULT_CATALOG_COLUMNS + EXTENDED_CATALOG_TAIL
        order_sql = "ORDER BY [XnDt] DESC, [XnNo] DESC, [XnId] DESC"

    col_sql = {"minimal": col_min, "extended": col_ext, "all": "*"}[args.columns]

    sql_count = f"SELECT COUNT_BIG(*) AS cnt FROM {args.view} WITH (NOLOCK) WHERE {where_sql}"
    sql_data = (
        f"SELECT TOP ({top_n}) {col_sql} FROM {args.view} WITH (NOLOCK) WHERE {where_sql} {order_sql}"
    )

    print(
        f"Period: {dr.label} ({dr.start} … {dr.end}) | preset={dr.period}",
        file=sys.stderr,
    )

    out_stream: Any = sys.stdout
    fh = None
    if args.output and not args.count_only:
        fh = open(args.output, "w", encoding="utf-8", newline="")
        out_stream = fh

    conn: pyodbc.Connection | None = None
    try:
        conn, driver = connect_mssql()
        print(f"(connected via ODBC driver: {driver})", file=sys.stderr)

        cur = conn.cursor()

        if args.count_only:
            print(sql_count, file=sys.stderr)
            cur.execute(sql_count, params)
            row_one = cur.fetchone()
            cnt = int(row_one[0]) if row_one and row_one[0] is not None else 0
            print(cnt)
            return

        print(sql_data, file=sys.stderr)
        cur.execute(sql_data, params)
        colnames = [d[0] for d in cur.description]
        rows = cur.fetchall()
        records = _rows_to_serializable(rows, colnames)
        print(f"{len(records)} row(s) (TOP {top_n}, ordered by date desc)", file=sys.stderr)

        if args.format == "json":
            _print_json(records, pretty=args.json_pretty, stream=out_stream)
        elif args.format == "csv":
            _print_csv(records, stream=out_stream)
        else:
            _print_tabular(records, max_col_width=args.max_col_width, stream=out_stream)

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if fh is not None:
            fh.close()


if __name__ == "__main__":
    main()
