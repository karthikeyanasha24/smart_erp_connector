"""
PostgreSQL Connection Layer
Uses asyncpg for fully async, high-performance PostgreSQL access.
Backs the RBAC system, conversation memory, and audit log.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Callable

import asyncpg

from src.config import cfg
from src.utils.logger import logger

# ─── Pool Singleton + Circuit Breaker ────────────────────────────────────────

_pool: Optional[asyncpg.Pool] = None
_pg_unavailable_until: float = 0.0   # epoch seconds; 0 = not in backoff
_PG_CONNECT_TIMEOUT_S = 10.0         # fail fast — don't block the event loop for 60s
_PG_BACKOFF_S = 30.0                 # after failure, skip retries for 30 s


def _pg_is_circuit_open() -> bool:
    """True when we are in the backoff window and should skip PG entirely."""
    return time.time() < _pg_unavailable_until


def _trip_circuit() -> None:
    """Mark PG as unavailable for _PG_BACKOFF_S seconds."""
    global _pg_unavailable_until
    _pg_unavailable_until = time.time() + _PG_BACKOFF_S
    logger.warning(
        "PostgreSQL circuit open — skipping for %.0fs", _PG_BACKOFF_S,
    )


async def get_pg_pool() -> asyncpg.Pool:
    global _pool

    if _pool is not None:
        return _pool

    # Circuit breaker: if a recent connect attempt failed, don't retry yet.
    if _pg_is_circuit_open():
        raise RuntimeError(
            f"PostgreSQL unavailable (circuit open for {int(_pg_unavailable_until - time.time())}s)"
        )

    if not cfg.rbac_url:
        raise RuntimeError("RBAC_DATABASE_URL / DATABASE_URL is not set")

    url = cfg.rbac_url

    # Detect SSL need (Render, Heroku, RDS etc.)
    ssl_required = (
        cfg.RBAC_DATABASE_URL.__contains__("render.com")
        or "sslmode=require" in url.lower()
    )

    try:
        _pool = await asyncio.wait_for(
            asyncpg.create_pool(
                dsn=url,
                min_size=1,
                max_size=10,
                command_timeout=30,
                ssl="require" if ssl_required else None,
            ),
            timeout=_PG_CONNECT_TIMEOUT_S,
        )
        logger.info("PostgreSQL pool created")
        return _pool
    except (asyncio.TimeoutError, Exception) as exc:
        _pool = None
        _trip_circuit()
        raise RuntimeError(f"PostgreSQL connect failed: {exc}") from exc


async def close_pg_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")


# ─── Query Helpers ────────────────────────────────────────────────────────────

async def pg_query(
    sql: str,
    *args: Any,
) -> List[Dict[str, Any]]:
    """Execute a query and return list of row dicts."""
    pool = await get_pg_pool()
    start = time.perf_counter()
    try:
        rows = await pool.fetch(sql, *args)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.debug("PG query", rows=len(rows), duration_ms=duration_ms)
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("PG query failed", error=str(exc), query=sql[:120])
        raise


async def pg_execute(sql: str, *args: Any) -> str:
    """Execute a DML/DDL statement and return status string."""
    pool = await get_pg_pool()
    return await pool.execute(sql, *args)


async def pg_fetch_one(sql: str, *args: Any) -> Optional[Dict[str, Any]]:
    """Fetch a single row, or None."""
    pool = await get_pg_pool()
    row = await pool.fetchrow(sql, *args)
    return dict(row) if row else None


async def pg_fetch_val(sql: str, *args: Any) -> Any:
    """Fetch a single scalar value."""
    pool = await get_pg_pool()
    return await pool.fetchval(sql, *args)


async def pg_transaction(fn: Callable) -> Any:
    """Run fn(conn) inside a transaction."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await fn(conn)


# ─── Health Check ─────────────────────────────────────────────────────────────

async def check_pg_health() -> Dict[str, Any]:
    try:
        start = time.perf_counter()
        await pg_fetch_val("SELECT 1")
        return {"connected": True, "latency_ms": int((time.perf_counter() - start) * 1000)}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


# ─── Schema Bootstrap ─────────────────────────────────────────────────────────

async def init_schema() -> None:
    logger.info("Initializing PostgreSQL RBAC schema...")

    await pg_execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email       TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL DEFAULT '',
            password    TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'viewer',
            branch_ids  TEXT[] NOT NULL DEFAULT '{}',
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await pg_execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            permissions JSONB NOT NULL DEFAULT '[]',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await pg_execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id  UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, role_id)
        )
    """)

    await pg_execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash    TEXT NOT NULL,
            expires_at    TIMESTAMPTZ NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ip_address    TEXT,
            user_agent    TEXT
        )
    """)

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)",
    ]:
        await pg_execute(idx_sql)

    await pg_execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id         BIGSERIAL PRIMARY KEY,
            user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
            action     TEXT NOT NULL,
            resource   TEXT,
            details    JSONB,
            ip_address TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at DESC)",
    ]:
        await pg_execute(idx_sql)

    await pg_execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title       TEXT NOT NULL DEFAULT 'New Conversation',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await pg_execute("""
        CREATE TABLE IF NOT EXISTS conversation_turns (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content          TEXT NOT NULL,
            sql_query        TEXT,
            intent           JSONB,
            result_summary   TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await pg_execute("""
        CREATE INDEX IF NOT EXISTS idx_conv_turns_conv_id
        ON conversation_turns(conversation_id, created_at DESC)
    """)

    # ── Analytics cache persistence (survives server restarts) ──────────────
    # Stores pre-computed KPI/dashboard results so restarts serve data instantly.
    await pg_execute("""
        CREATE TABLE IF NOT EXISTS analytics_cache (
            cache_key   TEXT PRIMARY KEY,
            value_json  TEXT NOT NULL,
            created_at  DOUBLE PRECISION NOT NULL,
            ttl_s       DOUBLE PRECISION NOT NULL
        )
    """)

    # Seed default roles
    await pg_execute("""
        INSERT INTO roles (name, description, permissions)
        VALUES
            ('admin',   'Full system access',           '["*"]'::jsonb),
            ('manager', 'Read all + export',            '["read:*","export:*","query:*"]'::jsonb),
            ('analyst', 'Read + NLQ',                   '["read:*","query:*"]'::jsonb),
            ('viewer',  'Read-only, own branches only', '["read:own"]'::jsonb)
        ON CONFLICT (name) DO NOTHING
    """)

    logger.info("PostgreSQL schema ready")
