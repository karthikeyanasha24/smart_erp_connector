"""
Supplier comparison FAQ SQL templates (extends nlq_faq_sql).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

SUPPLIER_COMPARE_AI_QUERIES: Tuple[str, ...] = (
    "Compare supplier sales contribution",
    "Compare supplier purchase cost trends",
    "Compare suppliers by margin percentage",
    "Compare supplier return percentage",
    "Compare local vs outstation suppliers",
    "Compare supplier performance by category",
    "Compare top suppliers over last 6 months",
    "Compare supplier delivery efficiency",
    "Compare supplier stock movement",
    "Compare supplier profitability contribution",
)


def register_supplier_compare_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _CBS,
        _PUR,
        _STOCK,
        _blob,
        _mtd_where,
        _pur_mtd_where,
        _sql_supplier_contribution_pct_mtd,
        _top_n_from_question,
    )

    def _sql_purchase_cost_trends_6m(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    p.[SupplierName],
    DATEFROMPARTS(YEAR(p.[PurInvDate]), MONTH(p.[PurInvDate]), 1) AS MonthStart,
    CAST(SUM(p.[NetPurNetAmount]) AS decimal(18, 2)) AS NetPurchaseCost,
    CAST(SUM(p.[NetPurQty]) AS decimal(18, 4)) AS NetPurchaseQty
FROM {_PUR} p WITH (NOLOCK)
WHERE p.[PurInvDate] >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND p.[PurInvDate] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND p.[SupplierName] IS NOT NULL
GROUP BY p.[SupplierName], DATEFROMPARTS(YEAR(p.[PurInvDate]), MONTH(p.[PurInvDate]), 1)
ORDER BY p.[SupplierName], MonthStart ASC
"""
        return _blob(
            "compare_supplier_purchase_cost_trends",
            sql,
            "Monthly net purchase cost by supplier for the last 6 months (PURXNS).",
            ["Metric: SUM(NetPurNetAmount); date: PurInvDate."],
        )

    def _sql_suppliers_by_margin_pct(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[SupplierName],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[CostValue]) AS decimal(18, 2)) AS MTDCost,
    CAST(SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS decimal(18, 2)) AS GrossProfit,
    CAST(
        CASE WHEN SUM(s.[NetAmount]) = 0 THEN NULL
             ELSE 100.0 * (SUM(s.[NetAmount]) - SUM(s.[CostValue])) / SUM(s.[NetAmount])
        END AS decimal(18, 4)
    ) AS GrossMarginPct
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY GrossMarginPct DESC
"""
        return _blob(
            "compare_suppliers_by_margin_percentage",
            sql,
            "MTD gross margin % by supplier for side-by-side comparison.",
            ["Margin = (NetAmount − CostValue) / NetAmount on APP_REPORT."],
        )

    def _sql_supplier_return_pct_all(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    p.[SupplierName],
    CAST(SUM(p.[PurQty]) AS decimal(18, 4)) AS PurchaseQty,
    CAST(SUM(p.[PrtQty]) AS decimal(18, 4)) AS ReturnQty,
    CAST(
        100.0 * SUM(p.[PrtQty]) / NULLIF(SUM(p.[PurQty]) + SUM(p.[PrtQty]), 0)
        AS decimal(18, 4)
    ) AS ReturnRatePct
FROM {_PUR} p WITH (NOLOCK)
WHERE {_pur_mtd_where("p")}
  AND p.[SupplierName] IS NOT NULL
GROUP BY p.[SupplierName]
HAVING SUM(p.[PurQty]) + SUM(p.[PrtQty]) > 0
ORDER BY ReturnRatePct DESC
"""
        return _blob(
            "compare_supplier_return_percentage",
            sql,
            "MTD purchase return rate by supplier: PrtQty / (PurQty + PrtQty).",
            ["PURXNS_REPORT; compare rates across all suppliers."],
        )

    def _sql_local_vs_outstation_suppliers(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    CASE
        WHEN s.[SupplierState] IN (N'Tamil Nadu', N'TN', N'Tamilnadu')
          OR s.[SupplierCity] LIKE N'%Chennai%'
          OR s.[SupplierCity] LIKE N'%Coimbatore%'
            THEN N'Local (TN / major city proxy)'
        ELSE N'Outstation'
    END AS SupplierOrigin,
    COUNT(DISTINCT s.[SupplierName]) AS SupplierCount,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[SupplierName] IS NOT NULL
GROUP BY CASE
    WHEN s.[SupplierState] IN (N'Tamil Nadu', N'TN', N'Tamilnadu')
      OR s.[SupplierCity] LIKE N'%Chennai%'
      OR s.[SupplierCity] LIKE N'%Coimbatore%'
        THEN N'Local (TN / major city proxy)'
    ELSE N'Outstation'
END
ORDER BY MTDRevenue DESC
"""
        return _blob(
            "compare_local_vs_outstation_suppliers",
            sql,
            "MTD sales split: local suppliers (TN / Chennai / Coimbatore proxy) vs outstation.",
            [
                "Heuristic geography — adjust SupplierState list for your HQ region.",
                "Uses SupplierState and SupplierCity on APP_REPORT.",
            ],
        )

    def _sql_supplier_performance_by_category(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[SupplierName],
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[SupplierName] IS NOT NULL
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[SupplierName], s.[CategoryShortName]
ORDER BY s.[SupplierName], MTDRevenue DESC
"""
        return _blob(
            "compare_supplier_performance_by_category",
            sql,
            "MTD revenue and quantity by supplier and category (comparison matrix).",
            ["Grain: SupplierName × CategoryShortName."],
        )

    def _sql_top_suppliers_last_6_months(q: str) -> Dict[str, Any]:
        n = _top_n_from_question(q, default=10)
        sql = f"""
SELECT TOP ({n})
    s.[SupplierName],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS RevenueLast6Months,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS QtyLast6Months
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
ORDER BY RevenueLast6Months DESC
"""
        return _blob(
            "compare_top_suppliers_last_6_months",
            sql,
            f"Top {n} suppliers by total net sales over the last 6 months.",
            ["Rolling 6-month window on APP_REPORT XnDt."],
        )

    def _sql_supplier_delivery_efficiency_blocked(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    N'Not supported' AS Status,
    N'No supplier delivery lead-time or GRN date column in schema_catalog for efficiency KPI.' AS Reason,
    N'Proxy: goods-in-transit by supplier from CBS_WITH_GIT — run stock/GIT report separately.' AS Suggestion,
    CAST(SUM(c.[GitQty]) AS decimal(18, 4)) AS TotalGitQtySnapshot,
    CAST(SUM(c.[GitCostValue]) AS decimal(18, 2)) AS TotalGitCostSnapshot
FROM {_CBS} c WITH (NOLOCK)
WHERE c.[SupplierName] IS NOT NULL
"""
        return _blob(
            "compare_supplier_delivery_efficiency_not_supported",
            sql,
            "Delivery efficiency needs procurement lead-time fields; shows GIT snapshot as related proxy.",
            ["Informational — GitQty/GitCostValue is in-transit stock, not OTIF."],
        )

    def _sql_supplier_stock_movement(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    st.[SupplierName],
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP,
    CAST(ISNULL(sa.MTDQtySold, 0) AS decimal(18, 4)) AS MTDQtySold
FROM {_STOCK} st WITH (NOLOCK)
LEFT JOIN (
    SELECT s.[SupplierName], SUM(s.[AppQty]) AS MTDQtySold
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[SupplierName] IS NOT NULL
    GROUP BY s.[SupplierName]
) sa ON sa.[SupplierName] = st.[SupplierName]
WHERE st.[SupplierName] IS NOT NULL
GROUP BY st.[SupplierName], sa.MTDQtySold
ORDER BY OnHandQty DESC
"""
        return _blob(
            "compare_supplier_stock_movement",
            sql,
            "On-hand stock vs MTD quantity sold by supplier (movement proxy).",
            ["Snapshot stock from STOCK_REPORT joined to MTD APP sales."],
        )

    def _sql_supplier_profit_contribution(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH sup AS (
    SELECT
        s.[SupplierName],
        SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS GrossProfit
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[SupplierName] IS NOT NULL
    GROUP BY s.[SupplierName]
)
SELECT TOP (500)
    [SupplierName],
    CAST(GrossProfit AS decimal(18, 2)) AS GrossProfit,
    CAST(
        100.0 * GrossProfit / NULLIF(SUM(GrossProfit) OVER (), 0)
        AS decimal(18, 4)
    ) AS ProfitContributionPct
FROM sup
WHERE GrossProfit IS NOT NULL
ORDER BY ProfitContributionPct DESC
"""
        return _blob(
            "compare_supplier_profitability_contribution",
            sql,
            "Each supplier's share of total MTD gross profit (not just revenue).",
            ["GrossProfit = SUM(NetAmount) − SUM(CostValue); % of company MTD profit pool."],
        )

    specs: List[tuple] = [
        (
            "compare_supplier_sales_contribution",
            [
                r"compare\s+supplier\s+sales?\s+contribution",
                r"supplier\s+sales?\s+contribution",
            ],
            _sql_supplier_contribution_pct_mtd,
        ),
        (
            "compare_supplier_purchase_cost_trends",
            [
                r"compare\s+supplier\s+purchase\s+cost\s+trends?",
                r"supplier\s+purchase\s+cost\s+trends?",
            ],
            _sql_purchase_cost_trends_6m,
        ),
        (
            "compare_suppliers_by_margin_percentage",
            [
                r"compare\s+suppliers?\s+by\s+margin\s+%",
                r"compare\s+suppliers?\s+by\s+margin\s+percentage",
                r"supplier\s+margin\s+percentage",
            ],
            _sql_suppliers_by_margin_pct,
        ),
        (
            "compare_supplier_return_percentage",
            [
                r"compare\s+supplier\s+return\s+%",
                r"compare\s+supplier\s+return\s+percentage",
                r"supplier\s+return\s+percentage",
            ],
            _sql_supplier_return_pct_all,
        ),
        (
            "compare_local_vs_outstation_suppliers",
            [
                r"compare\s+local\s+vs\.?\s+outstation\s+suppliers?",
                r"local\s+vs\.?\s+outstation\s+suppliers?",
            ],
            _sql_local_vs_outstation_suppliers,
        ),
        (
            "compare_supplier_performance_by_category",
            [
                r"compare\s+supplier\s+performance\s+by\s+categor",
                r"supplier\s+performance\s+by\s+categor",
            ],
            _sql_supplier_performance_by_category,
        ),
        (
            "compare_top_suppliers_last_6_months",
            [
                r"compare\s+top\s+suppliers?\s+over\s+last\s+6\s+months?",
                r"top\s+suppliers?\s+last\s+6\s+months?",
            ],
            _sql_top_suppliers_last_6_months,
        ),
        (
            "compare_supplier_delivery_efficiency_not_supported",
            [
                r"compare\s+supplier\s+delivery\s+efficiency",
                r"supplier\s+delivery\s+efficiency",
            ],
            _sql_supplier_delivery_efficiency_blocked,
        ),
        (
            "compare_supplier_stock_movement",
            [
                r"compare\s+supplier\s+stock\s+movement",
                r"supplier\s+stock\s+movement",
            ],
            _sql_supplier_stock_movement,
        ),
        (
            "compare_supplier_profitability_contribution",
            [
                r"compare\s+supplier\s+profitability\s+contribution",
                r"supplier\s+profitability\s+contribution",
            ],
            _sql_supplier_profit_contribution,
        ),
    ]

    for tid, patterns, builder in specs:
        register(tid, patterns, builder)
