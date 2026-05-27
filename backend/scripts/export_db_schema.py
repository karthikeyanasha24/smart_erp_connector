#!/usr/bin/env python3
"""
Export SQL Server tables, views, and columns to a human-readable catalog file.

Usage (from backend/):
    python scripts/export_db_schema.py
    python scripts/export_db_schema.py --output docs/schema_catalog.txt
    python scripts/export_db_schema.py --schema dbo --only-views
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Allow running as: python scripts/export_db_schema.py
BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from dotenv import load_dotenv

from column_used_for import VIEW_DESCRIPTIONS, describe_column

load_dotenv(BACKEND_ROOT / ".env")

try:
    import pyodbc
except ImportError:
    print("pyodbc is required. Run: pip install pyodbc")
    sys.exit(1)


# ─── Known analytics objects (titles + descriptions from product docs) ───────

KNOWN_OBJECTS: Dict[str, Dict[str, object]] = {
    "dbo.VW_MB_POWERBI_APP_REPORT": {
        "title": "Primary Sales View",
        "description": "This is the most important view — used for 90% of all analytics.",
        "columns": {
            "XnDt": "Date filter (all period calculations)",
            "BranchAlias": "Branch grouping / filter",
            "CategoryShortName": "Category breakdown",
            "DepartmentShortName": "Department breakdown",
            "NetSlsNetAmount": "Revenue (the main metric)",
            "GrossAmount": "Gross revenue (optional)",
            "DiscountAmount": "Discounts (optional)",
            "Quantity": "Units sold (optional)",
            "TransactionCount": "Transaction count (or use COUNT(*))",
        },
    },
    "dbo.VW_MB_POWERBI_SLS_REPORT": {
        "title": "Base Sales Table",
        "description": "Used for item-level and salesperson analytics.",
        "columns": {
            "InvoiceDt": "Date filter",
            "BranchId": "Branch filter",
            "BranchAlias": "Branch name",
            "NetSlsNetAmount": "Revenue",
            "ItemId": "Product ID",
            "ItemName": "Product name",
            "CustomerId": "Customer reference",
            "Quantity": "Quantity",
        },
    },
    "dbo.VwAISalesData": {
        "title": "AI Sales Summary View",
        "description": "Used for fast trend queries and NLQ.",
        "columns": {
            "InvoiceDt": "Date",
            "BranchId": "Branch",
            "BranchName": "Branch full name",
            "NetAmount": "Net sales",
            "GrossAmount": "Gross sales",
            "TxnCount": "Transaction count",
            "CustomerCount": "Unique customers",
        },
    },
    "dbo.VwAIBranch": {
        "title": "Branch Master",
        "description": "Used for Branch Intelligence page and branch lookups.",
        "columns": {
            "BranchId": "Branch identifier",
            "BranchName": "Full name",
            "BranchAlias": "Short alias (used in reports)",
            "Region": "Geographic region",
            "IsActive": "Active flag",
        },
    },
    "dbo.VwAICustomerDetails": {
        "title": "Customer View",
        "description": "Used for new customer KPI.",
        "columns": {
            "CustomerId": "Customer ID",
            "CustomerName": "Name",
            "CreatedDt": "Registration/acquisition date",
            "BranchId": "Assigned branch",
            "Segment": "Customer tier/segment",
            "TotalSpend": "Lifetime spend",
        },
    },
    "dbo.VwAIStockData": {
        "title": "Inventory View",
        "description": "Used for Products page and stock queries.",
        "columns": {
            "ItemId": "Item ID",
            "ItemName": "Item description",
            "Category": "Category",
            "OnHandQty": "Current stock",
            "ReorderLevel": "Reorder threshold",
            "EntryDt": "Stock entry date",
            "UnitCost": "Cost per unit",
            "StockValue": "Total value",
        },
    },
    "dbo.MstStockUnit": {
        "title": "Stock Unit Master",
        "description": "Backup for item-level stock data if view isn't available.",
        "columns": {},
    },
    "dbo.MstSalesPerson": {
        "title": "Salesperson Master",
        "description": "Used for salesperson name lookups.",
        "columns": {
            "SalesPersonId": "ID",
            "SalesPersonName": "Full name",
            "BranchId": "Assigned branch",
            "Target": "Monthly target",
        },
    },
    "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID": {
        "title": "Salesperson Top-N",
        "description": "Used for the Top Salespersons chart.",
        "columns": {
            "SalesPersonName": "Name",
            "BranchAlias": "Branch",
            "XnDt": "Date",
            "NetSlsNetAmount": "Revenue",
        },
    },
}

PRIORITY_ORDER = list(KNOWN_OBJECTS.keys())

SCHEMA_QUERY = """
SELECT
    t.TABLE_SCHEMA,
    t.TABLE_NAME,
    t.TABLE_TYPE,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.NUMERIC_SCALE,
    c.DATETIME_PRECISION,
    c.ORDINAL_POSITION
FROM INFORMATION_SCHEMA.TABLES t
INNER JOIN INFORMATION_SCHEMA.COLUMNS c
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
   AND t.TABLE_NAME = c.TABLE_NAME
WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
  AND t.TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest')
  {schema_filter}
ORDER BY
    t.TABLE_TYPE,
    t.TABLE_SCHEMA,
    t.TABLE_NAME,
    c.ORDINAL_POSITION
"""


@dataclass
class Column:
    name: str
    data_type: str
    used_for: str = ""


@dataclass
class DbObject:
    schema: str
    name: str
    object_type: str  # VIEW | TABLE
    columns: List[Column] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def kind_label(self) -> str:
        return "View" if self.object_type == "VIEW" else "Table"


def _db_credentials() -> Tuple[str, str, str, str, str]:
    server = os.getenv("DB_SERVER") or os.getenv("ERP_DB_HOST", "")
    port = str(os.getenv("DB_PORT") or os.getenv("ERP_DB_PORT", "1433"))
    database = os.getenv("DB_NAME") or os.getenv("ERP_DB_NAME", "")
    user = os.getenv("DB_USER") or os.getenv("ERP_DB_USER", "")
    password = os.getenv("DB_PASSWORD") or os.getenv("ERP_DB_PASSWORD", "")

    if not all([server, database, user, password]):
        raise ValueError(
            "Missing DB_SERVER, DB_NAME, DB_USER, or DB_PASSWORD in backend/.env"
        )
    return server, port, database, user, password


def _odbc_drivers_to_try() -> List[str]:
    preferred = os.getenv("ODBC_DRIVER", "")
    installed = []
    try:
        installed = list(pyodbc.drivers())
    except Exception:
        pass
    candidates = [
        preferred,
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]
    ordered: List[str] = []
    for d in candidates:
        if d and d not in ordered and (not installed or d in installed):
            ordered.append(d)
    if not ordered and installed:
        ordered = installed
    return ordered


def build_conn_str(driver: str) -> str:
    server, port, database, user, password = _db_credentials()
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"Connect Timeout=60;"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no;"
    )


def connect_pyodbc():
    last_err: Optional[Exception] = None
    for driver in _odbc_drivers_to_try():
        try:
            conn = pyodbc.connect(build_conn_str(driver), timeout=60)
            print(f"Connected via ODBC driver: {driver}")
            return conn
        except Exception as exc:
            last_err = exc
    raise RuntimeError(
        "Could not connect with pyodbc. Install 'ODBC Driver 17 for SQL Server' "
        "or run: pip install pymssql"
    ) from last_err


def connect_pymssql():
    import pymssql

    server, port, database, user, password = _db_credentials()
    conn = pymssql.connect(
        server=server,
        port=int(port),
        user=user,
        password=password,
        database=database,
        login_timeout=60,
        timeout=120,
    )
    print("Connected via pymssql")
    return conn


def connect():
    try:
        return connect_pyodbc()
    except Exception as pyodbc_err:
        try:
            import pymssql  # noqa: F401
        except ImportError:
            raise pyodbc_err
        print(f"pyodbc failed ({pyodbc_err}). Trying pymssql...")
        return connect_pymssql()


def format_sql_type(
    data_type: str,
    char_len: Optional[int],
    num_precision: Optional[int],
    num_scale: Optional[int],
) -> str:
    dt = (data_type or "").lower()
    if dt in ("varchar", "nvarchar", "char", "nchar"):
        return "varchar" if dt.startswith("var") or dt.startswith("n") else dt
    if dt in ("decimal", "numeric", "money", "smallmoney"):
        return "decimal"
    if dt in ("int", "bigint", "smallint", "tinyint"):
        return "int" if dt == "int" else dt
    if dt in ("float", "real"):
        return "decimal"
    if dt in ("datetime", "datetime2", "date", "smalldatetime"):
        return "datetime"
    if dt == "bit":
        return "bit"
    if dt in ("uniqueidentifier",):
        return "varchar"
    return dt or "unknown"


def fetch_objects(
    conn: pyodbc.Connection,
    schema: Optional[str] = None,
    only_views: bool = False,
    only_tables: bool = False,
) -> Dict[str, DbObject]:
    schema_filter = ""
    if schema:
        schema_filter = f"AND t.TABLE_SCHEMA = '{schema.replace(chr(39), chr(39)+chr(39))}'"

    query = SCHEMA_QUERY.format(schema_filter=schema_filter)
    cursor = conn.cursor()
    cursor.execute(query)

    objects: Dict[str, DbObject] = {}
    for row in cursor.fetchall():
        table_schema, table_name, table_type, col_name, data_type = row[0:5]
        char_len, num_prec, num_scale = row[5], row[6], row[7]

        otype = "VIEW" if table_type == "VIEW" else "TABLE"
        if only_views and otype != "VIEW":
            continue
        if only_tables and otype != "TABLE":
            continue

        key = f"{table_schema}.{table_name}"
        if key not in objects:
            objects[key] = DbObject(
                schema=table_schema,
                name=table_name,
                object_type=otype,
            )

        fmt_type = format_sql_type(data_type, char_len, num_prec, num_scale)
        known_cols = {}
        meta = KNOWN_OBJECTS.get(key)
        if meta:
            known_cols = meta.get("columns") or {}

        used_for = known_cols.get(col_name) or describe_column(col_name, key)
        objects[key].columns.append(
            Column(name=col_name, data_type=fmt_type, used_for=used_for)
        )

    return objects


def sort_object_keys(keys: List[str]) -> List[str]:
    priority = {name: i for i, name in enumerate(PRIORITY_ORDER)}
    return sorted(
        keys,
        key=lambda k: (
            priority.get(k, 1000),
            0 if k in priority else 1,
            k.lower(),
        ),
    )


def render_object(index: int, obj: DbObject) -> str:
    meta = KNOWN_OBJECTS.get(obj.full_name, {})
    view_meta = VIEW_DESCRIPTIONS.get(obj.full_name)
    if view_meta:
        title_suffix, description = view_meta[0], view_meta[1]
    else:
        title_suffix = meta.get("title") or obj.kind_label
        description = meta.get("description") or (
            f"SQL Server {obj.kind_label.lower()} `{obj.full_name}`."
        )

    lines = [
        f"{index}. {obj.full_name} — {title_suffix}",
        description,
        "Column\tType\tUsed for",
    ]

    for col in obj.columns:
        used = col.used_for or describe_column(col.name, obj.full_name)
        lines.append(f"{col.name}\t{col.data_type}\t{used}")

    lines.append("")
    return "\n".join(lines)


def write_catalog(
    objects: Dict[str, DbObject],
    output_path: Path,
    database_name: str,
) -> None:
    keys = sort_object_keys(list(objects.keys()))
    views = sum(1 for k in keys if objects[k].object_type == "VIEW")
    tables = len(keys) - views

    header = [
        "SmarterP Connector — Database Schema Catalog",
        f"Database: {database_name}",
        f"Objects: {len(keys)} ({views} views, {tables} tables)",
        "",
        "=" * 72,
        "",
    ]

    body = []
    for i, key in enumerate(keys, start=1):
        body.append(render_object(i, objects[key]))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(header) + "\n".join(body), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export SQL Server schema catalog")
    parser.add_argument(
        "--output",
        "-o",
        default=str(BACKEND_ROOT / "schema_catalog.txt"),
        help="Output file path (default: backend/schema_catalog.txt)",
    )
    parser.add_argument("--schema", default=None, help="Limit to one schema (e.g. dbo)")
    parser.add_argument("--only-views", action="store_true", help="Export views only")
    parser.add_argument("--only-tables", action="store_true", help="Export tables only")
    args = parser.parse_args()

    database = os.getenv("DB_NAME") or os.getenv("ERP_DB_NAME", "")

    print(f"Connecting to {database}...")
    conn = connect()
    try:
        objects = fetch_objects(
            conn,
            schema=args.schema,
            only_views=args.only_views,
            only_tables=args.only_tables,
        )
    finally:
        conn.close()

    if not objects:
        print("No tables or views found.")
        sys.exit(1)

    out = Path(args.output)
    write_catalog(objects, out, database)
    print(f"Wrote {len(objects)} objects ({sum(len(o.columns) for o in objects.values())} columns) to:")
    print(f"  {out.resolve()}")


if __name__ == "__main__":
    main()
