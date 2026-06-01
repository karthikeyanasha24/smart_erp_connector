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
from src.analytics.warmup import start_background_warmer, stop_background_warmer

# --- Legal page content -------------------------------------------------------

_LEGAL_CSS = """
  body{font-family:system-ui,sans-serif;max-width:720px;margin:60px auto;padding:0 24px;color:#1e293b;line-height:1.7}
  h1{color:#4f46e5;font-size:1.8rem;margin-bottom:4px}
  h2{color:#334155;font-size:1.1rem;margin-top:32px}
  p,li{color:#475569}
  a{color:#4f46e5}
  .badge{display:inline-block;background:#eef2ff;color:#4f46e5;padding:2px 10px;border-radius:20px;font-size:.8rem;margin-bottom:24px}
"""

_PRIVACY_HTML = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Privacy Policy — SmarterP ERP for Sheets</title>
<style>{_LEGAL_CSS}</style></head><body>
<h1>Privacy Policy</h1>
<span class="badge">SmarterP ERP for Sheets</span>
<p>Last updated: June 2026</p>
<h2>1. Data We Access</h2>
<p>SmarterP ERP for Sheets accesses only the Google Sheet you are actively working in (<code>spreadsheets.currentonly</code> scope). We do not access any other files in your Google Drive.</p>
<h2>2. Data We Collect</h2>
<p>The add-on connects to your own SmarterP ERP server using credentials you provide. We do not store, transmit, or share your ERP data with any third party. All data flows directly between your browser and your own server.</p>
<h2>3. Authentication</h2>
<p>Your SmarterP username and password are stored securely in Google Apps Script's PropertiesService, scoped to your account only. They are never sent to our servers.</p>
<h2>4. External Requests</h2>
<p>The add-on makes HTTP requests exclusively to the SmarterP server URL you configure. No data is sent to any other endpoint.</p>
<h2>5. Contact</h2>
<p>For privacy questions: <a href="mailto:officialwork24ak@gmail.com">officialwork24ak@gmail.com</a></p>
</body></html>"""

_TERMS_HTML = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Terms of Service — SmarterP ERP for Sheets</title>
<style>{_LEGAL_CSS}</style></head><body>
<h1>Terms of Service</h1>
<span class="badge">SmarterP ERP for Sheets</span>
<p>Last updated: June 2026</p>
<h2>1. Acceptance</h2>
<p>By installing SmarterP ERP for Sheets, you agree to these terms. If you do not agree, do not install the add-on.</p>
<h2>2. Use of the Add-on</h2>
<p>This add-on is designed for use with a valid SmarterP ERP account. You are responsible for maintaining the security of your credentials.</p>
<h2>3. No Warranty</h2>
<p>The add-on is provided "as is" without warranty of any kind. We are not liable for any data loss or business disruption arising from use of this add-on.</p>
<h2>4. Modifications</h2>
<p>We reserve the right to modify or discontinue the add-on at any time. Continued use after changes constitutes acceptance of the updated terms.</p>
<h2>5. Contact</h2>
<p>For support: <a href="https://smarterpconnector.in">smarterpconnector.in</a> · <a href="mailto:officialwork24ak@gmail.com">officialwork24ak@gmail.com</a></p>
</body></html>"""


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

    # Preload NLQ schema (file cache or live INFORMATION_SCHEMA)
    try:
        from src.ai.db_chat_pipeline import load_snapshot

        nlq_snap = await load_snapshot()
        logger.info(
            "NLQ schema ready",
            views=len(nlq_snap.get("objects", {})),
            source="cache" if nlq_snap.get("snapshotted_at") else "live",
        )
    except Exception as exc:
        logger.warning("NLQ schema preload failed — AI Query may not work", error=str(exc))

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

    # Restore in-memory analytics cache from PostgreSQL (if available), then warm in background.
    try:
        from src.analytics.cache import cache
        restored = await cache.restore_from_pg()
        if restored:
            logger.info("Analytics cache restored from PostgreSQL", entries=restored)
    except Exception as exc:
        logger.warning("Analytics cache restore skipped", error=str(exc))

    await start_background_warmer()
    logger.info("SmarterPConnector API ready", port=cfg.PORT, warmup=cfg.ANALYTICS_WARMUP)

    yield

    await stop_background_warmer()
    try:
        from src.analytics.cache import cache
        await cache.flush_to_pg()
    except Exception:
        pass

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

    # ── Legal pages for Google Workspace Marketplace listing ──────────────────
    from fastapi.responses import HTMLResponse

    @app.get("/privacy", include_in_schema=False)
    async def privacy_policy() -> HTMLResponse:
        return HTMLResponse(_PRIVACY_HTML)

    @app.get("/terms", include_in_schema=False)
    async def terms_of_service() -> HTMLResponse:
        return HTMLResponse(_TERMS_HTML)

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
