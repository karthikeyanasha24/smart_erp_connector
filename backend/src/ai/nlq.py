"""
NLQ Orchestrator
Full pipeline: natural language → intent → SQL → validate → execute → insights → response.

Entry point: process_query(query, user_id, conv_id)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import resolve_date_range
from src.ai.intent import extract_intent, extract_intent_fast, ExtractedIntent
from src.ai.sqlgen import generate_sql, generate_sql_template, GeneratedSQL
from src.ai.test_faq_loader import try_verified_faq
from src.ai.validator import validate_and_correct
from src.ai.memory import (
    create_conversation, get_conversation, add_turn, build_context_string,
)
from src.ai.insights import generate_insights
from src.db.mssql import execute_query


# ─── Response Types ───────────────────────────────────────────────────────────

@dataclass
class NLQResponse:
    query: str
    sql: Optional[str]
    records: List[Dict[str, Any]]
    record_count: int
    intent: Optional[Dict[str, Any]]
    chart_type: str
    period: str
    period_label: str
    description: str
    summary: Optional[str]
    insights: List[Dict[str, Any]]
    conv_id: Optional[str]
    duration_ms: int
    corrected: bool
    from_template: bool
    warnings: List[str]
    faq_template_id: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _intent_to_dict(intent: ExtractedIntent) -> Dict[str, Any]:
    return {
        "intent": intent.intent,
        "period": intent.period,
        "metric": intent.metric,
        "dimension": intent.dimension,
        "tables": intent.tables,
        "chart_type": intent.chart_type,
        "top_n": intent.top_n,
        "filters": intent.filters,
        "compare_with": intent.compare_with,
        "confidence": intent.confidence,
        "raw": intent.raw,
    }


def _infer_columns(records: List[Dict[str, Any]], intent: ExtractedIntent) -> Dict[str, str]:
    """Guess value and label columns from result set structure."""
    if not records:
        return {"value": "Revenue", "label": ""}

    cols = list(records[0].keys())
    value_col = "Revenue"
    label_col = ""

    # Find numeric column
    for name in ["Revenue", "NetSalesAmount", "TotalRevenue", "Amount", "Value"]:
        if name in cols:
            value_col = name
            break
    else:
        for col in cols:
            try:
                v = records[0].get(col)
                if v is None:
                    continue
                float(str(v).replace(",", ""))
                value_col = col
                break
            except (TypeError, ValueError):
                continue

    # Find string/label column
    dim_hints = {
        "branch": ["Branch", "BranchAlias", "BranchName"],
        "category": ["Category", "CategoryShortName"],
        "department": ["Department", "DepartmentShortName"],
        "salesperson": ["SalesPersonName", "Salesperson"],
    }
    if intent.dimension and intent.dimension in dim_hints:
        for col in dim_hints[intent.dimension]:
            if col in cols:
                label_col = col
                break

    if not label_col:
        for col in cols:
            if col != value_col and isinstance(records[0].get(col), str):
                label_col = col
                break

    return {"value": value_col, "label": label_col}


# ─── Main Orchestrator ────────────────────────────────────────────────────────

async def process_query(
    query: str,
    user_id: str = "anonymous",
    conv_id: Optional[str] = None,
    top_n_override: Optional[int] = None,
) -> NLQResponse:
    start = time.perf_counter()
    warnings: List[str] = []
    from_template = False

    # ── Step 1: Conversation context ───────────────────────────────────────────
    if conv_id:
        conv = get_conversation(conv_id)
        if conv is None:
            conv_id = None  # orphaned ID — reset

    if not conv_id:
        conv = create_conversation(user_id, title=query[:60])
        conv_id = conv.id

    context_str = build_context_string(conv_id)

    faq_template_id: Optional[str] = None
    faq_blob = try_verified_faq(query)
    faq_sql = ""
    if faq_blob and isinstance(faq_blob.get("sql"), str):
        faq_sql = faq_blob["sql"].strip()

    if faq_sql:
        # Same curated T-SQL path as CLI `terminal_openai_nlq_sql.py` / export scripts
        intent = extract_intent_fast(query)
        if top_n_override:
            intent.top_n = top_n_override

        date_range = resolve_date_range(intent.period)

        gen_sql = GeneratedSQL(
            sql=faq_sql,
            params={},
            description=(faq_blob.get("explanation") or faq_blob.get("template_id") or "")
            or "Verified FAQ SQL",
            estimated_rows="moderate",
            uses_date_range=False,
        )
        from_template = True
        faq_template_id = faq_blob.get("template_id")

        validation = await validate_and_correct(
            gen_sql.sql,
            query,
            allow_correction=False,
        )
        if not validation.valid:
            raise ValueError(
                f"Verified FAQ SQL failed validation: {'; '.join(validation.errors)}"
            )

        if validation.warnings:
            warnings.extend(validation.warnings)
    else:
        # ── Step 2+: Intent extraction (may call AI depending on cfg) ───────────
        intent = await extract_intent(query, context_str)
        if top_n_override:
            intent.top_n = top_n_override

        date_range = resolve_date_range(intent.period)

        gen_sql: Optional[GeneratedSQL] = None

        if cfg.NLQ_FAST_PATH:
            gen_sql = generate_sql_template(intent, date_range)
            if gen_sql:
                from_template = True

        if gen_sql is None:
            gen_sql = await generate_sql(intent, date_range, context_str)

        if gen_sql is None:
            raise RuntimeError("SQL generation returned nothing")

        validation = await validate_and_correct(
            gen_sql.sql,
            query,
            allow_correction=True,
        )

        if not validation.valid:
            raise ValueError(
                f"Generated SQL failed validation: {'; '.join(validation.errors)}"
            )

        if validation.corrected:
            warnings.append("SQL was auto-corrected by AI.")

        if validation.warnings:
            warnings.extend(validation.warnings)

    final_sql = validation.sql or gen_sql.sql

    try:
        result = await execute_query(
            final_sql,
            params=gen_sql.params if gen_sql.uses_date_range else None,
        )
        records = result["records"]
    except Exception as exc:
        logger.error("SQL execution failed", error=str(exc), sql=final_sql[:200])
        raise RuntimeError(f"Query execution failed: {exc}") from exc

    if len(records) > cfg.DATASET_HARD_CAP:
        records = records[:cfg.DATASET_HARD_CAP]
        warnings.append(f"Results capped at {cfg.DATASET_HARD_CAP:,} rows.")

    col_info = _infer_columns(records, intent)
    insight_data = await generate_insights(
        query=query,
        records=records,
        intent_type=intent.intent,
        period_label=date_range.label,
        value_column=col_info["value"],
        label_column=col_info["label"] or None,
    )

    narrative = insight_data.get("summary") or (
        insight_data["insights"][0]["description"]
        if insight_data.get("insights")
        else None
    )
    add_turn(conv_id, "user", query)
    add_turn(
        conv_id,
        "assistant",
        narrative or gen_sql.description,
        sql=final_sql,
        intent=_intent_to_dict(intent),
        result_summary=f"{len(records)} rows returned for {date_range.label}",
    )

    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "NLQ query processed",
        duration_ms=duration_ms,
        records=len(records),
        intent=intent.intent,
        period=intent.period,
        from_template=from_template,
        faq=bool(faq_template_id),
    )

    summary_out = narrative or gen_sql.description
    return NLQResponse(
        query=query,
        sql=final_sql,
        records=records,
        record_count=len(records),
        intent=_intent_to_dict(intent),
        chart_type=intent.chart_type,
        period=intent.period,
        period_label=date_range.label,
        description=gen_sql.description,
        summary=summary_out,
        insights=insight_data.get("insights", []),
        conv_id=conv_id,
        duration_ms=duration_ms,
        corrected=validation.corrected,
        from_template=from_template,
        warnings=warnings,
        faq_template_id=faq_template_id,
    )
