"""
Populate per-chart cache keys from a bundle payload so /analytics/branches etc.
are instant after /analytics/bundle or warmup — split-mode clients benefit too.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.config import cfg
from src.analytics.cache import cache
from src.utils.date_utils import trend_granularity


def assemble_bundle_from_chart_caches(
    period: str,
    top_n: int,
    *,
    include_kpis: bool = False,
    include_departments: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    If branches/trend/categories (+ optional kpis/depts) are already cached, build a bundle
    without hitting SQL — same speed as a warm bundle:v2 cache hit.
    """
    n = min(top_n, cfg.ANALYTICS_TOP_N_MAX)
    gran = trend_granularity(period)
    specs: list[tuple[str, str, bool]] = [
        ("branches", f"chart:branch:v2:{period}", True),
        ("trend", f"chart:trend:v4:{period}:{gran}", True),
        ("categories", f"chart:category:v2:{period}:{n}", True),
        ("kpis", f"kpi:v3:{period}", include_kpis),
        ("departments", f"chart:department:v3:{period}:{n}", include_departments),
    ]
    payload: Dict[str, Any] = {}
    for name, key, required in specs:
        if not required:
            continue
        val, _ = cache.get(key)
        if val is None:
            return None
        payload[name] = val
    return payload


def prime_chart_caches_from_bundle(
    period: str,
    payload: Dict[str, Any],
    *,
    top_n: Optional[int] = None,
) -> None:
    """Write-through chart/kpi cache entries (no SQL)."""
    n = min(top_n or cfg.ANALYTICS_TOP_N_MAX, cfg.ANALYTICS_TOP_N_MAX)
    gran = trend_granularity(period)

    if payload.get("branches") is not None:
        cache.set(f"chart:branch:v2:{period}", payload["branches"])
    if payload.get("trend") is not None:
        cache.set(f"chart:trend:v4:{period}:{gran}", payload["trend"])
    if payload.get("categories") is not None:
        cache.set(f"chart:category:v2:{period}:{n}", payload["categories"])
    if payload.get("departments") is not None:
        cache.set(f"chart:department:v3:{period}:{n}", payload["departments"])
    if payload.get("kpis") is not None:
        cache.set(f"kpi:v3:{period}", payload["kpis"])
