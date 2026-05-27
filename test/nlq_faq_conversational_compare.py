"""
Conversational / modifier comparison FAQ templates for NLQ memory testing.

These return standalone SQL on VW_MB_POWERBI_APP_REPORT (and related views).
Short follow-ups (e.g. "only Chennai") still use ConversationMemory + OpenAI in the terminal.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Tuple

_BRANCH_LIST = "dbo.VW_MB_POWERBI_BRANCH_LIST"

CONVERSATIONAL_COMPARE_AI_QUERIES: Tuple[str, ...] = (
    "Compare this with last year",
    "Compare only Chennai branches",
    "Compare top 5 categories",
    "Compare excluding returns",
    "Compare by quantity instead of revenue",
    "Compare only premium products",
    "Compare supplier-wise",
    "Compare trend month over month",
    "Compare before and after Diwali",
    "Compare branch contribution percentage",
    "Compare Chennai vs Bangalore sales this month",
)


def _two_places(q: str, default_a: str = "Chennai", default_b: str = "Bangalore") -> Tuple[str, str]:
    m = re.search(
        r"([a-z][a-z\s]{1,24}?)\s+vs\.?\s+([a-z][a-z\s]{1,24}?)(?:\s+sales|\s+this|\s|$|\?)",
        q,
        re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"\b(chennai|bangalore|bengaluru|mumbai|delhi)\b.*\b(vs\.?|versus)\b.*\b(chennai|bangalore|bengaluru|mumbai|delhi)\b", q, re.I)
    if m:
        return m.group(1).title(), m.group(3).title()
    return default_a, default_b


def _city_filter_pat(city: str) -> str:
    core = re.sub(r"[^a-z0-9]", "", city.lower()) or "chennai"
    return f"%{core}%"


def register_conversational_compare_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _SLSXNS,
        _blob,
        _mtd_where,
        _top_n_from_question,
    )

    def _sql_this_vs_last_year(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    N'CurrentMTD' AS PeriodLabel,
    CAST(SUM(CASE
        WHEN s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
         AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
        THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2)) AS TotalSales
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
UNION ALL
SELECT
    N'LastYearMTD',
    CAST(SUM(CASE
        WHEN s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
         AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE)))
        THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2))
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
"""
        return _blob(
            "conversational_compare_this_vs_last_year",
            sql,
            "MTD net sales this year vs the same calendar MTD window last year (two rows).",
            [
                "Standalone compare — for branch/category filters, ask a follow-up after this run.",
                "Uses APP_REPORT NetAmount and XnDt.",
            ],
        )

    def _sql_only_chennai_branches(_q: str) -> Dict[str, Any]:
        pat = _city_filter_pat("Chennai")
        sql = f"""
SELECT TOP (500)
    s.[BranchAlias],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT s.[XnNo]) AS BillCount
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND (
        s.[BranchAlias] LIKE N'{pat}'
     OR EXISTS (
            SELECT 1
            FROM {_BRANCH_LIST} br WITH (NOLOCK)
            WHERE (br.[ShortName] = s.[BranchAlias] OR br.[BranchName] = s.[BranchAlias])
              AND br.[City] LIKE N'{pat}'
        )
      )
GROUP BY s.[BranchAlias]
ORDER BY MTDSales DESC
"""
        return _blob(
            "conversational_compare_only_chennai_branches",
            sql,
            "MTD sales by branch filtered to Chennai (BranchAlias or BRANCH_LIST.City LIKE).",
            ["Modifier template — pair with memory for 'same but only Chennai' follow-ups."],
        )

    def _sql_top_n_categories(q: str) -> Dict[str, Any]:
        n = _top_n_from_question(q, default=5)
        sql = f"""
SELECT TOP ({n})
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName]
ORDER BY MTDRevenue DESC
"""
        return _blob(
            "conversational_compare_top_categories",
            sql,
            f"Top {n} categories by MTD net sales for comparison.",
            ["Change N via 'top 10' in the question."],
        )

    def _sql_excluding_returns(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    N'Net sales (APP billing)' AS MetricSource,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDNetSales,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[NetAmount] > 0
UNION ALL
SELECT
    N'Return qty (SLSXNS SlrQty)',
    NULL,
    CAST(SUM(x.[SlrQty]) AS decimal(18, 4))
FROM {_SLSXNS} x WITH (NOLOCK)
WHERE {_mtd_where("x")}
  AND x.[SlrQty] > 0
"""
        return _blob(
            "conversational_compare_excluding_returns",
            sql,
            "Compare net billed sales (APP, positive NetAmount) vs return quantity on SLSXNS (reference).",
            [
                "APP_REPORT is net billing — not double-counting returns in revenue.",
                "Use APP-only follow-up for sales comparisons excluding returns.",
            ],
        )

    def _sql_by_quantity_not_revenue(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[BranchAlias],
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[BranchAlias]
ORDER BY MTDQtySold DESC
"""
        return _blob(
            "conversational_compare_by_quantity_instead_of_revenue",
            sql,
            "MTD comparison ranked by quantity (AppQty) with revenue shown for context.",
            ["Primary sort = SUM(AppQty); use for 'compare by units' requests."],
        )

    def _sql_premium_products_only(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    CASE
        WHEN s.[ItemMRP] >= 2999 THEN N'Premium (MRP >= 2999)'
        ELSE N'Non-premium'
    END AS PriceBand,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[ItemMRP] IS NOT NULL
GROUP BY CASE
    WHEN s.[ItemMRP] >= 2999 THEN N'Premium (MRP >= 2999)'
    ELSE N'Non-premium'
END
ORDER BY MTDRevenue DESC
"""
        return _blob(
            "conversational_compare_premium_products_only",
            sql,
            "MTD sales: premium band (ItemMRP >= 2999) vs non-premium for comparison.",
            ["Threshold heuristic — align with your price band definitions."],
        )

    def _sql_supplier_wise(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[SupplierName],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
ORDER BY MTDRevenue DESC
"""
        return _blob(
            "conversational_compare_supplier_wise",
            sql,
            "MTD net sales by supplier (supplier-wise comparison list).",
            ["Uses SupplierName on APP_REPORT."],
        )

    def _sql_trend_month_over_month(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (24)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    DATENAME(MONTH, DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1))
        + N' ' + CAST(YEAR(DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)) AS varchar(4)) AS MonthLabel,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
ORDER BY MonthStart ASC
"""
        return _blob(
            "conversational_compare_trend_month_over_month",
            sql,
            "Month-over-month net sales trend for the last 12 months.",
            ["One row per calendar month on XnDt."],
        )

    def _sql_before_after_diwali(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    CASE
        WHEN MONTH(s.[XnDt]) = 10 THEN N'Before Diwali (October)'
        WHEN MONTH(s.[XnDt]) = 11 THEN N'Diwali season (November)'
        ELSE N'Other months'
    END AS DiwaliPeriod,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales,
    COUNT(DISTINCT CAST(s.[XnDt] AS DATE)) AS TradingDays
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1)
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND MONTH(s.[XnDt]) IN (10, 11)
GROUP BY CASE
    WHEN MONTH(s.[XnDt]) = 10 THEN N'Before Diwali (October)'
    WHEN MONTH(s.[XnDt]) = 11 THEN N'Diwali season (November)'
    ELSE N'Other months'
END
ORDER BY DiwaliPeriod
"""
        return _blob(
            "conversational_compare_before_after_diwali",
            sql,
            "YTD compare: October (pre-Diwali proxy) vs November (festive month) net sales.",
            [
                "No Diwali calendar table — Oct/Nov heuristic for Indian retail.",
                "Refine with exact festival dates when available.",
            ],
        )

    def _sql_branch_contribution_pct(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH BranchRev AS (
    SELECT s.[BranchAlias] AS Store, SUM(s.[NetAmount]) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")} AND s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
)
SELECT TOP (500)
    Store,
    CAST(Revenue AS decimal(18, 2)) AS MTDRevenue,
    CAST(100.0 * Revenue / NULLIF(SUM(Revenue) OVER (), 0) AS decimal(18, 4)) AS ContributionPct
FROM BranchRev
ORDER BY ContributionPct DESC
"""
        return _blob(
            "conversational_compare_branch_contribution_percentage",
            sql,
            "Each branch MTD sales and % share of total (contribution comparison).",
            ["Same KPI as branch compare module — works standalone without prior context."],
        )

    def _sql_chennai_vs_bangalore_sales_mtd(q: str) -> Dict[str, Any]:
        city_a, city_b = _two_places(q)
        pa, pb = _city_filter_pat(city_a), _city_filter_pat(city_b)
        sql = f"""
SELECT
    s.[BranchAlias],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS TotalQty,
    COUNT(DISTINCT s.[XnNo]) AS BillCount
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND (
        s.[BranchAlias] LIKE N'{pa}'
     OR s.[BranchAlias] LIKE N'{pb}'
      )
GROUP BY s.[BranchAlias]
ORDER BY TotalSales DESC
"""
        return _blob(
            "conversational_compare_chennai_vs_bangalore_sales_mtd",
            sql,
            f"MTD sales by BranchAlias matching {city_a} or {city_b} (example NLP compare query).",
            [
                f"Parsed cities: {city_a}, {city_b}.",
                "Uses dbo.VW_MB_POWERBI_APP_REPORT — NetAmount, XnDt, BranchAlias.",
                "BranchAlias may contain city name as store code; verify alias naming.",
            ],
        )

    specs: List[tuple] = [
        (
            "conversational_compare_this_vs_last_year",
            [r"^compare\s+this\s+with\s+last\s+year", r"compare\s+this\s+(?:to|vs\.?)\s+last\s+year"],
            _sql_this_vs_last_year,
        ),
        (
            "conversational_compare_only_chennai_branches",
            [r"compare\s+only\s+chennai\s+branches?", r"only\s+chennai\s+branches?"],
            _sql_only_chennai_branches,
        ),
        (
            "conversational_compare_top_categories",
            [r"compare\s+top\s+\d+\s+categor", r"compare\s+top\s+categor"],
            _sql_top_n_categories,
        ),
        (
            "conversational_compare_excluding_returns",
            [r"compare\s+excluding\s+returns?", r"excluding\s+returns?"],
            _sql_excluding_returns,
        ),
        (
            "conversational_compare_by_quantity_instead_of_revenue",
            [
                r"compare\s+by\s+quantity\s+instead\s+of\s+revenue",
                r"compare\s+by\s+(?:units?|quantity)\s+instead",
            ],
            _sql_by_quantity_not_revenue,
        ),
        (
            "conversational_compare_premium_products_only",
            [r"compare\s+only\s+premium\s+products?", r"only\s+premium\s+products?"],
            _sql_premium_products_only,
        ),
        (
            "conversational_compare_supplier_wise",
            [r"compare\s+supplier[\s-]?wise", r"supplier[\s-]?wise\s+compare"],
            _sql_supplier_wise,
        ),
        (
            "conversational_compare_trend_month_over_month",
            [r"compare\s+trend\s+month\s+over\s+month", r"month\s+over\s+month\s+trend"],
            _sql_trend_month_over_month,
        ),
        (
            "conversational_compare_before_after_diwali",
            [r"compare\s+before\s+and\s+after\s+diwali", r"before\s+and\s+after\s+diwali"],
            _sql_before_after_diwali,
        ),
        (
            "conversational_compare_branch_contribution_percentage",
            [
                r"^compare\s+branch\s+contribution\s+%",
                r"compare\s+branch\s+contribution\s+percentage",
            ],
            _sql_branch_contribution_pct,
        ),
        (
            "conversational_compare_chennai_vs_bangalore_sales_mtd",
            [
                r"compare\s+chennai\s+vs\.?\s+bangalore\s+sales?\s+this\s+month",
                r"chennai\s+vs\.?\s+bangalore\s+sales?\s+this\s+month",
            ],
            _sql_chennai_vs_bangalore_sales_mtd,
        ),
    ]

    for tid, patterns, builder in specs:
        register(tid, patterns, builder)
