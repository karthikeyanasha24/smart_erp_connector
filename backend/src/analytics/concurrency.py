"""
Concurrency controls for analytics SQL queries.

Two separate semaphores to ensure user-facing requests are NEVER blocked by warmup:
  - ANALYTICS_SQL_SEM (5 slots): user-facing API calls (dashboard, KPIs, charts)
  - WARMUP_SQL_SEM   (2 slots): background cache warmup only

Warmup uses its own 2-slot semaphore so it never competes with user requests.
Even during a 20-minute YTD warmup scan, the login and dashboard APIs are unblocked.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, TypeVar

# User-facing requests — never blocked by warmup.
ANALYTICS_SQL_SEM = asyncio.Semaphore(5)

# Warmup-only — intentionally limited so SQL Server is not overloaded.
# 2 concurrent warmup queries at a time; warmup just takes longer, never blocks users.
WARMUP_SQL_SEM = asyncio.Semaphore(2)

T = TypeVar("T")


async def run_analytics_sql(coro: Awaitable[T]) -> T:
    """User-facing analytics SQL — uses ANALYTICS_SQL_SEM (5 slots)."""
    async with ANALYTICS_SQL_SEM:
        return await coro


async def run_warmup_sql(coro: Awaitable[T]) -> T:
    """Warmup-only SQL — uses WARMUP_SQL_SEM (2 slots), never blocks user requests."""
    async with WARMUP_SQL_SEM:
        return await coro
