"""
Fast fetch for mtd/qtd/ytd breakdown scripts.

One GET /analytics/bundle (branches + trend + categories [+ departments] [+ kpis])
when possible — fastest on warm server cache.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Tuple

API_TOP_N_MAX = 100

HttpGet = Callable[..., Dict[str, Any]]
LogFn = Callable[[str], None]


def fetch_fast_bundle(
    period: str,
    base: str,
    token: str,
    *,
    log: LogFn,
    http_get: HttpGet,
    top_n: int = API_TOP_N_MAX,
    timeout: int = 300,
    with_departments: bool = True,
    include_kpis: bool = False,
) -> Tuple[Dict[str, Any], str]:
    base = base.rstrip("/")
    n = min(max(top_n, 1), API_TOP_N_MAX)
    inc_dept = "true" if with_departments else "false"
    inc_kpi = "true" if include_kpis else "false"
    url = (
        f"{base}/analytics/bundle?period={period}&top_n={n}"
        f"&include_departments={inc_dept}&include_kpis={inc_kpi}"
    )
    parts = ["branches", "trend", "categories"]
    if include_kpis:
        parts.append("kpis")
    if with_departments:
        parts.append("departments")
    log(f"  Fetching bundle ({', '.join(parts)}) — timeout {timeout}s")
    t0 = time.perf_counter()
    data = http_get(url, token=token, timeout=timeout, label="loading bundle")
    ms = round((time.perf_counter() - t0) * 1000, 1)
    log(f"       OK bundle in {ms:.0f} ms")

    raw: Dict[str, Any] = {
        "branches": {"branches": data.get("branches") or []},
        "trend": {"trend": data.get("trend") or []},
        "categories": {"categories": data.get("categories") or []},
        "kpis": data.get("kpis") or {},
        "_timings_ms": dict(data.get("timings_ms") or {"bundle": ms}),
    }
    if with_departments:
        raw["departments"] = {"departments": data.get("departments") or []}
    if data.get("errors"):
        raw["_errors"] = dict(data["errors"])
    return raw, "bundle (single call)"
