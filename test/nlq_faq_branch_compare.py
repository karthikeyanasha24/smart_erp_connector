"""
Branch comparison FAQ SQL templates (extends nlq_faq_sql).
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Tuple

_BRANCH = "dbo.[VwAIBranch]"
_BILLCOUNT = "dbo.[VW_MB_POWERBI_SLS_BILLCOUNT]"

BRANCH_COMPARE_AI_QUERIES: Tuple[str, ...] = (
    "Compare Chennai branches by sales growth",
    "Compare branch profitability",
    "Compare stock levels across branches",
    "Compare customer footfall between branches",
    "Compare branch conversion rate",
    "Compare branch inventory aging",
    "Compare transfer in vs transfer out between branches",
    "Compare branch sales contribution percentage",
    "Compare branch-wise average basket size",
    "Compare top-performing branches for womenswear",
)


def _city_from_question(q: str, default: str = "Chennai") -> str:
    m = re.search(r"compare\s+([a-z][a-z\s]{1,20}?)\s+branches?", q, re.I)
    if m:
        return m.group(1).strip().title()
    m = re.search(
        r"\b(chennai|bangalore|bengaluru|mumbai|delhi|hyderabad|kolkata|pune)\b",
        q,
        re.I,
    )
    if m:
        return m.group(1).title()
    return default


def _billcount_mtd_where(alias: str = "b") -> str:
    return (
        f"{alias}.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) "
        f"AND {alias}.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))"
    )


def register_branch_compare_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _STI,
        _STO,
        _STOCK,
        _SALESPERSON,
        _blob,
        _mtd_where,
        _sql_avg_bill_by_branch,
        _sql_stock_by_branch,
        _top_n_from_question,
    )

    def _sql_city_branches_sales_growth(q: str) -> Dict[str, Any]:
        city = _city_from_question(q)
        pat = f"%{city}%"
        sql = f"""
WITH Bounds AS (
    SELECT
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AS CurrStart,
        DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS PrevStart
),
BranchSales AS (
    SELECT
        sp.[BranchAlias] AS Store,
        sp.[BranchCity] AS City,
        SUM(CASE
            WHEN sp.[CashmemoDt] >= b.CurrStart
             AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
            THEN sp.[SalesNetAmount] ELSE 0 END) AS CurrSales,
        SUM(CASE
            WHEN sp.[CashmemoDt] >= b.PrevStart AND sp.[CashmemoDt] < b.CurrStart
            THEN sp.[SalesNetAmount] ELSE 0 END) AS PrevSales
    FROM {_SALESPERSON} sp WITH (NOLOCK)
    CROSS JOIN Bounds b
    WHERE sp.[BranchCity] LIKE N'{pat}'
      AND sp.[BranchAlias] IS NOT NULL
    GROUP BY sp.[BranchAlias], sp.[BranchCity]
)
SELECT TOP (500)
    Store,
    City,
    CAST(CurrSales AS decimal(18, 2)) AS MTDSales,
    CAST(PrevSales AS decimal(18, 2)) AS PriorMonthSales,
    CAST(
        CASE WHEN PrevSales = 0 THEN NULL
             ELSE 100.0 * (CurrSales - PrevSales) / PrevSales
        END AS decimal(18, 4)
    ) AS GrowthPct
FROM BranchSales
WHERE CurrSales > 0 OR PrevSales > 0
ORDER BY GrowthPct DESC, MTDSales DESC
"""
        return _blob(
            "compare_city_branches_sales_growth",
            sql,
            f"MTD vs prior-month sales growth % for branches in {city} (BranchCity filter).",
            [f"City: {city}; uses salesperson view CashmemoDt and SalesNetAmount."],
        )

    def _sql_branch_profitability(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[BranchAlias] AS Store,
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
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[BranchAlias]
ORDER BY GrossProfit DESC
"""
        return _blob(
            "compare_branch_profitability",
            sql,
            "MTD gross profit and margin % by branch (NetAmount − CostValue on APP_REPORT).",
            ["Profitability proxy — not full P&L (no opex)."],
        )

    def _sql_footfall_between_branches(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    COALESCE(br.[BranchShortName], br.[BranchName], CAST(b.[BranchId] AS varchar(20))) AS Store,
    br.[City],
    CAST(SUM(b.[BillCount]) AS decimal(18, 0)) AS MTDFootfallBills
FROM {_BILLCOUNT} b WITH (NOLOCK)
LEFT JOIN {_BRANCH} br WITH (NOLOCK) ON br.[BranchId] = b.[BranchId]
WHERE {_billcount_mtd_where("b")}
GROUP BY COALESCE(br.[BranchShortName], br.[BranchName], CAST(b.[BranchId] AS varchar(20))), br.[City]
ORDER BY MTDFootfallBills DESC
"""
        return _blob(
            "compare_customer_footfall_between_branches",
            sql,
            "MTD customer footfall proxy: SUM(BillCount) from SLS_BILLCOUNT by branch.",
            ["Joins VwAIBranch for store name and city.", "BillCount = transaction / footfall KPI per catalog."],
        )

    def _sql_branch_conversion_rate(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Footfall AS (
    SELECT
        COALESCE(br.[BranchShortName], br.[BranchName]) AS Store,
        CAST(SUM(b.[BillCount]) AS decimal(18, 4)) AS FootfallBills
    FROM {_BILLCOUNT} b WITH (NOLOCK)
    LEFT JOIN {_BRANCH} br WITH (NOLOCK) ON br.[BranchId] = b.[BranchId]
    WHERE {_billcount_mtd_where("b")}
    GROUP BY COALESCE(br.[BranchShortName], br.[BranchName])
),
Sales AS (
    SELECT
        s.[BranchAlias] AS Store,
        CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
        COUNT(DISTINCT s.[XnNo]) AS DistinctInvoices
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
)
SELECT TOP (500)
    COALESCE(sa.Store, f.Store) AS Store,
    CAST(ISNULL(sa.MTDRevenue, 0) AS decimal(18, 2)) AS MTDRevenue,
    CAST(ISNULL(f.FootfallBills, 0) AS decimal(18, 4)) AS FootfallBills,
    CAST(
        ISNULL(sa.MTDRevenue, 0) / NULLIF(f.FootfallBills, 0)
        AS decimal(18, 2)
    ) AS RevenuePerBill,
    CAST(
        ISNULL(sa.DistinctInvoices, 0) * 1.0 / NULLIF(f.FootfallBills, 0)
        AS decimal(18, 4)
    ) AS InvoicesPerFootfallUnit
FROM Sales sa
FULL OUTER JOIN Footfall f ON f.Store = sa.Store
WHERE ISNULL(f.FootfallBills, 0) > 0 OR ISNULL(sa.MTDRevenue, 0) > 0
ORDER BY RevenuePerBill DESC
"""
        return _blob(
            "compare_branch_conversion_rate",
            sql,
            "Conversion proxy: MTD revenue and invoices vs footfall bills (SLS_BILLCOUNT) per branch.",
            [
                "True visitor conversion needs traffic counters — not in catalog.",
                "RevenuePerBill = MTD sales / SUM(BillCount); match branch names via ShortName ≈ BranchAlias.",
            ],
        )

    def _sql_branch_inventory_aging(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    st.[BranchAlias] AS Store,
    CASE
        WHEN st.[PurInvoiceDt] IS NULL THEN N'Unknown date'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 30 THEN N'0-30 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 60 THEN N'31-60 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 90 THEN N'61-90 days'
        ELSE N'90+ days'
    END AS AgeBucket,
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS StockQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
FROM {_STOCK} st WITH (NOLOCK)
WHERE st.[StockQty] > 0
  AND st.[BranchAlias] IS NOT NULL
GROUP BY
    st.[BranchAlias],
    CASE
        WHEN st.[PurInvoiceDt] IS NULL THEN N'Unknown date'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 30 THEN N'0-30 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 60 THEN N'31-60 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 90 THEN N'61-90 days'
        ELSE N'90+ days'
    END
ORDER BY Store, AgeBucket
"""
        return _blob(
            "compare_branch_inventory_aging",
            sql,
            "On-hand stock by branch and age bucket (PurInvoiceDt on STOCK_REPORT).",
            ["Compare aging mix across stores side-by-side."],
        )

    def _sql_transfer_in_vs_out_by_branch(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH TransferIn AS (
    SELECT
        sti.[TargetBranchAlias] AS Store,
        CAST(SUM(sti.[StiQty]) AS decimal(18, 4)) AS TransferInQty,
        CAST(SUM(sti.[NetAmount]) AS decimal(18, 2)) AS TransferInValue
    FROM {_STI} sti WITH (NOLOCK)
    WHERE {_mtd_where("sti")}
      AND sti.[TargetBranchAlias] IS NOT NULL
    GROUP BY sti.[TargetBranchAlias]
),
TransferOut AS (
    SELECT
        sto.[SourceBranchAlias] AS Store,
        CAST(SUM(sto.[StoQty]) AS decimal(18, 4)) AS TransferOutQty,
        CAST(SUM(sto.[NetAmount]) AS decimal(18, 2)) AS TransferOutValue
    FROM {_STO} sto WITH (NOLOCK)
    WHERE {_mtd_where("sto")}
      AND sto.[SourceBranchAlias] IS NOT NULL
    GROUP BY sto.[SourceBranchAlias]
)
SELECT TOP (500)
    COALESCE(ti.Store, tou.Store) AS Store,
    ISNULL(ti.TransferInQty, 0) AS TransferInQty,
    ISNULL(tou.TransferOutQty, 0) AS TransferOutQty,
    CAST(ISNULL(ti.TransferInQty, 0) - ISNULL(tou.TransferOutQty, 0) AS decimal(18, 4)) AS NetTransferQty
FROM TransferIn ti
FULL OUTER JOIN TransferOut tou ON tou.Store = ti.Store
ORDER BY NetTransferQty DESC
"""
        return _blob(
            "compare_transfer_in_vs_out_between_branches",
            sql,
            "MTD stock transfer in (to branch) vs transfer out (from branch) quantities by store.",
            ["STI = inbound to TargetBranchAlias; STO = outbound from SourceBranchAlias."],
        )

    def _sql_branch_sales_contribution_pct(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH BranchRev AS (
    SELECT
        s.[BranchAlias] AS Store,
        SUM(s.[NetAmount]) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
)
SELECT TOP (500)
    Store,
    CAST(Revenue AS decimal(18, 2)) AS MTDRevenue,
    CAST(
        100.0 * Revenue / NULLIF(SUM(Revenue) OVER (), 0)
        AS decimal(18, 4)
    ) AS ContributionPct
FROM BranchRev
ORDER BY ContributionPct DESC
"""
        return _blob(
            "compare_branch_sales_contribution_percentage",
            sql,
            "Each branch MTD revenue and % share of total company MTD sales.",
            ["ContributionPct = branch revenue / SUM(all branches) × 100."],
        )

    def _sql_top_womenswear_branches(q: str) -> Dict[str, Any]:
        n = _top_n_from_question(q, default=10)
        sql = f"""
SELECT TOP ({n})
    s.[BranchAlias] AS Store,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS WomenswearMTDSales,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS WomenswearMTDQty,
    COUNT(DISTINCT s.[XnNo]) AS BillCount
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[BranchAlias] IS NOT NULL
  AND (
        s.[DepartmentShortName] LIKE N'%women%'
     OR s.[Department] LIKE N'%women%'
      )
GROUP BY s.[BranchAlias]
ORDER BY WomenswearMTDSales DESC
"""
        return _blob(
            "compare_top_branches_womenswear",
            sql,
            f"Top {n} branches by MTD womenswear sales (DepartmentShortName/Department LIKE '%women%').",
            ["Uses LIKE filter — matches Women's, Womenswear, etc."],
        )

    specs: List[tuple] = [
        (
            "compare_city_branches_sales_growth",
            [
                r"compare\s+chennai\s+branches?\s+by\s+sales?\s+growth",
                r"compare\s+\w+\s+branches?\s+by\s+sales?\s+growth",
                r"branches?\s+by\s+sales?\s+growth.*chennai",
            ],
            _sql_city_branches_sales_growth,
        ),
        (
            "compare_branch_profitability",
            [
                r"compare\s+branch\s+profitability",
                r"branch\s+profitability",
                r"compare\s+profitability\s+between\s+branches?",
            ],
            _sql_branch_profitability,
        ),
        (
            "compare_stock_levels_across_branches",
            [
                r"compare\s+stock\s+levels?\s+across\s+branches?",
                r"stock\s+levels?\s+across\s+branches?",
                r"compare\s+stock\s+by\s+branch",
            ],
            _sql_stock_by_branch,
        ),
        (
            "compare_customer_footfall_between_branches",
            [
                r"compare\s+customer\s+footfall\s+between\s+branches?",
                r"customer\s+footfall\s+between\s+branches?",
                r"compare\s+footfall\s+between\s+branches?",
            ],
            _sql_footfall_between_branches,
        ),
        (
            "compare_branch_conversion_rate",
            [
                r"compare\s+branch\s+conversion\s+rate",
                r"branch\s+conversion\s+rate",
                r"conversion\s+rate\s+between\s+branches?",
            ],
            _sql_branch_conversion_rate,
        ),
        (
            "compare_branch_inventory_aging",
            [
                r"compare\s+branch\s+inventory\s+aging",
                r"branch\s+inventory\s+aging",
                r"inventory\s+aging\s+between\s+branches?",
            ],
            _sql_branch_inventory_aging,
        ),
        (
            "compare_transfer_in_vs_out_between_branches",
            [
                r"compare\s+transfer\s+in\s+vs\.?\s+transfer\s+out",
                r"transfer\s+in\s+vs\.?\s+transfer\s+out\s+between\s+branches?",
            ],
            _sql_transfer_in_vs_out_by_branch,
        ),
        (
            "compare_branch_sales_contribution_percentage",
            [
                r"compare\s+branch\s+sales?\s+contribution\s+%",
                r"branch\s+sales?\s+contribution\s+percentage",
                r"sales?\s+contribution\s+%.*branch",
            ],
            _sql_branch_sales_contribution_pct,
        ),
        (
            "compare_branch_wise_average_basket_size",
            [
                r"compare\s+branch[\s-]?wise\s+average\s+basket",
                r"branch[\s-]?wise\s+average\s+basket\s+size",
                r"compare\s+average\s+basket\s+size\s+by\s+branch",
            ],
            _sql_avg_bill_by_branch,
        ),
        (
            "compare_top_branches_womenswear",
            [
                r"compare\s+top[\s-]?performing\s+branches?\s+for\s+womenswear",
                r"top[\s-]?performing\s+branches?\s+.*womenswear",
                r"womenswear.*top\s+branches?",
            ],
            _sql_top_womenswear_branches,
        ),
    ]

    for tid, patterns, builder in specs:
        register(tid, patterns, builder)
