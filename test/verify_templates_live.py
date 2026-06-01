"""
Live DB verification for all AI Query templates.
Runs each template SQL against SQL Server and reports row counts + sample totals.

Usage:
  python test/verify_templates_live.py
  python test/verify_templates_live.py --as-of 2026-05-31
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from verified_ai_templates import VERIFIED_AI_TEMPLATES, resolve_template


def _sql_as_of(sql: str, as_of: str) -> str:
    """Replace GETDATE() with a fixed date for reproducible MTD checks."""
    return re.sub(
        r"\bGETDATE\s*\(\s*\)",
        f"CAST('{as_of}' AS datetime)",
        sql,
        flags=re.IGNORECASE,
    )


async def main() -> int:
    from src.db.mssql import init_mssql, execute_raw, close_mssql
    from src.utils.date_utils import resolve_date_range

    ap = argparse.ArgumentParser(description="Live DB verification for AI Query templates")
    ap.add_argument(
        "--as-of",
        metavar="YYYY-MM-DD",
        help="Evaluate MTD/today filters as of this date (replaces GETDATE())",
    )
    args = ap.parse_args()

    await init_mssql()
    dr = resolve_date_range("mtd")
    label = f"as-of {args.as_of}" if args.as_of else "live GETDATE()"
    print(f"MTD window ({label}): {dr.start} -> {dr.end}\n")
    print(f"{'ID':6}  {'Rows':>6}  {'Template':36}  Notes")
    print("-" * 100)

    failures = 0
    empty = 0
    for spec in VERIFIED_AI_TEMPLATES:
        try:
            row = resolve_template(spec)
            sql = row["sql"]
            if args.as_of:
                sql = _sql_as_of(sql, args.as_of)
            r = await execute_raw(sql)
            n = len(r.get("records") or [])
            if n == 0:
                empty += 1
                note = "0 rows"
                if not args.as_of:
                    note += " (no MTD sales yet?)"
            else:
                first = r["records"][0]
                keys = list(first.keys())[:3]
                sample = ", ".join(f"{k}={first[k]}" for k in keys)
                note = sample[:55]
            # vat_03 today snapshot may legitimately be 0 on day with no sales
            # vat_04 MTD vs LY always returns 2 rows
            expect_rows = spec["id"] not in ("vat_03",) or args.as_of
            if n == 0 and expect_rows and spec["id"] != "vat_04":
                failures += 1
                note += " [FAIL expected data]"
            elif n == 0 and spec["id"] == "vat_04":
                failures += 1
                note += " [FAIL expected 2 rows]"
            print(f"{spec['id']:6}  {n:6}  {row['template_id']:36}  {note}")
        except Exception as exc:
            failures += 1
            print(f"{spec['id']:6}  {'ERR':>6}  {spec['expected_template_id']:36}  {exc}")

    await close_mssql()
    print()
    with_data = len(VERIFIED_AI_TEMPLATES) - empty
    print(f"With rows: {with_data}/{len(VERIFIED_AI_TEMPLATES)}  |  Failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
