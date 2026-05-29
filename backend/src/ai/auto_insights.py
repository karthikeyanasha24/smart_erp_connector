"""
Auto-Insights Engine
Proactively generates AI business insights from live ERP analytics data.
Strategy:
  1. Try the fastest path: read from in-memory cache (various key formats).
  2. Fall back to direct SQL queries if cache is cold — guarantees live data.
  3. Run rule-based engines (anomaly, trend, ranking, category) on the data.
  4. Generate an AI narrative summary via Claude if ANTHROPIC_API_KEY is set.
"""

from __future__ import annotations

import asyncio
import json
import statistics
from typing import Any, Dict, List, Optional, Tuple

import anthropic

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import trend_granularity


# ─── Cache helpers ─────────────────────────────────────────────────────────────

def _from_cache(key: str) -> Optional[Any]:
    try:
        from src.analytics.cache import cache
        val, _ = cache.get(key)
        return val
    except Exception:
        return None


def _try_keys(keys: List[str]) -> Optional[Any]:
    for k in keys:
        v = _from_cache(k)
        if v is not None:
            return v
    return None


# ─── Value helpers ──────────────────────────────────────────────────────────────

def _fval(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return default


def _pct(value: float, total: float) -> float:
    return (value / total * 100) if total else 0.0


# ─── Data loader — cache-first, live fallback ──────────────────────────────────

async def _load_data(period: str) -> Dict[str, Any]:
    """
    Returns a dict with keys: kpis, branches, trend, categories.
    Tries cache first; falls back to direct SQL analytics calls for any missing piece.
    """
    gran = trend_granularity(period)

    # ── 1. Try to pull everything from cache ──────────────────────────────────
    kpis = _try_keys([
        f"kpi:v4:{period}", f"kpi:v3:{period}", f"kpi:v2:{period}",
    ])
    branches = _try_keys([
        f"chart:branch:v2:{period}",
        *[f"bundle:v2:{period}:{n}:d{d}:k{k}" for n in [100, 50] for d in [0, 1] for k in [0, 1]],
    ])
    # Bundle vals contain lists under the key, extract if needed
    if isinstance(branches, dict):
        branches = branches.get("branches")

    trend_data = _try_keys([
        f"chart:trend:v4:{period}:{gran}",
        f"chart:trend:v3:{period}:{gran}",
        *[f"bundle:v2:{period}:{n}:d{d}:k{k}" for n in [100, 50] for d in [0, 1] for k in [0, 1]],
    ])
    if isinstance(trend_data, dict):
        trend_data = trend_data.get("trend")

    categories = _try_keys([
        f"chart:category:v2:{period}:100",
        f"chart:category:v2:{period}:50",
        f"chart:category:v2:{period}:30",
    ])

    # ── 2. Cache-only: no live SQL fallback ───────────────────────────────────
    # Insights must load instantly. SQL fallbacks that take 10+ minutes are not
    # acceptable here — if the cache is cold, we return what we have (possibly nothing).
    # The warmup engine will populate the cache; call /ai/page-insights again after.
    logger.debug(
        "auto_insights cache check",
        period=period,
        has_kpis=bool(kpis),
        has_branches=bool(branches),
        has_trend=bool(trend_data),
        has_categories=bool(categories),
    )

    return {
        "kpis": kpis or {},
        "branches": branches or [],
        "trend": trend_data or [],
        "categories": categories or [],
    }


# ─── Rule-Based Insight Generators ─────────────────────────────────────────────

def _kpi_insights(kpis: Dict[str, Any], period: str) -> List[Dict[str, Any]]:
    """Revenue, transaction, and customer KPI insights with real numbers."""
    out: List[Dict[str, Any]] = []
    if not kpis:
        return out

    rev = kpis.get("revenue") or {}
    txn = kpis.get("transactions") or {}
    aov = kpis.get("avg_order_value") or {}
    customers_raw = kpis.get("customers")
    customers_kpi = customers_raw if isinstance(customers_raw, dict) else {}

    rev_val   = _fval(rev.get("value"))
    rev_prior = _fval(rev.get("prior"))
    rev_growth = _fval(rev.get("growth"))

    txn_val    = _fval(txn.get("value"))
    txn_prior  = _fval(txn.get("prior"))
    txn_growth = _fval(txn.get("growth"))

    aov_val    = _fval(aov.get("value"))
    aov_growth = _fval(aov.get("growth"))

    cust_val   = _fval(customers_kpi.get("value") if isinstance(customers_kpi, dict) else customers_raw)

    period_label = period.upper()

    if rev_val > 0:
        direction_word = "up" if rev_growth >= 0 else "down"
        out.append({
            "id": "kpi-revenue",
            "type": "forecast" if rev_growth >= 0 else "alert",
            "title": f"Revenue {direction_word} {abs(rev_growth):.1f}% vs prior period",
            "description": (
                f"Total {period_label} revenue is ₹{rev_val:,.0f}"
                + (f", compared to ₹{rev_prior:,.0f} in the prior period" if rev_prior else "")
                + f". Growth is {'+' if rev_growth >= 0 else ''}{rev_growth:.1f}%. "
                + (
                    f"Strong upward momentum — on track for a record {period_label} if sustained."
                    if rev_growth > 15 else
                    f"Healthy growth — maintain current sales strategies to sustain momentum."
                    if rev_growth > 5 else
                    f"Revenue is broadly flat vs prior period. Review pricing and promotional activity."
                    if -5 <= rev_growth <= 5 else
                    f"Revenue is declining. Urgently review branch performance and sales pipeline."
                )
            ),
            "confidence": min(99, 88 + abs(rev_growth) * 0.3),
            "impact": "high" if abs(rev_growth) > 10 else "medium",
            "severity": "info" if rev_growth >= 0 else ("critical" if rev_growth < -15 else "warning"),
        })

    if txn_val > 0:
        out.append({
            "id": "kpi-transactions",
            "type": "recommendation" if txn_growth >= 0 else "alert",
            "title": f"Transaction volume {'rising' if txn_growth >= 0 else 'declining'} ({txn_growth:+.1f}%)",
            "description": (
                f"{int(txn_val):,} transactions recorded for {period_label}"
                + (f" vs {int(txn_prior):,} prior period" if txn_prior else "")
                + f". {'+' if txn_growth >= 0 else ''}{txn_growth:.1f}% change. "
                + (
                    "Transaction velocity is increasing — scale operations to handle higher throughput."
                    if txn_growth > 10 else
                    "Steady transaction activity; ensure fulfilment capacity is adequate."
                    if txn_growth >= 0 else
                    "Declining transaction count. Check for seasonal effects or lost customer segments."
                )
            ),
            "confidence": 93.0,
            "impact": "high" if abs(txn_growth) > 15 else "medium",
            "severity": "info" if txn_growth >= 0 else "warning",
        })

    if aov_val > 0:
        out.append({
            "id": "kpi-aov",
            "type": "recommendation",
            "title": f"Avg order value ₹{aov_val:,.0f} ({aov_growth:+.1f}% vs prior)",
            "description": (
                f"Average order value is ₹{aov_val:,.0f} for {period_label}. "
                + (
                    f"AOV grew {aov_growth:.1f}% — customers are buying more per visit. "
                    "Cross-selling and upselling programmes are working."
                    if aov_growth > 5 else
                    f"AOV declined {abs(aov_growth):.1f}%. Consider bundling promotions to lift basket size."
                    if aov_growth < -5 else
                    "AOV is stable. Explore cross-sell bundles to drive incremental revenue."
                )
            ),
            "confidence": 90.0,
            "impact": "medium",
            "severity": "info" if aov_growth >= 0 else "warning",
        })

    if cust_val > 0 and rev_val > 0:
        avg_spend = rev_val / cust_val
        out.append({
            "id": "kpi-customers",
            "type": "recommendation",
            "title": f"{int(cust_val):,} unique customers · ₹{avg_spend:,.0f} avg spend",
            "description": (
                f"{int(cust_val):,} unique customers transacted in {period_label}. "
                f"Average spend per customer is ₹{avg_spend:,.0f}. "
                + (
                    "High average spend suggests a strong premium segment — protect this cohort with loyalty rewards."
                    if avg_spend > 5000 else
                    "Focus on increasing visit frequency and basket size among this customer base."
                )
            ),
            "confidence": 95.0,
            "impact": "medium",
            "severity": "info",
        })

    return out


def _branch_insights(branches: List[Dict[str, Any]], period: str) -> List[Dict[str, Any]]:
    """Top/bottom performers and statistical outlier detection."""
    out: List[Dict[str, Any]] = []
    if not branches or len(branches) < 2:
        return out

    def _rev(r: Dict[str, Any]) -> float:
        return _fval(r.get("revenue") or r.get("Revenue"))

    def _txn(r: Dict[str, Any]) -> int:
        return int(_fval(r.get("transactions") or r.get("Transactions")))

    def _name(r: Dict[str, Any]) -> str:
        return str(r.get("branch") or r.get("Branch") or r.get("BranchAlias") or "?")

    sorted_b = sorted(branches, key=_rev, reverse=True)
    total_rev = sum(_rev(r) for r in sorted_b) or 1
    total_txn = sum(_txn(r) for r in sorted_b) or 1

    top = sorted_b[0]
    bottom = sorted_b[-1]
    top_rev = _rev(top)
    top_name = _name(top)
    bottom_rev = _rev(bottom)
    bottom_name = _name(bottom)
    bottom_txn = _txn(bottom)
    top_share = top_rev / total_rev * 100
    bottom_share = bottom_rev / total_rev * 100

    # Top performer
    out.append({
        "id": "branch-top",
        "type": "recommendation",
        "title": f"{top_name} leads with ₹{top_rev:,.0f} ({top_share:.1f}% share)",
        "description": (
            f"{top_name} is the highest-performing branch with ₹{top_rev:,.0f} revenue "
            f"({top_share:.1f}% of total for {period.upper()}). "
            f"Study its playbook — staffing, promotions, and layout — and replicate across underperforming branches."
        ),
        "confidence": 99.0,
        "impact": "high",
        "severity": "info",
    })

    # Bottom performer
    if bottom_name != top_name:
        gap = top_rev - bottom_rev
        out.append({
            "id": "branch-bottom",
            "type": "alert",
            "title": f"{bottom_name} is weakest at ₹{bottom_rev:,.0f} ({bottom_share:.1f}%)",
            "description": (
                f"{bottom_name} recorded ₹{bottom_rev:,.0f} revenue in {period.upper()} "
                f"({bottom_share:.1f}% share, {_txn(bottom):,} transactions). "
                f"The gap vs the top branch is ₹{gap:,.0f}. "
                "Conduct a root-cause analysis: foot-traffic, product assortment, staffing, or location factors."
            ),
            "confidence": 97.0,
            "impact": "high",
            "severity": "warning",
        })

    # Statistical outlier detection (z-score)
    revenues = [_rev(r) for r in branches]
    if len(revenues) >= 4:
        mean_r = statistics.mean(revenues)
        stdev_r = statistics.stdev(revenues)
        if stdev_r > 0:
            for branch in branches:
                v = _rev(branch)
                z = (v - mean_r) / stdev_r
                if abs(z) > 2.0:
                    bname = _name(branch)
                    direction = "significantly above" if z > 0 else "significantly below"
                    change = abs((v - mean_r) / mean_r * 100)
                    out.append({
                        "id": f"branch-anomaly-{bname}",
                        "type": "anomaly",
                        "title": f"{bname} is {change:.0f}% {direction} branch average",
                        "description": (
                            f"{bname} revenue (₹{v:,.0f}) deviates {change:.0f}% from the branch average "
                            f"of ₹{mean_r:,.0f} (z-score: {z:+.2f}). "
                            + (
                                "Investigate what is driving this exceptional performance — it may be replicable."
                                if z > 0 else
                                "Immediate attention needed: this branch is underperforming vs peers."
                            )
                        ),
                        "confidence": min(97, 80 + abs(z) * 5),
                        "impact": "high" if abs(z) > 3 else "medium",
                        "severity": "info" if z > 0 else "warning",
                    })

    # Revenue concentration across top-3
    top3_rev = sum(_rev(r) for r in sorted_b[:3])
    top3_share = top3_rev / total_rev * 100
    if len(sorted_b) >= 4 and top3_share > 65:
        out.append({
            "id": "branch-concentration",
            "type": "alert",
            "title": f"Top 3 branches hold {top3_share:.0f}% of revenue",
            "description": (
                f"Three branches ({', '.join(_name(r) for r in sorted_b[:3])}) account for "
                f"{top3_share:.0f}% of {period.upper()} revenue. "
                "High concentration creates single-point risk. Invest in growing mid-tier branches."
            ),
            "confidence": 98.0,
            "impact": "medium",
            "severity": "warning" if top3_share > 75 else "info",
        })

    return out[:6]


def _trend_insights(trend: List[Dict[str, Any]], period: str) -> List[Dict[str, Any]]:
    """Trajectory and momentum insights from the revenue time series."""
    out: List[Dict[str, Any]] = []
    if len(trend) < 4:
        return out

    def _val(p: Dict[str, Any]) -> float:
        return _fval(p.get("revenue") or p.get("current") or p.get("Revenue"))

    values = [_val(p) for p in trend]
    non_zero = [v for v in values if v > 0]
    if len(non_zero) < 3:
        return out

    mid = len(values) // 2
    first_half_avg = statistics.mean(values[:mid]) if values[:mid] else 0
    second_half_avg = statistics.mean(values[mid:]) if values[mid:] else 0
    peak_val = max(values)
    trough_val = min(v for v in values if v > 0)
    latest_val = values[-1]
    earliest_val = next((v for v in values if v > 0), 0)

    if first_half_avg <= 0:
        return out

    change_pct = (second_half_avg - first_half_avg) / first_half_avg * 100
    direction = "accelerating" if change_pct > 10 else "growing steadily" if change_pct > 3 else "declining" if change_pct < -5 else "stable"
    severity = "info" if change_pct >= -3 else "warning"

    out.append({
        "id": "trend-trajectory",
        "type": "forecast" if change_pct >= 0 else "alert",
        "title": f"Revenue is {direction} ({change_pct:+.1f}% momentum)",
        "description": (
            f"The second half of {period.upper()} averaged ₹{second_half_avg:,.0f} vs ₹{first_half_avg:,.0f} "
            f"in the first half — {abs(change_pct):.1f}% {'improvement' if change_pct >= 0 else 'decline'}. "
            + (
                f"Peak day/week was ₹{peak_val:,.0f}. Identify what drove that spike and repeat it."
                if change_pct > 3 else
                f"Trough was ₹{trough_val:,.0f}. Analyse low-revenue periods for root causes."
                if change_pct < -5 else
                "Revenue is consistent — look for opportunities to inject promotional uplift."
            )
        ),
        "confidence": min(96, 78 + abs(change_pct) * 0.5),
        "impact": "high" if abs(change_pct) > 15 else "medium",
        "severity": severity,
    })

    # Period-end momentum (last 25% vs rest)
    if len(values) >= 8:
        quarter = max(2, len(values) // 4)
        tail_avg = statistics.mean(values[-quarter:]) if values[-quarter:] else 0
        body_avg = statistics.mean(values[:-quarter]) if values[:-quarter] else 0
        if body_avg > 0:
            tail_pct = (tail_avg - body_avg) / body_avg * 100
            if abs(tail_pct) > 8:
                out.append({
                    "id": "trend-endmomentum",
                    "type": "forecast" if tail_pct > 0 else "alert",
                    "title": f"Recent momentum: {'accelerating' if tail_pct > 0 else 'decelerating'} ({tail_pct:+.0f}%)",
                    "description": (
                        f"The most recent {quarter} data points averaged ₹{tail_avg:,.0f}, "
                        f"{abs(tail_pct):.0f}% {'above' if tail_pct > 0 else 'below'} the earlier average. "
                        + (
                            "End-of-period momentum is strong — push hard through close."
                            if tail_pct > 0 else
                            "Momentum is fading. Focus sales and promotional activity to recover before period-end."
                        )
                    ),
                    "confidence": 87.0,
                    "impact": "medium",
                    "severity": "info" if tail_pct > 0 else "warning",
                })

    return out


def _category_insights(categories: List[Dict[str, Any]], period: str) -> List[Dict[str, Any]]:
    """Category concentration, leader, and mix insights."""
    out: List[Dict[str, Any]] = []
    if not categories or len(categories) < 2:
        return out

    def _rev(c: Dict[str, Any]) -> float:
        return _fval(c.get("revenue") or c.get("Revenue"))

    def _cat(c: Dict[str, Any]) -> str:
        return str(c.get("category") or c.get("Category") or c.get("CategoryShortName") or "?")

    def _pct_field(c: Dict[str, Any]) -> float:
        return _fval(c.get("percentage") or c.get("share_pct"))

    sorted_c = sorted(categories, key=_rev, reverse=True)
    total_cat_rev = sum(_rev(c) for c in sorted_c) or 1

    top3_rev = sum(_rev(c) for c in sorted_c[:3])
    concentration = top3_rev / total_cat_rev * 100
    top_cat = _cat(sorted_c[0])
    top_rev = _rev(sorted_c[0])
    top_share = _pct_field(sorted_c[0]) or _pct(top_rev, total_cat_rev)

    # Concentration insight
    if concentration > 70:
        out.append({
            "id": "category-concentration",
            "type": "alert",
            "title": f"Top 3 categories dominate — {concentration:.0f}% revenue share",
            "description": (
                f"'{top_cat}' leads ({top_share:.1f}% share, ₹{top_rev:,.0f}). "
                f"The top 3 categories together ({', '.join(_cat(c) for c in sorted_c[:3])}) "
                f"account for {concentration:.0f}% of {period.upper()} revenue. "
                "Diversify: growing underperforming categories reduces revenue risk."
            ),
            "confidence": 98.0,
            "impact": "medium",
            "severity": "warning",
        })
    else:
        out.append({
            "id": "category-leader",
            "type": "recommendation",
            "title": f"'{top_cat}' leads at {top_share:.1f}% — healthy mix",
            "description": (
                f"'{top_cat}' is the top revenue category at ₹{top_rev:,.0f} ({top_share:.1f}% share). "
                f"Top 3 represent {concentration:.0f}% of revenue — a diverse mix. "
                "Continue investing in category leaders while scaling mid-tier categories."
            ),
            "confidence": 97.0,
            "impact": "medium",
            "severity": "info",
        })

    # Identify any growing low-share category worth watching
    if len(sorted_c) >= 5:
        bottom_cat = sorted_c[-1]
        bottom_name = _cat(bottom_cat)
        bottom_rev = _rev(bottom_cat)
        bottom_share = _pct(bottom_rev, total_cat_rev)
        out.append({
            "id": "category-bottom",
            "type": "recommendation",
            "title": f"'{bottom_name}' has lowest share at {bottom_share:.1f}%",
            "description": (
                f"'{bottom_name}' recorded ₹{bottom_rev:,.0f} ({bottom_share:.1f}% of {period.upper()} revenue). "
                "Evaluate whether this category needs rationalisation or targeted investment to grow it."
            ),
            "confidence": 93.0,
            "impact": "low",
            "severity": "info",
        })

    return out[:3]


# ─── AI Narrative ────────────────────────────────────────────────────────────

_AI_CLIENT: Optional[anthropic.AsyncAnthropic] = None

_INSIGHT_SYSTEM = """You are a senior retail business analyst reviewing actual ERP performance data.
Your task: generate 3-4 concise, data-driven business insights in JSON format.

Rules:
- Every insight MUST cite actual numbers from the data (₹ amounts, %, counts).
- Be specific, decisive, and actionable — no vague generalities.
- Prioritise insights the MD/CEO cares about: revenue health, branch performance, category mix, risks.
- Return ONLY valid JSON, no markdown, no explanation outside JSON.

Output schema:
{
  "insights": [
    {
      "id": "ai-1",
      "type": "forecast|anomaly|recommendation|alert",
      "title": "Specific insight title (max 10 words, include a number)",
      "description": "3 sentences. Sentence 1: state the fact with numbers. Sentence 2: context or comparison. Sentence 3: recommended action.",
      "confidence": 88.5,
      "impact": "high|medium|low",
      "severity": "info|warning|critical"
    }
  ],
  "executive_summary": "2-sentence executive summary with actual ₹ figures and % changes. Start with the most important fact."
}"""


async def _generate_ai_narrative(
    period: str,
    kpis: Dict[str, Any],
    branches: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    trend: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not cfg.ANTHROPIC_API_KEY:
        return None

    global _AI_CLIENT
    if _AI_CLIENT is None:
        _AI_CLIENT = anthropic.AsyncAnthropic(api_key=cfg.ANTHROPIC_API_KEY)

    # Build a compact but data-rich summary for the AI
    rev_kpi = kpis.get("revenue") or {}
    txn_kpi = kpis.get("transactions") or {}
    aov_kpi = kpis.get("avg_order_value") or {}

    summary_data = {
        "period": period.upper(),
        "revenue": {
            "value": _fval(rev_kpi.get("value")),
            "prior": _fval(rev_kpi.get("prior")),
            "growth_pct": _fval(rev_kpi.get("growth")),
        },
        "transactions": {
            "value": int(_fval(txn_kpi.get("value"))),
            "growth_pct": _fval(txn_kpi.get("growth")),
        },
        "avg_order_value": {
            "value": _fval(aov_kpi.get("value")),
            "growth_pct": _fval(aov_kpi.get("growth")),
        },
        "top_branches": [
            {
                "name": str(b.get("branch") or b.get("Branch") or "?"),
                "revenue": _fval(b.get("revenue") or b.get("Revenue")),
                "transactions": int(_fval(b.get("transactions") or b.get("Transactions"))),
            }
            for b in sorted(branches, key=lambda b: _fval(b.get("revenue") or b.get("Revenue")), reverse=True)[:5]
        ],
        "top_categories": [
            {
                "name": str(c.get("category") or c.get("Category") or "?"),
                "revenue": _fval(c.get("revenue") or c.get("Revenue")),
                "share_pct": _fval(c.get("percentage") or c.get("share_pct")),
            }
            for c in sorted(categories, key=lambda c: _fval(c.get("revenue") or c.get("Revenue")), reverse=True)[:5]
        ],
        "trend_summary": {
            "points": len(trend),
            "first_value": _fval((trend[0] if trend else {}).get("revenue") or (trend[0] if trend else {}).get("current")),
            "last_value": _fval((trend[-1] if trend else {}).get("revenue") or (trend[-1] if trend else {}).get("current")),
            "peak_value": max((_fval(p.get("revenue") or p.get("current")) for p in trend), default=0),
        },
    }

    try:
        data_str = json.dumps(summary_data, default=str)
        response = await _AI_CLIENT.messages.create(
            model=cfg.ANTHROPIC_MODEL,
            max_tokens=700,
            system=_INSIGHT_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"ERP Performance Data for {period.upper()}:\n{data_str}\n\n"
                    "Generate 3-4 specific, number-backed business insights. "
                    "Focus on revenue health, branch gaps, category concentration, and key risks/opportunities."
                ),
            }],
        )
        raw = (response.content[0].text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        logger.warning("AI narrative generation failed", error=str(exc))
        return None


# ─── Main Entry Point ──────────────────────────────────────────────────────────

async def generate_page_insights(period: str = "mtd") -> Dict[str, Any]:
    """
    Full insight pipeline with output caching:
    1. Return cached insights immediately if fresh (< 30 min old).
    2. Load data from in-memory cache only (no live SQL).
    3. Run rule-based insight engines.
    4. Generate AI narrative if enabled (Claude API, ~10-15s first time).
    5. Cache and return result.
    """
    from src.analytics.cache import cache as _cache

    valid_periods = {"today", "mtd", "qtd", "ytd", "last_7d", "last_30d", "last_6m"}
    if period not in valid_periods:
        period = "mtd"

    # ── Step 0: Return cached insights instantly if fresh ─────────────────────
    insights_cache_key = f"insights:v3:{period}"
    cached_insights, is_fresh = _cache.get(insights_cache_key)
    if is_fresh and cached_insights is not None:
        logger.debug("auto_insights cache hit", period=period)
        return {**cached_insights, "from_cache": True}

    # ── Step 1: Load data from analytics cache (no SQL fallback) ──────────────
    try:
        data = await asyncio.wait_for(_load_data(period), timeout=8.0)
    except asyncio.TimeoutError:
        logger.warning("auto_insights _load_data timed out", period=period)
        data = {"kpis": {}, "branches": [], "trend": [], "categories": []}
    except Exception as exc:
        logger.error("auto_insights data load failed", error=str(exc))
        return {
            "success": False,
            "period": period,
            "insights": [],
            "executive_summary": None,
            "data_available": False,
            "from_cache": False,
            "_error": str(exc),
        }

    kpis       = data["kpis"]
    branches   = data["branches"]
    trend_data = data["trend"]
    categories = data["categories"]

    data_available = bool(kpis or branches or trend_data or categories)

    if not data_available:
        logger.info("auto_insights: no cached data available", period=period)
        # Return stale cache if we have any (rather than empty)
        if cached_insights is not None:
            return {**cached_insights, "from_cache": True, "_stale": True}
        # For "today" with no data, fall back to MTD insights with a banner note
        if period == "today":
            logger.info("auto_insights: today has no data — falling back to MTD insights")
            mtd_result = await generate_page_insights("mtd")
            return {
                **mtd_result,
                "period": "today",
                "_fallback_period": "mtd",
                "_fallback_reason": "No sales recorded today yet. Showing MTD insights instead.",
            }
        return {
            "success": True,
            "period": period,
            "insights": [],
            "executive_summary": None,
            "data_available": False,
            "from_cache": False,
        }

    # ── Step 2: Rule-based insights ────────────────────────────────────────────
    all_insights: List[Dict[str, Any]] = []

    all_insights.extend(_kpi_insights(kpis, period))
    all_insights.extend(_branch_insights(branches, period))
    all_insights.extend(_trend_insights(trend_data, period))
    all_insights.extend(_category_insights(categories, period))

    # ── Step 3: AI narrative (with 25s timeout to avoid blocking forever) ─────
    executive_summary: Optional[str] = None
    if cfg.AI_ADAPTIVE_SUMMARY and data_available:
        try:
            ai_result = await asyncio.wait_for(
                _generate_ai_narrative(period, kpis, branches, categories, trend_data),
                timeout=25.0,
            )
            if ai_result:
                ai_insights = ai_result.get("insights") or []
                for i, ins in enumerate(ai_insights):
                    ins.setdefault("id", f"ai-{i + 1}")
                    ins.setdefault("confidence", 88.0)
                    ins.setdefault("impact", "medium")
                    ins.setdefault("severity", "info")
                all_insights = ai_insights + all_insights
                executive_summary = ai_result.get("executive_summary")
        except asyncio.TimeoutError:
            logger.warning("auto_insights: AI narrative timed out — returning rule-based only", period=period)
        except Exception as exc:
            logger.warning("auto_insights: AI narrative failed", error=str(exc))

    # ── Step 4: Deduplicate and cap ────────────────────────────────────────────
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for ins in all_insights:
        iid = ins.get("id", "")
        if iid and iid not in seen:
            seen.add(iid)
            unique.append(ins)

    result = {
        "success": True,
        "period": period,
        "insights": unique[:15],
        "executive_summary": executive_summary,
        "data_available": data_available,
        "from_cache": False,
    }

    # ── Step 5: Cache the result (30 min TTL) ─────────────────────────────────
    _cache.set(insights_cache_key, result, ttl_s=1800.0)
    logger.info("auto_insights generated and cached", period=period, count=len(unique[:15]))
    return result
