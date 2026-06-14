"""
DASHBOARD ↔ ANALYTICS ↔ AI-QUERY CONSISTENCY VALIDATOR  (MTD)

Proves the same number is identical everywhere it appears. It computes the
Dashboard's authoritative figures using the SAME backend code the live site runs
(get_dashboard / get_home_kpis / get_category_breakdown / get_branch_chart), then
runs the relevant AI-Query templates and cross-checks each against the Dashboard:

  TOTAL MTD NET SALES   Dashboard == Analytics KPI == AI #1 (store sum)
                        == AI #3 (category sum) == AI #42 (category contribution)
                        == AI #29 (supplier contribution) == AI #43 (gross-margin revenue)
                        == AI #8 (CurrentMTD row)
  BILLS                 Dashboard == Analytics invoices == sum of AI #1 UniqueInvoices
  CATEGORY-LEVEL        Dashboard category revenue == get_category_breakdown == AI #42 (per category)
  BRANCH-LEVEL          Dashboard branch revenue == get_branch_chart == AI #1 (per store)

A row passes when the two figures agree within 0.1% (or ₹1). Customers are reported
but NOT asserted equal across stores (one buyer can shop at several branches, so the
per-store distinct sum legitimately exceeds the overall distinct count).

Run from repo root:   python test/verify_dashboard_consistency.py
Requires backend/.env (DB credentials).
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

PERIOD = "mtd"
TOL = 0.001  # 0.1%


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _L(v: float) -> str:
    return f"{v/100000:,.2f} L"


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(1.0, abs(b) * TOL)


def _flag(a: float, b: float) -> str:
    return "MATCH ✅" if _close(a, b) else f"DIFF ❌ (Δ {_L(a-b)})"


def _sum(records, key) -> float:
    return sum(_f(r.get(key)) for r in records if isinstance(r, dict))


async def _run(execute_raw, q: str):
    hit = try_faq_template(q)
    if not hit:
        return None, []
    r = await execute_raw(hit["sql"])
    return hit.get("template_id"), (r.get("records") or [])


async def main() -> int:
    from src.db.mssql import init_mssql, execute_raw, close_mssql  # noqa: E402
    from src.analytics.dashboard import get_dashboard  # noqa: E402
    from src.analytics.kpi import get_home_kpis  # noqa: E402
    from src.analytics.charts import get_category_breakdown, get_branch_chart  # noqa: E402

    await init_mssql()

    # ── Authoritative Dashboard + Analytics figures (live backend code) ──
    dash = await get_dashboard(PERIOD, force_refresh=True)
    kpis = await get_home_kpis(PERIOD, include_customers=True, include_extras=True)
    cat_break = await get_category_breakdown(PERIOD, 200)
    br_break = await get_branch_chart(PERIOD)

    d_sales = _f(dash["summary"]["mtd_sales"])
    d_bills = _f(dash["summary"]["bills"])
    d_qty = _f(dash["summary"]["quantity"])
    d_cust = dash["summary"].get("customers")
    d_cats = {str(c.get("name")): _f(c.get("revenue")) for c in dash.get("categories", [])}
    d_brs = {str(b.get("name")): _f(b.get("revenue")) for b in dash.get("branches", [])}

    a_rev = _f((kpis.get("revenue") or {}).get("value"))
    a_inv = _f((kpis.get("unique_invoices") or {}).get("value")) or _f((kpis.get("transactions") or {}).get("value"))
    a_qty = _f((kpis.get("quantity") or {}).get("value"))

    print("=" * 84)
    print(f"DASHBOARD CONSISTENCY VALIDATION   period={PERIOD}   range={dash['date_range']['start']} → {dash['date_range']['end']}")
    print("=" * 84)

    fails = 0

    # ── AI template aggregates ──
    _, store = await _run(execute_raw, "Store Wise MTD Sales, Unique Customer Count, ATS")
    _, cat3 = await _run(execute_raw, "Category Wise MTD Sales, Unique Customer Count, ATS")
    _, cc = await _run(execute_raw, "Category Contribution % in Total Revenue")
    _, sc = await _run(execute_raw, "Supplier Contribution % in Overall Sales")
    _, gm = await _run(execute_raw, "Gross Margin Analysis by Department/Category")
    _, gw = await _run(execute_raw, "YTD, QTD and MTD Growth vs Last Year")

    store_sales = _sum(store, "MTDSales")
    store_bills = _sum(store, "UniqueInvoices")
    cat3_sales = _sum(cat3, "MTDSales")
    cc_sales = _sum(cc, "Revenue")
    sc_sales = _sum(sc, "Revenue")
    gm_sales = _sum(gm, "Revenue")
    mtd_row = next((r for r in gw if str(r.get("PeriodLabel")) == "CurrentMTD"), {})
    gw_mtd = _f(mtd_row.get("TotalSales"))

    print("\n[A] TOTAL MTD NET SALES — should be identical everywhere")
    print(f"    {'Dashboard summary':32} {_L(d_sales)}")
    for label, val in [
        ("Analytics KPI (revenue)", a_rev),
        ("AI #1  store-sum",         store_sales),
        ("AI #3  category-sum",      cat3_sales),
        ("AI #42 category contrib",  cc_sales),
        ("AI #29 supplier contrib",  sc_sales),
        ("AI #43 gross-margin rev",  gm_sales),
        ("AI #8  CurrentMTD row",    gw_mtd),
    ]:
        ok = _close(val, d_sales); fails += 0 if ok else 1
        print(f"    {label:32} {_L(val):>14}   {_flag(val, d_sales)}")

    print("\n[B] BILLS / INVOICES (distinct) — should be identical")
    print(f"    {'Dashboard summary':32} {d_bills:,.0f}")
    for label, val in [("Analytics KPI invoices", a_inv), ("AI #1 sum UniqueInvoices", store_bills)]:
        ok = _close(val, d_bills); fails += 0 if ok else 1
        print(f"    {label:32} {val:>14,.0f}   {_flag(val, d_bills)}")

    print("\n[C] QUANTITY (units) — Dashboard vs Analytics KPI")
    ok = _close(a_qty, d_qty); fails += 0 if ok else 1
    print(f"    {'Dashboard summary':32} {d_qty:,.0f}")
    print(f"    {'Analytics KPI quantity':32} {a_qty:>14,.0f}   {_flag(a_qty, d_qty)}")

    print("\n[D] CATEGORY-LEVEL — Dashboard vs get_category_breakdown vs AI #42 (top 12 by revenue)")
    cb = {str(c.get("category")): _f(c.get("revenue")) for c in cat_break}
    cc_map = {str(c.get("Category")): _f(c.get("Revenue")) for c in cc}
    print(f"    {'Category':22} {'Dashboard':>13} {'Analytics':>13} {'AI #42':>13}  status")
    for name, rev in sorted(d_cats.items(), key=lambda x: -x[1])[:12]:
        av = cb.get(name, 0.0); cv = cc_map.get(name, 0.0)
        ok = _close(av, rev) and _close(cv, rev); fails += 0 if ok else 1
        print(f"    {name[:22]:22} {_L(rev):>13} {_L(av):>13} {_L(cv):>13}  {'✅' if ok else '❌'}")

    print("\n[E] BRANCH-LEVEL — Dashboard vs get_branch_chart vs AI #1 (top 12 by revenue)")
    bc = {str(b.get("branch")): _f(b.get("revenue")) for b in br_break}
    st_map = {str(r.get("Store")): _f(r.get("MTDSales")) for r in store}
    print(f"    {'Branch':22} {'Dashboard':>13} {'Analytics':>13} {'AI #1':>13}  status")
    for name, rev in sorted(d_brs.items(), key=lambda x: -x[1])[:12]:
        av = bc.get(name, 0.0); sv = st_map.get(name, 0.0)
        ok = _close(av, rev) and _close(sv, rev); fails += 0 if ok else 1
        print(f"    {name[:22]:22} {_L(rev):>13} {_L(av):>13} {_L(sv):>13}  {'✅' if ok else '❌'}")

    print("\n[F] CUSTOMERS (reported, not asserted — per-store sum can exceed overall distinct)")
    print(f"    Dashboard distinct customers : {d_cust}")
    print(f"    Analytics KPI customers      : {(kpis.get('customers') or {}).get('value')}")
    print(f"    AI #1 sum of per-store custs : {int(_sum(store, 'UniqueCustomers')):,}")

    print("\n" + "=" * 84)
    print(f"RESULT: {'ALL FIGURES CONSISTENT ✅' if fails == 0 else str(fails) + ' INCONSISTENCY(IES) FOUND ❌'}")
    print("=" * 84)

    await close_mssql()
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
