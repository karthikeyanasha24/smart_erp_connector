"""
Analytics Cache
TTL-based in-memory cache with stale-while-revalidate support.
Used for KPI and chart queries to avoid redundant SQL Server hits.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import cache_key_is_stale

# Keys whose data changes every minute or are date-specific -- do not persist to PG.
# Covers versioned (kpi:v3:today) AND plain warmup keys (kpi:today, bundle:mtd, ...).
_INTRADAY_PREFIXES = (
    # versioned prefixes
    "kpi:v3:today", "kpi:v3:yesterday", "kpi:v3:mtd",
    "kpi:v4:today", "kpi:v4:yesterday",
    "dashboard:v3:today", "dashboard:v3:yesterday", "dashboard:v3:mtd",
    "dashboard:v7:today", "dashboard:v7:yesterday",
    "dashboard:v2:today", "dashboard:v2:mtd",
    # plain warmup keys written by warmup.py
    "kpi:today", "kpi:yesterday", "kpi:mtd", "kpi:qtd", "kpi:ytd",
    "kpi:last_7d", "kpi:last_30d", "kpi:last_6m", "kpi:last_180d",
    "bundle:today", "bundle:yesterday", "bundle:mtd", "bundle:qtd", "bundle:ytd",
    "bundle:last_7d", "bundle:last_30d", "bundle:last_6m", "bundle:last_180d",
    "dashboard:today", "dashboard:yesterday", "dashboard:mtd", "dashboard:qtd",
    "dashboard:ytd", "dashboard:last_7d", "dashboard:last_30d",
    "dashboard:last_6m", "dashboard:last_180d",
    "department:today", "department:yesterday", "department:mtd",
    "txns:today", "txns:mtd",
)

_DATE_SUFFIX = re.compile(r":\d{4}-\d{2}-\d{2}$")


def _is_intraday(key: str) -> bool:
    if any(key.startswith(p) for p in _INTRADAY_PREFIXES):
        return True
    if _DATE_SUFFIX.search(key):
        return True
    # Catch versioned rolling keys like bundle:v2:today:100:d0:k0
    _rolling = re.compile(
        r":(today|yesterday|mtd|qtd|ytd|last_7d|last_14d|last_30d"
        r"|last_90d|last_180d|last_6m|last_365d)(:|$)"
    )
    return bool(_rolling.search(key))


def _is_department_chart_key(key: str) -> bool:
    return "chart:department:" in key


def _reject_empty_department_cache(key: str, value: Any) -> bool:
    """Empty department lists are not cached — they usually mean a failed cold SQL hit."""
    return _is_department_chart_key(key) and isinstance(value, list) and len(value) == 0


# --- Entry --------------------------------------------------------------------

@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl_s: float
    key: str
    hits: int = 0

    @property
    def age_s(self) -> float:
        return time.time() - self.created_at

    @property
    def is_fresh(self) -> bool:
        return self.age_s < self.ttl_s

    @property
    def is_stale_ok(self) -> bool:
        """Stale-while-revalidate: serve for up to N*TTL while background refresh runs."""
        stale_ttl = self.ttl_s * cfg.ANALYTICS_STALE_TTL_MULTIPLIER
        return self.age_s < stale_ttl


# --- Cache Store --------------------------------------------------------------

class AnalyticsCache:
    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}
        self._stats = {"hits": 0, "misses": 0, "stale_hits": 0}
        self._default_ttl_s = cfg.ANALYTICS_CACHE_TTL_MS / 1000
        self._revalidating: Dict[str, bool] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def get(self, key: str) -> Tuple[Optional[Any], bool]:
        """
        Returns (value, is_fresh).
          (value, True)   fresh hit
          (value, False)  stale hit (revalidation needed)
          (None,  False)  miss
        """
        if cache_key_is_stale(key):
            if key in self._store:
                del self._store[key]
            self._stats["misses"] += 1
            return None, False

        entry = self._store.get(key)
        if entry is None:
            self._stats["misses"] += 1
            return None, False

        entry.hits += 1

        if entry.is_fresh:
            if _reject_empty_department_cache(key, entry.value):
                del self._store[key]
                self._stats["misses"] += 1
                return None, False
            self._stats["hits"] += 1
            return entry.value, True

        if entry.is_stale_ok:
            if _reject_empty_department_cache(key, entry.value):
                del self._store[key]
                self._stats["misses"] += 1
                return None, False
            self._stats["stale_hits"] += 1
            return entry.value, False

        del self._store[key]
        self._stats["misses"] += 1
        return None, False

    def set(self, key: str, value: Any, ttl_s: Optional[float] = None) -> None:
        if _reject_empty_department_cache(key, value):
            self.delete(key)
            return
        ttl = ttl_s if ttl_s is not None else self._default_ttl_s
        self._store[key] = CacheEntry(value=value, created_at=time.time(), ttl_s=ttl, key=key)
        if not _is_intraday(key):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._pg_write(key, value, ttl))
            except RuntimeError:
                pass

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in to_delete:
            del self._store[k]
        return len(to_delete)

    def clear(self) -> int:
        n = len(self._store)
        self._store.clear()
        return n

    def stats(self) -> Dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"] + self._stats["stale_hits"]
        hit_rate = (self._stats["hits"] / total * 100) if total else 0
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate_pct": round(hit_rate, 1),
            "entries": len(self._store),
        }

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable,
        ttl_s: Optional[float] = None,
    ) -> Any:
        """
        Cache-aside with stale-while-revalidate + singleflight (per-key lock).

        1. Fresh hit  -- return immediately
        2. Stale hit  -- return stale data, kick off background refresh
        3. Miss       -- acquire per-key lock, re-check (another waiter may have
                         already populated it), then fetch once and release.
        """
        value, is_fresh = self.get(key)
        if is_fresh:
            return value

        if value is not None:
            if not self._revalidating.get(key):
                self._revalidating[key] = True
                asyncio.create_task(self._background_refresh(key, fetch_fn, ttl_s))
            return value

        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        lock = self._locks[key]

        async with lock:
            value, is_fresh = self.get(key)
            if is_fresh:
                logger.debug("Cache singleflight hit (waited)", key=key)
                return value
            if value is not None:
                return value

            result = await fetch_fn()
            self.set(key, result, ttl_s)
            return result

    async def _background_refresh(
        self, key: str, fetch_fn: Callable, ttl_s: Optional[float]
    ) -> None:
        try:
            result = await fetch_fn()
            self.set(key, result, ttl_s)
            logger.debug("Cache background refresh complete", key=key)
        except Exception as exc:
            logger.warning("Cache background refresh failed", key=key, error=str(exc))
        finally:
            self._revalidating.pop(key, None)

    # --- PostgreSQL Persistence ------------------------------------------------

    async def flush_to_pg(self) -> int:
        """
        Write ALL non-intraday in-memory cache entries to PostgreSQL synchronously.

        Call after each warmup phase and on graceful shutdown.
        This ensures every restart after the first cold start loads from PG in <200ms
        instead of waiting for SQL Server queries.
        """
        from src.config import cfg as _cfg
        if not _cfg.rbac_url:
            return 0
        from src.db.postgres import pg_execute
        written = 0
        errors = 0
        for key, entry in list(self._store.items()):
            if _is_intraday(key):
                continue
            try:
                value_json = json.dumps(entry.value, default=str)
                await pg_execute(
                    """
                    INSERT INTO analytics_cache (cache_key, value_json, created_at, ttl_s)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (cache_key) DO UPDATE
                    SET value_json = EXCLUDED.value_json,
                        created_at = EXCLUDED.created_at,
                        ttl_s      = EXCLUDED.ttl_s
                    """,
                    key,
                    value_json,
                    entry.created_at,
                    entry.ttl_s,
                )
                written += 1
            except Exception as exc:
                errors += 1
                logger.warning("Cache flush_to_pg entry failed", key=key, error=str(exc))
        logger.info("Cache flushed to PostgreSQL", written=written, errors=errors)
        return written

    async def _pg_write(self, key: str, value: Any, ttl_s: float) -> None:
        """Write one entry to PostgreSQL. Fire-and-forget from set()."""
        from src.config import cfg as _cfg
        if not _cfg.rbac_url:
            return
        from src.db.postgres import pg_execute
        try:
            value_json = json.dumps(value, default=str)
            await pg_execute(
                """
                INSERT INTO analytics_cache (cache_key, value_json, created_at, ttl_s)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (cache_key) DO UPDATE
                SET value_json = EXCLUDED.value_json,
                    created_at = EXCLUDED.created_at,
                    ttl_s      = EXCLUDED.ttl_s
                """,
                key,
                value_json,
                time.time(),
                ttl_s,
            )
        except Exception as exc:
            # repr() gives more detail than str() for asyncpg / RuntimeError exceptions
            err_msg = repr(exc) if not str(exc) else str(exc)
            logger.warning("Cache PG write failed", key=key, error=err_msg)

    async def restore_from_pg(self) -> int:
        """
        On startup: load all valid cache entries from PostgreSQL into memory.

        Rolling-period keys (today/mtd/qtd etc.) are deleted from PG before loading
        so stale data from the previous calendar day is never served after midnight.
        Historical period keys (last_month, last_quarter, last_year) are preserved.
        """
        from src.db.postgres import pg_query, pg_execute
        # Purge all rolling-period keys so stale today/mtd data is not served
        try:
            status = await pg_execute(
                "DELETE FROM analytics_cache WHERE "
                "cache_key ~ "
                "E':(today|yesterday|mtd|qtd|ytd|last_7d|last_14d|last_30d"
                "|last_90d|last_180d|last_6m|last_365d)(:|$)'"
                " OR cache_key ~ E':\\d{4}-\\d{2}-\\d{2}$'"
            )
            logger.info("PG cache: purged rolling-period entries on startup", status=status)
        except Exception as exc:
            logger.warning("PG cache: rolling-period purge failed (non-fatal)", error=str(exc))

        try:
            rows = await pg_query(
                "SELECT cache_key, value_json, created_at, ttl_s FROM analytics_cache"
            )
        except Exception as exc:
            logger.warning("Cache restore from PostgreSQL failed", error=str(exc))
            return 0

        now = time.time()
        loaded = 0
        skipped = 0
        for row in rows:
            key = str(row["cache_key"])
            if _is_intraday(key):
                skipped += 1
                continue
            if cache_key_is_stale(key):
                skipped += 1
                continue
            try:
                created_at = float(row["created_at"])
                ttl_s = float(row["ttl_s"])
            except (TypeError, ValueError):
                skipped += 1
                continue

            stale_limit = ttl_s * cfg.ANALYTICS_STALE_TTL_MULTIPLIER
            if (now - created_at) >= stale_limit:
                skipped += 1
                continue  # Too old even for stale serving

            try:
                value = json.loads(row["value_json"])
            except Exception:
                skipped += 1
                continue

            if _reject_empty_department_cache(key, value):
                skipped += 1
                continue

            self._store[key] = CacheEntry(
                value=value,
                created_at=created_at,
                ttl_s=ttl_s,
                key=key,
            )
            loaded += 1

        logger.info(
            "Analytics cache restored from PostgreSQL",
            loaded=loaded,
            skipped=skipped,
        )
        return loaded


# --- Singleton ----------------------------------------------------------------

cache = AnalyticsCache()
