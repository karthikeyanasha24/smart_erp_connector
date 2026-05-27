"""
Advanced executive comparison FAQ SQL templates (extends nlq_faq_sql).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

_BRANCH_LIST = "dbo.VW_MB_POWERBI_BRANCH_LIST"

EXECUTIVE_COMPARE_AI_QUERIES: Tuple[str, ...] = (
    "Compare sales growth vs profit growth",
    "Compare branch efficiency vs inventory holding",
    "Compare revenue vs bill count trends",
    "Compare GST contribution across states",
    "Compare sales trend before and after promotions",
    "Compare margin percentage across categories",
    "Compare purchase cost inflation month over month",
    "Compare category contribution to total revenue",
    "Compare branch sales vs target achievement",
    "Compare top-performing concepts by profitability",
)


def register_executive_compare_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _PUR,
        _STOCK,
        _blob,
        _mtd_where,
        _pur_mtd_where,
    )

    def _sql_ai_blocked_row(reason: str, suggestion: str, tid: str, explanation: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    N'Not supported' AS Status,
    N'{reason}' AS Reason,
    N'{suggestion}' AS Suggestion
"""
        return _blob(tid, sql, explanation, ["Informational single-row result."])

    def _sql_sales_growth_vs_profit_growth(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Bounds AS (
    SELECT
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AS CurrStart,
        DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS PrevStart
),
Agg AS (
    SELECT
        SUM(CASE WHEN s.[XnDt] >= b.CurrStart AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
            THEN s.[NetAmount] ELSE 0 END) AS CurrRev,
        SUM(CASE WHEN s.[XnDt] >= b.PrevStart AND s.[XnDt] < b.CurrStart
            THEN s.[NetAmount] ELSE 0 END) AS PrevRev,
        SUM(CASE WHEN s.[XnDt] >= b.CurrStart AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
            THEN s.[NetAmount] - s.[CostValue] ELSE 0 END) AS CurrProfit,
        SUM(CASE WHEN s.[XnDt] >= b.PrevStart AND s.[XnDt] < b.CurrStart
            THEN s.[NetAmount] - s.[CostValue] ELSE 0 END) AS PrevProfit
    FROM {_APP} s WITH (NOLOCK)
    CROSS JOIN Bounds b
    WHERE s.[XnDt] >= b.PrevStart
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    N'Revenue' AS Metric,
    CAST(CurrRev AS decimal(18, 2)) AS CurrentPeriod,
    CAST(PrevRev AS decimal(18, 2)) AS PriorPeriod,
    CAST(
        CASE WHEN PrevRev = 0 THEN NULL ELSE 100.0 * (CurrRev - PrevRev) / PrevRev END
        AS decimal(18, 4)
    ) AS GrowthPct
FROM Agg
UNION ALL
SELECT
    N'GrossProfit',
    CAST(CurrProfit AS decimal(18, 2)),
    CAST(PrevProfit AS decimal(18, 2)),
    CAST(
        CASE WHEN PrevProfit = 0 THEN NULL ELSE 100.0 * (CurrProfit - PrevProfit) / PrevProfit END
        AS decimal(18, 4)
    )
FROM Agg
"""
        return _blob(
            "compare_sales_growth_vs_profit_growth",
            sql,
            "MTD vs prior full month: revenue growth % vs gross profit growth % (two rows).",
            ["Current = MTD; prior = previous calendar month on XnDt."],
        )

    def _sql_branch_efficiency_vs_inventory(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Sales AS (
    SELECT
        s.[BranchAlias] AS Store,
        CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
        COUNT(DISTINCT s.[XnNo]) AS BillCount
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
),
Stock AS (
    SELECT
        st.[BranchAlias] AS Store,
        CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
        CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
    FROM {_STOCK} st WITH (NOLOCK)
    WHERE st.[BranchAlias] IS NOT NULL
    GROUP BY st.[BranchAlias]
)
SELECT TOP (500)
    COALESCE(sa.Store, st.Store) AS Store,
    sa.MTDRevenue,
    sa.BillCount,
    CAST(sa.MTDRevenue / NULLIF(sa.BillCount, 0) AS decimal(18, 2)) AS AvgBillValue,
    ISNULL(st.OnHandQty, 0) AS OnHandQty,
    ISNULL(st.StockValueAtMRP, 0) AS StockValueAtMRP,
    CAST(sa.MTDRevenue / NULLIF(st.OnHandQty, 0) AS decimal(18, 4)) AS RevenuePerStockUnit
FROM Sales sa
LEFT JOIN Stock st ON st.Store = sa.Store
ORDER BY RevenuePerStockUnit DESC
"""
        return _blob(
            "compare_branch_efficiency_vs_inventory_holding",
            sql,
            "Per branch: sales efficiency (avg bill) vs inventory held (qty and MRP value).",
            ["RevenuePerStockUnit = MTD revenue / on-hand qty — higher may mean leaner stores."],
        )

    def _sql_revenue_vs_bill_count_trends(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (24)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalRevenue,
    COUNT(DISTINCT s.[XnNo]) AS BillCount,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS AvgBillValue
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
ORDER BY MonthStart ASC
"""
        return _blob(
            "compare_revenue_vs_bill_count_trends",
            sql,
            "Monthly revenue and distinct bill count for the last 12 months (trend comparison).",
            ["Use MonthStart to plot revenue vs bill count over time."],
        )

    def _sql_gst_by_state(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    COALESCE(br.[State], s.[SupplierState], N'(Unknown)') AS StateOrRegion,
    CAST(SUM(s.[CGSTAmount] + s.[SGSTAmount] + s.[IGSTAmount]) AS decimal(18, 2)) AS TotalGST,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalNetSales,
    CAST(
        100.0 * SUM(s.[CGSTAmount] + s.[SGSTAmount] + s.[IGSTAmount])
        / NULLIF(SUM(SUM(s.[CGSTAmount] + s.[SGSTAmount] + s.[IGSTAmount])) OVER (), 0)
        AS decimal(18, 4)
    ) AS GSTContributionPct
FROM {_APP} s WITH (NOLOCK)
LEFT JOIN {_BRANCH_LIST} br WITH (NOLOCK)
    ON br.[ShortName] = s.[BranchAlias]
    OR br.[BranchName] = s.[BranchAlias]
WHERE {_mtd_where("s")}
GROUP BY COALESCE(br.[State], s.[SupplierState], N'(Unknown)')
ORDER BY TotalGST DESC
"""
        return _blob(
            "compare_gst_contribution_across_states",
            sql,
            "MTD GST totals (CGST+SGST+IGST) and % share by branch state (fallback SupplierState).",
            ["Prefer branch state from BRANCH_LIST when join matches BranchAlias."],
        )

    def _sql_sales_before_after_promotions(_q: str) -> Dict[str, Any]:
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
        s.[NetAmount],
        s.[MrpValue]
    FROM {_APP} s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(DAY, -60, CAST(GETDATE() AS DATE))
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    PeriodLabel,
    CAST(SUM([NetAmount]) AS decimal(18, 2)) AS TotalNetSales,
    CAST(SUM([MrpValue]) AS decimal(18, 2)) AS TotalMRP,
    CAST(SUM([MrpValue]) - SUM([NetAmount]) AS decimal(18, 2)) AS ImpliedDiscountValue
FROM Periods
WHERE PeriodLabel IS NOT NULL
GROUP BY PeriodLabel
ORDER BY PeriodLabel DESC
"""
        return _blob(
            "compare_sales_before_after_promotions",
            sql,
            "Proxy: net sales and implied discount last 30 days vs prior 30 days (no promotion calendar).",
            ["Not tied to named campaigns — MRP minus net as discount proxy."],
        )

    def _sql_margin_pct_by_category(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS decimal(18, 2)) AS GrossProfit,
    CAST(
        CASE WHEN SUM(s.[NetAmount]) = 0 THEN NULL
             ELSE 100.0 * (SUM(s.[NetAmount]) - SUM(s.[CostValue])) / SUM(s.[NetAmount])
        END AS decimal(18, 4)
    ) AS GrossMarginPct
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY GrossMarginPct DESC
"""
        return _blob(
            "compare_margin_percentage_across_categories",
            sql,
            "MTD gross margin % by category for side-by-side comparison.",
            ["Margin = (NetAmount − CostValue) / NetAmount."],
        )

    def _sql_purchase_cost_inflation_mom(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    DATEFROMPARTS(YEAR(p.[PurInvDate]), MONTH(p.[PurInvDate]), 1) AS MonthStart,
    CAST(SUM(p.[NetPurNetAmount]) AS decimal(18, 2)) AS TotalPurchaseCost,
    CAST(SUM(p.[NetPurQty]) AS decimal(18, 4)) AS TotalPurchaseQty,
    CAST(
        SUM(p.[NetPurNetAmount]) / NULLIF(SUM(p.[NetPurQty]), 0)
        AS decimal(18, 4)
    ) AS AvgCostPerUnit
FROM {_PUR} p WITH (NOLOCK)
WHERE p.[PurInvDate] >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND p.[PurInvDate] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND p.[NetPurQty] > 0
GROUP BY DATEFROMPARTS(YEAR(p.[PurInvDate]), MONTH(p.[PurInvDate]), 1)
ORDER BY MonthStart ASC
"""
        return _blob(
            "compare_purchase_cost_inflation_month_over_month",
            sql,
            "Monthly average purchase cost per unit (NetPurNetAmount / NetPurQty) for last 6 months.",
            ["MoM inflation = compare AvgCostPerUnit between consecutive months."],
        )

    def _sql_top_concepts_by_profitability(q: str) -> Dict[str, Any]:
        from nlq_faq_sql import _top_n_from_question

        n = _top_n_from_question(q, default=10)
        sql = f"""
SELECT TOP ({n})
    s.[Concept],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS decimal(18, 2)) AS GrossProfit,
    CAST(
        CASE WHEN SUM(s.[NetAmount]) = 0 THEN NULL
             ELSE 100.0 * (SUM(s.[NetAmount]) - SUM(s.[CostValue])) / SUM(s.[NetAmount])
        END AS decimal(18, 4)
    ) AS GrossMarginPct
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[Concept] IS NOT NULL
GROUP BY s.[Concept]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY GrossProfit DESC
"""
        return _blob(
            "compare_top_concepts_by_profitability",
            sql,
            f"Top {n} concepts by MTD gross profit with margin % for comparison.",
            ["Ranked by GrossProfit; Concept on APP_REPORT."],
        )

    def _sql_branch_sales_vs_target(_q: str) -> Dict[str, Any]:
        return _sql_ai_blocked_row(
            "No sales target / budget table in schema_catalog for achievement comparison.",
            "Load branch targets into a table or use dashboard target API, then re-ask.",
            "compare_branch_sales_vs_target_not_supported",
            "Branch target vs achievement requires a targets dataset not in the ERP views.",
        )

    def _sql_category_contribution_revenue(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH c AS (
    SELECT s.[CategoryShortName] AS Category, SUM(s.[NetAmount]) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")} AND s.[CategoryShortName] IS NOT NULL
    GROUP BY s.[CategoryShortName]
)
SELECT TOP (500)
    Category,
    CAST(Revenue AS decimal(18, 2)) AS MTDRevenue,
    CAST(100.0 * Revenue / NULLIF(SUM(Revenue) OVER (), 0) AS decimal(18, 4)) AS ContributionPct
FROM c
ORDER BY ContributionPct DESC
"""
        return _blob(
            "compare_category_contribution_to_total_revenue",
            sql,
            "Each category MTD revenue and % of total company sales.",
            ["Same logic as category_contribution_percentage KPI."],
        )

    specs: List[tuple] = [
        (
            "compare_sales_growth_vs_profit_growth",
            [r"compare\s+sales?\s+growth\s+vs\.?\s+profit\s+growth", r"sales?\s+growth\s+vs\.?\s+profit"],
            _sql_sales_growth_vs_profit_growth,
        ),
        (
            "compare_branch_efficiency_vs_inventory_holding",
            [
                r"compare\s+branch\s+efficiency\s+vs\.?\s+inventory",
                r"branch\s+efficiency\s+vs\.?\s+inventory\s+holding",
            ],
            _sql_branch_efficiency_vs_inventory,
        ),
        (
            "compare_revenue_vs_bill_count_trends",
            [r"compare\s+revenue\s+vs\.?\s+bill\s+count\s+trends?", r"revenue\s+vs\.?\s+bill\s+count\s+trends?"],
            _sql_revenue_vs_bill_count_trends,
        ),
        (
            "compare_gst_contribution_across_states",
            [r"compare\s+gst\s+contribution\s+across\s+states?", r"gst\s+contribution\s+across\s+states?"],
            _sql_gst_by_state,
        ),
        (
            "compare_sales_before_after_promotions",
            [
                r"compare\s+sales?\s+trend\s+before\s+and\s+after\s+promotions?",
                r"before\s+and\s+after\s+promotions?",
            ],
            _sql_sales_before_after_promotions,
        ),
        (
            "compare_margin_percentage_across_categories",
            [r"compare\s+margin\s+%?\s+across\s+categor", r"margin\s+percentage\s+across\s+categor"],
            _sql_margin_pct_by_category,
        ),
        (
            "compare_purchase_cost_inflation_month_over_month",
            [
                r"compare\s+purchase\s+cost\s+inflation\s+month",
                r"purchase\s+cost\s+inflation\s+month\s+over\s+month",
            ],
            _sql_purchase_cost_inflation_mom,
        ),
        (
            "compare_category_contribution_to_total_revenue",
            [
                r"compare\s+categor(?:y|ies)\s+contribution\s+to\s+total\s+revenue",
                r"categor(?:y|ies)\s+contribution\s+to\s+total\s+revenue",
            ],
            _sql_category_contribution_revenue,
        ),
        (
            "compare_branch_sales_vs_target_not_supported",
            [r"compare\s+branch\s+sales?\s+vs\.?\s+target", r"branch\s+sales?\s+vs\.?\s+target\s+achievement"],
            _sql_branch_sales_vs_target,
        ),
        (
            "compare_top_concepts_by_profitability",
            [
                r"compare\s+top[\s-]?performing\s+concepts?\s+by\s+profitability",
                r"top[\s-]?performing\s+concepts?\s+by\s+profitability",
            ],
            _sql_top_concepts_by_profitability,
        ),
    ]

    for tid, patterns, builder in specs:
        register(tid, patterns, builder)
