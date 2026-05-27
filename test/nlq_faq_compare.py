"""
Comparison-style FAQ SQL templates (extends nlq_faq_sql).

Loaded at import-finish of nlq_faq_sql via register_compare_faqs().
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Tuple

COMPARE_AI_QUERIES: Tuple[str, ...] = (
    "Compare this month sales vs last month",
    "Compare branch sales for Chennai vs Bangalore",
    "Compare department performance year over year",
    "Compare weekday vs weekend sales",
    "Compare online vs offline sales",
    "Compare category sales across branches",
    "Compare top 5 suppliers by revenue",
    "Compare current quarter vs previous quarter",
    "Compare bill count between branches",
    "Compare sales before and after discount campaigns",
)


def _two_places_from_question(q: str, default_a: str = "Chennai", default_b: str = "Bangalore") -> Tuple[str, str]:
    m = re.search(
        r"(?:for|between)\s+([a-z][a-z\s]{1,30}?)\s+vs\.?\s+([a-z][a-z\s]{1,30}?)(?:\s|$|\?)",
        q,
        re.I,
    )
    if m:
        return m.group(1).strip().title(), m.group(2).strip().title()
    m = re.search(r"\b([a-z]{3,})\s+vs\.?\s+([a-z]{3,})\b", q, re.I)
    if m:
        return m.group(1).strip().title(), m.group(2).strip().title()
    return default_a, default_b


def register_compare_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _SALESPERSON,
        _blob,
        _cashmemo_mtd_where,
        _mtd_where,
        _top_n_from_question,
    )

    def _sql_quarter_vs_prev_quarter(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Bounds AS (
    SELECT
        DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1) AS CurrQStart,
        DATEADD(QUARTER, -1, DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1)) AS PrevQStart
),
Sales AS (
    SELECT
        CASE
            WHEN s.[XnDt] >= b.CurrQStart
             AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
                THEN N'CurrentQuarter'
            WHEN s.[XnDt] >= b.PrevQStart AND s.[XnDt] < b.CurrQStart
                THEN N'PreviousQuarter'
        END AS PeriodLabel,
        s.[NetAmount]
    FROM {_APP} s WITH (NOLOCK)
    CROSS JOIN Bounds b
    WHERE s.[XnDt] >= b.PrevQStart
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    PeriodLabel,
    CAST(SUM([NetAmount]) AS decimal(18, 2)) AS TotalSales
FROM Sales
WHERE PeriodLabel IS NOT NULL
GROUP BY PeriodLabel
ORDER BY PeriodLabel DESC
"""
        return _blob(
            "compare_current_quarter_vs_previous_quarter",
            sql,
            "Net sales for the current calendar quarter vs the immediately prior quarter.",
            [
                "Current quarter is QTD through today; previous quarter is the full prior quarter.",
                "Distinct from 'QTD vs last year QTD' (see ytd_growth templates).",
            ],
        )

    def _sql_branch_cities_compare(q: str) -> Dict[str, Any]:
        city_a, city_b = _two_places_from_question(q)
        sql = f"""
SELECT
    CASE
        WHEN sp.[BranchCity] LIKE N'%{city_a}%' THEN N'{city_a}'
        WHEN sp.[BranchCity] LIKE N'%{city_b}%' THEN N'{city_b}'
    END AS City,
    sp.[BranchAlias] AS Store,
    CAST(SUM(sp.[SalesNetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT sp.[CashmemoNo]) AS BillCount
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE {_cashmemo_mtd_where("sp")}
  AND (
        sp.[BranchCity] LIKE N'%{city_a}%'
     OR sp.[BranchCity] LIKE N'%{city_b}%'
      )
GROUP BY
    CASE
        WHEN sp.[BranchCity] LIKE N'%{city_a}%' THEN N'{city_a}'
        WHEN sp.[BranchCity] LIKE N'%{city_b}%' THEN N'{city_b}'
    END,
    sp.[BranchAlias]
HAVING CASE
        WHEN sp.[BranchCity] LIKE N'%{city_a}%' THEN N'{city_a}'
        WHEN sp.[BranchCity] LIKE N'%{city_b}%' THEN N'{city_b}'
    END IS NOT NULL
ORDER BY City, MTDSales DESC
"""
        return _blob(
            "compare_branch_sales_two_cities",
            sql,
            f"MTD branch-level sales in {city_a} vs {city_b} (BranchCity on salesperson view).",
            [
                f"Cities parsed from question: {city_a}, {city_b}.",
                "Uses CashmemoDt MTD and SalesNetAmount.",
            ],
        )

    def _sql_department_yoy(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Bounds AS (
    SELECT
        DATEFROMPARTS(YEAR(GETDATE()), 1, 1) AS CurrYStart,
        DATEFROMPARTS(YEAR(GETDATE()) - 1, 1, 1) AS PrevYStart,
        DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) AS PrevYEnd
)
SELECT TOP (500)
    s.[DepartmentShortName] AS Department,
    CAST(SUM(CASE
        WHEN s.[XnDt] >= b.CurrYStart AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
        THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2)) AS CurrentYTD,
    CAST(SUM(CASE
        WHEN s.[XnDt] >= b.PrevYStart AND s.[XnDt] < b.PrevYEnd
        THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2)) AS LastYearYTD,
    CAST(SUM(CASE
        WHEN s.[XnDt] >= b.CurrYStart AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
        THEN s.[NetAmount] ELSE 0 END)
      - SUM(CASE
        WHEN s.[XnDt] >= b.PrevYStart AND s.[XnDt] < b.PrevYEnd
        THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2)) AS YoYChange
FROM {_APP} s WITH (NOLOCK)
CROSS JOIN Bounds b
WHERE s.[DepartmentShortName] IS NOT NULL
  AND s.[XnDt] >= b.PrevYStart
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY s.[DepartmentShortName]
ORDER BY CurrentYTD DESC
"""
        return _blob(
            "compare_department_performance_yoy",
            sql,
            "Each department: current YTD sales vs same day-range last year YTD.",
            ["Aligned YTD windows using DATEADD(YEAR,-1) on today's date."],
        )

    def _sql_weekday_vs_weekend(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    CASE
        WHEN DATEPART(WEEKDAY, s.[XnDt]) IN (1, 7) THEN N'Weekend'
        ELSE N'Weekday'
    END AS DayType,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT s.[XnNo]) AS BillCount
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
GROUP BY CASE
    WHEN DATEPART(WEEKDAY, s.[XnDt]) IN (1, 7) THEN N'Weekend'
    ELSE N'Weekday'
END
ORDER BY DayType
"""
        return _blob(
            "compare_weekday_vs_weekend_sales",
            sql,
            "MTD total sales and bill count: weekdays vs weekends (SQL Server WEEKDAY 1=Sun, 7=Sat).",
            ["Weekend definition follows server DATEFIRST default."],
        )

    def _sql_online_offline_blocked(_q: str) -> Dict[str, Any]:
        sql = """
SELECT
    N'Not supported' AS Status,
    N'No online/offline or channel column on VW_MB_POWERBI_APP_REPORT in schema_catalog.txt.' AS Reason,
    N'If e-commerce uses dedicated branch aliases, ask: compare branch sales for <OnlineBranch> vs <StoreBranch>.' AS Suggestion
"""
        return _blob(
            "compare_online_vs_offline_not_supported",
            sql,
            "Online vs offline split requires a channel flag or branch mapping not in the semantic catalog.",
            ["Informational single-row result."],
        )

    def _sql_category_sales_across_branches(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[CategoryShortName] AS Category,
    s.[BranchAlias] AS Store,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[CategoryShortName] IS NOT NULL
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[CategoryShortName], s.[BranchAlias]
ORDER BY s.[CategoryShortName], MTDSales DESC
"""
        return _blob(
            "compare_category_sales_across_branches",
            sql,
            "MTD net sales by category and branch (matrix-style rows).",
            ["TOP 500 rows — filter to one category in a follow-up if needed."],
        )

    def _sql_top_suppliers_by_revenue_compare(q: str) -> Dict[str, Any]:
        n = _top_n_from_question(q, default=5)
        sql = f"""
SELECT TOP ({n})
    s.[SupplierName] AS Supplier,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
ORDER BY MTDRevenue DESC
"""
        return _blob(
            "compare_top_suppliers_by_revenue",
            sql,
            f"Top {n} suppliers by MTD net revenue (ranked for comparison).",
            ["Use as a comparison list; contribution % available via supplier contribution template."],
        )

    def _sql_bill_count_between_branches(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[BranchAlias] AS Store,
    COUNT(DISTINCT s.[XnNo]) AS BillCount,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[BranchAlias]
ORDER BY BillCount DESC
"""
        return _blob(
            "compare_bill_count_between_branches",
            sql,
            "MTD distinct invoice count and sales by branch for side-by-side comparison.",
            ["BillCount = COUNT(DISTINCT XnNo) on APP_REPORT lines."],
        )

    def _sql_discount_before_after_proxy(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Periods AS (
    SELECT
        CASE
            WHEN s.[XnDt] >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE))
             AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
                THEN N'Last30Days'
            WHEN s.[XnDt] >= DATEADD(DAY, -60, CAST(GETDATE() AS DATE))
             AND s.[XnDt] < DATEADD(DAY, -30, CAST(GETDATE() AS DATE))
                THEN N'Prior30Days'
        END AS PeriodLabel,
        s.[MrpValue],
        s.[NetAmount]
    FROM {_APP} s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(DAY, -60, CAST(GETDATE() AS DATE))
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    PeriodLabel,
    CAST(SUM([MrpValue]) AS decimal(18, 2)) AS TotalMRP,
    CAST(SUM([NetAmount]) AS decimal(18, 2)) AS TotalNetSales,
    CAST(SUM([MrpValue]) - SUM([NetAmount]) AS decimal(18, 2)) AS ImpliedDiscountValue,
    CAST(
        100.0 * (SUM([MrpValue]) - SUM([NetAmount])) / NULLIF(SUM([MrpValue]), 0)
        AS decimal(18, 4)
    ) AS ImpliedDiscountPct
FROM Periods
WHERE PeriodLabel IS NOT NULL
GROUP BY PeriodLabel
ORDER BY PeriodLabel DESC
"""
        return _blob(
            "compare_sales_before_after_discount_proxy",
            sql,
            "Proxy: implied discount (MRP − net) for last 30 days vs prior 30 days — not campaign-specific.",
            [
                "No campaign calendar in catalog; cannot tie to named discount events.",
                "MrpValue and NetAmount on APP_REPORT.",
            ],
        )

    specs: List[tuple] = [
        (
            "compare_branch_sales_two_cities",
            [
                r"compare\s+branch\s+sales?\s+for\s+[a-z].+?\s+vs\.?\s+[a-z]",
                r"compare\s+branch\s+sales?\s+.*chennai.*bangalore",
            ],
            _sql_branch_cities_compare,
        ),
        (
            "compare_department_performance_yoy",
            [
                r"compare\s+department\s+performance\s+year\s+over\s+year",
                r"department\s+performance\s+yoy",
                r"compare\s+department.*year\s+over\s+year",
            ],
            _sql_department_yoy,
        ),
        (
            "compare_weekday_vs_weekend_sales",
            [
                r"compare\s+weekday\s+vs\.?\s+weekend\s+sales?",
                r"weekday\s+vs\.?\s+weekend\s+sales?",
            ],
            _sql_weekday_vs_weekend,
        ),
        (
            "compare_online_vs_offline_not_supported",
            [
                r"compare\s+online\s+vs\.?\s+offline\s+sales?",
                r"online\s+vs\.?\s+offline\s+sales?",
            ],
            _sql_online_offline_blocked,
        ),
        (
            "compare_category_sales_across_branches",
            [
                r"compare\s+categor(?:y|ies)\s+sales?\s+across\s+branches?",
                r"categor(?:y|ies)\s+sales?\s+across\s+branches?",
            ],
            _sql_category_sales_across_branches,
        ),
        (
            "compare_top_suppliers_by_revenue",
            [
                r"compare\s+top\s+\d+\s+suppliers?\s+by\s+revenue",
                r"compare\s+top\s+5\s+suppliers?\s+by\s+revenue",
                r"top\s+5\s+suppliers?\s+by\s+revenue",
            ],
            _sql_top_suppliers_by_revenue_compare,
        ),
        (
            "compare_current_quarter_vs_previous_quarter",
            [
                r"compare\s+current\s+quarter\s+vs\.?\s+previous\s+quarter",
                r"current\s+quarter\s+vs\.?\s+previous\s+quarter",
                r"compare\s+this\s+quarter\s+vs\.?\s+last\s+quarter",
            ],
            _sql_quarter_vs_prev_quarter,
        ),
        (
            "compare_bill_count_between_branches",
            [
                r"compare\s+bill\s+count\s+between\s+branches?",
                r"compare\s+bill\s+counts?\s+by\s+branch",
                r"bill\s+count\s+between\s+branches?",
            ],
            _sql_bill_count_between_branches,
        ),
        (
            "compare_sales_before_after_discount_proxy",
            [
                r"compare\s+sales?\s+before\s+and\s+after\s+discount",
                r"before\s+and\s+after\s+discount\s+campaigns?",
                r"discount\s+campaigns?.*compare",
            ],
            _sql_discount_before_after_proxy,
        ),
    ]

    for tid, patterns, builder in specs:
        register(tid, patterns, builder)
