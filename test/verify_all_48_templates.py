"""
Live cross-verification of ALL 48 verified AI Query templates.

For every entry in FREQUENT_AI_QUERIES it: matches the question to its template,
runs the template SQL against the live SQL Server, and reports:
  - which ERP view the SQL reads (CANON / SLSXNS / MIS_SUP / SALES_AI / STOCK / APP)
  - row count, query duration
  - PASS  (rows returned, no error)
    EMPTY (query ran but returned 0 rows — likely an empty/unpopulated source)
    ERROR (SQL failed — message shown)
    DEAD-VIEW (still points at VW_MB_POWERBI_APP_REPORT, which is empty in this DB)

This is the "check all 48" safety net. After the 2026-06-13 migration that moved
every sales template off the empty APP_REPORT view, this should report 0 DEAD-VIEW
and 0 ERROR. EMPTY is acceptable only where a source genuinely has no rows for the
current period (e.g. no returns this month).

Run from repo root:
    python test/verify_all_48_templates.py
Requires backend/.env (DB credentials) — same setup the other verify_*.py scripts use.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from nlq_faq_sql import try_faq_template  # noqa: E402
from nlq_faq_kpi import FREQUENT_AI_QUERIES  # noqa: E402


def _view_of(sql: str) -> str:
    if "SLS_DATA_WITHOUT_ITEMID" in sql:
        return "CANON"
    if "APP_REPORT" in sql:
        return "APP-DEAD"
    if "SLSXNS" in sql:
        return "SLSXNS"
    if "MIS_SUPPLIER" in sql:
        return "MIS_SUP"
    if "VwAISalesData" in sql:
        return "SALES_AI"
    if "STOCK" in sql or "PRODUCT_MASTER" in sql:
        return "STOCK"
    return "other"


async def main() -> int:
    from src.db.mssql import init_mssql, execute_raw, close_mssql  # noqa: E402

    await init_mssql()

    print("=" * 96)
    print(f"ALL-48 TEMPLATE LIVE CHECK   ({len(FREQUENT_AI_QUERIES)} templates)")
    print("=" * 96)
    print(f"{'#':>2}  {'STATUS':9} {'VIEW':9} {'ROWS':>6} {'ms':>6}  {'TEMPLATE':38} QUESTION")
    print("-" * 96)

    n_pass = n_empty = n_error = n_dead = n_nomatch = 0

    for i, q in enumerate(FREQUENT_AI_QUERIES, 1):
        hit = try_faq_template(q)
        if not hit:
            n_nomatch += 1
            print(f"{i:2}. {'NO-MATCH':9} {'-':9} {'-':>6} {'-':>6}  {'-':38} {q[:40]}")
            continue

        tid = hit.get("template_id", "?")
        view = _view_of(hit["sql"])
        if view == "APP-DEAD":
            n_dead += 1
            print(f"{i:2}. {'DEAD-VIEW':9} {view:9} {'-':>6} {'-':>6}  {tid[:38]:38} {q[:40]}")
            continue

        t0 = time.time()
        try:
            r = await execute_raw(hit["sql"])
            ms = int((time.time() - t0) * 1000)
            rows = len(r.get("records") or [])
            if rows > 0:
                n_pass += 1
                status = "PASS"
            else:
                n_empty += 1
                status = "EMPTY"
            print(f"{i:2}. {status:9} {view:9} {rows:>6} {ms:>6}  {tid[:38]:38} {q[:40]}")
        except Exception as exc:
            n_error += 1
            msg = str(exc).replace("\n", " ")[:60]
            print(f"{i:2}. {'ERROR':9} {view:9} {'-':>6} {'-':>6}  {tid[:38]:38} {msg}")

    print("-" * 96)
    print(
        f"SUMMARY:  PASS={n_pass}  EMPTY={n_empty}  ERROR={n_error}  "
        f"DEAD-VIEW={n_dead}  NO-MATCH={n_nomatch}   (of {len(FREQUENT_AI_QUERIES)})"
    )
    ok = (n_error == 0 and n_dead == 0 and n_nomatch == 0)
    print("RESULT:", "ALL TEMPLATES HEALTHY" if ok else "REVIEW NEEDED (see ERROR/DEAD-VIEW/EMPTY above)")
    print("=" * 96)

    await close_mssql()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
