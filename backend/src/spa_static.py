"""
Serve the Vite React build from FastAPI so deep links (/dashboard, /analytics, …)
return index.html instead of 404 when the browser requests them directly.

API routes (/auth, /analytics/*, /ai/*, /health) are unchanged and take priority.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from src.utils.logger import logger


def _is_api_path(path: str) -> bool:
    """True for API/OpenAPI paths (not the React /analytics page)."""
    if path in ("/health", "/openapi.json"):
        return True
    if path.startswith("/auth"):
        return True
    if path.startswith("/ai/"):
        return True
    if path.startswith("/analytics/"):
        return True
    if path.startswith(("/docs", "/redoc")):
        return True
    return False


def find_frontend_dist() -> Optional[Path]:
    """Locate Vite dist: FRONTEND_DIST env, backend/static (Docker), or repo dist/."""
    env = (os.getenv("FRONTEND_DIST") or "").strip()
    if env:
        p = Path(env).resolve()
        if (p / "index.html").is_file():
            logger.info("Frontend dist found via FRONTEND_DIST env", path=str(p))
            return p

    backend_dir = Path(__file__).resolve().parents[1]
    cwd = Path(os.getcwd()).resolve()

    candidates = [
        backend_dir / "static",      # Docker: /app/static
        backend_dir.parent / "dist", # Dev: repo root/dist
        cwd / "static",              # CWD-relative: /app/static
        cwd / "dist",                # CWD-relative: dist
        Path("/app/static"),         # Absolute Docker path
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            logger.info("Found frontend dist", path=str(candidate))
            return candidate.resolve()

    logger.warning(
        "Frontend dist not found — SPA routing disabled. "
        "Set FRONTEND_DIST env var to the path of the Vite build output.",
        checked=[str(c) for c in candidates],
    )
    return None


def _safe_file(dist: Path, url_path: str) -> Optional[Path]:
    rel = url_path.lstrip("/")
    if not rel or rel.endswith("/"):
        return None
    try:
        target = (dist / rel).resolve()
        dist_resolved = dist.resolve()
        if not str(target).startswith(str(dist_resolved)):
            return None
        return target if target.is_file() else None
    except (OSError, ValueError):
        return None


def register_spa_static(app: FastAPI) -> bool:
    """
    Mount built frontend when dist exists and SERVE_FRONTEND is not disabled.
    Returns True if SPA routes were registered.
    """
    if os.getenv("SERVE_FRONTEND", "1").strip().lower() in ("0", "false", "no"):
        return False

    dist = find_frontend_dist()
    if dist is None:
        return False

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    index_path = dist / "index.html"

    # HEAD / — Render & uptime monitors use HEAD for health checks.
    # Without this, HEAD / returns 405 which can mark the instance unhealthy.
    @app.head("/", include_in_schema=False)
    async def spa_root_head() -> Response:
        return Response(status_code=200)

    @app.get("/", include_in_schema=False)
    async def spa_root() -> FileResponse:
        return FileResponse(index_path)

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
    async def spa_fallback(request: Request, full_path: str) -> Response:
        path = request.url.path
        if _is_api_path(path):
            raise HTTPException(status_code=404, detail="Not Found")
        # HEAD requests — just confirm 200 for all non-API SPA routes
        if request.method == "HEAD":
            return Response(status_code=200)
        static_file = _safe_file(dist, path)
        if static_file is not None:
            return FileResponse(static_file)
        return FileResponse(index_path)

    logger.info("Serving frontend SPA from disk", dist=str(dist))
    return True
