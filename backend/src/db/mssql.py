"""
SQL Server Connection Layer
- Windows / local: pyodbc + Microsoft ODBC (default when drivers are installed)
- Render / Linux: pymssql + FreeTDS (set MSSQL_DRIVER=pymssql or use backend/Dockerfile)
"""

from __future__ import annotations

import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

from src.config import cfg
from src.utils.logger import logger

# ─── Driver selection ─────────────────────────────────────────────────────────

_selected_driver: Optional[str] = None
_use_pymssql: Optional[bool] = None

DbConnection = Any


def _installed_odbc_drivers() -> List[str]:
    try:
        import pyodbc

        return list(pyodbc.drivers())
    except Exception:
        return []


def _is_pymssql() -> bool:
    global _use_pymssql
    if _use_pymssql is not None:
        return _use_pymssql

    mode = (cfg.MSSQL_DRIVER or "auto").strip().lower()
    if mode == "pymssql":
        _use_pymssql = True
    elif mode == "pyodbc":
        _use_pymssql = False
    else:
        _use_pymssql = not bool(_installed_odbc_drivers())

    return _use_pymssql


def _param_placeholder() -> str:
    return "%s" if _is_pymssql() else "?"


# ─── pyodbc (Microsoft ODBC) ──────────────────────────────────────────────────

def _odbc_drivers_to_try() -> List[str]:
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


def _build_odbc_conn_str(driver: str) -> str:
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


def _connect_pyodbc() -> Tuple[DbConnection, str]:
    import pyodbc

    global _selected_driver
    last_err: Optional[Exception] = None
    for driver in _odbc_drivers_to_try():
        try:
            conn = pyodbc.connect(
                _build_odbc_conn_str(driver),
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
        "Install ODBC Driver 18, or set MSSQL_DRIVER=pymssql on Linux/Render."
    ) from last_err


# ─── pymssql (FreeTDS — no Microsoft ODBC) ────────────────────────────────────

def _connect_pymssql() -> Tuple[DbConnection, str]:
    import pymssql

    global _selected_driver
    conn = pymssql.connect(
        server=cfg.mssql_server,
        port=cfg.mssql_port,
        user=cfg.mssql_user,
        password=cfg.mssql_password,
        database=cfg.mssql_database,
        login_timeout=cfg.mssql_connect_timeout,
        timeout=cfg.mssql_request_timeout,
        tds_version="7.4",
    )
    _selected_driver = "pymssql (FreeTDS)"
    return conn, _selected_driver


def _connect() -> Tuple[DbConnection, str]:
    if _is_pymssql():
        return _connect_pymssql()
    return _connect_pyodbc()


def _ping_connection(conn: DbConnection) -> None:
    if _is_pymssql():
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
        finally:
            cur.close()
    else:
        conn.execute("SELECT 1")


# ─── Connection pool ───────────────────────────────────────────────────────────

class _ConnectionPool:
    def __init__(self, max_size: int = 10) -> None:
        self._max_size = max_size
        self._pool: List[DbConnection] = []
        self._odbc_conn_str: str = ""
        self._initialized = False

    def initialize(self) -> None:
        conn, driver = _connect()
        if not _is_pymssql() and _selected_driver:
            self._odbc_conn_str = _build_odbc_conn_str(_selected_driver)
        conn.close()
        self._initialized = True
        logger.info(
            "SQL Server client ready",
            driver=driver,
            mode="pymssql" if _is_pymssql() else "pyodbc",
        )

    def _new_connection(self) -> DbConnection:
        if _is_pymssql():
            conn, _ = _connect_pymssql()
            return conn

        import pyodbc

        if not self._odbc_conn_str and _selected_driver:
            self._odbc_conn_str = _build_odbc_conn_str(_selected_driver)
        if not self._odbc_conn_str:
            conn, driver = _connect_pyodbc()
            self._odbc_conn_str = _build_odbc_conn_str(driver)
            return conn
        conn = pyodbc.connect(
            self._odbc_conn_str,
            timeout=cfg.mssql_connect_timeout,
            autocommit=True,
        )
        conn.timeout = cfg.mssql_request_timeout
        return conn

    def _get_connection(self) -> DbConnection:
        if not self._initialized:
            raise RuntimeError("Connection pool not initialized — call initialize() first")

        while self._pool:
            conn = self._pool.pop()
            try:
                _ping_connection(conn)
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

        return self._new_connection()

    def _return_connection(self, conn: DbConnection) -> None:
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
    def connection(self) -> Generator[DbConnection, None, None]:
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
_health_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mssql-health")
_mssql_startup_ok = False


# ─── Init / Close ─────────────────────────────────────────────────────────────

async def init_mssql() -> None:
    _pool.initialize()
    loop = asyncio.get_event_loop()

    def _test() -> None:
        with _pool.connection() as conn:
            _ping_connection(conn)

    global _mssql_startup_ok
    try:
        await loop.run_in_executor(None, _test)
        _mssql_startup_ok = True
        logger.info(
            "SQL Server connected",
            server=cfg.mssql_server,
            port=cfg.mssql_port,
            database=cfg.mssql_database,
            client="pymssql" if _is_pymssql() else "pyodbc",
        )
    except Exception as exc:
        _mssql_startup_ok = False
        logger.error("SQL Server connection failed", error=str(exc))
        raise


async def close_mssql() -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _pool.close_all)
    logger.info("SQL Server pool closed")


# ─── Query helpers ─────────────────────────────────────────────────────────────

QueryParams = Dict[str, Any]
Row = Dict[str, Any]


def _apply_hints(sql: str, nolock: bool, recompile: bool) -> str:
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


def _rows_to_dicts(cursor: Any) -> List[Row]:
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
    final_sql = _apply_hints(sql, nolock, recompile)
    placeholder = _param_placeholder()

    param_values: List[Any] = []
    if params:
        def replace_param(m: re.Match) -> str:
            name = m.group(1)
            if name in params:
                param_values.append(params[name])
                return placeholder
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
    return await execute_query(sql, params, nolock=False, recompile=False)


# ─── Health check ──────────────────────────────────────────────────────────────

def _health_ping_sync() -> int:
    start = time.perf_counter()
    conn, _driver = _connect()
    try:
        _ping_connection(conn)
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
        return {
            "connected": True,
            "latency_ms": latency_ms,
            "client": "pymssql" if _is_pymssql() else "pyodbc",
        }
    except asyncio.TimeoutError:
        return {
            "connected": True,
            "latency_ms": None,
            "busy": True,
            "note": "ping slow — analytics queries may be running",
        }
    except Exception as exc:
        return {"connected": False, "error": str(exc)}
