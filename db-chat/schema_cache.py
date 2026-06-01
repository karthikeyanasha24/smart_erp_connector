"""
schema_cache.py — Offline schema store for db_chat.py
======================================================
Run once to snapshot your DB schema:
    python schema_cache.py

Then db_chat.py loads from schema_cache.json instead of querying the DB
every time. Re-run whenever your schema changes.
"""

import json
import os
import sys
from datetime import date, datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Load .env if present ──────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

DB_SERVER   = os.getenv("DB_SERVER",   "38.45.94.39")
DB_PORT     = os.getenv("DB_PORT",     "12866")
DB_NAME     = os.getenv("DB_NAME",     "zRetailHQ0")
DB_USER     = os.getenv("DB_USER",     "zorderai")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Mb@2026")

CACHE_FILE  = os.path.join(os.path.dirname(__file__), "schema_cache.json")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CURATED KNOWLEDGE  — correct view/column mappings from your .env config
# The AI will use this to write correct SQL without guessing column names.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CURATED: dict = {
    "primary_sales_view": {
        "name": "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID",
        "alias": "MAIN SALES VIEW (use this for revenue/sales questions)",
        "date_column": "CashmemoDt",
        "amount_column": "SalesNetAmount",
        "branch_column": "BranchAlias",
        "category_column": "CategoryShortName",
        "department_column": "DepartmentShortName",
        "salesperson_column": "SalesPersonName",
        "customer_id_column": "CustomerId",
        "transaction_id_column": "CashmemoNo",
        "quantity_column": "SalesQuantity",
        "cost_column": "SalesCost",
        "sample_query": (
            "SELECT TOP 5 BranchAlias, SUM(SalesNetAmount) AS Revenue "
            "FROM dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID WITH (NOLOCK) "
            "WHERE CashmemoDt >= DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1) "
            "AND CashmemoDt < DATEADD(month,1,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1)) "
            "GROUP BY BranchAlias ORDER BY Revenue DESC"
        ),
    },
    "transactions_view": {
        "name": "dbo.VW_MB_POWERBI_SLSXNS_REPORT",
        "alias": "TRANSACTION LINES VIEW (use for detailed transaction browsing)",
        "date_column": "XnDt",
        "amount_column": "NetSlsNetAmount",
        "branch_column": "BranchAlias",
        "category_column": "CategoryShortName",
        "transaction_id_column": "CashmemoNo",
        "note": "Use this view only for per-transaction detail, not revenue aggregation",
    },
    "customers_view": {
        "name": "dbo.VwAICustomerDetails",
        "alias": "CUSTOMER MASTER",
        "key_columns": ["CustomerId", "CustomerFirstName", "CustomerLastName",
                        "ContactMobile", "ContactEmail", "City", "State",
                        "CreatedOn", "ActiveStatus"],
    },
    "sales_view_simple": {
        "name": "dbo.VwAISalesData",
        "alias": "SIMPLE SALES FACT TABLE (for joins with customer/salesperson masters)",
        "date_column": "InvoiceDt",
        "amount_column": "SaleNetAmount",
        "customer_column": "CustomerId",
        "salesperson_column": "SalesPersonId",
        "branch_column": "BranchId",
    },
    "product_master": {
        "name": "dbo.VW_MB_POWERBI_PRODUCT_MASTER",
        "alias": "PRODUCT / ITEM CATALOG",
        "key_columns": ["ItemId", "Itemcode", "ArticleNo", "DepartmentShortName",
                        "CategoryShortName", "SubCategoryName", "SupplierName",
                        "SupplierAlias", "ItemMRP", "PurDate"],
    },
    "purchases_view": {
        "name": "dbo.VW_MB_POWERBI_PURXNS_REPORT",
        "alias": "PURCHASE TRANSACTIONS",
        "date_column": "XnDt",
        "branch_column": "BranchAlias",
        "category_column": "CategoryShortName",
    },
    "stock_view": {
        "name": "dbo.VwAIStockData",
        "alias": "CURRENT STOCK LEVELS",
        "key_columns": ["ItemId", "BranchId", "StockQty"],
    },
    "branches_view": {
        "name": "dbo.VW_MB_POWERBI_BRANCH_LIST",
        "alias": "BRANCH MASTER",
        "key_columns": ["BranchId", "BranchName", "ShortName", "City", "State", "ActiveStatus"],
    },
    "salespersons_view": {
        "name": "dbo.VwAISalesPerson",
        "alias": "SALESPERSON MASTER",
        "key_columns": ["SalesPersonId", "SalesPersonName", "SalesPersonShortName"],
    },
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DB HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _connect():
    import pyodbc
    preferred = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]
    installed = set(pyodbc.drivers())
    available = [d for d in preferred if d in installed]
    if not available:
        print(f"No ODBC driver found. Installed: {sorted(installed)}")
        sys.exit(1)

    last_err = None
    for driver in available:
        modern = "ODBC Driver" in driver or "Native Client" in driver
        base = (
            f"DRIVER={{{driver}}};"
            f"SERVER={DB_SERVER},{DB_PORT};"
            f"DATABASE={DB_NAME};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
            "Connection Timeout=30;"
        )
        variants = (
            [base + "TrustServerCertificate=yes;Encrypt=yes;",
             base + "TrustServerCertificate=yes;Encrypt=no;",
             base]
            if modern else [base]
        )
        for cs in variants:
            try:
                return pyodbc.connect(cs, timeout=30)
            except Exception as e:
                last_err = e
    print(f"Connection failed: {last_err}")
    sys.exit(1)


def _query(conn, sql: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute(sql)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SNAPSHOT LOGIC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_snapshot() -> dict:
    print(f"Connecting to {DB_NAME} on {DB_SERVER}:{DB_PORT}…")
    conn = _connect()
    print("Connected. Fetching schema…")

    rows = _query(conn, """
        SELECT
            o.TABLE_SCHEMA + '.' + o.TABLE_NAME AS object_name,
            o.TABLE_TYPE,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.IS_NULLABLE,
            c.ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.TABLES  o
        JOIN INFORMATION_SCHEMA.COLUMNS c
          ON c.TABLE_SCHEMA = o.TABLE_SCHEMA
         AND c.TABLE_NAME   = o.TABLE_NAME
        WHERE o.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
          AND o.TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA')
        ORDER BY o.TABLE_SCHEMA, o.TABLE_NAME, c.ORDINAL_POSITION
    """)

    conn.close()
    print(f"Fetched {len(rows)} column records.")

    # Group into objects
    objects: dict = {}
    for r in rows:
        name = r["object_name"]
        if name not in objects:
            objects[name] = {
                "type": "VIEW" if r["TABLE_TYPE"] == "VIEW" else "TABLE",
                "columns": [],
            }
        col_def = {
            "name": r["COLUMN_NAME"],
            "type": r["DATA_TYPE"],
            "nullable": r["IS_NULLABLE"] == "YES",
        }
        if r["CHARACTER_MAXIMUM_LENGTH"]:
            col_def["max_len"] = r["CHARACTER_MAXIMUM_LENGTH"]
        objects[name]["columns"].append(col_def)

    return {
        "db": DB_NAME,
        "server": f"{DB_SERVER}:{DB_PORT}",
        "snapshotted_at": datetime.now().isoformat(timespec="seconds"),
        "curated": CURATED,
        "objects": objects,
    }


def save_snapshot(snap: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    print(f"\nSchema saved to: {CACHE_FILE}")
    print(f"  {len(snap['objects'])} views/tables captured.")
    print(f"  {sum(len(o['columns']) for o in snap['objects'].values())} total columns.")


def load_snapshot() -> dict | None:
    if not os.path.exists(CACHE_FILE):
        return None
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RENDER  (schema → text block for AI context)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_schema_text(snap: dict, *, expand: bool = False) -> str:
    today = date.today().isoformat()
    lines = [
        f"DATABASE : {snap['db']}  SERVER: {snap['server']}",
        f"TODAY    : {today}",
        f"SCHEMA   : {snap.get('snapshotted_at','?')}",
        "",
        "=" * 70,
        "CURATED VIEW GUIDE  — AI MUST USE THESE COLUMN NAMES EXACTLY",
        "=" * 70,
    ]

    for key, info in snap.get("curated", {}).items():
        lines.append(f"\n▶ {info.get('alias', key)}")
        lines.append(f"  View : {info['name']}")
        for k, v in info.items():
            if k in ("name", "alias"):
                continue
            if isinstance(v, list):
                lines.append(f"  {k:25s}: {', '.join(v)}")
            else:
                lines.append(f"  {k:25s}: {v}")

    lines += [
        "",
        "=" * 70,
        "FULL SCHEMA  (all views and tables with every column)",
        "=" * 70,
    ]

    objects = snap.get("objects", {})
    for obj_name in sorted(objects):
        obj = objects[obj_name]
        cols = obj["columns"]
        col_strs = [
            f"{c['name']} ({c['type']}{'?' if c['nullable'] else ''})"
            for c in cols
        ]
        lines.append(f"\n[{obj['type']}] {obj_name}")
        if expand or len(col_strs) > 15:
            lines.append("  Columns:")
            lines.extend(f"    - {c}" for c in col_strs)
        else:
            lines.append(f"  Columns: {', '.join(col_strs)}")

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Snapshot DB schema to schema_cache.json")
    p.add_argument("--print", action="store_true", help="Print rendered schema text and exit")
    args = p.parse_args()

    if args.print:
        snap = load_snapshot()
        if not snap:
            print("No cache found. Run: python schema_cache.py")
            sys.exit(1)
        print(render_schema_text(snap, expand=True))
        sys.exit(0)

    snap = build_snapshot()
    save_snapshot(snap)
    print("\nPreview of rendered schema (first 60 lines):")
    print("-" * 60)
    preview = render_schema_text(snap).split("\n")[:60]
    print("\n".join(preview))
    print("…")
    print(f"\nDone. db_chat.py will now load schema from file — no DB hit on startup.")
