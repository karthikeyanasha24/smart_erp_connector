#!/usr/bin/env python3
"""
db_chat.py — Standalone ERP Database Q&A Assistant  (3-step AI pipeline)
=========================================================================
Ask natural-language questions about your MSSQL database.

Pipeline per question
  Step 1  AI picks 1-4 relevant views  (sees compact schema — names + cols only)
  Step 2  AI generates SQL              (sees ONLY the selected views' full details)
  Step 3  Column/table validator        (rejects hallucinated names, auto-retries)
  Step 4  Execute SQL on the database
  Step 5  AI explains results in plain English

Usage:
    python db_chat.py                          # interactive REPL
    python db_chat.py "top 5 branches by revenue this month"
    python db_chat.py --schema-only            # print schema and exit
    python db_chat.py --ai gpt                 # use OpenAI GPT instead of Claude

Requirements:
    pip install pyodbc anthropic openai python-dotenv rich
"""

import argparse
import json
import os
import re
import sys
import textwrap
from datetime import date, datetime
from typing import Any, Optional

# Windows terminals often default to cp1252; use UTF-8 so Rich symbols print cleanly.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Optional pretty output ──────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.syntax import Syntax
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None  # type: ignore

# ── Load .env if present ────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DB_SERVER   = os.getenv("DB_SERVER",   "38.45.94.39")
DB_PORT     = os.getenv("DB_PORT",     "12866")
DB_NAME     = os.getenv("DB_NAME",     "zRetailHQ0")
DB_USER     = os.getenv("DB_USER",     "zorderai")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Mb@2026")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY",    "")

DEFAULT_AI    = os.getenv("DB_CHAT_AI",           "claude")
CLAUDE_MODEL  = os.getenv("ANTHROPIC_MODEL",      "claude-sonnet-4-6")
GPT_MODEL     = os.getenv("OPENAI_MODEL",         "gpt-4o")
MAX_RESULT_ROWS = int(os.getenv("DB_CHAT_MAX_ROWS", "50"))

SCHEMA_CACHE_FILE = os.path.join(os.path.dirname(__file__), "schema_cache.json")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATABASE LAYER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_connection():
    try:
        import pyodbc
    except ImportError:
        _die("pyodbc not installed. Run: pip install pyodbc")

    preferred = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
        "FreeTDS",
    ]
    installed = set(pyodbc.drivers())
    available = [d for d in preferred if d in installed]

    if not available:
        _die(
            f"No ODBC driver found. Installed: {sorted(installed)}\n"
            "Download: https://aka.ms/downloadmsodbcsql"
        )

    last_err = None
    for driver in available:
        modern = "ODBC Driver" in driver or "Native Client" in driver
        base = (
            f"DRIVER={{{driver}}};"
            f"SERVER={DB_SERVER},{DB_PORT};"
            f"DATABASE={DB_NAME};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
            "Connection Timeout=30;"
        )
        variants = (
            [base + "TrustServerCertificate=yes;Encrypt=yes;",
             base + "TrustServerCertificate=yes;Encrypt=no;",
             base]
            if modern else [base]
        )
        for cs in variants:
            try:
                return pyodbc.connect(cs, timeout=30)
            except Exception as exc:
                last_err = exc
    _die(f"DB connection failed.\nLast error: {last_err}")


def run_query(sql: str, max_rows: int = MAX_RESULT_ROWS) -> list[dict]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = []
        for i, row in enumerate(cursor.fetchall()):
            if i >= max_rows:
                break
            rows.append(dict(zip(columns, [_serialize(v) for v in row])))
        return rows
    except Exception as exc:
        raise RuntimeError(f"SQL error: {exc}") from exc
    finally:
        conn.close()


def _serialize(val: Any) -> Any:
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCHEMA LOADING  (file-first, DB fallback)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_snap_cache: Optional[dict] = None


def load_snapshot() -> dict:
    """Return schema snapshot dict (from file or live DB)."""
    global _snap_cache
    if _snap_cache:
        return _snap_cache

    if os.path.exists(SCHEMA_CACHE_FILE):
        try:
            with open(SCHEMA_CACHE_FILE, "r", encoding="utf-8") as f:
                _snap_cache = json.load(f)
            _print_status(
                f"Schema loaded from cache (snapshotted {_snap_cache.get('snapshotted_at','?')})."
            )
            return _snap_cache
        except Exception as exc:
            _print_warn(f"Could not read schema_cache.json: {exc} — querying DB…")

    _print_status("No schema cache — querying DB (run schema_cache.py to cache this)…")
    _snap_cache = _build_live_snapshot()
    return _snap_cache


def _build_live_snapshot() -> dict:
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
        rows = run_query(sql, max_rows=8000)
    except Exception as exc:
        _print_warn(f"Schema discovery failed: {exc}")
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
        "db": DB_NAME,
        "server": f"{DB_SERVER}:{DB_PORT}",
        "snapshotted_at": datetime.now().isoformat(timespec="seconds"),
        "curated": {},
        "objects": objects,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCHEMA RENDERING HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _col_names(cols: list) -> list[str]:
    """Extract plain column name strings from snapshot column dicts or strings."""
    result = []
    for c in cols:
        if isinstance(c, dict):
            result.append(c["name"])
        else:
            result.append(str(c).split(" ")[0])
    return result


def _col_detail(cols: list) -> list[str]:
    """Full column detail strings: 'Name (type?)'"""
    result = []
    for c in cols:
        if isinstance(c, dict):
            nullable = "?" if c.get("nullable") else ""
            result.append(f"{c['name']} ({c['type']}{nullable})")
        else:
            result.append(str(c))
    return result


def compact_schema_for_view_selection(snap: dict) -> str:
    """
    Compact schema sent to AI for Step 1 (view selection).
    Shows each view/table with column NAMES only — no types, no details.
    Keeps token count low.
    """
    lines = [
        f"DATABASE: {snap.get('db', DB_NAME)}",
        f"TODAY: {date.today().isoformat()}",
        "",
        "AVAILABLE VIEWS AND TABLES:",
        "(column names only — full details provided after you select views)",
        "",
    ]

    # Add curated hints first so AI sees preferred views at the top
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
            # Add key mappings as hints
            for k, v in info.items():
                if k.endswith("_column") or k == "date_column" or k == "amount_column":
                    lines.append(f"  {k}: {v}")
        lines.append("\n=== ALL VIEWS AND TABLES ===")

    for obj_name in sorted(snap.get("objects", {})):
        obj = snap["objects"][obj_name]
        names = _col_names(obj["columns"])
        lines.append(f"\n[{obj.get('type','VIEW')}] {obj_name}")
        lines.append(f"  Columns: {', '.join(names)}")

    return "\n".join(lines)


def focused_schema_for_sql(snap: dict, selected_views: list[str]) -> str:
    """
    Full column details for ONLY the selected views.
    Sent to AI for Step 2 (SQL generation).
    """
    lines = [
        f"DATABASE: {snap.get('db', DB_NAME)}",
        f"TODAY: {date.today().isoformat()}",
        "",
        "SCHEMA FOR SELECTED VIEWS ONLY:",
        "(Use ONLY these views and ONLY the columns listed below)",
        "",
    ]

    curated = snap.get("curated", {})
    # Build a reverse map: view_name → curated info
    curated_by_name = {info["name"]: info for info in curated.values() if "name" in info}

    objects = snap.get("objects", {})
    found_any = False

    for view_name in selected_views:
        # Try exact match first, then case-insensitive
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

        lines.append(f"[{obj.get('type','VIEW')}] {view_name}")
        col_strs = _col_detail(obj["columns"])
        lines.append("  Columns:")
        for c in col_strs:
            lines.append(f"    - {c}")

        # Add curated hints if available for this view
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
        # Fallback: include all views if none matched
        _print_warn("View selection returned no matching views — using full schema.")
        for obj_name in sorted(objects):
            obj = objects[obj_name]
            lines.append(f"[{obj.get('type','VIEW')}] {obj_name}")
            for c in _col_detail(obj["columns"]):
                lines.append(f"  - {c}")
            lines.append("")

    return "\n".join(lines)


def render_full_schema(snap: dict) -> str:
    """Human-readable full schema for --schema-only display."""
    today = date.today().isoformat()
    lines = [
        f"DATABASE : {snap.get('db', DB_NAME)}  SERVER: {snap.get('server','')}",
        f"TODAY    : {today}",
        f"SNAPSHOT : {snap.get('snapshotted_at','live')}",
        "",
    ]
    curated = snap.get("curated", {})
    if curated:
        lines += ["=" * 70, "CURATED VIEW GUIDE", "=" * 70]
        for key, info in curated.items():
            lines.append(f"\n▶ {info.get('alias', key)}")
            lines.append(f"  View : {info['name']}")
            for k, v in info.items():
                if k in ("name", "alias"):
                    continue
                if isinstance(v, list):
                    lines.append(f"  {k:25s}: {', '.join(v)}")
                else:
                    lines.append(f"  {k:25s}: {v}")
        lines += [""]

    lines += ["=" * 70, "FULL SCHEMA", "=" * 70]
    for obj_name in sorted(snap.get("objects", {})):
        obj = snap["objects"][obj_name]
        lines.append(f"\n[{obj.get('type','VIEW')}] {obj_name}")
        lines.append("  Columns:")
        for c in _col_detail(obj["columns"]):
            lines.append(f"    - {c}")

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI PROVIDERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _call_claude(messages: list[dict], system: str) -> str:
    try:
        import anthropic
    except ImportError:
        _die("anthropic not installed. Run: pip install anthropic")
    if not ANTHROPIC_API_KEY:
        _die("ANTHROPIC_API_KEY not set.")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def _openai_chat_kwargs(model: str, *, max_out: int = 2048) -> dict:
    m = model.lower()
    if m.startswith(("gpt-5", "o1", "o3", "gpt-4.1")):
        return {"max_completion_tokens": max_out}
    return {"max_tokens": max_out, "temperature": 0}


def _call_gpt(messages: list[dict], system: str) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        _die("openai not installed. Run: pip install openai")
    if not OPENAI_API_KEY:
        _die("OPENAI_API_KEY not set.")
    client = OpenAI(api_key=OPENAI_API_KEY)
    full_messages = [{"role": "system", "content": system}] + messages
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=full_messages,
        **_openai_chat_kwargs(GPT_MODEL),
    )
    return response.choices[0].message.content


def call_ai(messages: list[dict], system: str, provider: str) -> str:
    if provider == "gpt":
        return _call_gpt(messages, system)
    return _call_claude(messages, system)


def parse_json_response(raw: str) -> dict:
    """Extract JSON from AI response, handles markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {"answer": text}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 — VIEW SELECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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


def select_views(question: str, snap: dict, provider: str) -> list[str]:
    """Step 1: Ask AI to pick the relevant views from the full schema."""
    compact = compact_schema_for_view_selection(snap)
    user_msg = f"Question: {question}\n\nSchema:\n{compact}"

    _print_status("Step 1/3 — Selecting relevant views…")
    raw = call_ai([{"role": "user", "content": user_msg}], VIEW_SELECTOR_SYSTEM, provider)
    result = parse_json_response(raw)

    selected = result.get("views", [])
    reason = result.get("reason", "")

    if reason:
        _print_status(f"  View selection reason: {reason}")

    # Validate: keep only names that actually exist in the schema
    objects = snap.get("objects", {})
    objects_lower = {k.lower(): k for k in objects}
    valid = []
    for v in selected:
        if v in objects:
            valid.append(v)
        elif v.lower() in objects_lower:
            valid.append(objects_lower[v.lower()])
        else:
            _print_warn(f"  AI selected unknown view '{v}' — skipping.")

    if not valid:
        # Fallback: keyword-based selection from curated views
        _print_warn("  AI returned no valid views — using curated fallback.")
        valid = _keyword_fallback(question, snap)

    _print_status(f"  Selected views: {', '.join(valid)}")
    return valid


def _keyword_fallback(question: str, snap: dict) -> list[str]:
    """Keyword-score fallback when AI selection fails."""
    q = question.lower()
    curated = snap.get("curated", {})
    objects = snap.get("objects", {})

    # Score curated views by keyword overlap
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

    # Always include primary sales view for revenue questions
    primary = "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID"
    if any(w in q for w in ("sales", "revenue", "branch", "category", "amount")):
        if primary not in top and primary in objects:
            top = [primary] + top[:1]

    return top or ([primary] if primary in objects else list(objects.keys())[:1])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2 — SQL GENERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
  Last N days: [DateCol] >= CAST(DATEADD(day,-N,GETDATE()) AS DATE)

Return ONLY a JSON object:
{
  "sql": "<valid T-SQL SELECT statement>",
  "explanation": "<one sentence describing what the query does>"
}

If no SQL is needed (e.g. the question is conversational), set sql to null and add an "answer" field.
""".strip()


def generate_sql(
    question: str,
    focused_schema: str,
    provider: str,
    prior_error: Optional[str] = None,
) -> tuple[str, str]:
    """Step 2: Generate SQL using ONLY the focused schema."""
    content = f"Question: {question}\n\nSchema to use:\n{focused_schema}"
    if prior_error:
        content += f"\n\nPREVIOUS ATTEMPT FAILED with this error/problem:\n{prior_error}\n\nPlease fix and regenerate."

    _print_status("Step 2/3 — Generating SQL…")
    raw = call_ai([{"role": "user", "content": content}], SQL_GEN_SYSTEM, provider)
    result = parse_json_response(raw)

    sql = result.get("sql") or ""
    explanation = result.get("explanation", "")
    answer = result.get("answer", "")

    # If AI says no SQL needed
    if not sql or sql.lower() in ("null", "none"):
        return "", answer or explanation

    return sql.strip(), explanation


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — SQL VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def validate_sql(sql: str, snap: dict, selected_views: list[str]) -> list[str]:
    """
    Check the generated SQL for hallucinated table/view names and column names.
    Returns a list of problem strings (empty = all good).
    """
    problems = []
    objects = snap.get("objects", {})
    objects_lower = {k.lower(): k for k in objects}

    # Extract table/view references: FROM x, JOIN x, WITH (NOLOCK) context
    # Handles: FROM [dbo].[ViewName], FROM dbo.ViewName, FROM ViewName
    table_pattern = re.compile(
        r'(?:FROM|JOIN)\s+(\[?\w+\]?\.\[?\w+\]?|\[?\w+\]?)',
        re.IGNORECASE
    )
    ref_tables = []
    for m in table_pattern.finditer(sql):
        raw = m.group(1).replace("[", "").replace("]", "")
        ref_tables.append(raw)

    for ref in ref_tables:
        # Skip common SQL keywords/functions that may match
        if ref.upper() in ("WITH", "NOLOCK", "SELECT", "WHERE", "AND", "OR", "ON"):
            continue
        if ref in objects:
            continue
        if ref.lower() in objects_lower:
            continue
        # Try with dbo. prefix
        if "dbo." + ref in objects or "dbo." + ref.lower() in objects_lower:
            continue
        problems.append(f"Unknown table/view '{ref}' — not found in schema.")

    # Extract column references in brackets: [ColumnName]
    col_pattern = re.compile(r'\[(\w+)\]')
    ref_cols = [m.group(1) for m in col_pattern.finditer(sql)]

    # Build set of all valid column names across selected views
    valid_cols: set[str] = set()
    for view_name in selected_views:
        obj = objects.get(view_name)
        if obj:
            for c in _col_names(obj["columns"]):
                valid_cols.add(c.lower())

    # Also include all columns across all objects (for joined queries)
    all_cols: set[str] = set()
    for obj in objects.values():
        for c in _col_names(obj["columns"]):
            all_cols.add(c.lower())

    for col in ref_cols:
        # Skip things that look like aliases or numbers
        if col.isdigit():
            continue
        if col.lower() not in all_cols:
            problems.append(
                f"Unknown column '[{col}]' — not found in any view in the schema."
            )

    return problems


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5 — EXPLAIN RESULTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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


def explain_results(
    question: str,
    sql: str,
    rows: list[dict],
    row_count: int,
    truncated: bool,
    provider: str,
) -> str:
    """Step 5: Ask AI to explain the query results."""
    results_json = json.dumps(rows, indent=2, default=str)
    truncation_note = f" (showing first {MAX_RESULT_ROWS} of {row_count}+)" if truncated else ""

    content = (
        f"Original question: {question}\n\n"
        f"SQL that was run:\n{sql}\n\n"
        f"Results ({row_count} rows{truncation_note}):\n{results_json}\n\n"
        "Explain the results in plain business English."
    )

    _print_status("Step 3/3 — Interpreting results…")
    raw = call_ai([{"role": "user", "content": content}], EXPLAIN_SYSTEM, provider)
    result = parse_json_response(raw)
    return result.get("answer") or raw


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def ask(question: str, provider: str, snap: dict) -> str:
    """
    Full 3-step AI pipeline:
      1. Select relevant views          (AI sees compact schema)
      2. Generate SQL                   (AI sees only selected views' full columns)
      3. Validate SQL                   (no DB hit — pure schema check)
      4. Execute SQL
      5. Explain results                (AI sees actual data rows)
    """
    # ── Step 1: View selection ───────────────────────────────────────────────
    selected_views = select_views(question, snap, provider)

    # ── Step 2: SQL generation ───────────────────────────────────────────────
    focused = focused_schema_for_sql(snap, selected_views)
    sql, explanation = generate_sql(question, focused, provider)

    # No SQL needed (conversational question)
    if not sql:
        return explanation

    _print_sql(sql, explanation)

    # Safety gate
    first_word = sql.strip().split()[0].upper()
    if first_word not in ("SELECT", "WITH"):
        return f"⚠️  AI generated a non-SELECT statement — blocked for safety.\nSQL: {sql}"

    # ── Step 3: Validate SQL ─────────────────────────────────────────────────
    problems = validate_sql(sql, snap, selected_views)
    if problems:
        problem_str = "; ".join(problems)
        _print_warn(f"SQL validation issues: {problem_str}")
        _print_status("Asking AI to fix SQL…")
        sql, explanation = generate_sql(question, focused, provider, prior_error=problem_str)
        if not sql:
            return explanation
        _print_sql(sql, f"(fixed) {explanation}")
        # Validate again — if still broken, proceed anyway and let DB error catch it
        problems2 = validate_sql(sql, snap, selected_views)
        if problems2:
            _print_warn(f"SQL still has issues after retry: {'; '.join(problems2)}")

    # ── Step 4: Execute SQL ──────────────────────────────────────────────────
    _print_status("Running query on database…")
    try:
        rows = run_query(sql)
        row_count = len(rows)
        truncated = row_count >= MAX_RESULT_ROWS
        _print_status(f"Got {row_count} rows{' (truncated)' if truncated else ''}.")
    except RuntimeError as exc:
        # Send error back to AI for one more fix attempt
        _print_warn(f"SQL execution error: {exc}")
        _print_status("Asking AI to fix the SQL error…")
        sql2, explanation2 = generate_sql(question, focused, provider, prior_error=str(exc))
        if not sql2:
            return explanation2 or str(exc)
        _print_sql(sql2, f"(error fix) {explanation2}")
        try:
            rows = run_query(sql2)
            row_count = len(rows)
            truncated = row_count >= MAX_RESULT_ROWS
            sql = sql2
        except RuntimeError as exc2:
            return f"❌ Query failed even after AI retry:\n{exc2}"

    # ── Step 5: Explain results ──────────────────────────────────────────────
    return explain_results(question, sql, rows, row_count, truncated, provider)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DISPLAY HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _print_status(msg: str) -> None:
    if RICH:
        console.print(f"[dim]▸ {msg}[/dim]")
    else:
        print(f"  ▸ {msg}")


def _print_warn(msg: str) -> None:
    if RICH:
        console.print(f"[yellow]⚠  {msg}[/yellow]")
    else:
        print(f"  ⚠  {msg}")


def _print_sql(sql: str, explanation: str) -> None:
    if RICH:
        if explanation:
            console.print(f"\n[bold cyan]Plan:[/bold cyan] {explanation}")
        console.print(Syntax(sql.strip(), "sql", theme="monokai", word_wrap=True))
    else:
        if explanation:
            print(f"\nPlan: {explanation}")
        print("SQL:\n" + textwrap.indent(sql.strip(), "  "))


def _print_answer(answer: str) -> None:
    if RICH:
        console.print(Panel(Markdown(answer), title="[bold green]Answer[/bold green]", border_style="green"))
    else:
        print("\n" + "=" * 60)
        print(answer)
        print("=" * 60)


def _die(msg: str) -> None:
    if RICH:
        console.print(f"[bold red]ERROR:[/bold red] {msg}")
    else:
        print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BANNER = """
╔═══════════════════════════════════════════════╗
║      ERP Database Q&A  (powered by AI)        ║
║  Type your question, or 'exit' / 'schema'     ║
╚═══════════════════════════════════════════════╝
"""

EXAMPLE_QUESTIONS = [
    "What is the total revenue for this month?",
    "Which branch had the highest sales today?",
    "Top 10 products by revenue this month",
    "Show me daily revenue trend for the last 30 days",
    "Which salesperson sold the most this quarter?",
    "How many unique customers did we have this month?",
    "Revenue breakdown by category for this year",
    "Compare this month's revenue to last year same period",
    "Which supplier has the most stock currently?",
    "Top 5 categories by purchase quantity this month",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ask natural-language questions about your ERP database.",
    )
    parser.add_argument("question", nargs="?", help="Question to ask (omit for interactive mode)")
    parser.add_argument("--ai", choices=["claude", "gpt"], default=DEFAULT_AI,
                        help=f"AI provider (default: {DEFAULT_AI})")
    parser.add_argument("--schema-only", action="store_true",
                        help="Print full schema and exit")
    parser.add_argument("--refresh-schema", action="store_true",
                        help="Re-snapshot schema from DB via schema_cache.py and exit")
    parser.add_argument("--examples", action="store_true",
                        help="Print example questions and exit")
    args = parser.parse_args()

    if args.examples:
        print("\nExample questions:\n")
        for i, q in enumerate(EXAMPLE_QUESTIONS, 1):
            print(f"  {i}. {q}")
        print()
        return

    if args.refresh_schema:
        import subprocess
        cache_script = os.path.join(os.path.dirname(__file__), "schema_cache.py")
        subprocess.run([sys.executable, cache_script], check=False)
        return

    # Load schema snapshot
    try:
        snap = load_snapshot()
    except SystemExit:
        raise
    except Exception as exc:
        _die(f"Failed to load schema: {exc}")

    if args.schema_only:
        if RICH:
            from rich.panel import Panel
            console.print(Panel(render_full_schema(snap), title="[bold blue]Database Schema[/bold blue]",
                                border_style="blue"))
        else:
            print(render_full_schema(snap))
        return

    provider = args.ai

    # ── Single question mode ─────────────────────────────────────────────────
    if args.question:
        print()
        try:
            answer = ask(args.question, provider, snap)
            _print_answer(answer)
        except KeyboardInterrupt:
            print("\nAborted.")
        return

    # ── Interactive REPL mode ────────────────────────────────────────────────
    if RICH:
        console.print(f"[bold magenta]{BANNER}[/bold magenta]")
        console.print(
            f"[dim]AI: [bold]{provider.upper()}[/bold]  |  DB: [bold]{DB_NAME}[/bold]  |  "
            f"Type [bold]examples[/bold] to see sample questions[/dim]\n"
        )
    else:
        print(BANNER)
        print(f"AI: {provider.upper()}  |  DB: {DB_NAME}\n")

    history: list[tuple[str, str]] = []

    while True:
        try:
            question = (console.input("[bold yellow]You:[/bold yellow] ") if RICH else input("You: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question:
            continue

        if question.lower() in ("exit", "quit", "q", "bye"):
            print("Goodbye!")
            break

        if question.lower() in ("schema", "show schema"):
            if RICH:
                console.print(Panel(render_full_schema(snap), title="[bold blue]Schema[/bold blue]",
                                    border_style="blue"))
            else:
                print(render_full_schema(snap))
            continue

        if question.lower() in ("examples", "help", "?"):
            print("\nExample questions:\n")
            for i, q in enumerate(EXAMPLE_QUESTIONS, 1):
                print(f"  {i}. {q}")
            print()
            continue

        if question.lower() == "history":
            if not history:
                print("  No questions asked yet.")
            else:
                for i, (q, a) in enumerate(history, 1):
                    print(f"\n  [{i}] Q: {q}")
                    print(f"       A: {a[:120]}{'…' if len(a) > 120 else ''}")
            print()
            continue

        print()
        try:
            answer = ask(question, provider, snap)
            _print_answer(answer)
            history.append((question, answer))
        except KeyboardInterrupt:
            print("\n  (interrupted)")
        except Exception as exc:
            _print_warn(f"Unexpected error: {exc}")
        print()


if __name__ == "__main__":
    main()
