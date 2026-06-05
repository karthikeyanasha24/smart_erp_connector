"""
Execute all 50 FREQUENT_AI_QUERIES against live SQL Server and write a review file.

Usage:
  python test/run_all_frequent_results.py
  python test/run_all_frequent_results.py --max-rows 25
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from nlq_faq_kpi import FREQUENT_AI_QUERIES
from nlq_faq_sql import try_faq_template


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


async def main() -> int:
    from src.db.mssql import close_mssql, execute_raw, init_mssql
    from src.utils.date_utils import resolve_date_range

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--max-rows",
        type=int,
        default=15,
        help="Max data rows per query in output (0 = summary table only)",
    )
    ap.add_argument(
        "-o",
        "--output",
        default=str(
            Path(__file__).resolve().parent / "frequent_50_live_results.md"
        ),
    )
    args = ap.parse_args()

    out_path = Path(args.output)
    dr = resolve_date_range("mtd")

    await init_mssql()

    results: list[dict[str, Any]] = []
    print(f"Running {len(FREQUENT_AI_QUERIES)} queries (MTD {dr.start} -> {dr.end})...")
    print(f"{'#':>3}  {'Rows':>8}  {'Status':8}  Template")
    print("-" * 72)

    for i, q in enumerate(FREQUENT_AI_QUERIES, 1):
        hit = try_faq_template(q)
        if not hit:
            results.append(
                {
                    "i": i,
                    "q": q,
                    "tid": None,
                    "status": "NO_MATCH",
                    "n": 0,
                    "records": [],
                    "error": None,
                }
            )
            print(f"{i:3}  {'—':>8}  NO_MATCH")
            continue

        tid = hit.get("template_id", "?")
        try:
            r = await execute_raw(hit["sql"])
            records = r.get("records") or []
            n = len(records)
            status = "OK" if n > 0 else "EMPTY"
            results.append(
                {
                    "i": i,
                    "q": q,
                    "tid": tid,
                    "status": status,
                    "n": n,
                    "records": records,
                    "error": None,
                }
            )
            print(f"{i:3}  {n:8,}  {status:8}  {tid}")
        except Exception as e:
            results.append(
                {
                    "i": i,
                    "q": q,
                    "tid": tid,
                    "status": "ERROR",
                    "n": 0,
                    "records": [],
                    "error": str(e),
                }
            )
            print(f"{i:3}  {'ERR':>8}  ERROR     {tid}")

    await close_mssql()

    lines: list[str] = []
    lines.append("# Frequent AI Queries — Live DB Results")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"MTD window: `{dr.start}` → `{dr.end}`")
    lines.append(f"Sample rows per query below: **{args.max_rows}** (0 = table only)")
    lines.append("")
    lines.append("| # | Status | Rows | Template | Question |")
    lines.append("|---|--------|-----:|----------|----------|")

    for row in results:
        q_short = row["q"].replace("|", "/")
        tid = row["tid"] or "—"
        lines.append(
            f"| {row['i']} | {row['status']} | {row['n']:,} | `{tid}` | {q_short} |"
        )

    if args.max_rows > 0:
        lines.append("")
        lines.append("---")
        lines.append("")
        for row in results:
            lines.append(f"## {row['i']}. {row['q']}")
            tid = row["tid"] or "—"
            lines.append(
                f"**Template:** `{tid}` · **Status:** {row['status']} · **Rows:** {row['n']:,}"
            )
            lines.append("")
            if row["error"]:
                lines.append(f"```\n{row['error']}\n```")
                lines.append("")
                continue
            if row["n"] == 0:
                lines.append("_No rows returned._")
                lines.append("")
                continue
            show = row["records"][: args.max_rows]
            if row["n"] > args.max_rows:
                lines.append(
                    f"_First {args.max_rows} of {row['n']:,} rows (open AI Query for full export)._"
                )
                lines.append("")
            lines.append("```json")
            lines.append(json.dumps(show, indent=2, default=_json_default))
            lines.append("```")
            lines.append("")

    ok = sum(1 for r in results if r["status"] == "OK")
    empty = sum(1 for r in results if r["status"] == "EMPTY")
    err = sum(1 for r in results if r["status"] in ("ERROR", "NO_MATCH"))
    lines.append("---")
    lines.append("")
    lines.append(
        f"**Summary:** {ok} OK with data · {empty} empty · {err} error/no-match · total 50"
    )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("-" * 72)
    print(f"Wrote {out_path}")
    print(f"OK: {ok}/50 | Empty: {empty} | Errors: {err}")
    return 1 if empty or err else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
