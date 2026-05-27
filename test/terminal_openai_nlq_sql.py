#!/usr/bin/env python3
"""
Terminal NLQ → ChatGPT/OpenAI → SQL Server (read-only) → print results.

Enhanced NLP-to-SQL engine with:
  • Intent parsing    — detects metrics, time period, dimensions, filters before hitting OpenAI
  • Semantic layer    — maps "revenue / MTD / branch" to exact T-SQL patterns injected into prompt
  • Conversational memory — follow-up questions like "only Chennai" remember prior context
  • Audit log         — every Q/SQL/result/timing saved to test/nlq_audit.jsonl
  • Colored REPL      — syntax highlighting, query history (↑/↓), per-query timing
  • Query planner     — intent-augmented prompt reduces wrong-view and wrong-date errors

You type a plain-English question in the terminal. The script:
  1) Parses intent (metrics, time period, dimensions) from your question.
  2) Merges conversational context (follow-ups like "same but only men's wear" work).
  3) Sends enriched payload + ERP schema to OpenAI → receives T-SQL SELECT.
  4) Validates SQL (read-only; blocks writes / DDL / RPC).
  5) Runs against SQL Server using DB_* credentials from backend/.env.
  6) Prints SQL, explanation, assumptions, results as aligned table + records audit entry.

Environment (set in backend/.env):
  OPENAI_API_KEY              — required
  OPENAI_MODEL                — default gpt-4o-mini
  DB_SERVER / DB_NAME / DB_USER / DB_PASSWORD  (or ERP_DB_* aliases)
  ODBC_DRIVER                 — optional
  LIST_TX_SCHEMA_FILE         — optional override path to schema text
  LIST_TX_SCHEMA_MAX_CHARS    — truncate schema for token limits (default 100000)
  OPENAI_SQL_TEMPERATURE      — optional; omit for model default
  OPENAI_SQL_RESPONSE_JSON    — set 0 to omit response_format=json_object
  OPENAI_SQL_RULES_FILE       — extra rules + few-shot examples appended to prompt
  OPENAI_SQL_PRIORITIZE_SCHEMA — reorder schema on truncation (default 1)
  OPENAI_SQL_AUTOFIX          — repair bad SQL with DB error context (default 1)
  OPENAI_SQL_MAX_ATTEMPTS     — max tries per question (default 2, max 5)
  OPENAI_SQL_WARN_LITERAL_DATES — warn about hard-coded dates (default 1)
  OPENAI_SQL_MAX_ROWS_PRINT   — max rows to display (default 200)
  OPENAI_BASE_URL             — optional Azure / compatible base URL
  NLQ_AUDIT_FILE              — audit log path (default test/nlq_audit.jsonl)
  NLQ_MEMORY_TURNS            — conversational memory depth (default 5)
  NLQ_NO_COLOR                — set 1 to disable ANSI colors
  NLQ_SEMANTIC_FILE           — semantic map JSON (default test/erp_semantic_layer.json)
  NLQ_FAQ_TEMPLATES           — set 0 to disable curated FAQ SQL (default 1 = on)

FAQ templates (no OpenAI): nlq_faq_sql + kpi + compare + product + branch modules. NLQ_FAQ_TEMPLATES=0 disables.

Usage:
  python test/terminal_openai_nlq_sql.py -i
  python test/terminal_openai_nlq_sql.py "Top 10 categories by revenue this month"
  python test/terminal_openai_nlq_sql.py --dry-run "How many branches?"
  python test/terminal_openai_nlq_sql.py --history
  python test/terminal_openai_nlq_sql.py --intent "Revenue by branch today"

REPL commands (interactive mode -i):
  history          show recent questions + timing
  clear            clear conversation memory
  export FILE.csv  export last result to CSV
  explain          show full SQL for last query
  intent QUESTION  parse and show intent without calling OpenAI
  quit / exit      leave

  pip install openai pyodbc python-dotenv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import textwrap
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── readline / history (optional — gives arrow-key history in REPL) ────────────
try:
    import readline as _readline  # noqa: F401
    _HAS_READLINE = True
except ImportError:
    _HAS_READLINE = False

_TESTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TESTS_DIR.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
DEFAULT_SCHEMA_PATH = _BACKEND_ROOT / "schema_catalog.txt"
DEFAULT_SEMANTIC_PATH = _TESTS_DIR / "erp_semantic_layer.json"
DEFAULT_AUDIT_PATH = _TESTS_DIR / "nlq_audit.jsonl"

# Curated FAQ SQL (template-first path)
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from nlq_faq_sql import (  # noqa: E402
    list_branch_compare_ai_queries,
    list_compare_ai_queries,
    list_customer_compare_ai_queries,
    list_conversational_compare_ai_queries,
    list_executive_compare_ai_queries,
    list_faq_ids,
    list_frequent_ai_queries,
    list_inventory_compare_ai_queries,
    list_product_compare_ai_queries,
    list_supplier_compare_ai_queries,
    try_faq_template,
)


def _faq_templates_enabled() -> bool:
    return os.getenv("NLQ_FAQ_TEMPLATES", "1").strip().lower() not in ("0", "false", "no")


# ─── ANSI Color Helpers ────────────────────────────────────────────────────────

class _C:
    """ANSI terminal colors — automatically disabled when not a TTY or NLQ_NO_COLOR=1."""
    _on: bool = (
        sys.stdout.isatty()
        and os.getenv("NLQ_NO_COLOR", "0").strip() not in ("1", "true", "yes")
    )

    RST   = "\033[0m"   if _on else ""
    BOLD  = "\033[1m"   if _on else ""
    DIM   = "\033[2m"   if _on else ""
    CYAN  = "\033[96m"  if _on else ""
    GREEN = "\033[92m"  if _on else ""
    YLW   = "\033[93m"  if _on else ""
    RED   = "\033[91m"  if _on else ""
    BLUE  = "\033[94m"  if _on else ""
    MAG   = "\033[95m"  if _on else ""
    GRAY  = "\033[90m"  if _on else ""
    WHITE = "\033[97m"  if _on else ""

    @classmethod
    def disable(cls) -> None:
        for a in ("RST", "BOLD", "DIM", "CYAN", "GREEN", "YLW", "RED", "BLUE", "MAG", "GRAY", "WHITE"):
            setattr(cls, a, "")


def _c(color: str, text: str) -> str:
    return f"{color}{text}{_C.RST}" if color else text


# ─── .env Loader ──────────────────────────────────────────────────────────────

def _load_dotenv_files() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("pip install python-dotenv", file=sys.stderr)
        sys.exit(1)
    for p in (_BACKEND_ROOT / ".env", _PROJECT_ROOT / ".env"):
        if p.is_file():
            load_dotenv(p, override=False)


def _truncate(text: str, max_chars: int) -> Tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[: max_chars - 200] + "\n\n...[truncated]...\n", True


# ─── Schema Loader ────────────────────────────────────────────────────────────

_SCHEMA_BLOCK_SPLIT = re.compile(r"\n={70,}\n")
_SCHEMA_VIEW_PRIORITY: Tuple[str, ...] = (
    "VW_MB_POWERBI_SLSXNS_REPORT",
    "VW_MB_POWERBI_APP_REPORT",
    "VW_MB_POWERBI_SLS_REPORT",
    "VW_MB_POWERBI_SLS_ARTICLE",
    "VW_MB_POWERBI_STOCK_REPORT",
    "VW_MB_POWERBI_PURXNS_REPORT",
    "VW_MB_POWERBI_PUR_REPORT",
    "VW_MB_POWERBI_PRODUCT_MASTER",
    "VwAISalesData",
    "VwAIBranch",
    "VwAICustomerDetails",
    "VwAIStockData",
)


def _section_sort_rank(section: str) -> Tuple[int, int]:
    head = section[:650].upper()
    for rank, needle in enumerate(_SCHEMA_VIEW_PRIORITY):
        if needle.upper() in head:
            return (rank, 0)
    return (999, 0)


def _prioritize_schema_catalog(raw: str, max_chars: int) -> Tuple[str, bool]:
    """Move high-traffic analytic views toward the front so truncation keeps them."""
    if len(raw) <= max_chars:
        return raw, False

    prio_on = os.getenv("OPENAI_SQL_PRIORITIZE_SCHEMA", "1").strip().lower() not in ("0", "false", "no")
    if not prio_on:
        return _truncate(raw, max_chars)

    parts = _SCHEMA_BLOCK_SPLIT.split(raw)
    if len(parts) < 2:
        return _truncate(raw, max_chars)

    header = parts[0]
    sections = parts[1:]
    sep = "\n========================================================================\n"
    idx_order = sorted(range(len(sections)), key=lambda i: (_section_sort_rank(sections[i]), i))
    merged = header + sep + sep.join(sections[i] for i in idx_order)
    print("(schema catalog reordered: prioritized views listed first)", file=sys.stderr)

    if len(merged) <= max_chars:
        return merged, False
    text, truncated = _truncate(merged, max_chars)
    if truncated:
        print(f"(schema truncated after reorder to ~{max_chars} chars)", file=sys.stderr)
    return text, truncated


def _load_schema_catalog() -> str:
    path = Path(os.getenv("LIST_TX_SCHEMA_FILE") or str(DEFAULT_SCHEMA_PATH))
    max_c = int(os.getenv("LIST_TX_SCHEMA_MAX_CHARS", "100000"))
    if not path.is_file():
        return (
            "Schema catalog file not found. Set LIST_TX_SCHEMA_FILE or add "
            f"backend/schema_catalog.txt.\nFallback: use dbo.VW_MB_POWERBI_APP_REPORT, "
            "dbo.VW_MB_POWERBI_SLS_REPORT, dbo.VW_MB_POWERBI_SLSXNS_REPORT for analytics."
        )
    raw = path.read_text(encoding="utf-8", errors="replace")
    text, was_cut = _prioritize_schema_catalog(raw, max_c)
    if was_cut:
        print("(schema excerpt shortened for model context — see OPENAI_SQL_PRIORITIZE_SCHEMA)", file=sys.stderr)
    return text


def _load_optional_sql_rules() -> str:
    """Extra system-prompt text: your org rules + few-shot Q→SQL (OPENAI_SQL_RULES_FILE)."""
    p = (os.getenv("OPENAI_SQL_RULES_FILE") or "").strip()
    if not p:
        return ""
    path = Path(p)
    if not path.is_file():
        print(f"Warning: OPENAI_SQL_RULES_FILE not found: {path}", file=sys.stderr)
        return ""
    try:
        return "\n\n--- User / org rules & examples (from file) ---\n" + path.read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError as exc:
        print(f"Warning: could not read OPENAI_SQL_RULES_FILE: {exc}", file=sys.stderr)
        return ""


# ─── Semantic layer (loaded from test/erp_semantic_layer.json) ─────────────────

_SEMANTIC_CACHE: Optional[Dict[str, Any]] = None


def _semantic_fallback() -> Dict[str, Any]:
    """Minimal inline fallback if JSON file is missing."""
    return {
        "metrics": {
            "revenue": {"agg": "SUM", "col": "[NetSlsNetAmount]", "view": "dbo.VW_MB_POWERBI_SLSXNS_REPORT"},
        },
        "time_periods": {
            "mtd": "[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND [XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))",
        },
        "dimensions": {"branch": {"col": "[BranchAlias]"}},
        "guardrails": [],
        "few_shot": [],
    }


def load_semantic_layer() -> Dict[str, Any]:
    """Load business-term -> SQL mapping from NLQ_SEMANTIC_FILE (JSON)."""
    global _SEMANTIC_CACHE
    if _SEMANTIC_CACHE is not None:
        return _SEMANTIC_CACHE

    path = Path(os.getenv("NLQ_SEMANTIC_FILE") or str(DEFAULT_SEMANTIC_PATH))
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            _SEMANTIC_CACHE = raw
            if os.getenv("NLQ_SEMANTIC_VERBOSE", "").strip().lower() in ("1", "true", "yes"):
                print(f"(semantic layer: {path.name})", file=sys.stderr)
            return raw
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Warning: could not load {path}: {exc}", file=sys.stderr)

    print(f"Warning: using minimal semantic fallback; add {DEFAULT_SEMANTIC_PATH.name}", file=sys.stderr)
    _SEMANTIC_CACHE = _semantic_fallback()
    return _SEMANTIC_CACHE


def _metric_expr(info: Dict[str, Any]) -> str:
    agg = (info.get("agg") or "SUM").upper()
    col = info.get("col") or ""
    if col.upper().startswith("DISTINCT "):
        return f"COUNT({col})"
    return f"{agg}({col})"


def _dimension_col(dim_info: Any) -> Optional[str]:
    if isinstance(dim_info, str):
        return dim_info
    if isinstance(dim_info, dict):
        return dim_info.get("col") or dim_info.get("display_col")
    return None


def _format_semantic_hint(intent: "QueryIntent") -> str:
    """Build hints from erp_semantic_layer.json for the current intent."""
    layer = load_semantic_layer()
    metrics = layer.get("metrics") or {}
    periods = layer.get("time_periods") or {}
    dimensions = layer.get("dimensions") or {}

    lines: List[str] = []
    if intent.metrics:
        for m in intent.metrics:
            info = metrics.get(m)
            if info and isinstance(info, dict):
                view = info.get("view", "").replace("dbo.", "")
                lines.append(f"  Metric '{m}' -> {_metric_expr(info)} from {view}")
    if intent.time_period:
        expr = periods.get(intent.time_period)
        if expr:
            lines.append(f"  Period '{intent.time_period}' -> WHERE {expr}")
    if intent.dimensions:
        for d in intent.dimensions:
            dim_info = dimensions.get(d)
            col = _dimension_col(dim_info)
            if col:
                extra = ""
                if isinstance(dim_info, dict) and dim_info.get("display_col"):
                    extra = f" (display: {dim_info['display_col']})"
                lines.append(f"  Dimension '{d}' -> GROUP BY / SELECT {col}{extra}")
            elif isinstance(dim_info, dict) and dim_info.get("note"):
                lines.append(f"  Dimension '{d}' -> NOTE: {dim_info['note']}")
    if intent.filters:
        for dim, val in intent.filters.items():
            col = _dimension_col(dimensions.get(dim))
            if col:
                lines.append(f"  Filter '{dim}={val}' -> WHERE {col} LIKE '%{val}%'")

    if not lines:
        return ""
    title = layer.get("title") or "erp_semantic_layer.json"
    return f"\n\n## Pre-resolved semantic hints ({title} - use exactly):\n" + "\n".join(lines)


def _format_view_catalog_line(key: str, v: Dict[str, Any]) -> str:
    """One-line view summary for the NLQ system prompt."""
    fqn = v.get("fqn") or key
    purpose = v.get("purpose") or ""
    bits: List[str] = []
    if v.get("date_col"):
        bits.append(f"date={v['date_col']}")
    if v.get("amount_col"):
        bits.append(f"amt={v['amount_col']}")
    if v.get("qty_col"):
        bits.append(f"qty={v['qty_col']}")
    if v.get("bill_col"):
        bits.append(f"bills={v['bill_col']}")
    suffix = f" [{', '.join(bits)}]" if bits else ""
    note = v.get("note")
    note_s = f" NOTE: {note}" if note else ""
    return f"- {key}: {fqn} — {purpose}{suffix}{note_s}"


def _semantic_context_block() -> str:
    """Guardrails + few-shot examples + full view index from semantic JSON."""
    layer = load_semantic_layer()
    parts: List[str] = []
    meta = layer.get("catalog_meta") or {}
    if meta:
        parts.append(
            f"\n## Schema coverage: {meta.get('view_count', '?')} views, "
            f"~{meta.get('approx_column_count', '?')} columns in {meta.get('full_column_inventory', 'schema_catalog.txt')}. "
            f"{meta.get('note', '')}"
        )
    guards = layer.get("guardrails") or []
    if guards:
        parts.append("\n## Semantic guardrails:\n")
        parts.extend(f"- {g}" for g in guards)
    shots = layer.get("few_shot") or []
    if shots:
        parts.append("\n## Approved query patterns:\n")
        parts.extend(f"- {s}" for s in shots)
    views = layer.get("views") or {}
    if views:
        n = len(views)
        parts.append(f"\n## View catalog ({n} views — pick by purpose; KPI columns only):\n")
        sorted_views = sorted(
            views.items(),
            key=lambda kv: (
                kv[1].get("catalog_no", 999) if isinstance(kv[1], dict) else 999,
                kv[0],
            ),
        )
        for key, v in sorted_views:
            if isinstance(v, dict):
                parts.append(_format_view_catalog_line(key, v))
    return "\n".join(parts)


# ─── Intent Parser ─────────────────────────────────────────────────────────────

@dataclass
class QueryIntent:
    """Structured intent extracted from a natural language question."""
    intent_type: str = "general"
    # intent_type values:
    #   revenue_query | count_query | trend_query | ranking_query
    #   breakdown_query | comparison_query | general
    time_period: Optional[str] = None
    # time_period values: today | yesterday | this_week | mtd | qtd | ytd
    #                     last_7d | last_30d | last_6m
    metrics: List[str] = field(default_factory=list)
    dimensions: List[str] = field(default_factory=list)
    filters: Dict[str, str] = field(default_factory=dict)
    limit: int = 10
    sort_desc: bool = True
    is_comparison: bool = False
    raw_question: str = ""

    def summary(self) -> str:
        parts: List[str] = [f"[{self.intent_type}]"]
        if self.time_period:
            parts.append(f"period={self.time_period}")
        if self.metrics:
            parts.append(f"metrics={','.join(self.metrics)}")
        if self.dimensions:
            parts.append(f"by={','.join(self.dimensions)}")
        if self.filters:
            parts.append(f"filters={self.filters}")
        return " ".join(parts)


def _extract_intent(question: str) -> QueryIntent:
    """
    Lightweight regex/keyword intent parser — runs locally before the OpenAI call.
    Populates QueryIntent so the prompt is pre-grounded with the right views/columns.
    """
    q = question.lower()
    intent = QueryIntent(raw_question=question)

    # ── Time period ────────────────────────────────────────────────────────────
    _tp_patterns: List[Tuple[str, str]] = [
        (r"\b(today|this day)\b",                                      "today"),
        (r"\b(yesterday)\b",                                            "yesterday"),
        (r"\b(this week|current week)\b",                               "this_week"),
        (r"\b(mtd|month.?to.?date|this month|current month)\b",        "mtd"),
        (r"\b(qtd|quarter.?to.?date|this quarter|current quarter)\b",  "qtd"),
        (r"\b(ytd|year.?to.?date|this year|current year)\b",           "ytd"),
        (r"\b(last\s+7\s+days?|past\s+7\s+days?)\b",                   "last_7d"),
        (r"\b(last\s+30\s+days?|past\s+30\s+days?)\b",                 "last_30d"),
        (r"\b(last\s+month|previous\s+month|prior\s+month)\b",          "last_month"),
        (r"\b(last\s+quarter|previous\s+quarter|prior\s+quarter|last\s+q\d?)\b", "last_quarter"),
        (r"\b(last\s+[2-5]\s+months?|past\s+[2-5]\s+months?)\b",       "last_few_months"),
        (r"\b(last\s+6\s+months?|past\s+6\s+months?)\b",               "last_6m"),
        (r"\b(last\s+12\s+months?|past\s+12\s+months?|last\s+year)\b", "last_12m"),
        (r"\b(last\s+24\s+months?|past\s+24\s+months?|last\s+2\s+years?)\b", "last_24m"),
        (r"\b(all\s+time|all\s+history|entire\s+history|since\s+beginning)\b", "all_time"),
    ]
    for pat, period in _tp_patterns:
        if re.search(pat, q):
            intent.time_period = period
            break

    # ── Metrics ────────────────────────────────────────────────────────────────
    _metric_patterns: List[Tuple[str, str]] = [
        (r"\b(revenue|net sales?|net sale|sales amount|turnover)\b",   "revenue"),
        (r"\b(transactions?|bills?|invoices?|memos?|cashmemos?)\b",    "transactions"),
        (r"\b(units?|qty|quantity|pieces?|items? sold)\b",              "units"),
        (r"\b(customers?|buyers?|unique customers?)\b",                 "customers"),
        (r"\b(gross sales?)\b",                                         "gross sales"),
        (r"\b(margin|profit|gross margin)\b",                           "margin"),
        (r"\b(stock|inventory|on.?hand)\b",                             "stock"),
        (r"\b(purchases?|procurement|purchase amount)\b",               "purchases"),
    ]
    for pat, metric in _metric_patterns:
        if re.search(pat, q):
            if metric not in intent.metrics:
                intent.metrics.append(metric)
    if not intent.metrics:
        # Default: revenue when no metric is specified
        intent.metrics = ["revenue"]

    # ── Dimensions ─────────────────────────────────────────────────────────────
    _dim_patterns: List[Tuple[str, str]] = [
        (r"\b(branch(?:es)?|store[s]?|outlet[s]?|location[s]?)\b",     "branch"),
        (r"\b(categor(?:y|ies))\b",                                     "category"),
        (r"\b(department[s]?|dept[s]?|section[s]?)\b",                  "department"),
        (r"\b(sales\s*persons?|salesperson[s]?|staff|employee[s]?)\b",  "salesperson"),
        (r"\b(brand[s]?)\b",                                             "brand"),
        (r"\b(product[s]?|article[s]?|item[s]?|sku[s]?)\b",            "product"),
        (r"\b(customer[s]?|client[s]?|buyer[s]?)\b",                    "customer"),
        (r"\b(supplier[s]?|vendor[s]?)\b",                              "supplier"),
        (r"\bby\s+(day|daily|date)\b",                                   "day"),
        (r"\bby\s+(month|monthly)\b",                                    "month"),
        (r"\bby\s+(week|weekly)\b",                                      "week"),
    ]
    for pat, dim in _dim_patterns:
        if re.search(pat, q):
            if dim not in intent.dimensions:
                intent.dimensions.append(dim)

    # ── Intent type ────────────────────────────────────────────────────────────
    if re.search(r"\b(trend|over time|daily|weekly|monthly|chart|graph|progression)\b", q):
        intent.intent_type = "trend_query"
    elif re.search(r"\b(top|bottom|best|worst|highest|lowest|rank|ranking|leading|trailing)\b", q):
        intent.intent_type = "ranking_query"
    elif re.search(r"\b(break\s*down|breakdown|split|distribution)\b", q):
        intent.intent_type = "breakdown_query"
    elif re.search(r"\b(how many|count|total number|number of)\b", q):
        intent.intent_type = "count_query"
    elif re.search(r"\b(compare|vs\.?|versus|difference|change|growth|yoy|mom)\b", q):
        intent.intent_type = "comparison_query"
        intent.is_comparison = True
    elif re.search(r"\b(revenue|sales|amount|turnover)\b", q):
        intent.intent_type = "revenue_query"
    else:
        intent.intent_type = "general"

    # ── Ranking limit ──────────────────────────────────────────────────────────
    top_match = re.search(r"\btop\s+(\d+)\b", q)
    if top_match:
        intent.limit = int(top_match.group(1))
    elif intent.intent_type == "trend_query":
        intent.limit = 30  # trends: 30 data points
    elif intent.intent_type in ("ranking_query", "breakdown_query"):
        intent.limit = 10
    else:
        intent.limit = 500  # aggregate / count queries

    # ── Sort direction ─────────────────────────────────────────────────────────
    if re.search(r"\b(bottom|lowest|worst|least|smallest|minimum)\b", q):
        intent.sort_desc = False

    return intent


# ─── Query Policy Enforcement ─────────────────────────────────────────────────

@dataclass
class PolicyResult:
    """What the policy engine did to an intent."""
    period_defaulted: bool = False       # True if MTD was auto-applied
    period_defaulted_to: str = ""        # which period was applied
    history_capped: bool = False         # True if max_history was added
    history_cap_months: int = 0
    heavy_query_warned: bool = False     # True if a slow-query warning was shown
    blocked: bool = False                # True if the query is blocked entirely
    block_reason: str = ""

    def notices(self) -> List[str]:
        out: List[str] = []
        if self.period_defaulted:
            out.append(f"No time period detected → defaulting to {self.period_defaulted_to.upper()}. Add a period ('today', 'MTD', 'last 30 days') to override, or use --no-policy.")
        if self.history_capped:
            out.append(f"History capped at {self.history_cap_months} months to avoid full-table scan.")
        if self.heavy_query_warned:
            out.append("Heavy query detected — this may take a while or time out.")
        return out


# Sales-metric names that should always carry a date filter
_SALES_METRICS = {"revenue", "sales", "net sales", "transactions", "bills", "units", "quantity", "customers", "gross sales"}


def _apply_query_policies(intent: QueryIntent, *, apply: bool = True) -> PolicyResult:
    """
    Enforce query_policies from erp_semantic_layer.json:
      1. No time period + sales metric  → default to default_period_sales (MTD)
      2. Trend / history               → cap at max_history_months
      3. Heavy patterns in question    → warn (do not block)
      4. Blocked dimensions (hour)     → block and explain
    Modifies intent in-place; returns a PolicyResult with what changed.
    """
    result = PolicyResult()
    if not apply:
        return result

    layer    = load_semantic_layer()
    policies = layer.get("query_policies") or {}
    if not policies:
        return result

    q_lower = intent.raw_question.lower()

    # ── 1. Block unsupported dimensions (e.g. hourly) ──────────────────────────
    blocked_dims: List[str] = policies.get("blocked_dimensions") or []
    for d in blocked_dims:
        if d in intent.dimensions or re.search(rf"\b{re.escape(d)}\b", q_lower):
            result.blocked = True
            result.block_reason = policies.get("blocked_dimensions_message") or f"Dimension '{d}' is not supported."
            return result

    # ── 2. Default time period for sales metrics ───────────────────────────────
    # Check for heavy/broad patterns before deciding on MTD default
    # (if user explicitly asks "all time" or "forecast", don't silently override with MTD)
    heavy_patterns_check: List[str] = policies.get("heavy_query_patterns") or []
    explicit_broad = any(re.search(rf"\b{re.escape(p.lower())}\b", q_lower) for p in heavy_patterns_check)

    sales_hit = any(m in _SALES_METRICS for m in intent.metrics)
    if (
        intent.time_period is None
        and sales_hit
        and not explicit_broad
        and intent.intent_type not in ("comparison_query",)
    ):
        default_p = (policies.get("default_period_sales") or "mtd").strip()
        intent.time_period = default_p
        result.period_defaulted = True
        result.period_defaulted_to = default_p

    # ── 3. Cap history for trend / open-ended history queries ─────────────────
    max_months: int = int(policies.get("max_history_months") or 24)
    # Periods that span multiple months and may scan large amounts of line-level data
    _MULTI_MONTH_PERIODS = {"last_few_months", "last_6m", "last_12m", "last_24m", "all_time"}
    is_open_history = (
        intent.intent_type == "trend_query"
        or intent.time_period in _MULTI_MONTH_PERIODS
        or re.search(r"\b(since|from|all time|all history|entire|every month|every year)\b", q_lower)
    )
    if is_open_history and max_months > 0:
        result.history_capped = True
        result.history_cap_months = max_months

    # ── 4. Warn on heavy patterns ──────────────────────────────────────────────
    heavy_patterns: List[str] = policies.get("heavy_query_patterns") or []
    for pat in heavy_patterns:
        if re.search(rf"\b{re.escape(pat.lower())}\b", q_lower):
            result.heavy_query_warned = True
            break

    return result


def _policy_prompt_injection(policy: PolicyResult) -> str:
    """Extra text injected into the system prompt when policies fire."""
    if not policy.history_capped and not policy.period_defaulted:
        return ""
    parts: List[str] = ["\n\n## Query policy constraints (enforced — follow these exactly):"]
    if policy.period_defaulted:
        parts.append(
            f"- No time period was stated by the user. Policy defaulted to "
            f"{policy.period_defaulted_to.upper()}. Apply that period in the WHERE clause."
        )
    if policy.history_capped:
        n = policy.history_cap_months
        parts.append(
            f"- History cap: do NOT scan more than {n} months of data on line-level sales views. "
            f"Use DATEADD(MONTH, -{n}, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) as the earliest start date."
        )
    return "\n".join(parts)


# ─── Conversational Memory ─────────────────────────────────────────────────────

@dataclass
class _Turn:
    question: str
    sql: str
    result_count: int
    elapsed_ms: float
    timestamp: str


class ConversationMemory:
    """
    Rolling short-term memory of recent Q→SQL turns.
    Enables follow-up questions:
      "same but only Chennai" — filters previous result
      "show last month instead" — replaces time period
      "also show units" — adds metric
    """

    _FOLLOW_UP_RE = re.compile(
        r"\b(same|but|only|instead|also|what about|how about|for|filter|"
        r"except|excluding|add|remove|change|show|limit|narrow|just)\b",
        re.IGNORECASE,
    )

    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns = max_turns
        self._turns: List[_Turn] = []

    def add(self, question: str, sql: str, result_count: int, elapsed_ms: float) -> None:
        t = _Turn(
            question=question,
            sql=sql,
            result_count=result_count,
            elapsed_ms=elapsed_ms,
            timestamp=datetime.utcnow().isoformat(),
        )
        self._turns.append(t)
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns :]

    def is_follow_up(self, question: str) -> bool:
        """Heuristic: short question, or contains follow-up signal words."""
        q = question.strip()
        word_count = len(q.split())
        has_signal = bool(self._FOLLOW_UP_RE.search(q))
        lacks_main_verb = not re.search(
            r"\b(show|give|list|what|how|which|get|find|tell|calculate|count|compare|display)\b",
            q, re.IGNORECASE,
        )
        convo_compare = bool(
            re.search(
                r"^compare\s+(only|top\s+\d+|excluding|this|supplier|trend|before|by\s+quantity)",
                q,
                re.I,
            )
        )
        return bool(self._turns) and (
            word_count <= 6 or (has_signal and lacks_main_verb) or (convo_compare and word_count <= 10)
        )

    def resolve_question(self, question: str) -> str:
        """
        Prepend previous context when question looks like a follow-up.
        This lets OpenAI understand "only Chennai" in context of the last query.
        """
        if not self._turns or not self.is_follow_up(question):
            return question
        last = self._turns[-1]
        return (
            f"[Follow-up to previous question: '{last.question}']\n"
            f"[Previous SQL that was executed:]\n{last.sql}\n\n"
            f"New instruction (modify the above query accordingly): {question}"
        )

    def prompt_context(self) -> str:
        """Serialize last 3 turns for injection into the system prompt."""
        if not self._turns:
            return ""
        parts = ["\n\n## Recent conversation history (use for follow-up resolution):"]
        for i, t in enumerate(self._turns[-3:], 1):
            parts.append(
                f"  Turn {i}: Q=\"{t.question[:120]}\"\n"
                f"  SQL: {t.sql[:180]}{'...' if len(t.sql) > 180 else ''}\n"
                f"  → {t.result_count} row(s)"
            )
        return "\n".join(parts)

    def clear(self) -> None:
        self._turns.clear()

    def show(self) -> None:
        if not self._turns:
            print(_c(_C.GRAY, "  (no conversation history yet)"))
            return
        print(_c(_C.BOLD + _C.CYAN, f"\n{'─'*58}"))
        print(_c(_C.BOLD, "  Conversation History"))
        print(_c(_C.CYAN, f"{'─'*58}"))
        for i, t in enumerate(self._turns, 1):
            ts = t.timestamp[:19].replace("T", " ")
            print(f"  {_c(_C.YLW, str(i)+'.')} {_c(_C.WHITE, t.question)}")
            print(f"     {_c(_C.GRAY, f'{t.result_count} rows · {t.elapsed_ms:.0f}ms · {ts}')}")
            print(_c(_C.DIM, f"     SQL: {t.sql[:90]}{'...' if len(t.sql)>90 else ''}"))
            print()


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLog:
    """
    Appends every Q/SQL/result/timing record to a newline-delimited JSON file.
    Use --history flag to tail the log, or read nlq_audit.jsonl directly.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def record(
        self,
        question: str,
        intent: Optional[QueryIntent],
        sql: str,
        result_count: int,
        elapsed_ms: float,
        error: Optional[str] = None,
        model: str = "",
    ) -> None:
        entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "question": question,
            "intent_type": intent.intent_type if intent else None,
            "time_period": intent.time_period if intent else None,
            "metrics": intent.metrics if intent else [],
            "dimensions": intent.dimensions if intent else [],
            "model": model,
            "sql": sql,
            "result_count": result_count,
            "elapsed_ms": round(elapsed_ms, 1),
            "error": error,
        }
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # never crash on audit write failure

    def show_recent(self, n: int = 10) -> None:
        if not self.path.is_file():
            print(_c(_C.GRAY, "  (no audit log found)"))
            return
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        lines = lines[-n:]
        print(_c(_C.BOLD + _C.CYAN, f"\n{'─'*58}"))
        print(_c(_C.BOLD, f"  Audit Log  ({self.path.name})  — last {len(lines)} entries"))
        print(_c(_C.CYAN, f"{'─'*58}"))
        for raw in lines:
            try:
                e = json.loads(raw)
                ts   = e.get("timestamp", "")[:19].replace("T", " ")
                q    = e.get("question", "")[:68]
                rows = e.get("result_count", "?")
                ms   = e.get("elapsed_ms", 0)
                err  = e.get("error")
                itype = e.get("intent_type", "")
                status = _c(_C.RED, "✗") if err else _c(_C.GREEN, "✓")
                print(f"  {status} {_c(_C.GRAY, ts)}  {_c(_C.WHITE, q)}")
                if not err:
                    print(f"     {_c(_C.GRAY, f'{rows} rows · {ms:.0f}ms')}  {_c(_C.DIM, itype)}")
                else:
                    print(f"     {_c(_C.RED, str(err)[:80])}")
            except Exception:
                continue
        print()


# ─── pyodbc Connection ────────────────────────────────────────────────────────

try:
    import pyodbc
except ImportError:
    print("pip install pyodbc", file=sys.stderr)
    sys.exit(1)


def _mssql_connection_params() -> Tuple[str, int, str, str, str]:
    server   = (os.getenv("DB_SERVER")   or os.getenv("ERP_DB_HOST") or "").strip()
    port_s   = os.getenv("DB_PORT")      or os.getenv("ERP_DB_PORT") or "1433"
    try:
        port = int(port_s)
    except ValueError:
        port = 1433
    database = (os.getenv("DB_NAME")     or os.getenv("ERP_DB_NAME") or "").strip()
    user     = (os.getenv("DB_USER")     or os.getenv("ERP_DB_USER") or "").strip()
    password = os.getenv("DB_PASSWORD")  or os.getenv("ERP_DB_PASSWORD") or ""
    return server, port, database, user, password


def _connect_timeout() -> int:
    try:
        return int(os.getenv("DB_CONNECT_TIMEOUT_MS", "60000")) // 1000
    except ValueError:
        return 60


def _query_timeout_sec() -> int:
    try:
        return min(600, max(15, int(os.getenv("OPENAI_SQL_DB_QUERY_TIMEOUT_SEC", "180"))))
    except ValueError:
        return 180


def _installed_odbc_drivers() -> List[str]:
    try:
        return list(pyodbc.drivers())
    except Exception:
        return []


def _odbc_drivers_to_try(cfg_driver: str) -> List[str]:
    installed = _installed_odbc_drivers()
    candidates = [
        (cfg_driver or "").strip(),
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]
    ordered: List[str] = []
    for d in candidates:
        if d and d not in ordered and (not installed or d in installed):
            ordered.append(d)
    if not ordered:
        for d in installed:
            if "sql" in d.lower() and d not in ordered:
                ordered.append(d)
        if installed and not ordered:
            ordered = installed[:]
    return ordered


def _build_conn_str(driver: str, server: str, port: int, database: str, user: str, password: str) -> str:
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"Connect Timeout={_connect_timeout()};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no;"
    )


def connect_mssql() -> Tuple[Any, str]:
    server, port, database, user, password = _mssql_connection_params()
    cfg_driver = os.getenv("ODBC_DRIVER") or ""
    missing = [
        n for n, v in [("server", server), ("database", database), ("user", user), ("password", password)]
        if not v
    ]
    if missing:
        print(f"Missing DB env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(2)
    last_exc: BaseException | None = None
    for driver in _odbc_drivers_to_try(cfg_driver):
        try:
            conn = pyodbc.connect(
                _build_conn_str(driver, server, port, database, user, password),
                timeout=_connect_timeout(),
                autocommit=True,
            )
            conn.timeout = _query_timeout_sec()
            return conn, driver
        except Exception as exc:
            last_exc = exc
    print(f"Cannot connect to SQL Server. Last error: {last_exc}", file=sys.stderr)
    sys.exit(3)


# ─── SQL Safety Validator ─────────────────────────────────────────────────────

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|"
    r"WAITFOR|SHUTDOWN|BACKUP|RESTORE|OPENROWSET|OPENDATASOURCE|BULK|SP_|XP_)\b",
    re.IGNORECASE,
)


def _normalize_sql(candidate: str) -> str:
    s = candidate.strip()
    # strip fenced ```sql ```
    fence = re.search(r"```(?:sql)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()
    return s.strip().rstrip(";")


def validate_readonly_sql(sql: str) -> Tuple[bool, str]:
    s = _normalize_sql(sql)
    if not s:
        return False, "Empty SQL."

    stmts = [x.strip() for x in re.split(r";\s*", s) if x.strip()]
    if len(stmts) != 1:
        return False, "Exactly one SQL statement is required (no semicolon batches)."

    s = stmts[0]
    prefix = re.sub(r"^\(\s*", "", s, count=10).lstrip()
    up_ok = prefix.upper().startswith("SELECT") or prefix.upper().startswith("WITH")
    if not up_ok:
        return False, "Only SELECT or WITH (leading to SELECT) queries are allowed."

    if _FORBIDDEN.search(s):
        return False, "Forbidden keyword detected (writes / RPC / DDL not allowed)."

    if re.search(r"\bINTO\s+(#|[\[]?tmp)", s, re.IGNORECASE):
        return False, "SELECT INTO temporary tables is not allowed."

    return True, s


_LITERAL_DATE_IN_SQL = re.compile(
    r"'(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])'"
)


def _warn_literal_sql_dates(sql: str) -> None:
    if os.getenv("OPENAI_SQL_WARN_LITERAL_DATES", "1").strip().lower() in ("0", "false", "no"):
        return
    if _LITERAL_DATE_IN_SQL.search(sql):
        print(
            _c(_C.YLW,
               "Hint: SQL uses literal 'YYYY-MM-DD' dates — rolling periods should use GETDATE() "
               "expressions. Silence: OPENAI_SQL_WARN_LITERAL_DATES=0."),
            file=sys.stderr,
        )


# ─── Row Serialization & Display ──────────────────────────────────────────────

def _serialize_row(row: Any, colnames: List[str]) -> Dict[str, Any]:
    rec: Dict[str, Any] = {}
    for i, name in enumerate(colnames):
        v = row[i]
        if isinstance(v, Decimal):
            rec[name] = float(v)
        elif isinstance(v, datetime):
            rec[name] = v.isoformat()
        elif isinstance(v, date) and not isinstance(v, datetime):
            rec[name] = v.isoformat()
        elif isinstance(v, bytes):
            rec[name] = "<bytes>"
        else:
            rec[name] = v
    return rec


def _print_table(records: List[Dict[str, Any]], max_w: int) -> None:
    if not records:
        print(_c(_C.GRAY, "  (no rows)"))
        return
    cols = list(records[0].keys())

    def fmt(val: Any) -> str:
        if val is None:
            return ""
        s = str(val).replace("\n", " ")
        return s if len(s) <= max_w else s[: max_w - 1] + "…"

    str_rows = [[fmt(r[c]) for c in cols] for r in records]
    widths = [len(c) for c in cols]
    for sr in str_rows:
        for i, cell in enumerate(sr):
            widths[i] = max(widths[i], len(cell))
    widths = [min(w, max_w) for w in widths]
    sep = " │ "
    header  = sep.join(_c(_C.BOLD + _C.CYAN, cols[i].ljust(widths[i])) for i in range(len(cols)))
    divider = _c(_C.CYAN, "─" * (sum(widths) + len(sep) * (len(cols) - 1)))
    print(divider)
    print(header)
    print(divider)
    for sr in str_rows:
        print(sep.join(sr[i][: widths[i]].ljust(widths[i]) for i in range(len(sr))))
    print(divider)


def _parse_nlq_json_content(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fixed = raw.strip().replace("\n```json\n", "").replace("\n```\n", "")
        fixed = fixed.strip("` \n")
        if fixed.lower().startswith("json"):
            fixed = fixed[4:].lstrip().strip()
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as exc:
            print("Model returned non-JSON. First 600 chars:", file=sys.stderr)
            print(raw[:600], file=sys.stderr)
            raise RuntimeError(f"Could not parse OpenAI JSON: {exc}") from exc


# ─── Prompt Builder ───────────────────────────────────────────────────────────

_REPAIR_APPEND = """

## Repair invocation (follow strictly when the user's JSON asks for a fix)
A previous SELECT failed on SQL Server. Use `previous_sql_that_failed` and `sql_server_error`
with the schema excerpt to produce corrected JSON (same keys: sql, explanation, assumptions).
Keep read-only SELECT/WITH only. Fix view/column names per catalog. Prefer SLSXNS + [XnDt] +
[NetSlsNetAmount] for revenue when grain is unclear. Avoid hard-coded dates unless the user gave exact bounds.
"""


def _build_nlq_system_prompt(
    today: str,
    extra_rules: str,
    *,
    repair: bool,
    intent: Optional[QueryIntent] = None,
    memory_ctx: str = "",
    policy: Optional["PolicyResult"] = None,
) -> str:
    semantic_hint = _format_semantic_hint(intent) if intent else ""
    semantic_ctx = _semantic_context_block()
    policy_ctx = _policy_prompt_injection(policy) if policy else ""
    intent_note = (
        f"\n\n## Detected query intent: {intent.summary()}\n"
        f"  • Suggested TOP N: {intent.limit}\n"
        f"  • Order descending: {intent.sort_desc}\n"
        if intent else ""
    )

    base = f"""You are a senior analytics engineer for SQL Server (T-SQL).

You receive:
1) ERP schema/catalog text describing views/columns for retail reporting (SmarterP / zRetail).
2) The user's analytical question (or a repair payload with a failed query + error text).

Output a single JSON object with keys ONLY:
- sql: one T-SQL SELECT or WITH ... SELECT returning the answer (no markdown, no prose inside sql).
- explanation: brief plain English describing what the query does (2-5 sentences max).
- assumptions: array of strings, optional; short notes (e.g. date boundaries, TOP limit).

Hard rules:
- Microsoft SQL Server T-SQL syntax (use brackets for identifiers where helpful).
- Read-only analytics: SELECT / WITH select only.
- Prefer listed views/tables from the schema excerpt when they fit.

Reliability rules (reduce wrong view / wrong date / empty filters):
- Revenue, MTD, "today", and **daily sales trends** that must match operational sales:
  prefer **dbo.VW_MB_POWERBI_SLSXNS_REPORT** with **[XnDt]** and **[NetSlsNetAmount]** (line-level net after returns).
  Do not switch to VW_MB_POWERBI_APP_REPORT for trends unless the user explicitly asks for that grain;
  APP_REPORT row coverage can differ and under-state some days vs SLSXNS.
- **dbo.VW_MB_POWERBI_SLS_REPORT** uses **XnMemoDate** as the date column (see catalog), not XnDt.
- **dbo.VW_MB_POWERBI_APP_REPORT** uses **XnDt** per catalog for date; **NetAmount** for revenue at that grain.
- **Never hard-code calendar dates** (e.g. '2026-05-01') in SQL unless the user pasted exact bounds.
  For MTD through "today", use expressions based on **GETDATE()** / **DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)**
  and **DATEADD(DAY, 1, CAST(GETDATE() AS date))** for an exclusive end, so the query stays valid tomorrow.
- For department/category/branch labels the user gives in natural language: **do not assume** exact **= 'Women'** style
  matches. Prefer **LIKE** with wildcards, or **COLLATE** case-insensitive compare, and state the filter in **assumptions**.
  If they gave an exact code, equality is OK.
- SLSXNS line items: use catalog columns (**XnNo**, **XnId**); **CashmemoNo** / **SalesPersonName** may not exist in all views.
- Always include TOP (default cap 500 unless the result is a single aggregate row).
  Use TOP 500 unless a smaller TOP is obviously enough (e.g. TOP 10).
- Add WITH (NOLOCK) on referenced views in FROM when suitable.

Reference "today" for business logic in assumptions as: **{today}** (client run date).

Return VALID JSON ONLY (json object).
{semantic_hint}{semantic_ctx}{intent_note}{policy_ctx}{memory_ctx}{extra_rules}
"""
    if repair:
        base += _REPAIR_APPEND
    return base


# ─── OpenAI Client ────────────────────────────────────────────────────────────

def _openai_make_client() -> Tuple[Any, str]:
    try:
        from openai import OpenAI
    except ImportError:
        print("pip install openai", file=sys.stderr)
        sys.exit(1)

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        print("Set OPENAI_API_KEY in backend/.env", file=sys.stderr)
        sys.exit(2)

    model   = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
    kw: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        kw["base_url"] = base_url
    return OpenAI(**kw), model


def _openai_chat_json(client: Any, model: str, system: str, user_obj: Dict[str, Any]) -> Dict[str, Any]:
    payload = json.dumps(user_obj, ensure_ascii=False)
    create_kwargs: Dict[str, Any] = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": payload},
        ],
    )
    temp_raw = os.getenv("OPENAI_SQL_TEMPERATURE")
    if temp_raw is not None and str(temp_raw).strip() != "":
        create_kwargs["temperature"] = float(str(temp_raw).strip())
    rf = os.getenv("OPENAI_SQL_RESPONSE_JSON", "1").strip().lower()
    if rf not in ("0", "false", "no"):
        create_kwargs["response_format"] = {"type": "json_object"}

    rsp = client.chat.completions.create(**create_kwargs)
    raw = rsp.choices[0].message.content or "{}"
    return _parse_nlq_json_content(raw)


def _openai_nlq(
    question: str,
    schema_text: str,
    intent: Optional[QueryIntent] = None,
    memory: Optional[ConversationMemory] = None,
    policy: Optional[PolicyResult] = None,
) -> Tuple[Dict[str, Any], str]:
    """Call OpenAI with intent + memory + policy context. Returns (blob, model_name)."""
    client, model = _openai_make_client()
    today      = date.today().isoformat()
    extra      = _load_optional_sql_rules()
    memory_ctx = memory.prompt_context() if memory else ""
    system     = _build_nlq_system_prompt(today, extra, repair=False, intent=intent, memory_ctx=memory_ctx, policy=policy)

    # Resolve follow-up phrasing using conversation memory
    resolved_q = memory.resolve_question(question) if memory else question

    user_obj: Dict[str, Any] = {
        "question": resolved_q,
        "reference_schema_excerpt": schema_text[:120_000],
    }
    if intent:
        user_obj["parsed_intent"] = {
            "type":            intent.intent_type,
            "time_period":     intent.time_period,
            "metrics":         intent.metrics,
            "dimensions":      intent.dimensions,
            "filters":         intent.filters,
            "suggested_limit": intent.limit,
            "sort_desc":       intent.sort_desc,
        }
    return _openai_chat_json(client, model, system, user_obj), model


def _openai_nlq_repair(
    question: str,
    schema_text: str,
    failed_sql: str,
    db_error: str,
    intent: Optional[QueryIntent] = None,
) -> Dict[str, Any]:
    client, model = _openai_make_client()
    today  = date.today().isoformat()
    extra  = _load_optional_sql_rules()
    system = _build_nlq_system_prompt(today, extra, repair=True, intent=intent)
    user_obj: Dict[str, Any] = {
        "mode":                      "repair_failed_select",
        "original_question":         question,
        "reference_schema_excerpt":  schema_text[:120_000],
        "previous_sql_that_failed":  failed_sql,
        "sql_server_error":          db_error[:8000],
    }
    return _openai_chat_json(client, model, system, user_obj)


# ─── Query Runner ─────────────────────────────────────────────────────────────

def run_question(
    question: str,
    *,
    dry_run: bool,
    csv_out: Optional[str],
    max_col_width: int,
    memory: Optional[ConversationMemory] = None,
    audit: Optional[AuditLog] = None,
    show_intent: bool = True,
    explain_only: bool = False,
    apply_policies: bool = True,
) -> Optional[List[Dict[str, Any]]]:
    """
    Full NLP-to-SQL pipeline:
      1. Extract intent (local — zero latency)
      1b. Apply query policies (default period, history cap, heavy-query warning)
      2. Call OpenAI with intent + memory + policy context
      3. Validate SQL safety
      4. Execute against SQL Server
      5. Display results
      6. Update memory + write audit record
    Returns list of result records, or None on dry-run.
    """
    schema_text = _load_schema_catalog()

    try:
        max_attempts = max(1, min(5, int(os.getenv("OPENAI_SQL_MAX_ATTEMPTS", "2"))))
    except ValueError:
        max_attempts = 2

    autofix = os.getenv("OPENAI_SQL_AUTOFIX", "1").strip().lower() not in ("0", "false", "no")

    # ── 1. Parse intent ───────────────────────────────────────────────────────
    intent = _extract_intent(question)

    # ── 1b. Apply query policies ──────────────────────────────────────────────
    policy = _apply_query_policies(intent, apply=apply_policies)

    # Blocked query (e.g. hourly analysis on a DATE-only view)
    if policy.blocked:
        print(_c(_C.RED, f"\n✗ Query blocked: {policy.block_reason}"), file=sys.stderr)
        return None

    # Notices about what the policy engine changed
    for notice in policy.notices():
        print(_c(_C.YLW, f"  ⚠ {notice}"), file=sys.stderr)

    # Heavy-query warning (not blocked — user can Ctrl+C)
    if policy.heavy_query_warned:
        layer    = load_semantic_layer()
        policies = layer.get("query_policies") or {}
        msg      = policies.get("heavy_query_message") or "Heavy query — may be slow."
        print(_c(_C.YLW, f"  ⚠ {msg}"), file=sys.stderr)

    if show_intent:
        print(_c(_C.GRAY, f"  ↳ {intent.summary()}"), file=sys.stderr)

    t0 = time.monotonic()
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    blob: Dict[str, Any]

    # ── 2. FAQ template (tested SQL, no OpenAI) ───────────────────────────────
    faq_hit: Optional[Dict[str, Any]] = None
    if _faq_templates_enabled():
        faq_hit = try_faq_template(question)
    if faq_hit:
        blob = {
            "sql": faq_hit["sql"],
            "explanation": faq_hit.get("explanation", ""),
            "assumptions": faq_hit.get("assumptions", []),
        }
        model_name = f"faq:{faq_hit.get('template_id', 'template')}"
        print(
            _c(_C.GREEN, f"→ FAQ template: {faq_hit.get('template_id')} (no OpenAI)"),
            file=sys.stderr,
        )
    else:
        print(_c(_C.BLUE, "→ Generating SQL…"), file=sys.stderr)
        blob, model_name = _openai_nlq(question, schema_text, intent=intent, memory=memory, policy=policy)

    conn: Any = None
    verdict = ""
    last_db_err = ""
    records: List[Dict[str, Any]] = []

    for attempt in range(max_attempts):
        sql_raw     = blob.get("sql") or ""
        explanation = blob.get("explanation") or ""
        assumptions = blob.get("assumptions") or []

        # ── 3. Validate ───────────────────────────────────────────────────────
        ok, checked = validate_readonly_sql(sql_raw)
        if not ok:
            print(_c(_C.RED, f"SQL rejected: {checked}"), file=sys.stderr)
            if autofix and attempt < max_attempts - 1:
                print(_c(_C.YLW, "→ Asking model to fix (safety rejection)…"), file=sys.stderr)
                blob = _openai_nlq_repair(
                    question, schema_text, sql_raw,
                    f"Safety checker rejected SQL: {checked}", intent=intent,
                )
                continue
            if audit:
                audit.record(question, intent, sql_raw, 0, (time.monotonic()-t0)*1000, error=checked)
            sys.exit(4)

        verdict = checked
        _warn_literal_sql_dates(verdict)

        # ── Display SQL ───────────────────────────────────────────────────────
        label = "Generated SQL" if attempt == 0 else f"Regenerated SQL (attempt {attempt+1}/{max_attempts})"
        bar   = "─" * 12
        print(f"\n{_c(_C.BOLD+_C.CYAN, bar+' '+label+' '+bar)}\n")
        print(_c(_C.WHITE, verdict))
        if explanation:
            print(f"\n{_c(_C.BOLD+_C.CYAN, '─── Explanation ───')}")
            print(textwrap.fill(explanation.strip(), width=88))
        if assumptions:
            print(f"\n{_c(_C.BOLD+_C.CYAN, '─── Assumptions ───')}")
            for a in assumptions:
                print(f"  {_c(_C.YLW, '•')} {a}")

        if dry_run or explain_only:
            print(_c(_C.GRAY, "\n(--dry-run: query not executed)"))
            return None

        # ── 4. Execute ────────────────────────────────────────────────────────
        try:
            conn, driver = connect_mssql()
            print(_c(_C.GRAY, f"\n(DB via {driver})"), file=sys.stderr)
            cur = conn.cursor()
            cur.execute(verdict)
            colnames = [d[0] for d in (cur.description or [])]
            rows     = cur.fetchall()
            records  = [_serialize_row(r, colnames) for r in rows]
            elapsed_ms = (time.monotonic() - t0) * 1000

            row_cap = int(os.getenv("OPENAI_SQL_MAX_ROWS_PRINT", "200"))
            clipped = records[:row_cap]

            row_label = _c(_C.GREEN, f"{len(records)} row(s)")
            clip_note = _c(_C.GRAY, f" (showing first {row_cap})") if len(records) > row_cap else ""
            timing    = _c(_C.GRAY, f" · {elapsed_ms:.0f}ms")
            print(f"\n{_c(_C.BOLD+_C.GREEN, '─── Result ───')}  {row_label}{clip_note}{timing}")

            # ── 5. Display / Export ───────────────────────────────────────────
            if csv_out:
                with open(csv_out, "w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=colnames)
                    w.writeheader()
                    for rec in clipped:
                        w.writerow({k: "" if v is None else v for k, v in rec.items()})
                print(_c(_C.GREEN, f"Wrote CSV: {csv_out}"))
            else:
                _print_table(clipped, max_col_width)

            # ── 6. Memory + audit ─────────────────────────────────────────────
            if memory:
                memory.add(question, verdict, len(records), elapsed_ms)
            if audit:
                audit.record(question, intent, verdict, len(records), elapsed_ms, model=model_name)
            return records

        except pyodbc.Error as exc_db:
            last_db_err = str(exc_db)
            elapsed_ms  = (time.monotonic() - t0) * 1000
            print(_c(_C.RED, f"\n(DB error) {last_db_err}"), file=sys.stderr)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None
            if not autofix or attempt >= max_attempts - 1:
                if audit:
                    audit.record(question, intent, verdict, 0, elapsed_ms, error=last_db_err)
                raise RuntimeError(last_db_err) from exc_db
            print(_c(_C.YLW, "→ OpenAI SQL autofix: retrying with server error context…"), file=sys.stderr)
            blob = _openai_nlq_repair(question, schema_text, verdict, last_db_err, intent=intent)

        except Exception:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None
            raise

    elapsed_ms = (time.monotonic() - t0) * 1000
    if audit:
        audit.record(question, intent, verdict, 0, elapsed_ms,
                     error=f"Exhausted {max_attempts} attempts. {last_db_err}")
    raise RuntimeError(f"Exhausted SQL attempts ({max_attempts}). Last DB error: {last_db_err}")


# ─── REPL Banner ──────────────────────────────────────────────────────────────

def _print_banner() -> None:
    today = date.today().isoformat()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    print(_c(_C.BOLD + _C.CYAN, """
╔══════════════════════════════════════════════════════╗
║         ERP Analytics  —  NLQ → SQL Terminal         ║
╚══════════════════════════════════════════════════════╝"""))
    print(f"  Model  : {_c(_C.YLW, model)}")
    print(f"  Today  : {_c(_C.WHITE, today)}")
    print(f"  Schema   : {_c(_C.GRAY, str(DEFAULT_SCHEMA_PATH))}")
    sem_path = Path(os.getenv("NLQ_SEMANTIC_FILE") or str(DEFAULT_SEMANTIC_PATH))
    print(f"  Semantic : {_c(_C.GRAY, str(sem_path))}")
    print(_c(_C.GRAY, "\n  Commands: faq · compare · convo · product · branch · supplier · customer · inventory · executive · quit"))
    n_faq = len(list_faq_ids()) if _faq_templates_enabled() else 0
    if n_faq:
        print(_c(_C.GRAY, f"  FAQ templates loaded: {n_faq} (type faq for frequent AI questions)"))
    print(_c(_C.CYAN, "  " + "─" * 52))


def _print_query_list(title: str, queries: List[str]) -> None:
    if not queries:
        print(_c(_C.YLW, f"{title}: list not available."))
        return
    print(_c(_C.BOLD, f"\n  {title}:\n"))
    for i, q in enumerate(queries, 1):
        hit = try_faq_template(q) if _faq_templates_enabled() else None
        mark = _c(_C.GREEN, "✓") if hit else _c(_C.YLW, "·")
        print(f"  {mark} {i:2}. {q}")
    print(_c(_C.GRAY, "\n  Paste any line as your question. ✓ = instant FAQ SQL (no OpenAI)."))


def _print_frequent_ai_queries() -> None:
    _print_query_list("Most frequently asked AI queries", list_frequent_ai_queries())


def _print_compare_ai_queries() -> None:
    _print_query_list("Comparison queries", list_compare_ai_queries())


def _print_product_compare_ai_queries() -> None:
    _print_query_list("Product / assortment comparison queries", list_product_compare_ai_queries())


def _print_branch_compare_ai_queries() -> None:
    _print_query_list("Branch comparison queries", list_branch_compare_ai_queries())


def _print_supplier_compare_ai_queries() -> None:
    _print_query_list("Supplier comparison queries", list_supplier_compare_ai_queries())


def _print_customer_compare_ai_queries() -> None:
    _print_query_list("Customer comparison queries", list_customer_compare_ai_queries())


def _print_inventory_compare_ai_queries() -> None:
    _print_query_list("Inventory comparison queries", list_inventory_compare_ai_queries())


def _print_executive_compare_ai_queries() -> None:
    _print_query_list("Executive comparison queries", list_executive_compare_ai_queries())


def _print_conversational_compare_ai_queries() -> None:
    _print_query_list("Conversational comparison queries (memory testing)", list_conversational_compare_ai_queries())


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    _load_dotenv_files()
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    ap = argparse.ArgumentParser(
        description="NLQ → OpenAI → read-only SQL Server — intent parsing, conversational memory, audit log.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("question",            nargs="?", default="", help="Question (omit with -i for REPL)")
    ap.add_argument("-i", "--interactive",  action="store_true",  help="Interactive REPL mode")
    ap.add_argument("--dry-run",            action="store_true",  help="Generate SQL only, do not execute")
    ap.add_argument("--explain",            action="store_true",  help="Alias for --dry-run")
    ap.add_argument("--intent",             action="store_true",  help="Show parsed intent and exit (no SQL)")
    ap.add_argument("--history",            action="store_true",  help="Show audit log tail and exit")
    ap.add_argument("--csv",                metavar="FILE", default="", help="Write results as CSV")
    ap.add_argument("--max-col-width",      type=int, default=36)
    ap.add_argument("--no-color",           action="store_true",  help="Disable ANSI colors")
    ap.add_argument("--no-memory",          action="store_true",  help="Disable conversational memory")
    ap.add_argument("--no-audit",           action="store_true",  help="Disable audit log")
    ap.add_argument("--no-policy",          action="store_true",  help="Disable query policy enforcement (MTD default, history cap, heavy-query warnings)")

    args = ap.parse_args()

    if args.no_color:
        _C.disable()

    load_semantic_layer()

    # ── Audit log ──────────────────────────────────────────────────────────────
    audit_path = Path(os.getenv("NLQ_AUDIT_FILE") or str(DEFAULT_AUDIT_PATH))
    audit: Optional[AuditLog] = None if args.no_audit else AuditLog(audit_path)

    # ── Show history and exit ──────────────────────────────────────────────────
    if args.history:
        if audit:
            audit.show_recent(20)
        else:
            print("Audit log disabled (--no-audit)")
        sys.exit(0)

    # ── Conversational memory ──────────────────────────────────────────────────
    try:
        mem_turns = max(0, int(os.getenv("NLQ_MEMORY_TURNS", "5")))
    except ValueError:
        mem_turns = 5
    memory: Optional[ConversationMemory] = None if args.no_memory else ConversationMemory(max_turns=mem_turns)

    csv_path = args.csv.strip() or None
    dry = args.dry_run or args.explain
    use_policy = not args.no_policy

    def _show_intent_only(q: str) -> None:
        intent = _extract_intent(q)
        print(f"\n  Question   : {_c(_C.WHITE, q)}")
        print(f"  Intent     : {_c(_C.CYAN, intent.intent_type)}")
        print(f"  Period     : {_c(_C.YLW, intent.time_period or '(none)')}")
        print(f"  Metrics    : {_c(_C.GREEN, ', '.join(intent.metrics) or '(none)')}")
        print(f"  Dimensions : {', '.join(intent.dimensions) or '(none)'}")
        print(f"  Filters    : {intent.filters or '(none)'}")
        print(f"  Limit      : {intent.limit}   Sort desc: {intent.sort_desc}")
        hint = _format_semantic_hint(intent)
        if hint:
            for line in hint.splitlines():
                print(_c(_C.GRAY, line))
        if _faq_templates_enabled():
            faq = try_faq_template(q)
            if faq:
                print(f"  Template   : {_c(_C.GREEN, faq.get('template_id', ''))} (FAQ SQL, no API)")
            else:
                print(f"  Template   : {_c(_C.GRAY, '(none — will use OpenAI)')}")

    def once(q: str) -> None:
        q = q.strip()
        if not q:
            return
        if args.intent:
            _show_intent_only(q)
            return
        try:
            run_question(
                q,
                dry_run=dry,
                csv_out=csv_path,
                max_col_width=args.max_col_width,
                memory=memory,
                audit=audit,
                show_intent=True,
                apply_policies=use_policy,
            )
        except Exception as exc:
            print(_c(_C.RED, f"Error: {exc}"), file=sys.stderr)
            if not args.interactive:
                sys.exit(1)

    if args.interactive:
        _print_banner()
        _last_result: List[Dict[str, Any]] = []

        while True:
            try:
                line = input(f"\n{_c(_C.BOLD+_C.CYAN, 'Ask')}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print(_c(_C.GRAY, "\nBye."))
                break

            if not line:
                continue
            low = line.lower()

            # ── REPL meta-commands ────────────────────────────────────────────────────────────────
            if low in ("exit", "quit", "bye"):
                print(_c(_C.GRAY, "Bye."))
                break

            if low in ("faq", "examples", "queries"):
                _print_frequent_ai_queries()
                continue

            if low in ("compare", "convo", "context"):
                _print_compare_ai_queries()
                _print_conversational_compare_ai_queries()
                continue

            if low == "product":
                _print_product_compare_ai_queries()
                continue

            if low == "branch":
                _print_branch_compare_ai_queries()
                continue

            if low == "supplier":
                _print_supplier_compare_ai_queries()
                continue

            if low == "customer":
                _print_customer_compare_ai_queries()
                continue

            if low == "inventory":
                _print_inventory_compare_ai_queries()
                continue

            if low == "executive":
                _print_executive_compare_ai_queries()
                continue

            if low == "history":
                if memory:
                    memory.show()
                if audit:
                    audit.show_recent(8)
                continue

            if low == "clear":
                if memory:
                    memory.clear()
                print(_c(_C.GREEN, "Conversation memory cleared."))
                continue

            if low.startswith("export "):
                fname = line[7:].strip()
                if _last_result and fname:
                    cols = list(_last_result[0].keys())
                    with open(fname, "w", newline="", encoding="utf-8") as fh:
                        w = csv.DictWriter(fh, fieldnames=cols)
                        w.writeheader()
                        for rec in _last_result:
                            w.writerow({k: "" if v is None else v for k, v in rec.items()})
                    print(_c(_C.GREEN, f"Exported {len(_last_result)} rows → {fname}"))
                else:
                    print(_c(_C.YLW, "Nothing to export yet. Run a query first."))
                continue

            if low in ("explain", "sql", "show sql"):
                if memory and memory._turns:
                    print(f"\n{_c(_C.BOLD, 'Last SQL:')}")
                    print(_c(_C.WHITE, memory._turns[-1].sql))
                else:
                    print(_c(_C.GRAY, "No previous query in memory."))
                continue

            if low.startswith("intent "):
                _show_intent_only(line[7:].strip())
                continue

            if low == "intent":
                print(_c(_C.YLW, "Usage: intent <your question>"))
                continue

            # ── Normal question ────────────────────────────────────────────────────────────────────
            try:
                result = run_question(
                    line,
                    dry_run=False,
                    csv_out=None,
                    max_col_width=args.max_col_width,
                    memory=memory,
                    audit=audit,
                    show_intent=True,
                    apply_policies=use_policy,
                )
                if result is not None:
                    _last_result = result
            except Exception as exc:
                print(_c(_C.RED, f"Error: {exc}"), file=sys.stderr)

            print()

    elif args.question.strip():
        once(args.question)
    else:
        _print_banner()
        ap.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
