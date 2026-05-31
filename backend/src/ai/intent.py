"""
Intent Extraction Engine
Classifies a natural language query into a structured intent object
that drives SQL generation and chart selection downstream.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

import anthropic

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import detect_period
from src.ai.schema_catalog import select_relevant_views, get_compact_view_index


def infer_relevant_tables(query: str) -> List[str]:
    """Returns the short_names of views most relevant to the query."""
    return [v["short_name"] for v in select_relevant_views(query, max_views=3)]

# ─── Types ────────────────────────────────────────────────────────────────────

QueryIntent = Literal[
    "aggregate", "trend", "comparison", "ranking", "detail",
    "kpi", "distribution", "forecast", "anomaly", "unknown",
]

ChartType = Literal[
    "bar", "line", "area", "pie", "donut",
    "scatter", "heatmap", "table", "kpi_card",
]


@dataclass
class ExtractedIntent:
    intent: QueryIntent
    period: str
    metric: str
    tables: List[str]
    chart_type: ChartType
    confidence: float
    raw: str
    compare_with: Optional[str] = None
    dimension: Optional[str] = None
    filters: Dict[str, str] = field(default_factory=dict)
    top_n: Optional[int] = None
    needs_clarification: Optional[str] = None


# ─── Fast-Path Rule Engine ────────────────────────────────────────────────────

def extract_intent_fast(query: str) -> ExtractedIntent:
    """Regex-based intent extractor — sub-millisecond, no AI call."""
    q = query.lower().strip()
    period = detect_period(query)
    tables = infer_relevant_tables(query)

    # Metric detection
    metric = "revenue"
    if re.search(r"\b(customer|client)\b", q):
        metric = "customer_count"
    elif re.search(r"\b(transaction|invoice|order)\b", q):
        metric = "transaction_count"
    elif re.search(r"\b(stock|inventory|unit)\b", q):
        metric = "stock_quantity"
    elif re.search(r"\b(quantity|qty|units sold)\b", q):
        metric = "quantity"
    elif re.search(r"\b(discount)\b", q):
        metric = "discount"
    elif re.search(r"\b(profit|margin)\b", q):
        metric = "profit"

    # Dimension detection
    dimension: Optional[str] = None
    if re.search(r"by branch|branchwise|branch.?wise", q):
        dimension = "branch"
    elif re.search(r"by category|categor(y|ies)", q):
        dimension = "category"
    elif re.search(r"by department|department", q):
        dimension = "department"
    elif re.search(r"by salesperson|salesperson|sales rep", q):
        dimension = "salesperson"
    elif re.search(r"by item|by product|product", q):
        dimension = "item"

    # Top-N detection
    top_n: Optional[int] = None
    top_match = re.search(r"\btop\s+(\d+)\b", q)
    if top_match:
        top_n = int(top_match.group(1))

    # Filters
    filters: Dict[str, str] = {}
    branch_match = re.search(r"\b(?:at|in|for)\s+([a-z]+)\s+branch\b", q)
    if branch_match:
        filters["branch"] = branch_match.group(1)

    # Intent + chart classification
    intent: QueryIntent
    chart_type: ChartType

    if re.search(r"\blast\s+\d+\s+years?\b|\b5\s+year.*analysis|\byear.*analysis.*department", q):
        intent, chart_type = "trend", "area"
    elif re.search(r"\btrend\b|\bover time\b|\bdaily\b|\bmonthly\b|\bweekly\b|\bby day\b|\bby month\b", q):
        intent, chart_type = "trend", "area"
    elif re.search(r"\bcompare\b|\bvs\b|\bversus\b|\bcomparison\b|\bprevious\b|\bprior\b", q):
        intent, chart_type = "comparison", "bar"
    elif re.search(r"\btop\s+\d+\b|\brank\b|\bbest\b|\bworst\b|\bhighest\b|\blowest\b", q):
        intent, chart_type = "ranking", "bar"
    elif re.search(r"\bdetail\b|\blist\b|\bshow me\b|\bwhat are\b|\bwhich\b", q):
        intent, chart_type = "detail", "table"
    elif re.search(r"\btotal\b|\bsum\b|\bhow much\b|\bhow many\b|\bcount\b", q) and not dimension:
        intent, chart_type = "kpi", "kpi_card"
    elif re.search(r"\bbreakdown\b|\bsplit\b|\bshare\b|\bportion\b|\bpercent\b", q):
        intent, chart_type = "distribution", "pie"
    elif re.search(r"\banomaly\b|\bspike\b|\bdrop\b|\bunusual\b|\boutlier\b", q):
        intent, chart_type = "anomaly", "line"
    elif re.search(r"\bforecast\b|\bpredict\b|\bexpect\b|\bprojection\b", q):
        intent, chart_type = "forecast", "line"
    elif dimension:
        intent, chart_type = "aggregate", "bar"
    else:
        intent, chart_type = "aggregate", "bar"

    # Compare-with period
    compare_with: Optional[str] = None
    if re.search(r"\bvs?\b|versus|compared to|vs prior", q, re.IGNORECASE):
        if period == "mtd":
            compare_with = "prior_mtd"
        elif period == "ytd":
            compare_with = "prior_ytd"
        elif period == "last_month":
            compare_with = "prior_month"
        else:
            compare_with = "prior_period"

    return ExtractedIntent(
        intent=intent,
        period=period,
        compare_with=compare_with,
        dimension=dimension,
        metric=metric,
        filters=filters,
        top_n=top_n,
        tables=tables,
        chart_type=chart_type,
        confidence=0.75,
        raw=query,
    )


# ─── AI Intent Extractor ──────────────────────────────────────────────────────

def _build_intent_system() -> str:
    view_index = get_compact_view_index()
    return f"""You are an ERP analytics query classifier for a retail business (database: zRetailHQ0).
Given a natural language query, extract a structured intent as JSON.

{view_index}

Output ONLY valid JSON with this shape:
{{
  "intent": "<aggregate|trend|comparison|ranking|detail|kpi|distribution|forecast|anomaly>",
  "period": "<today|yesterday|mtd|ytd|qtd|last_7d|last_30d|last_month|last_quarter|last_year>",
  "compare_with": "<comparison period or null>",
  "dimension": "<branch|category|department|salesperson|item|supplier|customer|null>",
  "metric": "<revenue|customer_count|transaction_count|quantity|stock_quantity|discount|profit|purchase_value>",
  "filters": {{}},
  "top_n": <number or null>,
  "tables": ["<primary view short_name>", "<secondary view if needed>"],
  "chart_type": "<bar|line|area|pie|donut|scatter|heatmap|table|kpi_card>",
  "confidence": <0.0-1.0>,
  "needs_clarification": "<question if ambiguous or null>"
}}

Rules:
- Default period to "mtd" if none mentioned
- For trend/daily/over-time queries: area or line chart
- For rankings/top-N: bar chart
- For distributions/breakdowns: pie or donut
- For single KPIs (total, count): kpi_card
- For tables/lists/detail: table
- Use the view index above to pick the most relevant tables[] for the query
- confidence 0.9+ for clear queries, 0.5-0.7 for ambiguous"""


_INTENT_SYSTEM: str = ""  # built lazily to avoid import-time catalog load

_ai_client: Optional[anthropic.AsyncAnthropic] = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.AsyncAnthropic(api_key=cfg.ANTHROPIC_API_KEY)
    return _ai_client


async def extract_intent_ai(
    query: str,
    conversation_context: Optional[str] = None,
) -> ExtractedIntent:
    global _INTENT_SYSTEM
    if not _INTENT_SYSTEM:
        _INTENT_SYSTEM = _build_intent_system()

    client = _get_client()

    user_msg = query
    if conversation_context:
        user_msg = f"Previous context:\n{conversation_context}\n\nNew query: {query}"

    try:
        response = await client.messages.create(
            model=cfg.ANTHROPIC_MODEL,
            max_tokens=600,
            system=_INTENT_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )

        text = response.content[0].text if response.content else ""
        json_match = re.search(r"\{[\s\S]*\}", text)
        if not json_match:
            raise ValueError("No JSON in AI response")

        parsed = json.loads(json_match.group())
        tables = infer_relevant_tables(query)

        return ExtractedIntent(
            intent=parsed.get("intent", "aggregate"),
            period=parsed.get("period") or detect_period(query),
            compare_with=parsed.get("compare_with"),
            dimension=parsed.get("dimension"),
            metric=parsed.get("metric", "revenue"),
            filters=parsed.get("filters", {}),
            top_n=parsed.get("top_n"),
            tables=parsed.get("tables", tables) or tables,
            chart_type=parsed.get("chart_type", "bar"),
            confidence=parsed.get("confidence", 0.8),
            needs_clarification=parsed.get("needs_clarification"),
            raw=query,
        )

    except Exception as exc:
        logger.warning("AI intent extraction failed, falling back to fast path", error=str(exc))
        return extract_intent_fast(query)


# ─── Public Entry Point ───────────────────────────────────────────────────────

async def extract_intent(
    query: str,
    conversation_context: Optional[str] = None,
) -> ExtractedIntent:
    if cfg.NLQ_FAST_PATH and not conversation_context:
        fast = extract_intent_fast(query)
        if fast.confidence >= 0.7:
            return fast

    if cfg.NLQ_INTENT_COMPILER:
        return await extract_intent_ai(query, conversation_context)

    return extract_intent_fast(query)
