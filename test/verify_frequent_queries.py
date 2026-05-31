"""
Verify all 50 FREQUENT_AI_QUERIES:
  1. Match a FAQ template
  2. Emit non-empty SQL
  3. Classify expected visualization shape
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nlq_faq_kpi import FREQUENT_AI_QUERIES
from nlq_faq_sql import try_faq_template

# template_id → expected UI shape for AI page
VIZ_EXPECTATIONS: dict[str, str] = {
    "store_mtd_sales_customers_ats": "bar (Store × MTDSales)",
    "department_mtd_sales_customers_ats": "bar (Department × MTDSales)",
    "category_mtd_sales_customers_ats": "bar (Category × MTDSales)",
    "monthly_sales_since_apr_2024": "area/line (Month × TotalSales)",
    "five_year_sales_dept_category": "area (monthly totals aggregated)",
    "average_sales_mtd_level": "KPI cards",
    "today_sales_customers_invoices": "KPI cards",
    "ytd_growth_vs_last_year": "bar (2 periods)",
    "qtd_growth_vs_last_year": "bar (2 periods)",
    "mtd_growth_vs_last_year": "bar (2 periods)",
    "highest_store_current_month": "KPI / single row",
    "highest_department_sales_mtd": "KPI / single row",
    "highest_category_sales_mtd": "KPI / single row",
    "most_selling_product_current_month_year": "bar/table",
    "least_selling_product_mtd": "bar/table",
    "highest_supplier_sales_mtd": "KPI / single row",
    "lowest_supplier_sales_mtd": "KPI / single row",
    "top_stores_by_growth_pct": "bar (Store × GrowthPct)",
    "bottom_stores_sales_decline": "bar (Store × SalesDecline)",
    "products_fastest_mom_growth": "bar/table",
    "categories_negative_growth_trends": "bar/table",
    "predict_next_month_sales": "note/forecast",
    "expected_stock_requirement_30_days": "bar/table",
    "potential_stockout_prediction": "bar/table",
    "slow_moving_inventory_identification": "bar/table",
    "fast_moving_inventory_identification": "bar/table",
    "customer_repeat_purchase_analysis": "bar/table",
    "peak_sales_hours_not_supported": "note (unsupported)",
    "festival_vs_non_festival_sales": "bar (2 groups)",
    "region_wise_sales_performance": "bar (Region × Sales)",
    "supplier_contribution_percentage": "pie/bar (Supplier share)",
    "average_basket_size_by_store": "bar (Store × basket)",
    "average_invoice_value_trend": "area/line",
    "discount_impact_sales": "note (LLM summary)",
    "store_ranking_sales_ats_customers": "bar (Store ranking)",
    "product_recommendation_customer": "note (LLM summary)",
    "demand_forecast_store_category": "note (LLM summary)",
    "daily_sales_target_achievement": "note (LLM summary)",
    "weather_festival_impact": "note (LLM summary)",
    "high_return_low_conversion_products": "bar/table",
    "sales_spike_drop_alert": "bar/table",
    "top_customers_purchase_value": "bar (Customer ranking)",
    "new_vs_repeat_customer_analysis": "bar/pie",
    "category_contribution_percentage": "pie (Category share)",
    "gross_margin_by_category": "bar (Category × margin)",
    "stock_aging_analysis": "bar/table",
    "dead_stock_identification": "bar/table",
    "product_sell_through_pct": "bar/table",
    "sales_trend_festivals_seasons": "area/line",
    "ai_insights_not_supported": "note (unsupported)",
}


def main() -> int:
    failures = []
    print(f"{'#':>2}  {'Status':4}  {'Template':40}  Expected viz")
    print("-" * 100)

    for i, q in enumerate(FREQUENT_AI_QUERIES, 1):
        hit = try_faq_template(q)
        if not hit:
            failures.append((q, "no template match"))
            print(f"{i:2}.  FAIL  {'—':40}  {q[:50]}")
            continue

        tid = hit.get("template_id") or "?"
        sql = (hit.get("sql") or "").strip()
        sql_upper = sql.upper()
        if not sql or not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            failures.append((q, "invalid sql"))
            status = "FAIL"
        else:
            status = "OK"

        viz = VIZ_EXPECTATIONS.get(tid, "bar/table (generic)")
        top = re.search(r"SELECT\s+TOP\s*\(\s*(\d+)\s*\)", sql, re.I)
        if top and tid == "five_year_sales_dept_category":
            failures.append((q, "five_year still has TOP"))
            status = "FAIL"
        if status == "FAIL":
            print(f"{i:2}.  {status}  {tid:40}  {viz}")
        else:
            print(f"{i:2}.  {status}  {tid:40}  {viz}")

    print()
    print(f"Verified: {len(FREQUENT_AI_QUERIES) - len(failures)}/{len(FREQUENT_AI_QUERIES)}")
    if failures:
        print("\nFailures:")
        for q, reason in failures:
            print(f"  - [{reason}] {q[:70]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
