"""
db_chat_pipeline — 3-step AI-to-SQL pipeline (ported from db-chat/db_chat.py)

  Step 1  AI picks 1-4 relevant views  (compact schema)
  Step 2  AI generates SQL              (focused schema for selected views only)
  Step 3  Column/table validator        (rejects hallucinated names, auto-retries)
  Step 4  Execute SQL on the database
  Step 5  AI explains results in plain English
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

from src.config import cfg
from src.utils.logger import logger

# ─── Paths ────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_CACHE_FILE = _PROJECT_ROOT / "db-chat" / "schema_cache.json"

MAX_RESULT_ROWS = int(os.getenv("DB_CHAT_MAX_ROWS", "500"))

_snap_cache: Optional[dict] = None


# ─── Result type ──────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    sql: Optional[str]
    records: list[dict[str, Any]]
    record_count: int
    summary: str
    description: str
    selected_views: list[str] = field(default_factory=list)
    view_selection_reason: str = ""
    warnings: list[str] = field(default_factory=list)
    corrected: bool = False
    truncated: bool = False
    conversational: bool = False


# ─── Schema loading ───────────────────────────────────────────────────────────

async def load_snapshot(force_refresh: bool = False) -> dict:
    """Return schema snapshot dict (from file or live DB)."""
    global _snap_cache
    if _snap_cache and not force_refresh and _snap_cache.get("objects"):
        return _snap_cache

    if _snap_cache and not _snap_cache.get("objects"):
        _snap_cache = None  # discard failed/empty cache

    if _SCHEMA_CACHE_FILE.exists() and not force_refresh:
        try:
            with open(_SCHEMA_CACHE_FILE, "r", encoding="utf-8") as f:
                _snap_cache = json.load(f)
            logger.info(
                "Schema loaded from cache",
                path=str(_SCHEMA_CACHE_FILE),
                snapshotted_at=_snap_cache.get("snapshotted_at"),
            )
            return _snap_cache
        except Exception as exc:
            logger.warning("Could not read schema cache — querying DB", error=str(exc))

    snap = await _build_live_snapshot()
    if not snap.get("objects"):
        raise RuntimeError(
            "Schema discovery returned 0 views/tables. "
            "Run: cd db-chat && python schema_cache.py"
        )
    _snap_cache = snap
    return _snap_cache


async def _build_live_snapshot() -> dict:
    # Must NOT use NOLOCK hints — they break INFORMATION_SCHEMA queries
    # (regex inserts WITH (NOLOCK) before table aliases).
    from src.db.mssql import execute_raw

    sql = """
        SELECT o.TABLE_SCHEMA + '.' + o.TABLE_NAME AS object_name,
               o.TABLE_TYPE, c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE
        FROM INFORMATION_SCHEMA.TABLES o
        JOIN INFORMATION_SCHEMA.COLUMNS c
          ON c.TABLE_SCHEMA = o.TABLE_SCHEMA AND c.TABLE_NAME = o.TABLE_NAME
        WHERE o.TABLE_TYPE IN ('BASE TABLE','VIEW')
          AND o.TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA')
        ORDER BY o.TABLE_SCHEMA, o.TABLE_NAME, c.ORDINAL_POSITION
    """
    try:
        result = await execute_raw(sql)
        rows = result["records"]
        logger.info("Schema discovered from live DB", columns=len(rows))
    except Exception as exc:
        logger.warning("Schema discovery failed", error=str(exc))
        rows = []

    objects: dict = {}
    for r in rows:
        name = r["object_name"]
        if name not in objects:
            objects[name] = {
                "type": "VIEW" if r["TABLE_TYPE"] == "VIEW" else "TABLE",
                "columns": [],
            }
        objects[name]["columns"].append({
            "name": r["COLUMN_NAME"],
            "type": r["DATA_TYPE"],
            "nullable": r["IS_NULLABLE"] == "YES",
        })

    return {
        "db": cfg.mssql_database,
        "server": f"{cfg.mssql_server}:{cfg.mssql_port}",
        "snapshotted_at": datetime.now().isoformat(timespec="seconds"),
        "curated": {},
        "objects": objects,
    }


# ─── Schema rendering ─────────────────────────────────────────────────────────

def _col_names(cols: list) -> list[str]:
    result = []
    for c in cols:
        if isinstance(c, dict):
            result.append(c["name"])
        else:
            result.append(str(c).split(" ")[0])
    return result


def _col_detail(cols: list) -> list[str]:
    result = []
    for c in cols:
        if isinstance(c, dict):
            nullable = "?" if c.get("nullable") else ""
            result.append(f"{c['name']} ({c['type']}{nullable})")
        else:
            result.append(str(c))
    return result


def compact_schema_for_view_selection(snap: dict) -> str:
    lines = [
        f"DATABASE: {snap.get('db', cfg.mssql_database)}",
        f"TODAY: {date.today().isoformat()}",
        "",
        "AVAILABLE VIEWS AND TABLES:",
        "(column names only — full details provided after you select views)",
        "",
    ]

    curated = snap.get("curated", {})
    if curated:
        lines.append("=== PREFERRED VIEWS (curated — use these when they fit) ===")
        for key, info in curated.items():
            view_name = info.get("name", "")
            alias = info.get("alias", key)
            lines.append(f"\n  {view_name}  [{alias}]")
            obj = snap.get("objects", {}).get(view_name)
            if obj:
                names = _col_names(obj["columns"])
                lines.append(f"  Columns: {', '.join(names)}")
            for k, v in info.items():
                if k.endswith("_column") or k in ("date_column", "amount_column"):
                    lines.append(f"  {k}: {v}")
        lines.append("\n=== ALL VIEWS AND TABLES ===")

    for obj_name in sorted(snap.get("objects", {})):
        obj = snap["objects"][obj_name]
        names = _col_names(obj["columns"])
        lines.append(f"\n[{obj.get('type', 'VIEW')}] {obj_name}")
        lines.append(f"  Columns: {', '.join(names)}")

    return "\n".join(lines)


def focused_schema_for_sql(snap: dict, selected_views: list[str]) -> str:
    lines = [
        f"DATABASE: {snap.get('db', cfg.mssql_database)}",
        f"TODAY: {date.today().isoformat()}",
        "",
        "SCHEMA FOR SELECTED VIEWS ONLY:",
        "(Use ONLY these views and ONLY the columns listed below)",
        "",
    ]

    curated = snap.get("curated", {})
    curated_by_name = {info["name"]: info for info in curated.values() if "name" in info}
    objects = snap.get("objects", {})
    found_any = False

    for view_name in selected_views:
        obj = objects.get(view_name)
        if obj is None:
            for k in objects:
                if k.lower() == view_name.lower():
                    obj = objects[k]
                    view_name = k
                    break
        if obj is None:
            continue
        found_any = True

        lines.append(f"[{obj.get('type', 'VIEW')}] {view_name}")
        lines.append("  Columns:")
        for c in _col_detail(obj["columns"]):
            lines.append(f"    - {c}")

        c_info = curated_by_name.get(view_name)
        if c_info:
            lines.append("  Key mappings (use these column names):")
            for k, v in c_info.items():
                if k not in ("name", "alias", "key_columns", "sample_query", "note") and isinstance(v, str):
                    lines.append(f"    {k}: {v}")
            if "sample_query" in c_info:
                lines.append(f"  Sample query: {c_info['sample_query']}")
        lines.append("")

    if not found_any:
        for obj_name in sorted(objects):
            obj = objects[obj_name]
            lines.append(f"[{obj.get('type', 'VIEW')}] {obj_name}")
            for c in _col_detail(obj["columns"]):
                lines.append(f"  - {c}")
            lines.append("")

    return "\n".join(lines)


# ─── AI providers ─────────────────────────────────────────────────────────────

def _call_claude(messages: list[dict], system: str) -> str:
    import anthropic

    if not cfg.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    client = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=cfg.ANTHROPIC_MODEL,
        max_tokens=2048,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def _openai_chat_kwargs(model: str, *, max_out: int = 2048) -> dict[str, Any]:
    """GPT-5 / o-series models use max_completion_tokens, not max_tokens."""
    m = model.lower()
    if m.startswith(("gpt-5", "o1", "o3", "gpt-4.1")):
        return {"max_completion_tokens": max_out}
    return {"max_tokens": max_out, "temperature": 0}


def _call_gpt(messages: list[dict], system: str) -> str:
    from openai import OpenAI

    if not cfg.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set.")
    client = OpenAI(api_key=cfg.OPENAI_API_KEY)
    full_messages = [{"role": "system", "content": system}] + messages
    response = client.chat.completions.create(
        model=cfg.OPENAI_MODEL,
        messages=full_messages,
        **_openai_chat_kwargs(cfg.OPENAI_MODEL),
    )
    return response.choices[0].message.content or ""


def call_ai(messages: list[dict], system: str, provider: str) -> str:
    if provider in ("gpt", "openai"):
        return _call_gpt(messages, system)
    return _call_claude(messages, system)


async def call_ai_async(messages: list[dict], system: str, provider: str) -> str:
    return await asyncio.to_thread(call_ai, messages, system, provider)


def parse_json_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {"answer": text}


def normalize_provider(provider: str) -> str:
    return "gpt" if provider == "openai" else "claude"


# ─── Step 1 — View selection ──────────────────────────────────────────────────

VIEW_SELECTOR_SYSTEM = """
You are a database expert for a retail ERP on Microsoft SQL Server.
Your ONLY job is to choose which database views/tables are needed to answer a question.

Rules:
- Choose 1 to 4 views maximum. Fewer is better.
- Return ONLY exact view/table names from the list provided. Never invent names.
- For revenue / sales / branch performance → prefer dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID
- For detailed per-item sales transactions → dbo.VW_MB_POWERBI_SLSXNS_REPORT
- For customer information → dbo.VwAICustomerDetails
- For stock / inventory levels → dbo.VwAIStockData or dbo.VW_MB_POWERBI_STOCK_REPORT
- For purchases → dbo.VW_MB_POWERBI_PURXNS_REPORT
- For product/item catalog → dbo.VW_MB_POWERBI_PRODUCT_MASTER or dbo.VwMstItems
- For salesperson info → dbo.VwAISalesPerson

Return ONLY a JSON object like:
{
  "views": ["dbo.ViewName1", "dbo.ViewName2"],
  "reason": "one sentence explaining why these views"
}
""".strip()


async def select_views(question: str, snap: dict, provider: str) -> tuple[list[str], str]:
    compact = compact_schema_for_view_selection(snap)
    user_msg = f"Question: {question}\n\nSchema:\n{compact}"

    raw = await call_ai_async(
        [{"role": "user", "content": user_msg}],
        VIEW_SELECTOR_SYSTEM,
        provider,
    )
    result = parse_json_response(raw)
    selected = result.get("views", [])
    reason = result.get("reason", "")

    objects = snap.get("objects", {})
    objects_lower = {k.lower(): k for k in objects}
    valid: list[str] = []
    for v in selected:
        if v in objects:
            valid.append(v)
        elif v.lower() in objects_lower:
            valid.append(objects_lower[v.lower()])

    if not valid:
        valid = _keyword_fallback(question, snap)

    return valid, reason


def _keyword_fallback(question: str, snap: dict) -> list[str]:
    q = question.lower()
    curated = snap.get("curated", {})
    objects = snap.get("objects", {})

    scores: list[tuple[float, str]] = []
    for key, info in curated.items():
        view_name = info.get("name", "")
        if view_name not in objects:
            continue
        alias = (info.get("alias", "") + " " + key).lower()
        score = sum(1 for word in q.split() if word in alias or word in view_name.lower())
        scores.append((score, view_name))

    scores.sort(reverse=True)
    top = [v for s, v in scores if s > 0][:2]

    primary = "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID"
    if any(w in q for w in ("sales", "revenue", "branch", "category", "amount")):
        if primary not in top and primary in objects:
            top = [primary] + top[:1]

    return top or ([primary] if primary in objects else list(objects.keys())[:1])


# ─── Step 2 — SQL generation ──────────────────────────────────────────────────

SQL_GEN_SYSTEM = """
You are an expert T-SQL analyst for a retail ERP on Microsoft SQL Server (zRetailHQ0).
Generate T-SQL SELECT queries using ONLY the views and columns listed in the schema provided.

Rules:
1. ONLY use table/view names and column names from the provided schema. NEVER invent names.
2. Always add WITH (NOLOCK) after every table/view reference.
3. Use TOP N (default 20) to limit results.
4. NEVER write DROP, DELETE, UPDATE, INSERT, EXEC, or DDL. SELECT and WITH (CTEs) only.
5. Use square brackets around column names: [ColumnName].
6. For date filtering use CAST(@date AS DATE) comparisons.

DATE PATTERNS — use EXACTLY these:
  This month : [DateCol] >= DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1)
               AND [DateCol] < DATEADD(month,1,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))
  Today      : CAST([DateCol] AS DATE) = CAST(GETDATE() AS DATE)
  This year  : [DateCol] >= DATEFROMPARTS(YEAR(GETDATE()),1,1)
               AND [DateCol] < DATEADD(year,1,DATEFROMPARTS(YEAR(GETDATE()),1,1))
  Last month : [DateCol] >= DATEFROMPARTS(YEAR(DATEADD(month,-1,GETDATE())),MONTH(DATEADD(month,-1,GETDATE())),1)
               AND [DateCol] < DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1)
  Last N days: [DateCol] >= CAST(DATEADD(day,-N,GETDATE()) AS DATE)

Return ONLY a JSON object:
{
  "sql": "<valid T-SQL SELECT statement>",
  "explanation": "<one sentence describing what the query does>"
}

If no SQL is needed (e.g. the question is conversational), set sql to null and add an "answer" field.
""".strip()


async def generate_sql(
    question: str,
    focused_schema: str,
    provider: str,
    prior_error: Optional[str] = None,
    top_n: Optional[int] = None,
) -> tuple[str, str, str]:
    content = f"Question: {question}\n\nSchema to use:\n{focused_schema}"
    if top_n:
        content += f"\n\nUse TOP {top_n} when ranking or limiting rows."
    if prior_error:
        content += (
            f"\n\nPREVIOUS ATTEMPT FAILED with this error/problem:\n{prior_error}\n\n"
            "Please fix and regenerate."
        )

    raw = await call_ai_async(
        [{"role": "user", "content": content}],
        SQL_GEN_SYSTEM,
        provider,
    )
    result = parse_json_response(raw)

    sql = result.get("sql") or ""
    explanation = result.get("explanation", "")
    answer = result.get("answer", "")

    if not sql or str(sql).lower() in ("null", "none"):
        return "", answer or explanation, answer or explanation

    return sql.strip(), explanation, ""


# ─── Step 3 — SQL validation ──────────────────────────────────────────────────

def _sql_aliases(sql: str) -> set[str]:
    """Collect column aliases so we don't flag them as unknown columns."""
    aliases: set[str] = set()
    for m in re.finditer(r"\bAS\s+\[?(\w+)\]?", sql, re.IGNORECASE):
        aliases.add(m.group(1).lower())
    return aliases


def validate_sql(sql: str, snap: dict, selected_views: list[str]) -> list[str]:
    problems: list[str] = []
    objects = snap.get("objects", {})
    objects_lower = {k.lower(): k for k in objects}
    aliases = _sql_aliases(sql)

    table_pattern = re.compile(
        r"(?:FROM|JOIN)\s+(\[?\w+\]?\.\[?\w+\]?|\[?\w+\]?)",
        re.IGNORECASE,
    )
    for m in table_pattern.finditer(sql):
        raw = m.group(1).replace("[", "").replace("]", "")
        if raw.upper() in ("WITH", "NOLOCK", "SELECT", "WHERE", "AND", "OR", "ON"):
            continue
        if raw in objects or raw.lower() in objects_lower:
            continue
        if f"dbo.{raw}" in objects or f"dbo.{raw}".lower() in objects_lower:
            continue
        problems.append(f"Unknown table/view '{raw}' — not found in schema.")

    all_cols: set[str] = set()
    for obj in objects.values():
        for c in _col_names(obj["columns"]):
            all_cols.add(c.lower())

    col_pattern = re.compile(r"\[(\w+)\]")
    for m in col_pattern.finditer(sql):
        col = m.group(1)
        if col.isdigit() or col.lower() in aliases:
            continue
        if col.lower() not in all_cols:
            problems.append(
                f"Unknown column '[{col}]' — not found in any view in the schema."
            )

    return problems


# ─── Step 5 — Explain results ─────────────────────────────────────────────────

EXPLAIN_SYSTEM = """
You are a helpful retail business analyst. You have run a SQL query against an ERP database
and received results. Explain what the data means in clear, plain English.

Rules:
- Be specific: include actual numbers, names, and values from the data.
- Format currency in Indian style (₹ with lakh/crore: e.g. ₹12,34,567 or ₹1.2 lakh).
- If the result is empty (0 rows), explain what that means in context.
- Keep the answer concise but complete — 2 to 6 sentences is ideal.
- Do NOT repeat the SQL query.

Return ONLY a JSON object:
{
  "answer": "<plain English explanation of the results>"
}
""".strip()


async def explain_results(
    question: str,
    sql: str,
    rows: list[dict],
    row_count: int,
    truncated: bool,
    provider: str,
) -> str:
    results_json = json.dumps(rows, indent=2, default=str)
    truncation_note = f" (showing first {MAX_RESULT_ROWS} of {row_count}+)" if truncated else ""

    content = (
        f"Original question: {question}\n\n"
        f"SQL that was run:\n{sql}\n\n"
        f"Results ({row_count} rows{truncation_note}):\n{results_json}\n\n"
        "Explain the results in plain business English."
    )

    raw = await call_ai_async(
        [{"role": "user", "content": content}],
        EXPLAIN_SYSTEM,
        provider,
    )
    result = parse_json_response(raw)
    return result.get("answer") or raw


# ─── Main pipeline ────────────────────────────────────────────────────────────

async def run_pipeline(
    question: str,
    provider: str = "claude",
    snap: Optional[dict] = None,
    top_n: Optional[int] = None,
    execute_fn: Optional[Callable] = None,
) -> PipelineResult:
    """
    Full db_chat pipeline for the AI Query page.
    """
    from src.db.mssql import execute_query

    if execute_fn is None:
        execute_fn = execute_query

    ai_provider = normalize_provider(provider)
    warnings: list[str] = []
    corrected = False

    if snap is None:
        snap = await load_snapshot()

    if not snap.get("objects"):
        raise RuntimeError(
            "No database schema loaded — cannot answer queries. "
            "Run: cd db-chat && python schema_cache.py"
        )

    selected_views, view_reason = await select_views(question, snap, ai_provider)
    logger.info(
        "db_chat view selection",
        views=selected_views,
        reason=view_reason,
    )

    focused = focused_schema_for_sql(snap, selected_views)
    sql, explanation, conversational_answer = await generate_sql(
        question, focused, ai_provider, top_n=top_n
    )

    if not sql:
        return PipelineResult(
            sql=None,
            records=[],
            record_count=0,
            summary=conversational_answer or explanation,
            description=explanation or "Conversational response",
            selected_views=selected_views,
            view_selection_reason=view_reason,
            warnings=warnings,
            conversational=True,
        )

    first_word = sql.strip().split()[0].upper()
    if first_word not in ("SELECT", "WITH"):
        raise ValueError("AI generated a non-SELECT statement — blocked for safety.")

    problems = validate_sql(sql, snap, selected_views)
    if problems:
        problem_str = "; ".join(problems)
        warnings.append(f"SQL validation issues: {problem_str}")
        sql2, explanation2, _ = await generate_sql(
            question, focused, ai_provider, prior_error=problem_str, top_n=top_n
        )
        if sql2:
            sql, explanation = sql2, explanation2
            corrected = True
            problems2 = validate_sql(sql, snap, selected_views)
            if problems2:
                warnings.append(
                    f"SQL still has issues after retry: {'; '.join(problems2)}"
                )

    try:
        result = await execute_fn(sql, nolock=True, recompile=False)
        records = result["records"]
    except Exception as exc:
        logger.warning("SQL execution failed — retrying with AI fix", error=str(exc))
        sql2, explanation2, _ = await generate_sql(
            question, focused, ai_provider, prior_error=str(exc), top_n=top_n
        )
        if not sql2:
            raise RuntimeError(str(exc)) from exc
        sql, explanation = sql2, explanation2
        corrected = True
        result = await execute_fn(sql, nolock=True, recompile=False)
        records = result["records"]

    row_count = len(records)
    truncated = row_count >= MAX_RESULT_ROWS
    if truncated:
        records = records[:MAX_RESULT_ROWS]
        warnings.append(f"Results capped at {MAX_RESULT_ROWS} rows for display.")

    if len(records) > cfg.DATASET_HARD_CAP:
        records = records[: cfg.DATASET_HARD_CAP]
        warnings.append(f"Results capped at {cfg.DATASET_HARD_CAP:,} rows.")

    summary = await explain_results(
        question, sql, records, row_count, truncated, ai_provider
    )

    return PipelineResult(
        sql=sql,
        records=records,
        record_count=len(records),
        summary=summary,
        description=explanation,
        selected_views=selected_views,
        view_selection_reason=view_reason,
        warnings=warnings,
        corrected=corrected,
        truncated=truncated,
    )
