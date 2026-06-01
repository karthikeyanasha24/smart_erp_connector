"""
Verified AI Query templates — independent script.

Each entry maps a natural-language question to tested T-SQL via nlq_faq_sql
FAQ matchers (same engine as the backend NLQ pipeline).

Usage:
  python test/verified_ai_templates.py              # verify all templates
  python test/verified_ai_templates.py --write-json # export for AI Query UI
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nlq_faq_sql import try_faq_template


class TemplateSpec(TypedDict):
    id: str
    label: str
    question: str
    category: str
    expected_template_id: str


# ── Curated questions (verified against FAQ SQL builders) ────────────────────

VERIFIED_AI_TEMPLATES: List[TemplateSpec] = [
    {
        "id": "vat_01",
        "label": "Store MTD sales & customers",
        "question": "Store Wise MTD Sales, Unique Customer Count, ATS",
        "category": "Store",
        "expected_template_id": "store_mtd_sales_customers_ats",
    },
    {
        "id": "vat_02",
        "label": "Department MTD KPIs",
        "question": "Department Wise MTD Sales, Unique Customer Count, ATS",
        "category": "Department",
        "expected_template_id": "department_mtd_sales_customers_ats",
    },
    {
        "id": "vat_03",
        "label": "Today's sales snapshot",
        "question": "Today's Sales with Unique Customer Count and Unique Invoices Billed",
        "category": "Today",
        "expected_template_id": "today_sales_customers_invoices",
    },
    {
        "id": "vat_04",
        "label": "MTD vs last year",
        "question": "Current Year MTD Growth vs Last Year MTD Growth",
        "category": "Growth",
        "expected_template_id": "mtd_growth_vs_last_year",
    },
    {
        "id": "vat_05",
        "label": "Top store this month",
        "question": "Which Store has the Highest Sales in the Current Month?",
        "category": "Store",
        "expected_template_id": "highest_store_current_month",
    },
    {
        "id": "vat_06",
        "label": "Top stores by growth %",
        "question": "Top 10 Performing Stores based on Growth %",
        "category": "Growth",
        "expected_template_id": "top_stores_by_growth_pct",
    },
    {
        "id": "vat_07",
        "label": "Category revenue share",
        "question": "Category Contribution % in Total Revenue",
        "category": "Category",
        "expected_template_id": "category_contribution_percentage",
    },
    {
        "id": "vat_08",
        "label": "Top customers by value",
        "question": "Top Customers based on Purchase Value",
        "category": "Customer",
        "expected_template_id": "top_customers_purchase_value",
    },
    {
        "id": "vat_09",
        "label": "Average basket by store",
        "question": "Average Basket Size by Store",
        "category": "Revenue",
        "expected_template_id": "average_basket_size_by_store",
    },
    {
        "id": "vat_10",
        "label": "Monthly sales since Apr 2024",
        "question": "Month-wise Sales Comparison since Apr'24",
        "category": "Trend",
        "expected_template_id": "monthly_sales_since_apr_2024",
    },
    {
        "id": "vat_11",
        "label": "Top 10 customers by purchase",
        "question": "Top 10 Customers by Purchase Value",
        "category": "Customer",
        "expected_template_id": "top_customers_by_purchase_value",
    },
    {
        "id": "vat_12",
        "label": "Top 10 supplier purchases MTD",
        "question": "Top 10 purchases by supplier this month",
        "category": "Purchase",
        "expected_template_id": "purchases_by_supplier_mtd",
    },
    {
        "id": "vat_13",
        "label": "Top 20 selling products MTD",
        "question": "Top 20 best selling products this month",
        "category": "Product",
        "expected_template_id": "top_products_mtd",
    },
    {
        "id": "vat_14",
        "label": "Bottom 10 stores by decline",
        "question": "Bottom 10 Performing Stores based on Sales Decline",
        "category": "Growth",
        "expected_template_id": "bottom_stores_sales_decline",
    },
    {
        "id": "vat_15",
        "label": "Top 20 customers by purchase",
        "question": "Top 20 Customers by Purchase Value",
        "category": "Customer",
        "expected_template_id": "top_customers_by_purchase_value",
    },
]

def _valid_sql(sql: str) -> bool:
    s = (sql or "").strip()
    if not s:
        return False
    upper = s.upper()
    return upper.startswith("SELECT") or upper.startswith("WITH")


def resolve_template(spec: TemplateSpec) -> Dict[str, Any]:
    """Match question → FAQ SQL; raise if missing or wrong template."""
    hit = try_faq_template(spec["question"])
    if not hit:
        raise ValueError(f"no FAQ match for: {spec['question'][:60]}")
    tid = hit.get("template_id") or ""
    if tid != spec["expected_template_id"]:
        raise ValueError(
            f"expected template {spec['expected_template_id']!r}, got {tid!r}"
        )
    sql = (hit.get("sql") or "").strip()
    if not _valid_sql(sql):
        raise ValueError(f"invalid SQL for {spec['id']}")
    return {
        "id": spec["id"],
        "label": spec["label"],
        "question": spec["question"],
        "category": spec["category"],
        "template_id": tid,
        "sql": sql,
        "explanation": hit.get("explanation") or "",
        "builtin": True,
    }


def verify_all() -> tuple[List[Dict[str, Any]], List[str]]:
    resolved: List[Dict[str, Any]] = []
    errors: List[str] = []
    for spec in VERIFIED_AI_TEMPLATES:
        try:
            resolved.append(resolve_template(spec))
        except ValueError as exc:
            errors.append(f"{spec['id']}: {exc}")
    return resolved, errors


def write_json(out_path: Path) -> int:
    resolved, errors = verify_all()
    if errors:
        for e in errors:
            print(f"FAIL  {e}", file=sys.stderr)
        return 1
    payload = [
        {k: v for k, v in row.items() if k in ("id", "label", "question", "category", "template_id", "sql", "builtin")}
        for row in resolved
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload)} templates -> {out_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify AI Query templates")
    ap.add_argument(
        "--write-json",
        action="store_true",
        help="Export verified templates to src/data/ai_query_templates.json",
    )
    args = ap.parse_args()

    if args.write_json:
        root = Path(__file__).resolve().parent.parent
        return write_json(root / "src" / "data" / "ai_query_templates.json")

    print(f"{'#':>2}  {'Status':4}  {'Template':38}  Question")
    print("-" * 110)
    failures = 0
    for i, spec in enumerate(VERIFIED_AI_TEMPLATES, 1):
        try:
            row = resolve_template(spec)
            sql = row["sql"]
            if spec["id"] == "vat_11" and "TOP (10)" not in sql.upper():
                raise ValueError("expected TOP (10) in top customers SQL")
            if spec["id"] == "vat_12" and "TOP (10)" not in sql.upper():
                raise ValueError("expected TOP (10) in supplier purchase SQL")
            if spec["id"] == "vat_13" and "TOP (20)" not in sql.upper():
                raise ValueError("expected TOP (20) in top products SQL")
            if spec["id"] == "vat_15" and "TOP (20)" not in sql.upper():
                raise ValueError("expected TOP (20) in top 20 customers SQL")
            print(f"{i:2}.  OK    {row['template_id']:38}  {spec['question'][:45]}")
        except ValueError as exc:
            failures += 1
            print(f"{i:2}.  FAIL  {'—':38}  {exc}")

    print()
    ok = len(VERIFIED_AI_TEMPLATES) - failures
    print(f"Verified: {ok}/{len(VERIFIED_AI_TEMPLATES)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
