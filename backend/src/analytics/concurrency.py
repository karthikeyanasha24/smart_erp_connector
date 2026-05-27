"""Shared limit on concurrent analytics SQL (bundle, warmup, heavy fetches)."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, TypeVar

# Avoid cold-cache stampede on SQL Server (5× YTD scans can exceed 10+ minutes).
ANALYTICS_SQL_SEM = asyncio.Semaphore(3)

T = TypeVar("T")


async def run_analytics_sql(coro: Awaitable[T]) -> T:
    async with ANALYTICS_SQL_SEM:
        return await coro
