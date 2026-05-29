"""
Build schema index: crawls every VIEW in dbo schema, records columns + date ranges,
then auto-resolves which view/column to use for each business concept.

Output: backend/src/schema_index.json

Run from backend/:
    python scripts/build_schema_index.py              # fast: 11 priority views, capped MTD probe
    python scripts/build_schema_index.py --skip-probe # instant: columns + catalog routing only
    python scripts/build_schema_index.py --full       # slow: full-table COUNT (diagnostics)
    python scripts/build_schema_index.py --all-views --probe-all  # every view, every date col
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.mssql import init_mssql, execute_query

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "schema_index.json"
)

DATE_TYPES = {"date", "datetime", "datetime2", "smalldatetime"}
NUM_TYPES  = {"int","bigint","smallint","tinyint","float","real","decimal","numeric","money","smallmoney"}

# Views we actually care about (crawl all, but rank these first)
PRIORITY_VIEWS = [
    "VW_MB_POWERBI_APP_REPORT",
    "VW_MB_POWERBI_SLS_REPORT",
    "VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID",
    "VW_MB_POWERBI_STO_REPORT",
    "VW_MB_POWERBI_STI_REPORT",
    "VW_MB_POWERBI_STOCK_REPORT",
    "VW_MB_POWERBI_PRODUCT_MASTER",
    "VwAISalesData",
    "VwAIBranch",
    "VwAICustomerDetails",
    "VwAIStockData",
]

# Business concepts → candidate column name patterns (checked against actual columns)
CONCEPT_PATTERNS = {
    "date":       ["XnDt","XnMemoDate","CashmemoDt","InvoiceDt","Sales_Date","EntryDt","TransactionDate","OrderDate","Date","Dt"],
    "amount":     ["NetAmount","NetSlsNetAmount","SalesNetAmount","Amount","Revenue","Sales","GrossAmount"],
    "quantity":   ["AppQty","NetSlsQty","Qty","Quantity","SalesQty","Units"],
    "bill_count": ["BillCount","InvoiceCount","Bills","CashmemoCount"],
    "branch":     ["BranchAlias","BranchName","Branch","BranchCode","BranchId"],
    "category":   ["CategoryShortName","CategoryName","Category","CatName"],
    "department": ["DepartmentShortName","DepartmentName","Department","DeptName"],
    "item_id":    ["ItemId","ItemCode","Itemcode","ArticleNo","SKU"],
    "item_name":  ["ItemName","ItemDescription","Description","ProductName"],
    "customer":   ["CustomerId","CustomerCode","MemberId"],
    "bill_no":    ["CashmemoNo","InvoiceNo","BillNo","ReceiptNo"],
    "supplier":   ["SupplierName","SupplierAlias","VendorName"],
    "mrp":        ["ItemMRP","MRP","MaxRetailPrice"],
    "purchase_price": ["PurchasePrice","CostPrice","Cost"],
}

# Per-view: only probe these date columns (skip PurDate etc. on huge sales views)
VIEW_DATE_COLUMN_HINTS: dict[str, list[str]] = {
    "VW_MB_POWERBI_SLS_REPORT": ["XnMemoDate"],
    "VW_MB_POWERBI_APP_REPORT": ["XnDt", "CashmemoDt"],
    "VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID": ["XnMemoDate", "Sales_Date"],
}

# Fallback routing when MTD probe is 0 or skipped (from schema_catalog)
SALES_VIEW_DEFAULTS = {
    "VW_MB_POWERBI_SLS_REPORT": {
        "date_col": "XnMemoDate",
        "amount_col": "NetAmount",
        "quantity_col": "NetSlsQty",
        "bill_count_mode": "rows",
    },
    "VW_MB_POWERBI_APP_REPORT": {
        "date_col": "XnDt",
        "amount_col": "NetAmount",
        "quantity_col": "AppQty",
        "bill_count_col": "BillCount",
        "bill_count_mode": "column",
    },
}


def mtd_window() -> tuple[str, str]:
    """Current calendar month [start, end) as ISO dates for bounded probes."""
    today = date.today()
    start = today.replace(day=1)
    end = today + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _date_str(v) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v)[:10]


def _order_date_columns(date_cols: list[str], view_name: str) -> list[str]:
    """Prefer known business date columns; cap how many we hit per view."""
    hints = VIEW_DATE_COLUMN_HINTS.get(view_name)
    if hints:
        hinted = [c for c in hints if c in date_cols]
        rest = [c for c in date_cols if c not in hinted]
        ordered = hinted + rest
    else:
        preferred = CONCEPT_PATTERNS["date"]
        col_set = {c.lower(): c for c in date_cols}
        ordered = [col_set[p.lower()] for p in preferred if p.lower() in col_set]
        ordered += [c for c in date_cols if c not in ordered]
    return ordered[:6]


async def get_all_views():
    sql = """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.VIEWS
        WHERE TABLE_SCHEMA = 'dbo'
        ORDER BY TABLE_NAME
    """
    res = await execute_query(sql)
    return [r["TABLE_NAME"] for r in res["records"]]


async def get_columns(view_name: str):
    sql = """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = @view
        ORDER BY ORDINAL_POSITION
    """
    res = await execute_query(sql, params={"view": view_name})
    return res["records"]


# Stop after this many MTD rows (routing only needs >100; keeps huge views fast).
MTD_COUNT_CAP = 151


async def probe_date_column_capped(
    view_name: str, date_col: str, mtd_start: str, mtd_end: str
) -> dict:
    """Count MTD rows up to MTD_COUNT_CAP via SELECT TOP — fast on huge views."""
    safe = date_col.replace("]", "]]")
    sql = f"""
        SELECT
            COUNT(*) AS MTD_Rows,
            MIN(d) AS MinDate,
            MAX(d) AS MaxDate
        FROM (
            SELECT TOP (@cap) CAST([{safe}] AS DATE) AS d
            FROM dbo.[{view_name}] WITH (NOLOCK)
            WHERE [{safe}] >= @mtd_start AND [{safe}] < @mtd_end
        ) sample
    """
    try:
        res = await execute_query(
            sql,
            params={
                "cap": MTD_COUNT_CAP,
                "mtd_start": mtd_start,
                "mtd_end": mtd_end,
            },
        )
        rec = res["records"][0] if res["records"] else {}
        mtd = int(rec.get("MTD_Rows") or 0)
        return {
            "min_date": _date_str(rec.get("MinDate")),
            "max_date": _date_str(rec.get("MaxDate")),
            "total_rows": None,
            "mtd_rows": mtd,
            "mtd_rows_capped": mtd >= MTD_COUNT_CAP,
            "probe_mode": "mtd_capped",
            "mtd_window": [mtd_start, mtd_end],
        }
    except Exception as e:
        return {"error": str(e)[:120], "probe_mode": "mtd_capped"}


async def probe_date_columns_fast(view_name: str, date_cols: list[str]) -> dict[str, dict]:
    """Probe each date column with a capped MTD sample (parallel when multiple cols)."""
    if not date_cols:
        return {}

    mtd_start, mtd_end = mtd_window()
    results = await asyncio.gather(
        *[probe_date_column_capped(view_name, dc, mtd_start, mtd_end) for dc in date_cols]
    )
    return dict(zip(date_cols, results))


async def probe_date_column_full(view_name: str, date_col: str) -> dict:
    """Slow legacy probe: full-table MIN/MAX/COUNT (use --full only for diagnostics)."""
    mtd_start, mtd_end = mtd_window()
    try:
        safe = date_col.replace("]", "]]")
        sql = f"""
            SELECT
                MIN(CAST([{safe}] AS DATE)) AS MinDate,
                MAX(CAST([{safe}] AS DATE)) AS MaxDate,
                COUNT(*) AS TotalRows,
                SUM(CASE WHEN [{safe}] >= @mtd_start AND [{safe}] < @mtd_end THEN 1 ELSE 0 END) AS MTD_Rows
            FROM dbo.[{view_name}] WITH (NOLOCK)
        """
        res = await execute_query(sql, params={"mtd_start": mtd_start, "mtd_end": mtd_end})
        rec = res["records"][0] if res["records"] else {}
        return {
            "min_date": _date_str(rec.get("MinDate")),
            "max_date": _date_str(rec.get("MaxDate")),
            "total_rows": int(rec.get("TotalRows") or 0),
            "mtd_rows": int(rec.get("MTD_Rows") or 0),
            "probe_mode": "full_table",
            "mtd_window": [mtd_start, mtd_end],
        }
    except Exception as e:
        return {"error": str(e)[:120], "probe_mode": "full_table"}


def resolve_concept(col_names: list, concept: str) -> str | None:
    """Find first matching column for a concept pattern."""
    patterns = CONCEPT_PATTERNS.get(concept, [])
    col_set = {c.lower(): c for c in col_names}
    for p in patterns:
        if p.lower() in col_set:
            return col_set[p.lower()]
    return None


async def build_view_entry(
    view_name: str,
    *,
    probe_dates: bool = True,
    full_probe: bool = False,
) -> dict:
    t0 = time.perf_counter()
    print(f"  Scanning {view_name}...", end=" ", flush=True)
    cols = await get_columns(view_name)
    if not cols:
        print("no columns")
        return {}

    col_names   = [c["COLUMN_NAME"] for c in cols]
    date_cols   = [c["COLUMN_NAME"] for c in cols if c["DATA_TYPE"].lower() in DATE_TYPES]
    num_cols    = [c["COLUMN_NAME"] for c in cols if c["DATA_TYPE"].lower() in NUM_TYPES]
    all_col_map = {c["COLUMN_NAME"]: c["DATA_TYPE"] for c in cols}

    date_probes: dict[str, dict] = {}
    if probe_dates and date_cols:
        to_probe = _order_date_columns(date_cols, view_name)
        if full_probe:
            for dc in to_probe:
                date_probes[dc] = await probe_date_column_full(view_name, dc)
        else:
            date_probes = await probe_date_columns_fast(view_name, to_probe)

    # Pick best date column = highest MTD count; else prefer catalog hint / concept "date"
    best_date = None
    best_mtd  = -1
    for dc, info in date_probes.items():
        if info.get("error"):
            continue
        mtd = info.get("mtd_rows", 0) or 0
        if mtd > best_mtd:
            best_mtd = mtd
            best_date = dc
    if best_date is None:
        hints = VIEW_DATE_COLUMN_HINTS.get(view_name, [])
        for h in hints:
            if h in date_cols:
                best_date = h
                break
        if best_date is None:
            best_date = resolve_concept(col_names, "date")
        best_mtd = max(best_mtd, 0)

    concepts = {}
    for concept in CONCEPT_PATTERNS:
        found = resolve_concept(col_names, concept)
        if found:
            concepts[concept] = found

    elapsed = time.perf_counter() - t0
    probe_note = "no date probe" if not probe_dates else ("full" if full_probe else "mtd")
    print(
        f"OK ({len(col_names)} cols, best_date={best_date}, mtd_rows={best_mtd}, "
        f"{probe_note}, {elapsed:.1f}s)",
        flush=True,
    )

    return {
        "view": view_name,
        "schema": "dbo",
        "columns": all_col_map,
        "date_columns": date_probes,
        "numeric_columns": num_cols,
        "best_date_column": best_date,
        "best_date_mtd_rows": best_mtd,
        "concepts": concepts,
    }


def build_routing_map(index: dict) -> dict:
    """
    Build a direct routing map: business_metric → {view, date_col, amount_col, qty_col, ...}
    Picks the view with the highest MTD row count for each concept.
    """
    entries = list(index["views"].values())

    def best_view_for(concept: str, min_mtd: int = 100) -> dict | None:
        candidates = [
            e for e in entries
            if concept in e.get("concepts", {})
            and (e.get("best_date_mtd_rows") or 0) >= min_mtd
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda e: e.get("best_date_mtd_rows", 0))

    def view_entry(view_name: str) -> dict | None:
        return index["views"].get(view_name)

    routing = {}

    def _sales_routing(vname: str, ve: dict, *, probed: bool) -> dict:
        c = ve.get("concepts", {})
        defaults = SALES_VIEW_DEFAULTS.get(vname, {})
        return {
            "view": f"dbo.{vname}",
            "date_col": ve.get("best_date_column") or defaults.get("date_col"),
            "amount_col": c.get("amount", defaults.get("amount_col", "NetAmount")),
            "quantity_col": c.get("quantity", defaults.get("quantity_col", "NetSlsQty")),
            "bill_count_col": c.get("bill_count") or defaults.get("bill_count_col"),
            "bill_count_mode": (
                "column" if c.get("bill_count") or defaults.get("bill_count_mode") == "column"
                else "rows"
            ),
            "branch_col": c.get("branch", "BranchAlias"),
            "category_col": c.get("category", "CategoryShortName"),
            "department_col": c.get("department", "DepartmentShortName"),
            "mtd_rows": ve.get("best_date_mtd_rows"),
            "source_view_name": vname,
            "routing_source": "mtd_probe" if probed else "catalog_default",
        }

    # Prefer APP_REPORT if MTD qualifies; else SLS_REPORT; else defaults without probe
    for vname in ["VW_MB_POWERBI_APP_REPORT", "VW_MB_POWERBI_SLS_REPORT"]:
        ve = view_entry(vname)
        if not ve:
            continue
        mtd = ve.get("best_date_mtd_rows") or 0
        if mtd > 100:
            routing["sales_main"] = _sales_routing(vname, ve, probed=True)
            break

    if "sales_main" not in routing:
        for vname in ["VW_MB_POWERBI_SLS_REPORT", "VW_MB_POWERBI_APP_REPORT"]:
            ve = view_entry(vname)
            if ve and vname in SALES_VIEW_DEFAULTS:
                routing["sales_main"] = _sales_routing(vname, ve, probed=False)
                break

    # ── Today's sales ──
    # Same as sales_main but use the same view — the date filter handles "today"
    if "sales_main" in routing:
        routing["today_sales"] = dict(routing["sales_main"])
        routing["today_sales"]["note"] = "same view as sales_main, filter date_col = today"

    # ── Stock / inventory ──
    ve = view_entry("VW_MB_POWERBI_STOCK_REPORT")
    if ve and ve.get("concepts"):
        c = ve["concepts"]
        routing["stock"] = {
            "view": "dbo.VW_MB_POWERBI_STOCK_REPORT",
            "date_col":   ve["best_date_column"],
            "qty_col":    c.get("quantity"),
            "item_id_col":c.get("item_id"),
            "branch_col": c.get("branch"),
        }

    # ── Stock transfers out ──
    ve = view_entry("VW_MB_POWERBI_STO_REPORT")
    if ve and ve.get("concepts"):
        c = ve["concepts"]
        routing["stock_transfers_out"] = {
            "view": "dbo.VW_MB_POWERBI_STO_REPORT",
            "date_col":   ve["best_date_column"],
            "amount_col": c.get("amount"),
            "qty_col":    c.get("quantity"),
        }

    # ── Stock transfers in ──
    ve = view_entry("VW_MB_POWERBI_STI_REPORT")
    if ve and ve.get("concepts"):
        c = ve["concepts"]
        routing["stock_transfers_in"] = {
            "view": "dbo.VW_MB_POWERBI_STI_REPORT",
            "date_col":   ve["best_date_column"],
            "amount_col": c.get("amount"),
            "qty_col":    c.get("quantity"),
        }

    # ── Product master ──
    ve = view_entry("VW_MB_POWERBI_PRODUCT_MASTER")
    if ve and ve.get("concepts"):
        c = ve["concepts"]
        routing["product_master"] = {
            "view": "dbo.VW_MB_POWERBI_PRODUCT_MASTER",
            "item_id_col":     c.get("item_id"),
            "item_name_col":   c.get("item_name"),
            "category_col":    c.get("category"),
            "department_col":  c.get("department"),
            "supplier_col":    c.get("supplier"),
            "mrp_col":         c.get("mrp"),
            "purchase_price_col": c.get("purchase_price"),
        }

    # ── Salesperson ──
    ve = view_entry("VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID")
    if ve and ve.get("concepts"):
        c = ve["concepts"]
        routing["salesperson"] = {
            "view": "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID",
            "date_col":   ve["best_date_column"] or c.get("date"),
            "amount_col": c.get("amount"),
        }

    return routing


def parse_args():
    p = argparse.ArgumentParser(description="Build schema_index.json from SQL Server views")
    p.add_argument(
        "--full",
        action="store_true",
        help="Full-table COUNT/MIN/MAX per date column (slow; diagnostic only)",
    )
    p.add_argument(
        "--all-views",
        action="store_true",
        help="Include every dbo view in the index (default: PRIORITY_VIEWS only)",
    )
    p.add_argument(
        "--probe-all",
        action="store_true",
        help="MTD-probe all indexed views, not only PRIORITY_VIEWS",
    )
    p.add_argument(
        "--skip-probe",
        action="store_true",
        help="Metadata + catalog defaults only (no MTD SQL probes)",
    )
    return p.parse_args()


async def main():
    args = parse_args()
    await init_mssql()

    mtd_start, mtd_end = mtd_window()
    mode = "full_table" if args.full else "mtd_capped"
    print(f"\n-- Probe mode: {mode} (MTD {mtd_start} .. {mtd_end}) --")

    print("\n── Fetching all views ──")
    all_views = await get_all_views()
    print(f"Found {len(all_views)} views: {all_views[:10]}{'...' if len(all_views) > 10 else ''}")

    ordered = [v for v in PRIORITY_VIEWS if v in all_views]
    rest    = [v for v in all_views if v not in ordered]
    to_scan = (ordered + rest) if args.all_views else ordered
    priority_set = set(PRIORITY_VIEWS)

    print(f"\n── Scanning {len(to_scan)} views ──")
    views_index = {}
    for vname in to_scan:
        probe_dates = (
            not args.skip_probe
            and (args.probe_all or vname in priority_set)
        )
        entry = await build_view_entry(
            vname,
            probe_dates=probe_dates,
            full_probe=args.full,
        )
        if entry:
            views_index[vname] = entry

    print("\n── Building routing map ──")
    routing = build_routing_map({"views": views_index})

    output = {
        "generated_at": datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        "probe_mode": mode,
        "mtd_window": [mtd_start, mtd_end],
        "total_views": len(views_index),
        "routing": routing,
        "views": views_index,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✅ Schema index written → {OUTPUT_PATH}")
    print(f"\n── ROUTING MAP ──")
    for concept, r in routing.items():
        print(f"\n  [{concept}]")
        for k, v in r.items():
            print(f"    {k}: {v}")

asyncio.run(main())
