#!/usr/bin/env python3
"""
List products from SQL Server using the same connection settings as the backend.

Loads credentials from backend/.env (preferred) or the project-root .env:
  DB_SERVER or ERP_DB_HOST
  DB_PORT or ERP_DB_PORT (default 1433)
  DB_NAME or ERP_DB_NAME
  DB_USER or ERP_DB_USER
  DB_PASSWORD or ERP_DB_PASSWORD
  ODBC_DRIVER (optional; tries 18 / 17 / SQL Server drivers automatically)

Prints rows to stdout. Does not modify the database or call the HTTP API.

Default table/view: dbo.VW_MB_POWERBI_PRODUCT_MASTER — item master used by analytics.

Examples:
  python test/list_products_db.py
  python test/list_products_db.py --top 100
  python test/list_products_db.py --search ART
  python test/list_products_db.py --view dbo.VwMstItems --columns all
  python test/list_products_db.py --format json --top 500
  python test/list_products_db.py --format csv --output products.csv

Requires: pip install pyodbc python-dotenv (see backend/requirements.txt)
SQL Server ODBC driver 17 or 18 must be installed on the machine.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

# ─── Locate .env ───────────────────────────────────────────────────────────────

_TESTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TESTS_DIR.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"


def _load_dotenv_files() -> None:
    """Load backend/.env first, then project .env for overrides (optional)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Install python-dotenv: pip install python-dotenv", file=sys.stderr)
        sys.exit(1)

    paths = [_BACKEND_ROOT / ".env", _PROJECT_ROOT / ".env"]
    for p in paths:
        if p.is_file():
            load_dotenv(p, override=False)


# ─── Config (mirrors backend/src/config.py env names only) ──────────────────────


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


# ─── pyodbc (same strategy as backend/src/db/mssql.py; copied here standalone) ─

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


def _sql_literal_percent(pattern: str) -> str:
    """Escape LIKE wildcards when building a literal pattern fragment."""
    return pattern.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")


DEFAULT_VIEW = "dbo.VW_MB_POWERBI_PRODUCT_MASTER"

# Readable subset when --columns preset (avoid huge terminal lines).
MINIMAL_COLUMNS = (
    "[ItemId], [Itemcode], [DepartmentShortName], [CategoryShortName], "
    "[ArticleNo], [SupplierAlias], [SupplierName], [ItemMRP], [PurchasePrice]"
)


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

    def fmt(v: Any) -> str:
        if v is None:
            return ""
        s = str(v).replace("\n", " ").replace("\r", "")
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
    ap = argparse.ArgumentParser(description="Fetch product list from SQL Server and print to terminal.")
    ap.add_argument(
        "--view",
        default=DEFAULT_VIEW,
        help=f"Fully qualified table or view name (default: {DEFAULT_VIEW})",
    )
    ap.add_argument(
        "--columns",
        choices=("minimal", "all"),
        default="minimal",
        help=(
            "minimal = key columns (expects %s columns; use --columns all for other views); "
            "all = SELECT * (very wide)"
        )
        % DEFAULT_VIEW,
    )
    ap.add_argument("--top", type=int, default=200, metavar="N", help="Maximum rows (default 200)")
    ap.add_argument(
        "--search",
        default="",
        metavar="TEXT",
        help="Case-insensitive filter: Itemcode / ItemId / CategoryShortName / ArticleNo CONTAINS text",
    )
    ap.add_argument(
        "--format",
        choices=("table", "json", "csv"),
        default="table",
        help="Output format (default table)",
    )
    ap.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON (--format json)")
    ap.add_argument(
        "--max-col-width",
        type=int,
        default=36,
        metavar="W",
        help="Truncate cell width in table mode (default 36)",
    )
    ap.add_argument(
        "--output",
        "-o",
        default="",
        metavar="FILE",
        help="Write CSV/JSON/table to FILE instead of stdout",
    )

    args = ap.parse_args()
    top = max(1, min(args.top, 1_000_000))

    col_sql = "*" if args.columns == "all" else MINIMAL_COLUMNS

    params: Tuple[Any, ...] = ()
    if args.search.strip():
        pat = f"%{_sql_literal_percent(args.search.strip())}%"
        collate = " COLLATE SQL_Latin1_General_CP1_CI_AS"
        filter_sql = (
            " AND ("
            f"LOWER(ISNULL(Itemcode,'')){collate} LIKE LOWER(?){collate} OR "
            f"LOWER(ISNULL(ItemId,'')){collate} LIKE LOWER(?){collate} OR "
            f"LOWER(ISNULL(CategoryShortName,'')){collate} LIKE LOWER(?){collate} OR "
            f"LOWER(ISNULL(ArticleNo,'')){collate} LIKE LOWER(?){collate}"
            ")"
        )
        params = (pat, pat, pat, pat)
    else:
        filter_sql = ""

    # TOP must be validated int (already)
    sql = (
        f"SELECT TOP ({top}) {col_sql} FROM {args.view} WITH (NOLOCK) "
        f"WHERE 1=1{filter_sql} ORDER BY ItemId"
    )

    _load_dotenv_files()

    if args.columns == "minimal" and args.view.strip().lower() != DEFAULT_VIEW.lower():
        print(
            "Warning: --columns minimal is tailored to %s; using another --view may fail. "
            "Use --columns all if the query errors."
            % DEFAULT_VIEW,
            file=sys.stderr,
        )

    out_stream: Any = sys.stdout
    fh = None
    if args.output:
        fh = open(args.output, "w", encoding="utf-8", newline="")
        out_stream = fh

    conn: pyodbc.Connection | None = None
    try:
        conn, driver = connect_mssql()
        print(f"(connected via ODBC driver: {driver})", file=sys.stderr)
        print(sql, file=sys.stderr)

        cur = conn.cursor()
        cur.execute(sql, params)
        colnames = [d[0] for d in cur.description]
        rows = cur.fetchall()
        records = _rows_to_serializable(rows, colnames)

        print(f"{len(records)} row(s)", file=sys.stderr)

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
