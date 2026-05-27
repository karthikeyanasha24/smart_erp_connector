"""
SQL Server Connection Layer
Uses pyodbc with a thread-pool executor for async compatibility.
Connection pooling is managed manually since pyodbc has no native async pool.
"""

from __future__ import annotations

import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

import pyodbc

from src.config import cfg
from src.utils.logger import logger

# ─── ODBC driver resolution ───────────────────────────────────────────────────

_selected_driver: Optional[str] = None


def _installed_odbc_drivers() -> List[str]:
    try:
        return list(pyodbc.drivers())
    except Exception:
        return []


def _odbc_drivers_to_try() -> List[str]:
    """Pick ODBC drivers that exist on this machine (Windows often has only 'SQL Server')."""
    installed = _installed_odbc_drivers()
    candidates = [
        cfg.ODBC_DRIVER,
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]
    ordered: List[str] = []
    for d in candidates:
        if d and d not in ordered and (not installed or d in installed):
            ordered.append(d)
    if not ordered:
        for d in installed:
            if "sql" in d.lower() and d not in ordered:
                ordered.append(d)
    if not ordered and installed:
        ordered = installed[:]
    return ordered


def _build_conn_str(driver: str) -> str:
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={cfg.mssql_server},{cfg.mssql_port};"
        f"DATABASE={cfg.mssql_database};"
        f"UID={cfg.mssql_user};"
        f"PWD={cfg.mssql_password};"
        f"Connect Timeout={cfg.mssql_connect_timeout};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no;"
    )


def _connect_pyodbc() -> Tuple[pyodbc.Connection, str]:
    """Try each installed ODBC driver until one connects."""
    global _selected_driver
    last_err: Optional[Exception] = None
    for driver in _odbc_drivers_to_try():
        try:
            conn = pyodbc.connect(
                _build_conn_str(driver),
                timeout=cfg.mssql_connect_timeout,
                autocommit=True,
            )
            conn.timeout = cfg.mssql_request_timeout
            _selected_driver = driver
            return conn, driver
        except Exception as exc:
            last_err = exc
    installed = _installed_odbc_drivers()
    raise RuntimeError(
        f"Could not connect to SQL Server. Tried: {_odbc_drivers_to_try()}. "
        f"Installed ODBC drivers: {installed or 'none'}. "
        "Install 'ODBC Driver 18 for SQL Server' or set ODBC_DRIVER=SQL Server in .env"
    ) from last_err


# ─── Simple Connection Pool ───────────────────────────────────────────────────

class _ConnectionPool:
    """
    Lightweight pyodbc connection pool.
    Maintains a queue of idle connections with max size enforcement.
    """

    def __init__(self, max_size: int = 10) -> None:
        self._max_size = max_size
        self._pool: List[pyodbc.Connection] = []
        self._active = 0
        self._lock = asyncio.Lock()
        self._conn_str: str = ""
        self._initialized = False

    def initialize(self) -> None:
        conn, driver = _connect_pyodbc()
        self._conn_str = _build_conn_str(driver)
        conn.close()
        self._initialized = True
        logger.info("SQL Server ODBC driver selected", driver=driver)

    def _new_connection(self) -> pyodbc.Connection:
        if not self._conn_str and _selected_driver:
            self._conn_str = _build_conn_str(_selected_driver)
        if not self._conn_str:
            conn, driver = _connect_pyodbc()
            self._conn_str = _build_conn_str(driver)
            return conn
        conn = pyodbc.connect(
            self._conn_str,
            timeout=cfg.mssql_connect_timeout,
            autocommit=True,
        )
        conn.timeout = cfg.mssql_request_timeout
        return conn

    def _get_connection(self) -> pyodbc.Connection:
        """Get a connection from the pool or create a new one (sync, called in thread)."""
        if not self._initialized:
            raise RuntimeError("Connection pool not initialized — call initialize() first")

        # Try a pooled connection
        while self._pool:
            conn = self._pool.pop()
            try:
                conn.execute("SELECT 1")
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

        # Create new if under limit
        return self._new_connection()

    def _return_connection(self, conn: pyodbc.Connection) -> None:
        """Return a connection to the pool (sync, called in thread)."""
        if len(self._pool) < self._max_size:
            try:
                self._pool.append(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
        else:
            try:
                conn.close()
            except Exception:
                pass

    @contextmanager
    def connection(self) -> Generator[pyodbc.Connection, None, None]:
        """Sync context manager for use inside thread executor."""
        conn = self._get_connection()
        try:
            yield conn
            self._return_connection(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            raise

    def close_all(self) -> None:
        for conn in self._pool:
            try:
                conn.close()
            except Exception:
                pass
        self._pool.clear()


_pool = _ConnectionPool(max_size=cfg.DB_POOL_MAX)
_executor = None  # Will use default ThreadPoolExecutor

# Dedicated thread + connection for /health — never waits on the analytics connection pool.
_health_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mssql-health")
_mssql_startup_ok = False


# ─── Init / Close ─────────────────────────────────────────────────────────────

async def init_mssql() -> None:
    """Initialize pool and test connectivity."""
    _pool.initialize()
    loop = asyncio.get_event_loop()

    def _test() -> None:
        with _pool.connection() as conn:
            conn.execute("SELECT 1")

    global _mssql_startup_ok
    try:
        await loop.run_in_executor(None, _test)
        _mssql_startup_ok = True
        logger.info(
            "SQL Server connected",
            server=cfg.mssql_server,
            port=cfg.mssql_port,
            database=cfg.mssql_database,
        )
    except Exception as exc:
        _mssql_startup_ok = False
        logger.error("SQL Server connection failed", error=str(exc))
        raise


async def close_mssql() -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _pool.close_all)
    logger.info("SQL Server pool closed")


# ─── Query Helpers ────────────────────────────────────────────────────────────

QueryParams = Dict[str, Any]

Row = Dict[str, Any]


def _apply_hints(sql: str, nolock: bool, recompile: bool) -> str:
    """Inject WITH (NOLOCK) and OPTION (RECOMPILE) hints safely."""
    q = sql.strip()

    if nolock and "with (nolock)" not in q.lower():
        q = re.sub(
            r"\b(FROM|JOIN)\s+([\[\]\w.]+)",
            lambda m: f"{m.group(1)} {m.group(2)} WITH (NOLOCK)",
            q,
            flags=re.IGNORECASE,
        )

    if recompile and not re.search(r"OPTION\s*\(", q, re.IGNORECASE):
        q = re.sub(r";?\s*$", " OPTION (RECOMPILE)", q)

    return q


def _rows_to_dicts(cursor: pyodbc.Cursor) -> List[Row]:
    """Convert cursor result to list of dicts."""
    if cursor.description is None:
        return []
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _bind_and_execute(
    sql: str,
    params: Optional[QueryParams],
    nolock: bool,
    recompile: bool,
) -> Tuple[List[Row], float]:
    """Run inside thread executor."""
    final_sql = _apply_hints(sql, nolock, recompile)

    # Replace @name params with ? for pyodbc
    param_values: List[Any] = []
    if params:
        def replace_param(m: re.Match) -> str:
            name = m.group(1)
            if name in params:
                param_values.append(params[name])
                return "?"
            return m.group(0)
        final_sql = re.sub(r"@(\w+)", replace_param, final_sql)

    start = time.perf_counter()
    with _pool.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(final_sql, param_values or [])
        rows = _rows_to_dicts(cursor)
        duration = (time.perf_counter() - start) * 1000

    logger.debug("SQL query executed", rows=len(rows), duration_ms=int(duration))
    return rows, duration


async def execute_query(
    sql: str,
    params: Optional[QueryParams] = None,
    nolock: Optional[bool] = None,
    recompile: Optional[bool] = None,
    timeout_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Async SQL Server query execution.
    Returns {"records": [...], "duration": ms}
    """
    use_nolock = nolock if nolock is not None else cfg.ANALYTICS_NOLOCK
    use_recompile = recompile if recompile is not None else cfg.ANALYTICS_RECOMPILE

    loop = asyncio.get_event_loop()

    if not _pool._initialized:
        _pool.initialize()

    records, duration = await loop.run_in_executor(
        None,
        _bind_and_execute,
        sql,
        params,
        use_nolock,
        use_recompile,
    )

    return {"records": records, "duration": duration}


async def execute_raw(sql: str, params: Optional[QueryParams] = None) -> Dict[str, Any]:
    """Execute SQL without hint injection (DDL, stored procs, etc.)"""
    return await execute_query(sql, params, nolock=False, recompile=False)


# ─── Health Check ─────────────────────────────────────────────────────────────

def _health_ping_sync() -> int:
    """Ping SQL Server on a connection outside the shared pool (fast under load)."""
    start = time.perf_counter()
    conn, _driver = _connect_pyodbc()
    try:
        conn.execute("SELECT 1 AS ping")
        return int((time.perf_counter() - start) * 1000)
    finally:
        try:
            conn.close()
        except Exception:
            pass


async def check_mssql_health() -> Dict[str, Any]:
    if not _mssql_startup_ok:
        return {"connected": False, "error": "SQL Server not initialized"}
    try:
        loop = asyncio.get_event_loop()
        latency_ms = await asyncio.wait_for(
            loop.run_in_executor(_health_executor, _health_ping_sync),
            timeout=3.0,
        )
        return {"connected": True, "latency_ms": latency_ms}
    except asyncio.TimeoutError:
        return {
            "connected": True,
            "latency_ms": None,
            "busy": True,
            "note": "ping slow — analytics queries may be running",
        }
    except Exception as exc:
        return {"connected": False, "error": str(exc)}
