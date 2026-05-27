"""
Shared API reachability for breakdown scripts.

Do not block on /health while cache warmup sets status=busy — login and /analytics/bundle
work; only /health is slow or reports busy.
"""

from __future__ import annotations

import socket
import time
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

TCP_WAIT_MAX_S = 120
HEALTH_PROBE_TIMEOUT_S = 4

HttpGet = Callable[..., Dict[str, Any]]
LogFn = Callable[[str], None]


def _parse_host_port(base: str) -> Tuple[str, int]:
    parsed = urlparse(base)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port


def wait_for_tcp_port(
    base: str,
    *,
    log: LogFn,
    max_wait: float = TCP_WAIT_MAX_S,
    api_hint: str,
) -> None:
    host, port = _parse_host_port(base)
    deadline = time.monotonic() + max_wait
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            with socket.create_connection((host, port), timeout=5):
                log(f"  Port {host}:{port} is open")
                return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Nothing listening on {host}:{port} ({exc}).{api_hint}"
                ) from exc
            log(f"  Waiting for {host}:{port} (attempt {attempt})...")
            time.sleep(2)


def try_health(
    base: str,
    http_get: HttpGet,
    *,
    timeout: int = HEALTH_PROBE_TIMEOUT_S,
) -> Optional[Dict[str, Any]]:
    try:
        return http_get("GET", f"{base.rstrip('/')}/health", timeout=timeout)
    except RuntimeError:
        return None


def ensure_api_reachable(
    base: str,
    *,
    http_get: HttpGet,
    log: LogFn,
    api_start_hint: str,
    wait_warmup: bool = False,
    tcp_max_wait: float = TCP_WAIT_MAX_S,
    health_timeout: int = HEALTH_PROBE_TIMEOUT_S,
) -> Dict[str, Any]:
    """
    Wait for TCP, then optionally probe /health — never spin on status=busy.
    """
    wait_for_tcp_port(base, log=log, max_wait=tcp_max_wait, api_hint=api_start_hint)

    if wait_warmup:
        log("  --wait-warmup: not polling /health (it often hangs during SQL warmup).")
        log("  Will retry login if needed (see script login options).")
        return {"status": "warming", "mssql": {}}

    health = try_health(base, http_get, timeout=health_timeout)
    if health is None:
        log("  /health did not respond quickly — skipping (server may be busy warming cache).")
        log("  Proceeding to login + bundle...")
        return {"status": "unknown", "mssql": {}}

    status = health.get("status", "unknown")
    mssql = (health.get("mssql") or {}).get("connected")
    if status == "busy":
        log("  Server warming cache — proceeding to login + bundle...")
    else:
        log(f"  Health: {status} | SQL Server: {mssql}")
    return health
