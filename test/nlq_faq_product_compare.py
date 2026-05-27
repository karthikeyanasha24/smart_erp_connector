"""
Product / assortment comparison FAQ SQL templates (extends nlq_faq_sql).
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Tuple

PRODUCT_COMPARE_AI_QUERIES: Tuple[str, ...] = (
    "Compare sales of kurtis vs sarees",
    "Compare fabric performance by season",
    "Compare color-wise sales trends",
    "Compare MRP vs actual selling price",
    "Compare top-selling articles between months",
    "Compare product return rates by category",
    "Compare premium vs budget product sales",
    "Compare size-wise sales distribution",
    "Compare stock turnover by category",
    "Compare old collection vs new collection performance",
)


def _two_product_terms(q: str, default_a: str = "Kurtis", default_b: str = "Sarees") -> Tuple[str, str]:
    m = re.search(
        r"compare\s+sales?\s+of\s+([a-z][a-z\s]{1,24}?)\s+vs\.?\s+([a-z][a-z\s]{1,24}?)(?:\s|$|\?)",
        q,
        re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"\b([a-z]{4,})\s+vs\.?\s+([a-z]{4,})\b", q, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return default_a, default_b


def _like_pat(term: str) -> str:
    core = re.sub(r"[^a-z0-9]", "", term.lower())
    if not core:
        core = "x"
    return f"%{core}%"


def register_product_compare_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _PM,
        _SLSXNS,
        _STOCK,
        _blob,
        _mtd_where,
        _sql_inventory_turnover_ratio,
        _top_n_from_question,
    )

    def _sql_kurtis_vs_sarees(q: str) -> Dict[str, Any]:
        a, b = _two_product_terms(q)
        pa, pb = _like_pat(a), _like_pat(b)
        sql = f"""
SELECT
    CASE
        WHEN s.[CategoryShortName] LIKE N'{pa}'
          OR s.[DepartmentShortName] LIKE N'{pa}'
          OR s.[Category] LIKE N'{pa}'
            THEN N'{a.title()}'
        WHEN s.[CategoryShortName] LIKE N'{pb}'
          OR s.[DepartmentShortName] LIKE N'{pb}'
          OR s.[Category] LIKE N'{pb}'
            THEN N'{b.title()}'
    END AS ProductGroup,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND (
        s.[CategoryShortName] LIKE N'{pa}'
     OR s.[DepartmentShortName] LIKE N'{pa}'
     OR s.[Category] LIKE N'{pa}'
     OR s.[CategoryShortName] LIKE N'{pb}'
     OR s.[DepartmentShortName] LIKE N'{pb}'
     OR s.[Category] LIKE N'{pb}'
      )
GROUP BY CASE
    WHEN s.[CategoryShortName] LIKE N'{pa}'
      OR s.[DepartmentShortName] LIKE N'{pa}'
      OR s.[Category] LIKE N'{pa}'
        THEN N'{a.title()}'
    WHEN s.[CategoryShortName] LIKE N'{pb}'
      OR s.[DepartmentShortName] LIKE N'{pb}'
      OR s.[Category] LIKE N'{pb}'
        THEN N'{b.title()}'
END
ORDER BY MTDRevenue DESC
"""
        return _blob(
            "compare_product_groups_sales",
            sql,
            f"MTD sales comparison: {a.title()} vs {b.title()} (category/department name LIKE).",
            [f"Terms from question: {a}, {b}.", "Uses CategoryShortName, DepartmentShortName, Category on APP_REPORT."],
        )

    def _sql_fabric_by_season(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[Fabric],
    ISNULL(NULLIF(LTRIM(RTRIM(s.[Property])), N''), N'(No season tag)') AS SeasonTag,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[Fabric] IS NOT NULL
GROUP BY s.[Fabric], ISNULL(NULLIF(LTRIM(RTRIM(s.[Property])), N''), N'(No season tag)')
ORDER BY MTDRevenue DESC, s.[Fabric], SeasonTag
"""
        return _blob(
            "compare_fabric_performance_by_season",
            sql,
            "MTD revenue and qty by Fabric and Property (season tag proxy on APP_REPORT).",
            ["Property column used as season/assortment tag when populated."],
        )

    def _sql_color_sales_trends(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    s.[Color],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[Color] IS NOT NULL
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1), s.[Color]
ORDER BY MonthStart ASC, Revenue DESC
"""
        return _blob(
            "compare_color_wise_sales_trends",
            sql,
            "Monthly net sales by Color for the last 12 complete months (trend comparison).",
            ["One row per month × color; TOP 500 rows returned."],
        )

    def _sql_mrp_vs_selling_price(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    CAST(SUM(s.[MrpValue]) AS decimal(18, 2)) AS TotalMRPValue,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalNetSales,
    CAST(SUM(s.[MrpValue]) - SUM(s.[NetAmount]) AS decimal(18, 2)) AS ImpliedDiscountValue,
    CAST(
        100.0 * (SUM(s.[MrpValue]) - SUM(s.[NetAmount])) / NULLIF(SUM(s.[MrpValue]), 0)
        AS decimal(18, 4)
    ) AS ImpliedDiscountPct,
    CAST(SUM(s.[NetAmount]) / NULLIF(SUM(s.[AppQty]), 0) AS decimal(18, 2)) AS AvgSellingPricePerUnit,
    CAST(SUM(s.[MrpValue]) / NULLIF(SUM(s.[AppQty]), 0) AS decimal(18, 2)) AS AvgMRPPerUnit
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
"""
        return _blob(
            "compare_mrp_vs_actual_selling_price",
            sql,
            "MTD totals: MRP value vs net sales (actual) with implied discount % and average unit prices.",
            ["MrpValue and NetAmount are line totals on APP_REPORT; per-unit = sum / sum(AppQty)."],
        )

    def _sql_top_articles_month_vs_month(_q: str) -> Dict[str, Any]:
        n = _top_n_from_question(_q, default=20)
        sql = f"""
WITH ThisMonth AS (
    SELECT
        s.[ArticleNo],
        CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[ArticleNo] IS NOT NULL
    GROUP BY s.[ArticleNo]
),
LastMonth AS (
    SELECT
        s.[ArticleNo],
        CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND s.[XnDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
      AND s.[ArticleNo] IS NOT NULL
    GROUP BY s.[ArticleNo]
),
TopThis AS (
    SELECT TOP ({n}) ArticleNo, Revenue AS ThisMonthRevenue
    FROM ThisMonth
    ORDER BY Revenue DESC
),
TopLast AS (
    SELECT TOP ({n}) ArticleNo, Revenue AS LastMonthRevenue
    FROM LastMonth
    ORDER BY Revenue DESC
)
SELECT
    COALESCE(t.[ArticleNo], l.[ArticleNo]) AS ArticleNo,
    ISNULL(t.ThisMonthRevenue, 0) AS ThisMonthRevenue,
    ISNULL(l.LastMonthRevenue, 0) AS LastMonthRevenue,
    CAST(ISNULL(t.ThisMonthRevenue, 0) - ISNULL(l.LastMonthRevenue, 0) AS decimal(18, 2)) AS RevenueChange
FROM TopThis t
FULL OUTER JOIN TopLast l ON l.[ArticleNo] = t.[ArticleNo]
ORDER BY ThisMonthRevenue DESC, LastMonthRevenue DESC
"""
        return _blob(
            "compare_top_articles_between_months",
            sql,
            f"Top {n} articles this month vs top {n} last month (full outer join on ArticleNo).",
            ["This month = MTD; last month = prior full calendar month."],
        )

    def _sql_return_rates_by_category(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Ret AS (
    SELECT
        s.[CategoryShortName] AS Category,
        SUM(s.[SlrQty]) AS ReturnQty
    FROM {_SLSXNS} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[SlrQty] > 0
      AND s.[CategoryShortName] IS NOT NULL
    GROUP BY s.[CategoryShortName]
),
Sales AS (
    SELECT
        s.[CategoryShortName] AS Category,
        SUM(s.[AppQty]) AS SoldQty
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[CategoryShortName] IS NOT NULL
    GROUP BY s.[CategoryShortName]
)
SELECT TOP (500)
    COALESCE(r.Category, sa.Category) AS Category,
    CAST(ISNULL(r.ReturnQty, 0) AS decimal(18, 4)) AS ReturnQty,
    CAST(ISNULL(sa.SoldQty, 0) AS decimal(18, 4)) AS MTDQtySold,
    CAST(
        100.0 * ISNULL(r.ReturnQty, 0) / NULLIF(ISNULL(sa.SoldQty, 0), 0)
        AS decimal(18, 4)
    ) AS ReturnRatePct
FROM Ret r
FULL OUTER JOIN Sales sa ON sa.Category = r.Category
WHERE ISNULL(sa.SoldQty, 0) > 0
ORDER BY ReturnRatePct DESC
"""
        return _blob(
            "compare_return_rates_by_category",
            sql,
            "MTD return quantity (SLSXNS SlrQty) vs sold qty (APP AppQty) by category — return rate %.",
            ["Returns from SLSXNS_REPORT; sales qty from APP_REPORT."],
        )

    def _sql_premium_vs_budget(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    CASE
        WHEN s.[ItemMRP] >= 2999 THEN N'Premium (MRP >= 2999)'
        WHEN s.[ItemMRP] < 999 THEN N'Budget (MRP < 999)'
        ELSE N'Mid-range'
    END AS PriceBand,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold,
    COUNT(DISTINCT s.[Itemcode]) AS DistinctItems
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[ItemMRP] IS NOT NULL
  AND s.[ItemMRP] > 0
GROUP BY CASE
    WHEN s.[ItemMRP] >= 2999 THEN N'Premium (MRP >= 2999)'
    WHEN s.[ItemMRP] < 999 THEN N'Budget (MRP < 999)'
    ELSE N'Mid-range'
END
ORDER BY MTDRevenue DESC
"""
        return _blob(
            "compare_premium_vs_budget_sales",
            sql,
            "MTD sales split by ItemMRP bands: Premium >= 2999, Budget < 999, else Mid-range.",
            ["Thresholds are heuristics — adjust in ERP config if your price bands differ."],
        )

    def _sql_size_distribution(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[Size],
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(
        100.0 * SUM(s.[AppQty]) / NULLIF(SUM(SUM(s.[AppQty])) OVER (), 0)
        AS decimal(18, 4)
    ) AS PctOfTotalQty
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[Size] IS NOT NULL
  AND LTRIM(RTRIM(s.[Size])) <> N''
GROUP BY s.[Size]
ORDER BY MTDQtySold DESC
"""
        return _blob(
            "compare_size_wise_sales_distribution",
            sql,
            "MTD quantity and revenue share by Size (PctOfTotalQty = % of all units sold).",
            ["Distribution ranked by quantity sold."],
        )

    def _sql_old_vs_new_collection(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    CASE
        WHEN pm.[Collection] IS NOT NULL AND LTRIM(RTRIM(pm.[Collection])) <> N''
            THEN pm.[Collection]
        WHEN pm.[PurDate] >= DATEADD(MONTH, -6, CAST(GETDATE() AS DATE))
            THEN N'New (PurDate last 6 months)'
        WHEN pm.[PurDate] < DATEADD(MONTH, -18, CAST(GETDATE() AS DATE))
            THEN N'Old (PurDate 18+ months ago)'
        ELSE N'Mid-age assortment'
    END AS CollectionBucket,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold
FROM {_APP} s WITH (NOLOCK)
INNER JOIN {_PM} pm WITH (NOLOCK) ON pm.[Itemcode] = s.[Itemcode]
WHERE {_mtd_where("s")}
GROUP BY CASE
    WHEN pm.[Collection] IS NOT NULL AND LTRIM(RTRIM(pm.[Collection])) <> N''
        THEN pm.[Collection]
    WHEN pm.[PurDate] >= DATEADD(MONTH, -6, CAST(GETDATE() AS DATE))
        THEN N'New (PurDate last 6 months)'
    WHEN pm.[PurDate] < DATEADD(MONTH, -18, CAST(GETDATE() AS DATE))
        THEN N'Old (PurDate 18+ months ago)'
    ELSE N'Mid-age assortment'
END
ORDER BY MTDRevenue DESC
"""
        return _blob(
            "compare_old_vs_new_collection_performance",
            sql,
            "MTD sales by Collection name from product master, else PurDate buckets (new 6M / old 18M+).",
            ["Join APP_REPORT to PRODUCT_MASTER on Itemcode.", "Collection column preferred when populated."],
        )

    specs: List[tuple] = [
        (
            "compare_product_groups_sales",
            [
                r"compare\s+sales?\s+of\s+\w+\s+vs\.?\s+\w+",
                r"compare\s+kurtis?\s+vs\.?\s+sarees?",
                r"sales?\s+of\s+kurtis?\s+vs\.?\s+sarees?",
            ],
            _sql_kurtis_vs_sarees,
        ),
        (
            "compare_fabric_performance_by_season",
            [
                r"compare\s+fabric\s+performance\s+by\s+season",
                r"fabric\s+performance\s+by\s+season",
            ],
            _sql_fabric_by_season,
        ),
        (
            "compare_color_wise_sales_trends",
            [
                r"compare\s+color[\s-]?wise\s+sales?\s+trends?",
                r"color[\s-]?wise\s+sales?\s+trends?",
            ],
            _sql_color_sales_trends,
        ),
        (
            "compare_mrp_vs_actual_selling_price",
            [
                r"compare\s+mrp\s+vs\.?\s+actual\s+selling\s+price",
                r"compare\s+mrp\s+vs\.?\s+(?:net\s+)?sales?",
                r"mrp\s+vs\.?\s+actual\s+selling",
            ],
            _sql_mrp_vs_selling_price,
        ),
        (
            "compare_top_articles_between_months",
            [
                r"compare\s+top[\s-]?selling\s+articles?\s+between\s+months?",
                r"top[\s-]?selling\s+articles?\s+between\s+months?",
                r"compare\s+articles?\s+this\s+month\s+vs\s+last\s+month",
            ],
            _sql_top_articles_month_vs_month,
        ),
        (
            "compare_return_rates_by_category",
            [
                r"compare\s+product\s+return\s+rates?\s+by\s+categor",
                r"return\s+rates?\s+by\s+categor",
                r"compare\s+return\s+rates?\s+by\s+categor",
            ],
            _sql_return_rates_by_category,
        ),
        (
            "compare_premium_vs_budget_sales",
            [
                r"compare\s+premium\s+vs\.?\s+budget\s+product\s+sales?",
                r"premium\s+vs\.?\s+budget\s+product",
            ],
            _sql_premium_vs_budget,
        ),
        (
            "compare_size_wise_sales_distribution",
            [
                r"compare\s+size[\s-]?wise\s+sales?\s+distribution",
                r"size[\s-]?wise\s+sales?\s+distribution",
            ],
            _sql_size_distribution,
        ),
        (
            "compare_stock_turnover_by_category",
            [
                r"compare\s+stock\s+turnover\s+by\s+categor",
                r"stock\s+turnover\s+by\s+categor",
            ],
            _sql_inventory_turnover_ratio,
        ),
        (
            "compare_old_vs_new_collection_performance",
            [
                r"compare\s+old\s+collection\s+vs\.?\s+new\s+collection",
                r"old\s+collection\s+vs\.?\s+new\s+collection\s+performance",
            ],
            _sql_old_vs_new_collection,
        ),
    ]

    for tid, patterns, builder in specs:
        register(tid, patterns, builder)
