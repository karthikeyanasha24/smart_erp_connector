"""
Cache Warmup Engine
Pre-populates the analytics cache on startup and periodically thereafter.
This ensures the first user request gets fast cached data, not a cold SQL Server hit.
"""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine

from src.config import cfg
from src.utils.logger import logger
from src.analytics.cache import cache
from src.analytics.cache_prime import prime_chart_caches_from_bundle
from src.analytics.concurrency import run_warmup_sql


_warmup_running = False
_warmup_complete = False


def is_warmup_running() -> bool:
    return _warmup_running


def is_warmup_complete() -> bool:
    return _warmup_complete


# --- Warmup Tasks -------------------------------------------------------------

async def warmup_all() -> None:
    """
    Warm cache in parallel phases so critical data is ready fast.

    Phase 0: KPIs for today + MTD in parallel (fast, needed for login KPI cards).
    Phase 1: bundles + dashboards for today/MTD in parallel (charts + full dashboard).
    Phase 2: last_30d charts + dashboards in parallel (Analytics page default period).
    Phase 3: QTD + YTD in parallel (slow but run together - bottleneck is SQL I/O).

    The ANALYTICS_SQL_SEM semaphore (concurrency.py) caps concurrent SQL queries at 3,
    so parallel phases do not overload SQL Server -- tasks queue behind the semaphore.
    Each phase awaits completion before the next starts, so critical data (Phase 0)
    is always cached before heavier scans begin.
    """
    global _warmup_running, _warmup_complete

    from src.analytics.dashboard import get_dashboard
    from src.analytics.kpi import get_home_kpis
    from src.analytics.charts import (
        get_revenue_trend,
        get_category_breakdown,
        get_branch_chart,
        get_department_chart,
        get_top_salespersons,
    )

    _warmup_running = True
    _t0 = __import__('time').perf_counter()

    async def _safe(name: str, coro: Coroutine[Any, Any, Any]) -> None:
        t = __import__('time').perf_counter()
        try:
            await coro
            elapsed = round((__import__('time').perf_counter() - t) * 1000)
            logger.info("Cache warmed", key=name, ms=elapsed)
        except Exception as exc:
            logger.warning("Cache warmup task failed", task=name, error=str(exc))

    async def _flush(label: str) -> None:
        """Persist all cached entries to PG right after each phase completes.
        This means even if the server is restarted mid-warmup, the completed
        phases are already saved and the next restart loads them instantly."""
        try:
            n = await cache.flush_to_pg()
            logger.info(f"Cache persisted to PG after {label}", entries=n)
        except Exception as exc:
            logger.warning(f"PG flush after {label} failed", error=str(exc))

    try:
        # Kick off the slow product catalog fetch as a background task immediately —
        # it takes ~7 min cold so we start it now and await it at the end of Phase 3.
        # This way it runs in parallel with all dashboard phases instead of blocking them.
        from src.analytics.products_catalog import fetch_product_catalog, fetch_top_products
        _products_task = asyncio.create_task(
            _safe("products:catalog", fetch_product_catalog(limit=50, offset=0))
        )
        _top_products_task = asyncio.create_task(
            _safe("products:top:mtd", fetch_top_products("mtd", 15))
        )
        logger.info("Product catalog warmup started in background (runs alongside all phases)")

        # Phase 0: KPIs (fast -- 2 SQL queries each, cached after ~5-10s)
        logger.info("Cache warmup Phase 0 -- critical KPIs (today + MTD)")
        await asyncio.gather(
            _safe("kpi:today", get_home_kpis("today")),
            _safe("kpi:mtd",   get_home_kpis("mtd")),
        )
        await _flush("Phase 0")
        logger.info(
            "Phase 0 complete -- KPI cards will now load instantly on next restart",
            elapsed_s=round((__import__('time').perf_counter() - _t0), 1),
        )

        # Phase 1: MTD + Today + QTD dashboards + first-page transactions in parallel.
        # QTD is promoted to Phase 1 because it's the 3rd most-used Analytics tab and
        # users expect it to load as fast as MTD. The semaphore (max 3 concurrent SQL
        # queries) ensures SQL Server is not overloaded — extra tasks queue behind it.
        from src.analytics.transactions import get_transactions as _get_txns
        logger.info("Cache warmup Phase 1 -- today/MTD/QTD dashboards + breakdown bundles")
        await asyncio.gather(
            _safe("dashboard:mtd",      get_dashboard("mtd")),
            _safe("dashboard:today",    get_dashboard("today")),
            _safe("dashboard:qtd",      get_dashboard("qtd")),
            _safe("bundle:mtd",         _prime_breakdown_bundle("mtd")),
            _safe("bundle:today",       _prime_breakdown_bundle("today")),
            _safe("bundle:qtd",         _prime_breakdown_bundle("qtd")),
            _safe("kpi:qtd",            get_home_kpis("qtd")),
            _safe("department:mtd",     run_warmup_sql(get_department_chart("mtd"))),
            _safe("department:today",   run_warmup_sql(get_department_chart("today"))),
            _safe("txns:mtd:p1",        run_warmup_sql(_get_txns("mtd",   1, 12))),
            _safe("txns:today:p1",      run_warmup_sql(_get_txns("today", 1, 12))),
        )
        await _flush("Phase 1")
        logger.info(
            "Phase 1 complete -- ALL dashboard charts + QTD load instantly on next restart",
            elapsed_s=round((__import__('time').perf_counter() - _t0), 1),
        )

        # Phase 2: Last-6M (always warm — frequently used Analytics tab)
        # Run in parallel; semaphore caps concurrency so SQL Server is not overloaded.
        logger.info("Cache warmup Phase 2 -- Last-6M (always on)")
        await asyncio.gather(
            _safe("kpi:last_6m",        get_home_kpis("last_6m")),
            _safe("bundle:last_6m",     _prime_breakdown_bundle("last_6m")),
            _safe("dashboard:last_6m",  get_dashboard("last_6m")),
            _safe("department:qtd",     run_warmup_sql(get_department_chart("qtd"))),
        )
        await _flush("Phase 2")

        # Phase 3: last_7d + last_30d + YTD + product catalog background tasks.
        # last_7d and last_30d are always warm now — Transactions and Branch pages use them.
        logger.info("Cache warmup Phase 3 -- last_7d + last_30d + YTD + products")
        await asyncio.gather(
            _safe("kpi:ytd",         get_home_kpis("ytd")),
            _safe("bundle:ytd",      _prime_breakdown_bundle("ytd")),
            _safe("dashboard:ytd",   get_dashboard("ytd")),
            _safe("kpi:last_7d",     get_home_kpis("last_7d")),
            _safe("bundle:last_7d",  _prime_breakdown_bundle("last_7d")),
            _safe("dashboard:last_7d", get_dashboard("last_7d")),
            _products_task,
            _top_products_task,
        )
        await _flush("Phase 3")

        # Phase 4: last_30d (always on, not deep-mode-only — Transactions page needs it)
        logger.info("Cache warmup Phase 4 -- last_30d")
        await asyncio.gather(
            _safe("kpi:last_30d",       get_home_kpis("last_30d")),
            _safe("bundle:last_30d",    _prime_breakdown_bundle("last_30d")),
            _safe("dashboard:last_30d", get_dashboard("last_30d")),
        )
        await _flush("Phase 4")

        if cfg.ANALYTICS_WARMUP_DEEP:
            # Phase 5: deep charts for last_30d (optional)
            logger.info("Cache warmup Phase 5 -- last_30d detailed charts (deep mode)")
            await asyncio.gather(
                _safe("trend:last_30d",      get_revenue_trend("last_30d")),
                _safe("category:last_30d",   get_category_breakdown("last_30d")),
                _safe("branch:last_30d",     get_branch_chart("last_30d")),
                _safe("department:last_30d", get_department_chart("last_30d")),
                _safe("salesperson:last_30d",get_top_salespersons("last_30d")),
            )
            await _flush("Phase 5")
        else:
            logger.info("Deep warmup (Phase 5) skipped -- set ANALYTICS_WARMUP_DEEP=true to enable")

        stats = cache.stats()
        logger.info("Cache warmup complete", **stats)
        _warmup_complete = True
    finally:
        _warmup_running = False


async def _prime_breakdown_bundle(period: str) -> None:
    """Store bundle:v2 (+ per-chart keys) so breakdown scripts and --split hit cache."""
    from src.analytics.kpi import get_home_kpis
    from src.analytics.charts import (
        get_branch_chart,
        get_revenue_trend,
        get_category_breakdown,
        get_department_chart,
    )

    n = min(100, cfg.ANALYTICS_TOP_N_MAX)

    async def _branches() -> Any:
        return await get_branch_chart(period)

    async def _trend() -> Any:
        return await get_revenue_trend(period)

    async def _categories() -> Any:
        return await get_category_breakdown(period, n)

    async def _kpis() -> Any:
        return await get_home_kpis(period)

    async def _departments() -> Any:
        return await get_department_chart(period, n)

    # Lean bundle first (matches test/breakdown_fetch.py -- 3 SQL queries).
    # CancelledError guard: uvicorn hot-reload cancels the gather mid-flight, which leaves
    # inner coroutines never-awaited and logs RuntimeWarning. Shield the gather so
    # cancellation is handled cleanly.
    try:
        branches, trend, categories = await asyncio.gather(
            run_warmup_sql(_branches()),
            run_warmup_sql(_trend()),
            run_warmup_sql(_categories()),
        )
    except asyncio.CancelledError:
        return
    lean = {
        "success": True,
        "period": period,
        "branches": branches,
        "trend": trend,
        "categories": categories,
        "timings_ms": {"warmup": 0},
    }
    cache.set(f"bundle:v2:{period}:{n}:d0:k0", lean)
    prime_chart_caches_from_bundle(period, lean, top_n=n)

    try:
        departments, kpis = await asyncio.gather(
            run_warmup_sql(_departments()),
            run_warmup_sql(_kpis()),
        )
    except asyncio.CancelledError:
        return
    with_depts = {**lean, "departments": departments}
    full = {**with_depts, "kpis": kpis}
    cache.set(f"bundle:v2:{period}:{n}:d1:k0", with_depts)
    cache.set(f"bundle:v2:{period}:{n}:d0:k1", full)
    cache.set(f"bundle:v2:{period}:{n}:d1:k1", full)
    prime_chart_caches_from_bundle(period, full, top_n=n)


# --- Background Warmer --------------------------------------------------------

_warmer_task: asyncio.Task | None = None


async def start_background_warmer() -> None:
    """
    Starts a background task that re-warms the cache at the configured interval.
    Typically called once at application startup.
    """
    global _warmer_task

    if not cfg.ANALYTICS_WARMUP:
        logger.info("Cache warmup disabled")
        return

    async def _loop() -> None:
        # Small startup grace period so the DB pool can establish connections
        # before warmup fires its first queries. Phase 0 (KPIs) runs immediately
        # after this delay; heavy YTD scans only start in Phase 3 -- by then the
        # cache is already warm for all dashboard/KPI requests.
        initial_delay_s = max(0, cfg.ANALYTICS_WARMUP_INITIAL_DELAY_MS) / 1000
        await asyncio.sleep(initial_delay_s)
        await warmup_all()

        interval_s = cfg.ANALYTICS_WARMUP_INTERVAL_MS / 1000
        logger.info("Cache warmer interval", interval_s=interval_s)

        while True:
            await asyncio.sleep(interval_s)
            logger.info("Scheduled cache re-warm triggered")
            await warmup_all()

    _warmer_task = asyncio.create_task(_loop())
    logger.info("Background cache warmer started")


async def stop_background_warmer() -> None:
    global _warmer_task
    if _warmer_task and not _warmer_task.done():
        _warmer_task.cancel()
        try:
            await _warmer_task
        except asyncio.CancelledError:
            pass
    _warmer_task = None
    logger.info("Background cache warmer stopped")
