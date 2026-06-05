"""Live DB check for previously broken frequent AI queries (#20, #28, #34, #36, #38, #40)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from nlq_faq_kpi import FREQUENT_AI_QUERIES
from nlq_faq_sql import try_faq_template

INDICES = (20, 28, 34, 36, 38, 40)


async def main() -> int:
    from src.db.mssql import close_mssql, execute_raw, init_mssql

    await init_mssql()
    failures = 0
    print(f"{'#':>3}  {'Rows':>7}  {'Template':36}  Question")
    print("-" * 100)
    for i in INDICES:
        q = FREQUENT_AI_QUERIES[i - 1]
        hit = try_faq_template(q)
        if not hit:
            print(f"{i:3}  {'—':>7}  {'NO MATCH':36}  {q[:40]}")
            failures += 1
            continue
        tid = hit.get("template_id", "?")
        try:
            r = await execute_raw(hit["sql"])
            n = len(r.get("records") or [])
            status = "OK" if n > 0 else "EMPTY"
            if n == 0:
                failures += 1
            print(f"{i:3}  {n:7}  {tid:36}  {status}")
        except Exception as e:
            failures += 1
            print(f"{i:3}  {'ERR':>7}  {tid:36}  {str(e)[:60]}")
    await close_mssql()
    print(f"\nFailures (0 rows or error): {failures}/{len(INDICES)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
