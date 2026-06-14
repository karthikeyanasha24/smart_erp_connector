"""
Live cross-verification for the 2026-06-13 targeted FAQ fixes (Manoj issues).

What it proves, against the live SQL Server:
  1. Category Contribution %  (#42) — now reads the canonical SLS_DATA_WITHOUT_ITEMID
     view instead of the sparse APP_REPORT view.
  2. Supplier Contribution %  (#29) — same switch.
  3. Gross Margin by Category (#43) — now Revenue=SalesNetAmount, Cost=SalesCost on
     the canonical view.

For each, it runs BOTH the OLD (APP_REPORT) SQL and the NEW (canonical) SQL for the
same MTD window, prints the grand totals side by side, and shows how far apart they
were. It then reconciles the NEW category-contribution total against the Analytics
dashboard's own category math (src.analytics.dashboard._query_contribution) — these
should now match within a rounding tolerance, which is the whole point of the fix.

Run from the repo root or the test/ folder:
    python test/verify_contribution_margin_fix.py

Requires backend/.env (DB credentials) — same setup the other verify_*.py scripts use.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from nlq_faq_sql import try_faq_template  # noqa: E402

# Canonical view + the OLD sparse view, so we can run both for comparison.
_SALESPERSON = "dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID]"
_APP = "dbo.[VW_MB_POWERBI_APP_REPORT]"

_CASHMEMO_MTD = (
    "sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) "
    "AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))"
)
_XN_MTD = (
    "s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) "
    "AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))"
)

# OLD (APP_REPORT) totals — what the templates used to return.
OLD_CATEGORY_TOTAL = f"SELECT CAST(SUM(s.[NetAmount]) AS decimal(18,2)) AS T FROM {_APP} s WITH (NOLOCK) WHERE {_XN_MTD} AND s.[CategoryShortName] IS NOT NULL"
OLD_SUPPLIER_TOTAL = f"SELECT CAST(SUM(s.[NetAmount]) AS decimal(18,2)) AS T FROM {_APP} s WITH (NOLOCK) WHERE {_XN_MTD} AND s.[SupplierName] IS NOT NULL"

# NEW (canonical) totals — what they return now.
NEW_CATEGORY_TOTAL = f"SELECT CAST(SUM(sp.[SalesNetAmount]) AS decimal(18,2)) AS T FROM {_SALESPERSON} sp WITH (NOLOCK) WHERE {_CASHMEMO_MTD} AND sp.[CategoryShortName] IS NOT NULL"
NEW_SUPPLIER_TOTAL = f"SELECT CAST(SUM(sp.[SalesNetAmount]) AS decimal(18,2)) AS T FROM {_SALESPERSON} sp WITH (NOLOCK) WHERE {_CASHMEMO_MTD} AND sp.[SupplierName] IS NOT NULL"


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _L(v: float) -> str:
    """Format rupees as ₹ Lakhs."""
    return f"{v/100000:,.2f} L"


def _first_total(records) -> float:
    if not records:
        return 0.0
    row = records[0]
    return _f(row.get("T") if isinstance(row, dict) else None)


def _sum_col(records, key) -> float:
    return sum(_f(r.get(key)) for r in records if isinstance(r, dict))


async def main() -> int:
    from src.db.mssql import init_mssql, execute_raw, close_mssql  # noqa: E402
    from src.analytics.dashboard import _query_contribution  # noqa: E402
    from src.utils.date_utils import resolve_date_range  # noqa: E402

    await init_mssql()
    mtd = resolve_date_range("mtd")
    print("=" * 78)
    print("FAQ FIX CROSS-VERIFICATION  (Manoj issues #2/#3 + supplier/margin)")
    print(f"MTD window (IST): {mtd.start} -> {mtd.end}")
    print("=" * 78)

    failures = 0

    # ── 1. Category contribution ──────────────────────────────────────────────
    print("\n[1] CATEGORY CONTRIBUTION %  (template #42)")
    old_t = _first_total((await execute_raw(OLD_CATEGORY_TOTAL)).get("records"))
    new_t = _first_total((await execute_raw(NEW_CATEGORY_TOTAL)).get("records"))
    print(f"    OLD APP_REPORT total      : {_L(old_t)}")
    print(f"    NEW canonical total       : {_L(new_t)}")
    diff_pct = abs(new_t - old_t) / new_t * 100 if new_t else 0
    print(f"    Divergence the fix removes: {diff_pct:,.1f}%")

    hit = try_faq_template("Category Contribution % in Total Revenue")
    assert hit and hit["template_id"] == "category_contribution_percentage", "template did not match!"
    recs = (await execute_raw(hit["sql"])).get("records") or []
    ai_total = _sum_col(recs, "Revenue")
    # Dashboard's own category math (same view) — the reconciliation target.
    dash = await _query_contribution(mtd, "category", 200)
    dash_total = sum(_f(d.get("revenue")) for d in dash)
    print(f"    AI template now uses view : VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID")
    print(f"    AI template total         : {_L(ai_total)}  ({len(recs)} categories)")
    print(f"    Dashboard category total  : {_L(dash_total)}  ({len(dash)} categories)")
    ok = dash_total and abs(ai_total - dash_total) <= max(1.0, dash_total * 0.001)
    print(f"    RECONCILES WITH DASHBOARD : {'YES ✅' if ok else 'NO ❌'}")
    if not ok:
        failures += 1
    # show top 3 categories with their %
    for r in recs[:3]:
        print(f"        - {str(r.get('Category',''))[:24]:24} {_L(_f(r.get('Revenue'))):>12}  {_f(r.get('ContributionPct')):6.2f}%")

    # ── 2. Supplier contribution ──────────────────────────────────────────────
    print("\n[2] SUPPLIER CONTRIBUTION %  (template #29)")
    old_t = _first_total((await execute_raw(OLD_SUPPLIER_TOTAL)).get("records"))
    new_t = _first_total((await execute_raw(NEW_SUPPLIER_TOTAL)).get("records"))
    print(f"    OLD APP_REPORT total      : {_L(old_t)}")
    print(f"    NEW canonical total       : {_L(new_t)}")
    hit = try_faq_template("Supplier Contribution % in Overall Sales")
    assert hit and hit["template_id"] == "supplier_contribution_percentage", "template did not match!"
    recs = (await execute_raw(hit["sql"])).get("records") or []
    ai_total = _sum_col(recs, "Revenue")
    ok = new_t and abs(ai_total - new_t) <= max(1.0, new_t * 0.001)
    print(f"    AI template total         : {_L(ai_total)}  ({len(recs)} suppliers)")
    print(f"    USES CANONICAL VIEW       : {'YES ✅' if ok else 'NO ❌'}")
    if not ok:
        failures += 1
    for r in recs[:3]:
        print(f"        - {str(r.get('SupplierName',''))[:24]:24} {_L(_f(r.get('Revenue'))):>12}  {_f(r.get('ContributionPct')):6.2f}%")

    # ── 3. Gross margin by category ───────────────────────────────────────────
    print("\n[3] GROSS MARGIN BY CATEGORY  (template #43)")
    hit = try_faq_template("Gross Margin Analysis by Department/Category")
    if not hit or hit.get("template_id") != "gross_margin_by_category":
        hit = try_faq_template("gross margin by category")
    assert hit and hit["template_id"] == "gross_margin_by_category", "template did not match!"
    recs = (await execute_raw(hit["sql"])).get("records") or []
    rev = _sum_col(recs, "Revenue")
    cost = _sum_col(recs, "CostValue")
    gp = rev - cost
    margin = gp / rev * 100 if rev else 0
    print(f"    Revenue (SalesNetAmount)  : {_L(rev)}")
    print(f"    Cost (SalesCost / COGS)   : {_L(cost)}")
    print(f"    Gross profit / margin     : {_L(gp)}  ({margin:.2f}%)")
    # Sanity: revenue here should match the dashboard category total (same view/window).
    ok = dash_total and abs(rev - dash_total) <= max(1.0, dash_total * 0.001)
    print(f"    REVENUE TIES TO DASHBOARD : {'YES ✅' if ok else 'NO ❌'}")
    sane = (0 < margin < 100) and cost > 0
    print(f"    MARGIN IN SANE RANGE      : {'YES ✅' if sane else 'CHECK ❌'}")
    if not (ok and sane):
        failures += 1
    for r in recs[:3]:
        print(f"        - {str(r.get('Category',''))[:24]:24} margin {_f(r.get('GrossMarginPct')):6.2f}%")

    print("\n" + "=" * 78)
    print(f"RESULT: {'ALL CHECKS PASSED ✅' if failures == 0 else str(failures) + ' CHECK(S) FAILED ❌'}")
    print("=" * 78)

    await close_mssql()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
