"""
AI Insights Engine
Generates natural-language business insights from query results:
- Rule-based anomaly detection
- AI-powered trend narratives
- Adaptive summaries
"""

from __future__ import annotations

import json
import re
import statistics
from typing import Any, Dict, List, Optional

import anthropic

from src.config import cfg
from src.utils.logger import logger

# ─── OpenAI client (lazy) ─────────────────────────────────────────────────────
_openai_client = None

def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI  # type: ignore
            _openai_client = AsyncOpenAI(api_key=cfg.OPENAI_API_KEY)
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")
    return _openai_client

# ─── Types ────────────────────────────────────────────────────────────────────

InsightSeverity = str   # "info" | "warning" | "critical"


class Insight:
    def __init__(
        self,
        kind: str,
        title: str,
        description: str,
        severity: InsightSeverity = "info",
        value: Optional[float] = None,
        change_pct: Optional[float] = None,
        dimension: Optional[str] = None,
    ) -> None:
        self.kind = kind
        self.title = title
        self.description = description
        self.severity = severity
        self.value = value
        self.change_pct = change_pct
        self.dimension = dimension

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "value": self.value,
            "change_pct": self.change_pct,
            "dimension": self.dimension,
        }


# ─── Rule-Based Anomaly Detection ─────────────────────────────────────────────

def detect_anomalies(
    records: List[Dict[str, Any]],
    value_column: str = "Revenue",
    label_column: Optional[str] = None,
    z_threshold: float = 2.0,
) -> List[Insight]:
    """
    Z-score based anomaly detection on a numeric series.
    Returns insights for data points that deviate significantly from the mean.
    """
    insights: List[Insight] = []

    values = []
    for row in records:
        v = row.get(value_column)
        if v is not None:
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                pass

    if len(values) < 4:
        return insights

    mean = statistics.mean(values)
    stdev = statistics.stdev(values)

    if stdev == 0:
        return insights

    for row in records:
        raw_v = row.get(value_column)
        if raw_v is None:
            continue
        try:
            v = float(raw_v)
        except (TypeError, ValueError):
            continue

        z = (v - mean) / stdev
        if abs(z) < z_threshold:
            continue

        label = row.get(label_column or "") if label_column else None
        dim_str = f" for {label}" if label else ""
        direction = "spike" if z > 0 else "drop"
        severity = "critical" if abs(z) > 3.5 else "warning"
        change_pct = ((v - mean) / mean * 100) if mean else 0

        insights.append(
            Insight(
                kind="anomaly",
                title=f"Revenue {direction}{dim_str}",
                description=(
                    f"{value_column}{dim_str} is {abs(change_pct):.1f}% "
                    f"{'above' if z > 0 else 'below'} average "
                    f"(value: {v:,.0f}, avg: {mean:,.0f})"
                ),
                severity=severity,
                value=v,
                change_pct=change_pct,
                dimension=str(label) if label else None,
            )
        )

    return insights[:5]   # Cap to top 5


def _row_value(row: Dict[str, Any], value_column: str) -> float:
    try:
        return float(row.get(value_column) or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_date_column(col: str, records: List[Dict[str, Any]]) -> bool:
    cl = col.lower()
    if any(h in cl for h in ("month", "date", "day", "period")):
        return True
    for row in records[:8]:
        raw = row.get(col)
        if raw is None:
            continue
        s = str(raw)
        if re.match(r"^\d{4}-\d{2}-\d{2}", s) or re.search(
            r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec", s, re.I
        ):
            return True
    return False


def _aggregate_for_insights(
    records: List[Dict[str, Any]],
    value_column: str,
    label_column: str,
) -> List[Dict[str, Any]]:
    """Sum metrics by label when rows share the same dimension (e.g. category across months)."""
    totals: Dict[str, float] = {}
    for row in records:
        label = str(row.get(label_column) or "Unknown")
        totals[label] = totals.get(label, 0.0) + _row_value(row, value_column)
    return [{label_column: label, value_column: total} for label, total in totals.items()]


def _prepare_insight_records(
    records: List[Dict[str, Any]],
    value_column: str,
    label_column: Optional[str],
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Pick a sensible label column and aggregate multi-grain rows before ranking."""
    if not records or not label_column:
        return records, label_column

    cols = list(records[0].keys())
    date_cols = [c for c in cols if _is_date_column(c, records)]
    dim_cols = [
        c for c in cols
        if c not in date_cols and c != value_column and not _is_numeric_col(c, records)
    ]

    # Dept + category time series → rank by composite key
    if date_cols and "Department" in dim_cols and "Category" in dim_cols:
        composite = "_composite_dept_cat"
        aggregated: Dict[str, float] = {}
        for row in records:
            label = f"{row.get('Department', '')} · {row.get('Category', '')}".strip(" ·")
            aggregated[label] = aggregated.get(label, 0.0) + _row_value(row, value_column)
        rows = [{composite: k, value_column: v} for k, v in aggregated.items()]
        return rows, composite

    # Time series with a single dimension → aggregate by that dimension
    if date_cols and dim_cols:
        primary = dim_cols[0]
        return _aggregate_for_insights(records, value_column, primary), primary

    labels = [str(r.get(label_column) or "") for r in records]
    if len(set(labels)) < len(labels):
        return _aggregate_for_insights(records, value_column, label_column), label_column

    return records, label_column


def _is_numeric_col(col: str, records: List[Dict[str, Any]]) -> bool:
    for row in records[:10]:
        raw = row.get(col)
        if raw is None:
            continue
        try:
            float(str(raw).replace(",", ""))
            return True
        except (TypeError, ValueError):
            continue
    return False


def top_bottom_insights(
    records: List[Dict[str, Any]],
    value_column: str = "Revenue",
    label_column: str = "Branch",
    top_n: int = 3,
) -> List[Insight]:
    """Highlight top and bottom performers."""
    insights: List[Insight] = []
    if not records or len(records) < 2:
        return insights

    prepared, label_col = _prepare_insight_records(records, value_column, label_column)
    if not label_col:
        return insights

    def _val(row: Dict[str, Any]) -> float:
        return _row_value(row, value_column)

    sorted_rows = sorted(prepared, key=_val, reverse=True)
    total = sum(_val(r) for r in prepared) or 1

    for i, row in enumerate(sorted_rows[:top_n]):
        v = _val(row)
        label = row.get(label_col, "Unknown")
        share = v / total * 100
        rank = i + 1
        insights.append(
            Insight(
                kind="top_performer",
                title=f"#{rank} {label}",
                description=f"{label} contributed {share:.1f}% of total {value_column.lower()} ({v:,.0f}).",
                severity="info",
                value=v,
                dimension=str(label),
            )
        )

    # Bottom performer
    if len(sorted_rows) >= top_n + 1:
        bottom = sorted_rows[-1]
        v = _val(bottom)
        label = bottom.get(label_col, "Unknown")
        share = v / total * 100
        insights.append(
            Insight(
                kind="low_performer",
                title=f"Lowest: {label}",
                description=f"{label} is the lowest performer at {share:.1f}% share ({v:,.0f}).",
                severity="warning",
                value=v,
                dimension=str(label),
            )
        )

    return insights


def trend_insights(
    records: List[Dict[str, Any]],
    value_column: str = "Revenue",
    date_column: str = "TransactionDate",
) -> List[Insight]:
    """Detect growth/decline in a time series."""
    insights: List[Insight] = []
    if len(records) < 3:
        return insights

    # Aggregate when rows share a date column but have extra dimensions
    if date_column in (records[0] or {}):
        labels = [str(r.get(date_column) or "") for r in records]
        if len(set(labels)) < len(labels):
            records = _aggregate_for_insights(records, value_column, date_column)

    values = []
    for row in records:
        values.append(_row_value(row, value_column))

    # Compare first half vs second half
    mid = len(values) // 2
    first_half_avg = statistics.mean(values[:mid]) if values[:mid] else 0
    second_half_avg = statistics.mean(values[mid:]) if values[mid:] else 0

    if first_half_avg == 0:
        return insights

    change_pct = (second_half_avg - first_half_avg) / first_half_avg * 100
    direction = "growing" if change_pct > 0 else "declining"
    severity = "info" if change_pct > 0 else ("warning" if change_pct < -10 else "info")

    insights.append(
        Insight(
            kind="trend",
            title=f"Revenue is {direction}",
            description=(
                f"The second half of the period shows a {abs(change_pct):.1f}% "
                f"{'increase' if change_pct > 0 else 'decrease'} compared to the first half."
            ),
            severity=severity,
            change_pct=change_pct,
        )
    )
    return insights


# ─── AI Narrative Summary ──────────────────────────────────────────────────────

_ai_client: Optional[anthropic.AsyncAnthropic] = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.AsyncAnthropic(api_key=cfg.ANTHROPIC_API_KEY)
    return _ai_client


_SUMMARY_SYSTEM = """You are an expert business analyst summarizing ERP data results.
Write a concise 2-3 sentence business insight narrative about the data.
Be specific: mention actual numbers, branch names, percentages.
Currency values in the JSON are RAW INDIAN RUPEES: 1 lakh = 100,000; 1 crore = 10,000,000.
Example: 2748884356 = ₹274.89 crore (never divide by 10^8).
YTD means Indian financial year from 1 April, not calendar year.
Tone: professional, decisive, actionable.
Format: plain paragraph text, no markdown, no bullets."""


async def generate_ai_summary(
    query: str,
    records: List[Dict[str, Any]],
    intent_type: str = "aggregate",
    period_label: str = "this period",
    provider: str = "claude",
) -> Optional[str]:
    """Generate a 2-3 sentence AI narrative about the query result.

    Routes to Claude (Anthropic) or ChatGPT (OpenAI) based on `provider`.
    """
    if not records:
        return None

    sample = records[:20]
    data_str = json.dumps(sample, default=str)
    user_content = (
        f'Query: "{query}"\n'
        f"Period: {period_label}\n"
        f"Intent: {intent_type}\n"
        f"Data ({len(records)} rows):\n{data_str}\n\n"
        "Write a business insight summary."
    )

    try:
        if provider == "openai":
            if not cfg.OPENAI_API_KEY:
                logger.warning("OpenAI API key not configured, falling back to Claude")
                provider = "claude"
            else:
                oai = _get_openai_client()
                response = await oai.chat.completions.create(
                    model=cfg.OPENAI_MODEL,
                    max_tokens=256,
                    messages=[
                        {"role": "system", "content": _SUMMARY_SYSTEM},
                        {"role": "user", "content": user_content},
                    ],
                )
                text = response.choices[0].message.content or ""
                logger.info("OpenAI summary generated", model=cfg.OPENAI_MODEL, chars=len(text))
                return text.strip() or None

        # Claude (default)
        if not cfg.ANTHROPIC_API_KEY:
            return None
        client = _get_client()
        response = await client.messages.create(
            model=cfg.ANTHROPIC_MODEL,
            max_tokens=256,
            system=_SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        return (response.content[0].text or "").strip() if response.content else None

    except Exception as exc:
        logger.warning("AI summary generation failed", provider=provider, error=str(exc))
        return None


# ─── Combined Insight Pipeline ─────────────────────────────────────────────────

async def generate_insights(
    query: str,
    records: List[Dict[str, Any]],
    intent_type: str = "aggregate",
    period_label: str = "this period",
    value_column: str = "Revenue",
    label_column: Optional[str] = None,
    date_column: str = "TransactionDate",
    provider: str = "claude",
) -> Dict[str, Any]:
    """
    Full insight pipeline:
    1. Rule-based anomalies
    2. Top/bottom performers
    3. Trend analysis
    4. AI narrative summary
    """
    rule_insights: List[Insight] = []

    # Resolve date column from records when default is absent
    if records and date_column not in records[0]:
        for candidate in ("MonthStart", "MonthLabel", "TransactionDate", "InvoiceDt", "XnDt"):
            if candidate in records[0]:
                date_column = candidate
                break

    if intent_type == "trend":
        rule_insights.extend(trend_insights(records, value_column, date_column))
        if label_column:
            prepared, insight_label = _prepare_insight_records(records, value_column, label_column)
            rule_insights.extend(
                top_bottom_insights(prepared, value_column, insight_label or label_column)
            )
        rule_insights.extend(detect_anomalies(records, value_column, label_column))

    elif intent_type in ("aggregate", "ranking", "distribution"):
        if label_column:
            prepared, insight_label = _prepare_insight_records(records, value_column, label_column)
            rule_insights.extend(top_bottom_insights(prepared, value_column, insight_label or label_column))
        rule_insights.extend(detect_anomalies(records, value_column, label_column))

    elif intent_type == "comparison":
        rule_insights.extend(detect_anomalies(records, value_column, label_column))

    # AI summary
    ai_summary: Optional[str] = None
    if cfg.AI_ADAPTIVE_SUMMARY and records:
        ai_summary = await generate_ai_summary(query, records, intent_type, period_label, provider)

    return {
        "insights": [i.to_dict() for i in rule_insights],
        "summary": ai_summary,
        "record_count": len(records),
    }
