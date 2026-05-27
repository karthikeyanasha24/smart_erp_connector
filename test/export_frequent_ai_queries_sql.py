"""
Export curated T-SQL for the "most frequent AI queries" list (FAQ templates).

Reads SQL from nlq_faq_sql.try_faq_template() — single source of truth with the NLQ terminal.

Usage (from repo root):
  python test/export_frequent_ai_queries_sql.py --write           # write test/frequent_ai_queries_faq.sql
  python test/export_frequent_ai_queries_sql.py                   # verify templates only (default)
  python test/export_frequent_ai_queries_sql.py --verify          # same as default
  python test/export_frequent_ai_queries_sql.py --execute         # run each on DB (needs env)

Requires DB_* / ERP_* env vars for --execute (same as terminal_openai_nlq_sql.py).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# test/ on path
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _faq_rows() -> List[Tuple[int, str, Dict[str, Any]]]:
    from nlq_faq_kpi import FREQUENT_AI_QUERIES
    from nlq_faq_sql import try_faq_template

    rows: List[Tuple[int, str, Dict[str, Any]]] = []
    for i, q in enumerate(FREQUENT_AI_QUERIES, start=1):
        hit = try_faq_template(q)
        if not hit:
            raise RuntimeError(f"No FAQ template for [{i}] {q!r}")
        rows.append((i, q, hit))
    return rows


def write_sql_bundle(path: Path) -> None:
    rows = _faq_rows()
    sep = "-- " + "=" * 76 + "\n"
    lines = [
        "/*",
        "  Frequent AI queries — FAQ-generated T-SQL bundle",
        f"  Generated: {datetime.now(timezone.utc).isoformat()}",
        "  Source: nlq_faq_kpi.FREQUENT_AI_QUERIES + nlq_faq_sql.try_faq_template",
        "  Execute per block as needed (read-only analytical queries).",
        "*/",
        "",
    ]
    for i, q, hit in rows:
        tid = hit.get("template_id", "?")
        expl = (hit.get("explanation") or "").replace("*/", "* /").replace("\r\n", "\n")
        assumptions = hit.get("assumptions") or []
        sql = (hit.get("sql") or "").strip()
        lines.append(sep.strip())
        lines.append(f"-- {i}/{len(rows)} • {q}")
        lines.append(f"-- template_id: {tid}")
        lines.append(f"-- explanation: {expl}")
        for a in assumptions:
            aa = str(a).replace("*/", "* /")
            lines.append(f"-- assumption: {aa}")
        lines.append(sep.strip())
        lines.append(sql)
        lines.append("")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def verify_match_only() -> bool:
    rows = _faq_rows()
    print(f"OK: {len(rows)} FAQ phrases match templates.")
    for i, q, hit in rows:
        print(f"  {i:2}. [{hit['template_id']}] {q[:62]}{'...' if len(q) > 62 else ''}")
    return True


def _db_env_ready() -> Tuple[bool, List[str]]:
    server = (os.getenv("DB_SERVER") or os.getenv("ERP_DB_HOST") or "").strip()
    database = (os.getenv("DB_NAME") or os.getenv("ERP_DB_NAME") or "").strip()
    user = (os.getenv("DB_USER") or os.getenv("ERP_DB_USER") or "").strip()
    password = os.getenv("DB_PASSWORD") or os.getenv("ERP_DB_PASSWORD") or ""
    missing = [n for n, v in [("DB_SERVER/ERP_DB_HOST", server), ("DB_NAME/ERP_DB_NAME", database), ("DB_USER/ERP_DB_USER", user), ("DB_PASSWORD/ERP_DB_PASSWORD", password)] if not v]
    return len(missing) == 0, missing


def verify_execute(timeout_sec: int = 120) -> bool:
    """Run each FAQ SQL once against SQL Server (pyodbc)."""
    ok_env, missing = _db_env_ready()
    if not ok_env:
        print(
            "Skip --execute: missing env: " + ", ".join(missing) + " (same as NLQ terminal).",
            file=sys.stderr,
        )
        return True

    try:
        from terminal_openai_nlq_sql import connect_mssql
    except ImportError:
        print("Cannot import terminal_openai_nlq_sql.connect_mssql; run from project root.", file=sys.stderr)
        return False

    rows = _faq_rows()
    conn, driver = connect_mssql()
    conn.timeout = timeout_sec
    cur = conn.cursor()
    ok = 0
    fail: List[Tuple[int, str, str]] = []
    print(f"(DB driver: {driver}, timeout={timeout_sec}s)")
    for i, q, hit in rows:
        tid = hit["template_id"]
        sql = hit["sql"]
        label = f"{i}/{len(rows)} [{tid}]"
        try:
            cur.execute(sql)
            if cur.description:
                cur.fetchmany(5)
            else:
                rowcount = getattr(cur, "rowcount", -1)
                if rowcount == -1:
                    pass
            ok += 1
            print(f"  OK {label}")
        except Exception as exc:  # noqa: BLE001
            fail.append((i, tid, str(exc)))
            print(f"  FAIL {label}: {exc}")

    conn.close()
    print(f"\nExecuted: {ok}/{len(rows)} OK, {len(fail)} failed")
    for i, tid, err in fail:
        print(f"  #{i} {tid}: {err[:180]}")
    return len(fail) == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Export / verify FAQ SQL for frequent AI queries.")
    ap.add_argument(
        "--write",
        nargs="?",
        const=str(_HERE / "frequent_ai_queries_faq.sql"),
        metavar="FILE",
        help="Write consolidated .sql bundle (default: test/frequent_ai_queries_faq.sql)",
    )
    ap.add_argument("--verify", action="store_true", help="Only verify phrases → templates (default if no --write/--execute)")
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Execute each FAQ SQL against DB (needs DB_* / ERP_* env like NLQ terminal)",
    )
    ap.add_argument("--timeout", type=int, default=120, help="Per-query ODBC timeout seconds (execute mode)")
    args = ap.parse_args()

    code = 0
    if args.write:
        p = Path(args.write).resolve()
        write_sql_bundle(p)
        print(f"Wrote {p} ({p.stat().st_size} bytes)")
    if args.verify or (not args.write and not args.execute):
        if not verify_match_only():
            code = 1
    if args.execute:
        if not verify_match_only():
            code = 1
        if not verify_execute(timeout_sec=args.timeout):
            code = 1

    # default with no flags: template match only (handled above)


if __name__ == "__main__":
    raise SystemExit(main())
