"""
SmarterPConnector - FastAPI Main Application
Boot sequence:
  PostgreSQL -> SQL Server -> RBAC init -> FastAPI app -> cache warmup
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.config import cfg
from src.utils.logger import logger
from src.db.postgres import get_pg_pool, close_pg_pool
from src.db.mssql import init_mssql, close_mssql
from src.auth.rbac import init_rbac
from src.analytics.warmup import start_background_warmer, stop_background_warmer
from src.middleware.error import register_error_handlers

# --- Routes -------------------------------------------------------------------
from src.routes.auth import router as auth_router
from src.routes.ai import router as ai_router
from src.routes.analytics import router as analytics_router


# --- Periodic cache flush ------------------------------------------------------

async def _periodic_cache_flush() -> None:
    """
    Every 2 minutes, write all in-memory cache entries to PostgreSQL.
    Ensures that even if the server is restarted mid-warmup, any queries that
    already completed are saved and the next restart loads them instantly.
    """
    FLUSH_INTERVAL_S = 120  # 2 minutes
    await asyncio.sleep(FLUSH_INTERVAL_S)
    while True:
        try:
            if cfg.RBAC_ENABLED and cfg.rbac_url:
                from src.analytics.cache import cache as _analytics_cache
                n = await _analytics_cache.flush_to_pg()
                if n > 0:
                    logger.debug("Periodic cache flush complete", entries=n)
        except Exception as exc:
            logger.warning("Periodic cache flush error", error=str(exc))
        await asyncio.sleep(FLUSH_INTERVAL_S)


# --- Lifespan -----------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("SmarterPConnector API starting up...")

    # 1. PostgreSQL
    if cfg.RBAC_ENABLED and cfg.rbac_url:
        try:
            await get_pg_pool()
            logger.info("PostgreSQL connected")
        except Exception as exc:
            logger.warning("PostgreSQL unavailable - RBAC features disabled", error=str(exc))

    # 2. SQL Server
    try:
        await init_mssql()
    except Exception as exc:
        logger.error("SQL Server connection failed", error=str(exc))

    # 3. RBAC init
    if cfg.RBAC_ENABLED:
        try:
            await init_rbac()
        except Exception as exc:
            logger.warning("RBAC init failed", error=str(exc))

    # 3b. Restore analytics cache from PostgreSQL.
    # First-ever start: cache empty, warmup runs, data writes to PG.
    # Every subsequent restart: PG loads in <200ms, warmup refreshes stale in background.
    # With ANALYTICS_STALE_TTL_MULTIPLIER=96, covers overnight/weekend restarts.
    if cfg.RBAC_ENABLED and cfg.rbac_url:
        try:
            from src.analytics.cache import cache as _analytics_cache
            _n = await _analytics_cache.restore_from_pg()
            if _n > 0:
                logger.info("Cache hot from PostgreSQL -- dashboard data ready", entries=_n)
            else:
                logger.info("Cache cold -- warmup will populate (first run or all expired)")
        except Exception as _exc:
            logger.warning("Cache PG restore skipped", error=str(_exc))

    # 4. Cache warmup (runs in background, refreshes stale PG data)
    await start_background_warmer()

    # 5. Periodic flush -- saves partial warmup results every 2 min.
    # Without this, a restart mid-warmup loses all computed data.
    _flush_task = asyncio.create_task(_periodic_cache_flush())

    logger.info("SmarterPConnector API ready", port=cfg.PORT)

    yield

    # --- Shutdown: flush cache to PG before exiting ---------------------------
    logger.info("SmarterPConnector API shutting down -- saving cache to PostgreSQL...")
    _flush_task.cancel()
    try:
        await _flush_task
    except asyncio.CancelledError:
        pass
    if cfg.RBAC_ENABLED and cfg.rbac_url:
        try:
            from src.analytics.cache import cache as _analytics_cache
            saved = await _analytics_cache.flush_to_pg()
            logger.info("Cache saved on shutdown", entries=saved)
        except Exception as exc:
            logger.warning("Cache flush on shutdown failed", error=str(exc))
    await stop_background_warmer()
    await close_mssql()
    try:
        await close_pg_pool()
    except Exception:
        pass
    logger.info("Shutdown complete")


# --- App ----------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="SmarterPConnector API",
        description="AI-powered ERP analytics intelligence engine",
        version="2.0.0",
        docs_url="/docs" if cfg.is_dev else None,
        redoc_url="/redoc" if cfg.is_dev else None,
        lifespan=lifespan,
    )

    from src.utils.logger import make_request_logger
    app.add_middleware(make_request_logger())
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    app.include_router(auth_router)
    app.include_router(ai_router)
    app.include_router(analytics_router)

    @app.get("/", include_in_schema=False)
    async def root() -> Dict[str, Any]:
        return {
            "product": "SmarterPConnector",
            "version": "2.0.0",
            "status": "operational",
            "docs": "/docs" if cfg.is_dev else None,
        }

    @app.get("/health", include_in_schema=False)
    async def health() -> Dict[str, Any]:
        from src.analytics.warmup import is_warmup_running, is_warmup_complete
        from src.db.mssql import check_mssql_health

        mssql = await check_mssql_health()
        if mssql.get("busy"):
            status = "busy"
        elif mssql.get("connected"):
            status = "healthy"
        else:
            status = "degraded"
        if is_warmup_running() and status == "healthy":
            status = "busy"
        warehouse = {
            "erp_database": (cfg.mssql_database or "").strip(),
            "analytics_line_table": (cfg.ANALYTICS_BASE_TABLE or "").strip(),
            "sales_ai_table": (cfg.SALES_AI_TABLE or "").strip(),
            "sales_view": "dbo.VW_MB_POWERBI_APP_REPORT",
            "transactions_view": "dbo.VW_MB_POWERBI_SLSXNS_REPORT",
            "schema_catalog_objects": 28,
        }
        return {
            "status": status,
            "mssql": mssql,
            "warmup": {"running": is_warmup_running(), "complete": is_warmup_complete()},
            "warehouse": warehouse,
        }

    return app


app = create_app()


# --- Entry Point --------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=cfg.PORT,
        reload=cfg.is_dev,
        log_level="info",
        access_log=cfg.is_dev,
        proxy_headers=cfg.TRUST_PROXY,
        forwarded_allow_ips="*" if cfg.TRUST_PROXY else None,
    )
