"""
Export T-SQL bundles for all NLQ "comparison" FAQ lists (sales, product, branch, …).

Each phrase is resolved with nlq_faq_sql.try_faq_template() — same as the terminal.

Usage (from repo root):
  python test/export_comparison_queries_sql.py              # verify all phrases match FAQs
  python test/export_comparison_queries_sql.py --write      # write test/comparison_queries_faq.sql
  python test/export_comparison_queries_sql.py --execute    # optional: run on DB (needs DB_* env)

Also writes per-section files under test/comparison_queries_faq/ when using --write.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# (section title, query tuple from nlq_faq_* module)
def _sections() -> List[Tuple[str, Tuple[str, ...]]]:
    from nlq_faq_branch_compare import BRANCH_COMPARE_AI_QUERIES
    from nlq_faq_compare import COMPARE_AI_QUERIES
    from nlq_faq_conversational_compare import CONVERSATIONAL_COMPARE_AI_QUERIES
    from nlq_faq_customer_compare import CUSTOMER_COMPARE_AI_QUERIES
    from nlq_faq_executive_compare import EXECUTIVE_COMPARE_AI_QUERIES
    from nlq_faq_inventory_compare import INVENTORY_COMPARE_AI_QUERIES
    from nlq_faq_product_compare import PRODUCT_COMPARE_AI_QUERIES
    from nlq_faq_supplier_compare import SUPPLIER_COMPARE_AI_QUERIES

    return [
        ("Sales Comparison Questions", COMPARE_AI_QUERIES),
        ("Product Comparison Questions", PRODUCT_COMPARE_AI_QUERIES),
        ("Branch Comparison Questions", BRANCH_COMPARE_AI_QUERIES),
        ("Supplier Comparison Questions", SUPPLIER_COMPARE_AI_QUERIES),
        ("Customer Comparison Questions", CUSTOMER_COMPARE_AI_QUERIES),
        ("Inventory Comparison Questions", INVENTORY_COMPARE_AI_QUERIES),
        ("Advanced Executive Comparison Questions", EXECUTIVE_COMPARE_AI_QUERIES),
        ("Conversational Comparison Queries", CONVERSATIONAL_COMPARE_AI_QUERIES),
    ]


def collect_rows() -> Tuple[List[Tuple[str, int, str, Dict[str, Any]]], int]:
    from nlq_faq_sql import try_faq_template

    flat: List[Tuple[str, int, str, Dict[str, Any]]] = []
    global_i = 0
    total_q = 0
    for section, queries in _sections():
        for j, q in enumerate(queries, start=1):
            total_q += 1
            hit = try_faq_template(q)
            if not hit:
                raise RuntimeError(f"No FAQ template for [{section}] #{j}: {q!r}")
            global_i += 1
            flat.append((section, global_i, q, hit))
    return flat, total_q


def _render_block(section: str, global_i: int, total: int, q: str, hit: Dict[str, Any]) -> List[str]:
    sep = "-- " + "=" * 76
    tid = hit.get("template_id", "?")
    expl = (hit.get("explanation") or "").replace("*/", "* /").replace("\r\n", "\n")
    assumptions = hit.get("assumptions") or []
    sql = (hit.get("sql") or "").strip()
    lines = [
        sep,
        f"-- SECTION: {section}",
        f"-- {global_i}/{total} • {q}",
        f"-- template_id: {tid}",
        f"-- explanation: {expl}",
    ]
    for a in assumptions:
        lines.append(f"-- assumption: {str(a).replace('*/', '* /')}")
    lines.append(sep)
    lines.append(sql)
    lines.append("")
    lines.append("")
    return lines


def write_combined_bundle(path: Path, rows: List[Tuple[str, int, str, Dict[str, Any]]]) -> None:
    total = len(rows)
    iso = datetime.now(timezone.utc).isoformat()
    header = [
        "/*",
        "  NLQ comparison queries — FAQ-generated T-SQL",
        f"  Generated: {iso}",
        "  Source: nlq_faq_* COMPARE_AI_QUERIES + try_faq_template",
        f"  Total blocks: {total}",
        "*/",
        "",
    ]
    out: List[str] = []
    cur_section = ""
    for section, gi, q, hit in rows:
        if section != cur_section:
            out.append("")
            out.append("-- " + "#" * 76)
            out.append(f"-- {section}")
            out.append("-- " + "#" * 76)
            out.append("")
            cur_section = section
        out.extend(_render_block(section, gi, total, q, hit))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(header + out), encoding="utf-8")


def write_section_files(out_dir: Path, rows: List[Tuple[str, int, str, Dict[str, Any]]]) -> None:
    """One .sql file per section (basename from section title)."""
    from collections import defaultdict

    by_section: Dict[str, List[Tuple[int, str, Dict[str, Any]]]] = defaultdict(list)
    for section, gi, q, hit in rows:
        by_section[section].append((gi, q, hit))
    total = len(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    for section, items in by_section.items():
        safe = (
            section.lower()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("(", "")
            .replace(")", "")
        )
        path = out_dir / f"{safe}.sql"
        iso = datetime.now(timezone.utc).isoformat()
        lines = [
            "/*",
            f"  {section}",
            f"  Generated: {iso}",
            f"  Blocks: {len(items)}",
            "*/",
            "",
        ]
        for gi, q, hit in items:
            lines.extend(_render_block(section, gi, total, q, hit))
        path.write_text("\n".join(lines), encoding="utf-8")


def verify_print(rows: List[Tuple[str, int, str, Dict[str, Any]]]) -> None:
    print(f"OK: {len(rows)} comparison phrases resolve to FAQ templates.")
    prev = ""
    for section, gi, q, hit in rows:
        if section != prev:
            print(f"\n## {section}")
            prev = section
        tid = hit["template_id"]
        print(f"  {gi:3}. [{tid}] {q[:70]}{'...' if len(q) > 70 else ''}")


def _db_env_ready() -> Tuple[bool, List[str]]:
    server = (os.getenv("DB_SERVER") or os.getenv("ERP_DB_HOST") or "").strip()
    database = (os.getenv("DB_NAME") or os.getenv("ERP_DB_NAME") or "").strip()
    user = (os.getenv("DB_USER") or os.getenv("ERP_DB_USER") or "").strip()
    password = os.getenv("DB_PASSWORD") or os.getenv("ERP_DB_PASSWORD") or ""
    missing = [
        n
        for n, v in [
            ("DB_SERVER/ERP_DB_HOST", server),
            ("DB_NAME/ERP_DB_NAME", database),
            ("DB_USER/ERP_DB_USER", user),
            ("DB_PASSWORD/ERP_DB_PASSWORD", password),
        ]
        if not v
    ]
    return len(missing) == 0, missing


def execute_all(rows: List[Tuple[str, int, str, Dict[str, Any]]], timeout_sec: int) -> bool:
    ok_env, missing = _db_env_ready()
    if not ok_env:
        print(
            "Skip --execute: missing env: " + ", ".join(missing),
            file=sys.stderr,
        )
        return True
    try:
        from terminal_openai_nlq_sql import connect_mssql
    except ImportError:
        print("Cannot import connect_mssql; run from project root.", file=sys.stderr)
        return False

    conn, driver = connect_mssql()
    conn.timeout = timeout_sec
    cur = conn.cursor()
    ok = 0
    fail: List[Tuple[int, str, str]] = []
    print(f"(DB driver: {driver}, timeout={timeout_sec}s)")
    for _section, gi, _q, hit in rows:
        tid = hit["template_id"]
        sql = hit["sql"]
        try:
            cur.execute(sql)
            if cur.description:
                cur.fetchmany(5)
            ok += 1
            print(f"  OK {gi}/{len(rows)} [{tid}]")
        except Exception as exc:  # noqa: BLE001
            fail.append((gi, tid, str(exc)))
            print(f"  FAIL {gi}/{len(rows)} [{tid}]: {exc}")
    conn.close()
    print(f"\nExecuted: {ok}/{len(rows)} OK, {len(fail)} failed")
    for gi, tid, err in fail:
        print(f"  #{gi} {tid}: {err[:200]}")
    return len(fail) == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Export / verify FAQ SQL for comparison queries.")
    ap.add_argument(
        "--write",
        action="store_true",
        help=f"Write {_HERE / 'comparison_queries_faq.sql'} + per-section folder",
    )
    ap.add_argument("--execute", action="store_true", help="Run each SQL on SQL Server (needs env)")
    ap.add_argument("--timeout", type=int, default=120, help="ODBC timeout per query (--execute)")
    args = ap.parse_args()

    rows, _ = collect_rows()

    code = 0
    verify_print(rows)

    if args.write:
        combined = _HERE / "comparison_queries_faq.sql"
        write_combined_bundle(combined, rows)
        print(f"\nWrote {combined} ({combined.stat().st_size} bytes)")
        sect_dir = _HERE / "comparison_queries_faq"
        write_section_files(sect_dir, rows)
        print(f"Wrote section files under {sect_dir}/")

    if args.execute:
        if not execute_all(rows, args.timeout):
            code = 1

    return code


if __name__ == "__main__":
    raise SystemExit(main())
