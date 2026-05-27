"""
Global Error Handlers for FastAPI.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.utils.logger import logger


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "APP_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError", code=exc.code, message=exc.message, path=str(request.url))
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": exc.message, "code": exc.code},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("ValueError", error=str(exc), path=str(request.url))
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(exc), "code": "VALIDATION_ERROR"},
        )

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
        logger.error("RuntimeError", error=str(exc), path=str(request.url))
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc), "code": "SERVER_ERROR"},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception", error=str(exc), path=str(request.url), exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error", "code": "INTERNAL_ERROR"},
        )
