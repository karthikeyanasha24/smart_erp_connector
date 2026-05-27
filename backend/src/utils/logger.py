"""
Structured logger — uses structlog with stdlib routing so that
add_logger_name works correctly in both dev and production.
"""

import logging
import logging.config
import sys
import time
from typing import Any, Callable

import structlog
from src.config import cfg


def _setup_structlog() -> None:
    # Wire structlog into Python's stdlib logging so add_logger_name works
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if cfg.is_dev else logging.INFO,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%H:%M:%S" if cfg.is_dev else "iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if cfg.is_dev:
        processors: list[Any] = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = shared_processors + [
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if cfg.is_dev else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


_setup_structlog()

logger = structlog.get_logger("smarterp")


# ── Request Logger Middleware ─────────────────────────────────────────────────

def make_request_logger() -> Callable:
    """
    Returns a Starlette/FastAPI middleware callable that logs each request
    with method, path, status code, and duration.
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class RequestLoggerMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            start = time.perf_counter()
            response: Response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)

            level = "error" if response.status_code >= 500 else \
                    "warning" if response.status_code >= 400 else "info"

            getattr(logger, level)(
                f"{request.method} {request.url.path} → {response.status_code}",
                duration_ms=duration_ms,
                ip=request.client.host if request.client else None,
            )
            return response

    return RequestLoggerMiddleware
