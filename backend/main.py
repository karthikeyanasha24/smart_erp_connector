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
from src.db.mssql import init_mssql, close_mssql
from src.middleware.error import register_error_handlers
from src.spa_static import register_spa_static

# --- Routes -------------------------------------------------------------------
from src.routes.auth import router as auth_router
from src.routes.ai import router as ai_router
from src.routes.analytics import router as analytics_router


# --- Lifespan -----------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("SmarterPConnector API starting up...")

    try:
        await init_mssql()
        logger.info("SQL Server connected")
    except Exception as exc:
        logger.error("SQL Server connection failed", error=str(exc))

    # Auto-configure analytics from schema index (built by build_schema_index.py)
    try:
        from src.analytics.schema_router import patch_config_from_index, available, route
        if available():
            applied = patch_config_from_index()
            if applied:
                r = route("sales_main")
                logger.info(
                    "Schema index loaded — analytics auto-configured",
                    view=r["view"],
                    date_col=r["date_col"],
                    amount_col=r["amount_col"],
                    quantity_col=r["quantity_col"],
                    mtd_rows=r.get("mtd_rows"),
                )
            else:
                logger.warning("Schema index present but patch_config failed — using .env values")
        else:
            logger.warning(
                "schema_index.json not found — using .env config. "
                "Run: python scripts/build_schema_index.py to auto-configure."
            )
    except Exception as exc:
        logger.error("Schema index load failed", error=str(exc))

    logger.info("SmarterPConnector API ready — live SQL queries, no cache", port=cfg.PORT)

    yield

    await close_mssql()
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

    @app.get("/health", include_in_schema=False)
    async def health() -> Dict[str, Any]:
        from src.db.mssql import check_mssql_health
        mssql = await check_mssql_health()
        status = "healthy" if mssql.get("connected") else "degraded"
        return {
            "status": status,
            "mssql": mssql,
            "mode": "live",
        }

    spa_enabled = register_spa_static(app)

    if not spa_enabled:

        @app.head("/", include_in_schema=False)
        async def root_head() -> Dict[str, Any]:
            from fastapi.responses import Response
            return Response(status_code=200)

        @app.get("/", include_in_schema=False)
        async def root() -> Dict[str, Any]:
            return {
                "product": "SmarterPConnector",
                "version": "2.0.0",
                "status": "operational",
                "docs": "/docs" if cfg.is_dev else None,
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
