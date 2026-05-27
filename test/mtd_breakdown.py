#!/usr/bin/env python3
"""
MTD sales breakdown — list rows for:
  - Day-wise (daily sales in month-to-date)
  - Branch-wise
  - Category-wise
  - Department-wise

Runs standalone against SQL Server (same env/columns as backend). Does not call the HTTP API.

Loads credentials + analytics overrides from backend/.env (preferred) or project-root .env.
See backend/.env.example and backend/src/config.py for variables.

Examples:
  python test/mtd_breakdown.py
  python test/mtd_breakdown.py --no-departments
  python test/mtd_breakdown.py --dashboard
  python test/mtd_breakdown.py --json -o mtd.json

Requires: pip install pyodbc python-dotenv (see backend/requirements.txt)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

# Reuse MSSQL connection + date presets from sibling test helper
from list_transactions_db import (  # noqa: E402
    DateRange,
    _load_dotenv_files,
    connect_mssql,
    resolve_date_range,
)

PERIOD = "mtd"
API_TOP_N_MAX = 100


def _log(msg: str) -> None:
    print(msg, flush=True)


@dataclass
class AnalyticsEnv:
    """Mirror backend Settings analytics fields — read from environment."""

    sales_table: str
    date_column: str
    amount_column: str
    quantity_column: str
    bill_count_column: str
    bill_count_mode: str
    branch_dim: str
    category_dim: str
    department_dim: str

    @classmethod
    def from_os(cls) -> AnalyticsEnv:
        return cls(
            sales_table=(os.getenv("SALES_AI_TABLE") or "dbo.VW_MB_POWERBI_SLS_REPORT").strip(),
            date_column=(
                os.getenv("MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN") or "XnMemoDate"
            ).strip(),
            amount_column=(os.getenv("SALES_ANALYTICS_AMOUNT_COLUMN") or "NetAmount").strip(),
            quantity_column=(
                os.getenv("SALES_ANALYTICS_QUANTITY_COLUMN") or "NetSlsQty"
            ).strip(),
            bill_count_column=(
                os.getenv("SALES_ANALYTICS_BILL_COUNT_COLUMN") or "BillCount"
            ).strip(),
            bill_count_mode=(
                os.getenv("SALES_ANALYTICS_BILL_COUNT_MODE") or "rows"
            ).strip().lower(),
            branch_dim=(os.getenv("SALES_ANALYTICS_BRANCH_DIM") or "BranchAlias").strip(),
            category_dim=(
                os.getenv("SALES_ANALYTICS_CATEGORY_DIM") or "CategoryShortName"
            ).strip(),
            department_dim=(
                os.getenv("SALES_ANALYTICS_DEPARTMENT_DIM") or "DepartmentShortName"
            ).strip(),
        )


def sql_table(qualified_name: str) -> str:
    """[schema].[object] helper — matches backend/src/utils/sql_ref.sql_table."""
    name = (qualified_name or "").strip()
    if not name:
        return name
    if "." in name:
        schema, obj = name.split(".", 1)
        return f"[{schema.strip()}].[{obj.strip()}]"
    return f"[{name}]"


def _transactions_aggregate(env: AnalyticsEnv) -> str:
    if env.bill_count_mode == "rows":
        return "COUNT(*)"
    return f"SUM([{env.bill_count_column}])"


def _bill_count_case(
    env: AnalyticsEnv,
) -> str:
    """Single-period bill/line count CASE (current window only)."""
    dc = env.date_column
    end_expr = "DATEADD(day,1,CAST(? AS DATE))"
    if env.bill_count_mode == "rows":
        return (
            f"SUM(CASE WHEN [{dc}] >= ? AND [{dc}] < {end_expr} "
            f"THEN 1 ELSE 0 END)"
        )
    col = env.bill_count_column
    return (
        f"SUM(CASE WHEN [{dc}] >= ? AND [{dc}] < {end_expr} "
        f"THEN [{col}] ELSE 0 END)"
    )


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def get_prior_year_range(period: str, ref_date: Optional[date] = None) -> DateRange:
    """Same calendar window one year earlier (matches backend date_utils)."""
    dr = resolve_date_range(period, ref_date)
    s = date.fromisoformat(dr.start).replace(
        year=date.fromisoformat(dr.start).year - 1
    )
    e = date.fromisoformat(dr.end).replace(year=date.fromisoformat(dr.end).year - 1)
    return DateRange(s.isoformat(), e.isoformat(), f"LY {dr.label}", f"ly_{dr.period}")


def _period_key(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    s = str(raw).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")[:26]).date().isoformat()
    except ValueError:
        return s[:10]


def _prior_year_day_key(day_key: str) -> str:
    d = date.fromisoformat(day_key)
    return d.replace(year=d.year - 1).isoformat()


def _execute_sql(
    conn: Any,
    sql: str,
    params: Tuple[Any, ...],
) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(sql, params)
    if cur.description is None:
        return []
    colnames = [d[0] for d in cur.description]
    rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        rec = {}
        for i, name in enumerate(colnames):
            v = row[i]
            if isinstance(v, datetime):
                v = v.date().isoformat() if hasattr(v, "date") else v.isoformat()
            elif hasattr(v, "isoformat") and callable(getattr(v, "isoformat")):
                try:
                    v = v.isoformat()
                except Exception:
                    pass
            rec[name] = v
        out.append(rec)
    return out


def _fetch_branches(
    conn: Any, env: AnalyticsEnv, dr: DateRange
) -> Tuple[str, Dict[str, Any], float]:
    t0 = time.perf_counter()
    tbl = sql_table(env.sales_table)
    dc = env.date_column
    sql = f"""
        SELECT
            [{env.branch_dim}] AS Branch,
            SUM([{env.amount_column}]) AS Revenue,
            {_transactions_aggregate(env)} AS Transactions
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= ?
          AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        GROUP BY [{env.branch_dim}]
        ORDER BY Revenue DESC
        OPTION (RECOMPILE)
    """
    recs = _execute_sql(conn, sql, (dr.start, dr.end))
    branches = [
        {
            "branch": str(r.get("Branch", "")),
            "revenue": _safe_float(r.get("Revenue")),
            "transactions": int(_safe_float(r.get("Transactions"))),
        }
        for r in recs
    ]
    return "branches", {"branches": branches}, (time.perf_counter() - t0) * 1000


def _fetch_trend_daily(
    conn: Any, env: AnalyticsEnv, dr: DateRange
) -> Tuple[str, Dict[str, Any], float]:
    t0 = time.perf_counter()
    tbl = sql_table(env.sales_table)
    dc = env.date_column
    sql = f"""
        SELECT
            CAST([{dc}] AS DATE) AS TransactionDate,
            SUM([{env.amount_column}]) AS Revenue,
            {_transactions_aggregate(env)} AS Transactions,
            SUM([{env.quantity_column}]) AS Quantity
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= ?
          AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        GROUP BY CAST([{dc}] AS DATE)
        ORDER BY TransactionDate ASC
        OPTION (RECOMPILE)
    """
    recs = _execute_sql(conn, sql, (dr.start, dr.end))
    trend = [
        {
            "date": str(r.get("TransactionDate", ""))[:10],
            "label": str(r.get("TransactionDate", ""))[:10],
            "revenue": _safe_float(r.get("Revenue")),
            "transactions": int(_safe_float(r.get("Transactions"))),
            "quantity": int(_safe_float(r.get("Quantity"))),
        }
        for r in recs
    ]
    return "trend", {"trend": trend}, (time.perf_counter() - t0) * 1000


def _fetch_trend_yoy(
    conn: Any,
    env: AnalyticsEnv,
    dr: DateRange,
    ly_dr: DateRange,
) -> Tuple[str, Dict[str, Any], float]:
    t0 = time.perf_counter()
    tbl = sql_table(env.sales_table)
    dc = env.date_column
    sql_curr = f"""
        SELECT
            CAST([{dc}] AS DATE) AS PeriodKey,
            FORMAT(CAST([{dc}] AS DATE), 'dd-MMM') AS Label,
            SUM([{env.amount_column}]) AS Revenue,
            {_transactions_aggregate(env)} AS Bills,
            SUM([{env.quantity_column}]) AS Quantity
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= ?
          AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        GROUP BY CAST([{dc}] AS DATE)
        ORDER BY PeriodKey ASC
        OPTION (RECOMPILE)
    """
    sql_ly = f"""
        SELECT
            CAST([{dc}] AS DATE) AS PeriodKey,
            SUM([{env.amount_column}]) AS Revenue
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= ?
          AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        GROUP BY CAST([{dc}] AS DATE)
        ORDER BY PeriodKey ASC
        OPTION (RECOMPILE)
    """
    curr_res = _execute_sql(conn, sql_curr, (dr.start, dr.end))
    ly_res = _execute_sql(conn, sql_ly, (ly_dr.start, ly_dr.end))
    ly_map: Dict[str, float] = {}
    for r in ly_res:
        key = _period_key(r.get("PeriodKey"))
        if key:
            ly_map[key] = _safe_float(r.get("Revenue"))

    dash_trend: List[Dict[str, Any]] = []
    for r in curr_res:
        key = _period_key(r.get("PeriodKey"))
        label = str(r.get("Label", key))
        try:
            prior = ly_map.get(_prior_year_day_key(key), 0) if key else 0
        except ValueError:
            prior = 0
        dash_trend.append(
            {
                "label": label,
                "date": key,
                "current": _safe_float(r.get("Revenue")),
                "prior": prior,
                "bills": int(_safe_float(r.get("Bills"))),
                "quantity": _safe_float(r.get("Quantity")),
            }
        )

    api_trend = [
        {
            "date": p["date"],
            "label": p["label"],
            "revenue": p["current"],
            "transactions": p["bills"],
            "quantity": p["quantity"],
        }
        for p in dash_trend
    ]
    out: Dict[str, Any] = {
        "dashboard": {
            "trend": dash_trend,
            "period_label": dr.label,
            "date_range": {"start": dr.start, "end": dr.end},
        },
        "trend": {"trend": api_trend},
    }
    return "yoy_bundle", out, (time.perf_counter() - t0) * 1000


def _fetch_categories(
    conn: Any,
    env: AnalyticsEnv,
    dr: DateRange,
    top_n: int,
) -> Tuple[str, Dict[str, Any], float]:
    t0 = time.perf_counter()
    tbl = sql_table(env.sales_table)
    dc = env.date_column
    n = min(max(top_n, 1), API_TOP_N_MAX)
    sql = f"""
        SELECT TOP ({n})
            [{env.category_dim}] AS Category,
            SUM([{env.amount_column}]) AS Revenue,
            {_transactions_aggregate(env)} AS Transactions,
            CAST(
                SUM([{env.amount_column}]) * 100.0
                / SUM(SUM([{env.amount_column}])) OVER ()
                AS DECIMAL(10,2)
            ) AS Percentage
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= ?
          AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        GROUP BY [{env.category_dim}]
        ORDER BY Revenue DESC
        OPTION (RECOMPILE)
    """
    recs = _execute_sql(conn, sql, (dr.start, dr.end))
    cats = [
        {
            "category": str(r.get("Category", "")),
            "revenue": _safe_float(r.get("Revenue")),
            "transactions": int(_safe_float(r.get("Transactions"))),
            "percentage": _safe_float(r.get("Percentage")),
        }
        for r in recs
    ]
    return "categories", {"categories": cats}, (time.perf_counter() - t0) * 1000


def _fetch_departments(
    conn: Any,
    env: AnalyticsEnv,
    dr: DateRange,
    top_n: int,
) -> Tuple[str, Dict[str, Any], float]:
    t0 = time.perf_counter()
    tbl = sql_table(env.sales_table)
    dc = env.date_column
    n = min(max(top_n, 1), API_TOP_N_MAX)
    sql = f"""
        SELECT TOP ({n})
            [{env.department_dim}] AS Department,
            SUM([{env.amount_column}]) AS Revenue,
            {_transactions_aggregate(env)} AS Transactions
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= ?
          AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        GROUP BY [{env.department_dim}]
        ORDER BY Revenue DESC
        OPTION (RECOMPILE)
    """
    recs = _execute_sql(conn, sql, (dr.start, dr.end))
    depts = [
        {
            "department": str(r.get("Department", "")),
            "revenue": _safe_float(r.get("Revenue")),
            "transactions": int(_safe_float(r.get("Transactions"))),
        }
        for r in recs
    ]
    return "departments", {"departments": depts}, (time.perf_counter() - t0) * 1000


def _fetch_kpis(
    conn: Any,
    env: AnalyticsEnv,
    dr: DateRange,
    ly_dr: DateRange,
) -> Tuple[str, Dict[str, Any], float]:
    t0 = time.perf_counter()
    tbl = sql_table(env.sales_table)
    dc = env.date_column
    bills_case = _bill_count_case(env)
    sql = f"""
        SELECT
            ISNULL(SUM(CASE WHEN [{dc}] >= ? AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
                THEN [{env.amount_column}] ELSE 0 END), 0) AS CurrentSales,
            ISNULL(SUM(CASE WHEN [{dc}] >= ? AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
                THEN [{env.amount_column}] ELSE 0 END), 0) AS LYSales,
            ISNULL({bills_case}, 0) AS Bills,
            ISNULL(SUM(CASE WHEN [{dc}] >= ? AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
                THEN [{env.quantity_column}] ELSE 0 END), 0) AS Quantity
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= ?
          AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        OPTION (RECOMPILE)
    """
    params = (
        dr.start,
        dr.end,
        ly_dr.start,
        ly_dr.end,
        dr.start,
        dr.end,
        dr.start,
        dr.end,
        ly_dr.start,
        dr.end,
    )
    recs = _execute_sql(conn, sql, params)
    row = recs[0] if recs else {}
    curr = _safe_float(row.get("CurrentSales"))
    ly = _safe_float(row.get("LYSales"))
    growth = round((curr - ly) / ly * 100, 2) if ly else None
    kpis = {
        "revenue": {"value": curr, "prior": ly, "growth": growth},
        "transactions": {
            "value": int(_safe_float(row.get("Bills"))),
            "prior": None,
            "growth": None,
        },
        "quantity": {"value": _safe_float(row.get("Quantity")), "prior": None, "growth": None},
    }
    return "kpis", kpis, (time.perf_counter() - t0) * 1000


def _fetch_summary_for_dashboard(
    conn: Any,
    env: AnalyticsEnv,
    dr: DateRange,
    ly_dr: DateRange,
) -> Dict[str, Any]:
    tbl = sql_table(env.sales_table)
    dc = env.date_column
    bills_case = _bill_count_case(env)
    sql = f"""
        SELECT
            ISNULL(SUM(CASE WHEN [{dc}] >= ? AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
                THEN [{env.amount_column}] ELSE 0 END), 0) AS CurrentSales,
            ISNULL(SUM(CASE WHEN [{dc}] >= ? AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
                THEN [{env.amount_column}] ELSE 0 END), 0) AS LYSales,
            ISNULL({bills_case}, 0) AS Bills,
            ISNULL(SUM(CASE WHEN [{dc}] >= ? AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
                THEN [{env.quantity_column}] ELSE 0 END), 0) AS Quantity
        FROM {tbl} WITH (NOLOCK)
        WHERE [{dc}] >= ?
          AND [{dc}] < DATEADD(day,1,CAST(? AS DATE))
        OPTION (RECOMPILE)
    """
    params = (
        dr.start,
        dr.end,
        ly_dr.start,
        ly_dr.end,
        dr.start,
        dr.end,
        dr.start,
        dr.end,
        ly_dr.start,
        dr.end,
    )
    recs = _execute_sql(conn, sql, params)
    row = recs[0] if recs else {}
    curr = _safe_float(row.get("CurrentSales"))
    ly = _safe_float(row.get("LYSales"))
    growth = round((curr - ly) / ly * 100, 2) if ly else None
    return {
        "mtd_sales": curr,
        "ly_sales": ly,
        "sales_growth_pct": growth,
        "quantity": _safe_float(row.get("Quantity")),
        "bills": int(_safe_float(row.get("Bills"))),
    }


def _run_query_with_fresh_connection(
    fn: Callable[[Any], Tuple[str, Dict[str, Any], float]],
) -> Tuple[str, Dict[str, Any], float]:
    """
    pyodbc connections are not safe for concurrent commands. Parallel workers each
    need their own SQL Server session to avoid:
    Connection is busy with results for another command (HY000).
    """
    isolated, _drv = connect_mssql()
    try:
        return fn(isolated)
    finally:
        try:
            isolated.close()
        except Exception:
            pass


def fetch_mtd_from_db(
    conn: Any,
    *,
    use_dashboard: bool,
    with_departments: bool,
    include_kpis: bool,
    top_n: int,
    sequential: bool,
) -> Tuple[Dict[str, Any], str]:
    env = AnalyticsEnv.from_os()
    dr = resolve_date_range(PERIOD)
    ly_dr = get_prior_year_range(PERIOD)
    timings: Dict[str, float] = {}

    # Each callable takes a connection (same queries as backend charts/dashboard).
    job_fns: List[Callable[[Any], Tuple[str, Dict[str, Any], float]]] = []
    if use_dashboard:
        job_fns.extend(
            [
                lambda c: _fetch_trend_yoy(c, env, dr, ly_dr),
                lambda c: _fetch_branches(c, env, dr),
                lambda c: _fetch_categories(c, env, dr, top_n),
            ]
        )
        if with_departments:
            job_fns.append(lambda c: _fetch_departments(c, env, dr, top_n))
    else:
        job_fns.extend(
            [
                lambda c: _fetch_branches(c, env, dr),
                lambda c: _fetch_trend_daily(c, env, dr),
                lambda c: _fetch_categories(c, env, dr, top_n),
            ]
        )
        if with_departments:
            job_fns.append(lambda c: _fetch_departments(c, env, dr, top_n))

    raw: Dict[str, Any] = {"_timings_ms": timings}

    def _merge_job_result(name: str, data: Dict[str, Any], ms: float) -> None:
        timings[name] = round(ms, 1)
        if name == "yoy_bundle":
            raw.update(data)
        else:
            # Keep {"branches": {"branches": [...]}} shape expected by build_report
            raw[name] = data

    if sequential:
        for fn in job_fns:
            name, data, ms = fn(conn)
            _merge_job_result(name, data, ms)
    else:
        with ThreadPoolExecutor(max_workers=len(job_fns)) as pool:
            futs = [pool.submit(_run_query_with_fresh_connection, fn) for fn in job_fns]
            for fut in as_completed(futs):
                name, data, ms = fut.result()
                _merge_job_result(name, data, ms)

    if include_kpis and not use_dashboard:
        name, kpi_payload, kms = _fetch_kpis(conn, env, dr, ly_dr)
        timings[name] = round(kms, 1)
        raw["kpis"] = kpi_payload

    if use_dashboard:
        summ = _fetch_summary_for_dashboard(conn, env, dr, ly_dr)
        dash = raw.setdefault("dashboard", {})
        dash["summary"] = summ
        raw["_mode"] = (
            "sql (dashboard YoY, parallel)" if not sequential else "sql (dashboard YoY, sequential)"
        )

    contrib_branches = raw.get("branches", {}).get("branches") or []
    contrib_cats = raw.get("categories", {}).get("categories") or []
    if use_dashboard and contrib_branches:
        raw.setdefault("dashboard", {})["branches"] = [
            {"name": b.get("branch"), "revenue": b.get("revenue")} for b in contrib_branches
        ]
    if use_dashboard and contrib_cats:
        raw.setdefault("dashboard", {})["categories"] = [
            {"name": c.get("category"), "revenue": c.get("revenue"), "percentage": c.get("percentage")}
            for c in contrib_cats
        ]

    if not use_dashboard:
        raw["_mode"] = (
            "sql (parallel, one connection per worker)" if not sequential else "sql (sequential)"
        )

    return raw, str(raw.get("_mode", "sql"))


def _n(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def lakhs(v: float) -> str:
    return f"₹{v / 100_000:,.2f} L"


def _day_label(iso_date: str) -> str:
    try:
        d = datetime.fromisoformat(iso_date[:10])
        return d.strftime("%d-%b")
    except ValueError:
        return iso_date[:10]


def build_report(raw: Dict[str, Any]) -> Dict[str, Any]:
    dash = raw.get("dashboard") or {}
    kpis = raw.get("kpis") or {}
    api_trend = (raw.get("trend") or {}).get("trend") or []

    summary = dict(dash.get("summary") or {})
    if not summary and kpis:
        rev = kpis.get("revenue") or {}
        txn = kpis.get("transactions") or {}
        qty = kpis.get("quantity") or {}
        summary = {
            "mtd_sales": rev.get("value"),
            "ly_sales": rev.get("prior"),
            "sales_growth_pct": rev.get("growth"),
            "bills": txn.get("value"),
            "quantity": qty.get("value") or 0,
        }

    trend_pts = dash.get("trend") or []
    dash_cats = dash.get("categories") or []
    dash_branches = dash.get("branches") or []

    api_branches = (raw.get("branches") or {}).get("branches") or []
    api_categories = (raw.get("categories") or {}).get("categories") or []
    api_departments = (raw.get("departments") or {}).get("departments") or []

    branches = (
        api_branches
        if api_branches
        else [
            {"branch": b.get("name"), "revenue": b.get("revenue"), "transactions": None}
            for b in dash_branches
        ]
    )
    categories = (
        api_categories
        if api_categories
        else [
            {
                "category": c.get("name"),
                "revenue": c.get("revenue"),
                "transactions": None,
                "percentage": c.get("percentage"),
            }
            for c in dash_cats
        ]
    )

    if trend_pts:
        daywise = [
            {
                "date": p.get("date"),
                "label": p.get("label"),
                "sales": _n(p.get("current")),
                "sales_lakhs": round(_n(p.get("current")) / 100_000, 4),
                "last_year_sales": _n(p.get("prior")),
                "bills": int(_n(p.get("bills"))),
                "quantity": _n(p.get("quantity")),
            }
            for p in trend_pts
        ]
    else:
        daywise = [
            {
                "date": str(t.get("date", ""))[:10],
                "label": _day_label(str(t.get("date", ""))),
                "sales": _n(t.get("revenue")),
                "sales_lakhs": round(_n(t.get("revenue")) / 100_000, 4),
                "last_year_sales": 0,
                "bills": int(_n(t.get("transactions"))),
                "quantity": _n(t.get("quantity")),
            }
            for t in api_trend
        ]

    if not summary.get("mtd_sales") and daywise:
        summary = {
            **summary,
            "mtd_sales": sum(d["sales"] for d in daywise),
            "bills": summary.get("bills") or sum(d["bills"] for d in daywise),
            "quantity": summary.get("quantity") or sum(d["quantity"] for d in daywise),
        }
    elif summary.get("quantity") in (None, 0) and daywise:
        summary = {**summary, "quantity": sum(d["quantity"] for d in daywise)}

    branch_rows = sorted(
        [
            {
                "branch": str(b.get("branch", b.get("name", ""))),
                "sales": _n(b.get("revenue")),
                "sales_lakhs": round(_n(b.get("revenue")) / 100_000, 4),
                "transactions": int(_n(b.get("transactions")))
                if b.get("transactions") is not None
                else None,
            }
            for b in branches
        ],
        key=lambda x: -x["sales"],
    )

    category_rows = sorted(
        [
            {
                "category": str(c.get("category", c.get("name", ""))),
                "sales": _n(c.get("revenue")),
                "sales_lakhs": round(_n(c.get("revenue")) / 100_000, 4),
                "transactions": int(_n(c.get("transactions")))
                if c.get("transactions") is not None
                else None,
                "share_pct": _n(c.get("percentage")),
            }
            for c in categories
        ],
        key=lambda x: -x["sales"],
    )

    department_rows = sorted(
        [
            {
                "department": str(d.get("department", "")),
                "sales": _n(d.get("revenue")),
                "sales_lakhs": round(_n(d.get("revenue")) / 100_000, 4),
                "transactions": int(_n(d.get("transactions"))),
            }
            for d in api_departments
        ],
        key=lambda x: -x["sales"],
    )

    total_sales = _n(summary.get("mtd_sales"))
    period_label = dash.get("period_label") or "Month-to-Date"
    date_range = dash.get("date_range")
    if not date_range and daywise:
        date_range = {"start": daywise[0]["date"], "end": daywise[-1]["date"]}
    elif not date_range:
        ddr = resolve_date_range(PERIOD)
        date_range = {"start": ddr.start, "end": ddr.end}

    return {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "period": PERIOD,
        "period_label": period_label,
        "date_range": date_range,
        "summary": {
            "total_sales": total_sales,
            "total_sales_lakhs": round(total_sales / 100_000, 4),
            "bills": int(_n(summary.get("bills"))),
            "quantity": _n(summary.get("quantity")),
            "ly_sales": _n(summary.get("ly_sales")),
            "sales_growth_pct": summary.get("sales_growth_pct"),
        },
        "daywise": daywise,
        "branch_wise": branch_rows,
        "category_wise": category_rows,
        "department_wise": department_rows,
        "counts": {
            "days": len(daywise),
            "branches": len(branch_rows),
            "categories": len(category_rows),
            "departments": len(department_rows),
        },
        "_timings_ms": raw.get("_timings_ms"),
        "_errors": raw.get("_errors"),
        "_mode": raw.get("_mode"),
    }


def _print_table(title: str, headers: List[str], rows: List[List[str]]) -> None:
    print(f"\n{'=' * 78}")
    print(f"  {title} ({len(rows)} rows)")
    print("=" * 78)
    if not rows:
        print("  (no data)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("-" * (sum(widths) + 2 * (len(headers) - 1)))
    for row in rows:
        print(fmt.format(*row))


def print_report(r: Dict[str, Any]) -> None:
    s = r["summary"]
    dr = r.get("date_range") or {}
    print()
    print("=" * 78)
    print("  MTD SALES BREAKDOWN (Month-to-date)")
    print(f"  {r.get('period_label', 'MTD')}  |  {dr.get('start', '?')} to {dr.get('end', '?')}")
    print(f"  Fetched: {r['fetched_at']}")
    if r.get("_timings_ms"):
        print(f"  SQL timings (ms): {r['_timings_ms']}")
    if r.get("_mode"):
        print(f"  Mode: {r['_mode']}")
    print("=" * 78)
    print(
        f"\n  TOTAL MTD SALES: {lakhs(s['total_sales'])}  |  Bills: {s['bills']:,}  |  Qty: {s['quantity']:,.0f}"
    )
    if s.get("sales_growth_pct") is not None:
        print(
            f"  vs last year (same dates): {s['sales_growth_pct']:+.2f}%  (LY {lakhs(s['ly_sales'])})"
        )

    _print_table(
        "DAY-WISE SALES",
        ["#", "Date", "Label", "Sales", "Bills", "Qty", "LY Sales"],
        [
            [
                str(i + 1),
                str(d["date"]),
                str(d["label"]),
                lakhs(d["sales"]),
                str(d["bills"]),
                f"{d['quantity']:,.0f}",
                lakhs(d["last_year_sales"]),
            ]
            for i, d in enumerate(r["daywise"])
        ],
    )

    _print_table(
        "BRANCH-WISE SALES (all branches)",
        ["#", "Branch", "Sales", "Bills"],
        [
            [
                str(i + 1),
                row["branch"],
                lakhs(row["sales"]),
                str(row["transactions"]) if row["transactions"] is not None else "—",
            ]
            for i, row in enumerate(r["branch_wise"])
        ],
    )

    _print_table(
        "CATEGORY-WISE SALES (all returned)",
        ["#", "Category", "Sales", "Share %", "Bills"],
        [
            [
                str(i + 1),
                row["category"],
                lakhs(row["sales"]),
                f"{row['share_pct']:.2f}" if row.get("share_pct") else "—",
                str(row["transactions"]) if row["transactions"] is not None else "—",
            ]
            for i, row in enumerate(r["category_wise"])
        ],
    )

    if r["department_wise"]:
        _print_table(
            "DEPARTMENT-WISE SALES (all returned)",
            ["#", "Department", "Sales", "Bills"],
            [
                [
                    str(i + 1),
                    row["department"],
                    lakhs(row["sales"]),
                    str(row["transactions"]),
                ]
                for i, row in enumerate(r["department_wise"])
            ],
        )
    else:
        print(f"\n{'=' * 78}")
        print("  DEPARTMENT-WISE — skipped (re-run without --no-departments)")
        print("=" * 78)

    c = r["counts"]
    print(
        f"\n  Totals listed: {c['days']} days | {c['branches']} branches | "
        f"{c['categories']} categories | {c['departments']} departments"
    )
    if r.get("_errors"):
        print(f"  Warnings: {r['_errors']}")
    print()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="MTD sales: day / branch / category / department (direct SQL)",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Day-wise with last-year column (runs extra SQL for YoY trend)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run SQL one after another on the main connection (parallel mode opens one ODBC connection per query batch)",
    )
    parser.add_argument(
        "--no-departments",
        action="store_true",
        help="Skip department breakdown",
    )
    parser.add_argument(
        "--with-kpis",
        action="store_true",
        help="Include YoY KPI block (matches optional bundle KPIs)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=API_TOP_N_MAX,
        help=f"Category/department TOP N (max {API_TOP_N_MAX})",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument("-o", "--output", help="Write JSON report to file")
    args = parser.parse_args()

    _load_dotenv_files()
    t0 = time.perf_counter()

    _log("Connecting to SQL Server (backend/.env DB_* or ERP_DB_*)...")
    conn, driver = connect_mssql()
    _log(f"  Connected via {driver}")

    try:
        raw, mode = fetch_mtd_from_db(
            conn,
            use_dashboard=args.dashboard,
            with_departments=not args.no_departments,
            include_kpis=args.with_kpis and not args.dashboard,
            top_n=args.top_n,
            sequential=args.sequential,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    raw["_mode"] = mode
    _log("Done querying. Building report...")
    report = build_report(raw)
    report["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Wrote {args.output}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif not args.output:
        print_report(report)
    else:
        print_report(report)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
