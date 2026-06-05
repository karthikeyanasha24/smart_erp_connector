"""
Populate per-chart cache keys from a bundle payload so /analytics/branches etc.
are instant after /analytics/bundle or warmup — split-mode clients benefit too.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.config import cfg
from src.analytics.cache import cache
from src.utils.date_utils import trend_granularity, period_cache_key


# Rolling periods where a stale cache hit is treated as a miss so we re-query SQL.
_STALE_MISS_PERIODS = frozenset({"today", "yesterday", "mtd", "last_7d", "last_30d"})


def assemble_bundle_from_chart_caches(
    period: str,
    top_n: int,
    *,
    include_kpis: bool = False,
    include_departments: bool = False,
    force_refresh: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    If branches/trend/categories (+ optional kpis/depts) are already cached, build a bundle
    without hitting SQL — same speed as a warm bundle:v2 cache hit.
    Returns None when force_refresh=True or when any required key is stale for a
    rolling period (so the caller re-queries SQL for up-to-date data).
    """
    if force_refresh:
        return None
    n = min(top_n, cfg.ANALYTICS_TOP_N_MAX)
    gran = trend_granularity(period)
    specs: list[tuple[str, str, bool]] = [
        ("branches", period_cache_key("chart:branch:v2", period), True),
        ("trend", f"{period_cache_key('chart:trend:v4', period)}:{gran}", True),
        ("categories", f"{period_cache_key('chart:category:v2', period)}:{n}", True),
        ("kpis", period_cache_key("kpi:v3", period), include_kpis),
        ("departments", f"{period_cache_key('chart:department:v3', period)}:{n}", include_departments),
    ]
    payload: Dict[str, Any] = {}
    for name, key, required in specs:
        if not required:
            continue
        val, is_fresh = cache.get(key)
        if val is None:
            return None
        # For rolling/intraday periods treat a stale entry as a miss → caller re-queries SQL.
        if not is_fresh and period in _STALE_MISS_PERIODS:
            return None
        payload[name] = val
    return payload


def bundle_cache_fetched_at(
    period: str,
    top_n: int,
    *,
    include_kpis: bool = False,
    include_departments: bool = False,
) -> Optional[float]:
    """Oldest cache write time among bundle chart keys (when served from cache)."""
    n = min(top_n, cfg.ANALYTICS_TOP_N_MAX)
    gran = trend_granularity(period)
    keys: list[str] = [
        period_cache_key("chart:branch:v2", period),
        f"{period_cache_key('chart:trend:v4', period)}:{gran}",
        f"{period_cache_key('chart:category:v2', period)}:{n}",
    ]
    if include_kpis:
        keys.append(period_cache_key("kpi:v3", period))
    if include_departments:
        keys.append(f"{period_cache_key('chart:department:v3', period)}:{n}")
    times = [t for k in keys if (t := cache.get_created_at(k)) is not None]
    return min(times) if times else None


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
        cache.set(period_cache_key("chart:branch:v2", period), payload["branches"])
    if payload.get("trend") is not None:
        cache.set(f"{period_cache_key('chart:trend:v4', period)}:{gran}", payload["trend"])
    if payload.get("categories") is not None:
        cache.set(f"{period_cache_key('chart:category:v2', period)}:{n}", payload["categories"])
    if payload.get("departments") is not None:
        cache.set(f"{period_cache_key('chart:department:v3', period)}:{n}", payload["departments"])
    if payload.get("kpis") is not None:
        cache.set(period_cache_key("kpi:v3", period), payload["kpis"])
