/*
  Branch Comparison Questions
  Generated: 2026-05-26T21:22:09.380117+00:00
  Blocks: 10
*/

-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 21/81 • Compare Chennai branches by sales growth
-- template_id: compare_city_branches_sales_growth
-- explanation: MTD vs prior-month sales growth % for branches in Chennai (BranchCity filter).
-- assumption: City: Chennai; uses salesperson view CashmemoDt and SalesNetAmount.
-- ============================================================================
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
    FROM dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] sp WITH (NOLOCK)
    CROSS JOIN Bounds b
    WHERE sp.[BranchCity] LIKE N'%Chennai%'
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


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 22/81 • Compare branch profitability
-- template_id: compare_branch_profitability
-- explanation: MTD gross profit and margin % by branch (NetAmount − CostValue on APP_REPORT).
-- assumption: Profitability proxy — not full P&L (no opex).
-- ============================================================================
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
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[BranchAlias]
ORDER BY GrossProfit DESC


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 23/81 • Compare stock levels across branches
-- template_id: compare_stock_levels_across_branches
-- explanation: Current on-hand stock quantity and MRP value by branch (snapshot).
-- assumption: View: STOCK_REPORT; no date filter — point-in-time stock.
-- ============================================================================
SELECT TOP (500)
    st.[BranchAlias],
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS TotalStockQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
WHERE st.[BranchAlias] IS NOT NULL
GROUP BY st.[BranchAlias]
ORDER BY TotalStockQty DESC


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 24/81 • Compare customer footfall between branches
-- template_id: compare_customer_footfall_between_branches
-- explanation: MTD customer footfall proxy: SUM(BillCount) from SLS_BILLCOUNT by branch.
-- assumption: Joins VwAIBranch for store name and city.
-- assumption: BillCount = transaction / footfall KPI per catalog.
-- ============================================================================
SELECT TOP (500)
    COALESCE(br.[BranchShortName], br.[BranchName], CAST(b.[BranchId] AS varchar(20))) AS Store,
    br.[City],
    CAST(SUM(b.[BillCount]) AS decimal(18, 0)) AS MTDFootfallBills
FROM dbo.[VW_MB_POWERBI_SLS_BILLCOUNT] b WITH (NOLOCK)
LEFT JOIN dbo.[VwAIBranch] br WITH (NOLOCK) ON br.[BranchId] = b.[BranchId]
WHERE b.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND b.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY COALESCE(br.[BranchShortName], br.[BranchName], CAST(b.[BranchId] AS varchar(20))), br.[City]
ORDER BY MTDFootfallBills DESC


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 25/81 • Compare branch conversion rate
-- template_id: compare_branch_conversion_rate
-- explanation: Conversion proxy: MTD revenue and invoices vs footfall bills (SLS_BILLCOUNT) per branch.
-- assumption: True visitor conversion needs traffic counters — not in catalog.
-- assumption: RevenuePerBill = MTD sales / SUM(BillCount); match branch names via ShortName ≈ BranchAlias.
-- ============================================================================
WITH Footfall AS (
    SELECT
        COALESCE(br.[BranchShortName], br.[BranchName]) AS Store,
        CAST(SUM(b.[BillCount]) AS decimal(18, 4)) AS FootfallBills
    FROM dbo.[VW_MB_POWERBI_SLS_BILLCOUNT] b WITH (NOLOCK)
    LEFT JOIN dbo.[VwAIBranch] br WITH (NOLOCK) ON br.[BranchId] = b.[BranchId]
    WHERE b.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND b.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
    GROUP BY COALESCE(br.[BranchShortName], br.[BranchName])
),
Sales AS (
    SELECT
        s.[BranchAlias] AS Store,
        CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
        COUNT(DISTINCT s.[XnNo]) AS DistinctInvoices
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
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


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 26/81 • Compare branch inventory aging
-- template_id: compare_branch_inventory_aging
-- explanation: On-hand stock by branch and age bucket (PurInvoiceDt on STOCK_REPORT).
-- assumption: Compare aging mix across stores side-by-side.
-- ============================================================================
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
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
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


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 27/81 • Compare transfer in vs transfer out between branches
-- template_id: compare_transfer_in_vs_out_between_branches
-- explanation: MTD stock transfer in (to branch) vs transfer out (from branch) quantities by store.
-- assumption: STI = inbound to TargetBranchAlias; STO = outbound from SourceBranchAlias.
-- ============================================================================
WITH TransferIn AS (
    SELECT
        sti.[TargetBranchAlias] AS Store,
        CAST(SUM(sti.[StiQty]) AS decimal(18, 4)) AS TransferInQty,
        CAST(SUM(sti.[NetAmount]) AS decimal(18, 2)) AS TransferInValue
    FROM dbo.[VW_MB_POWERBI_STI_REPORT] sti WITH (NOLOCK)
    WHERE sti.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sti.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND sti.[TargetBranchAlias] IS NOT NULL
    GROUP BY sti.[TargetBranchAlias]
),
TransferOut AS (
    SELECT
        sto.[SourceBranchAlias] AS Store,
        CAST(SUM(sto.[StoQty]) AS decimal(18, 4)) AS TransferOutQty,
        CAST(SUM(sto.[NetAmount]) AS decimal(18, 2)) AS TransferOutValue
    FROM dbo.[VW_MB_POWERBI_STO_REPORT] sto WITH (NOLOCK)
    WHERE sto.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sto.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
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


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 28/81 • Compare branch sales contribution percentage
-- template_id: compare_branch_sales_contribution_percentage
-- explanation: Each branch MTD revenue and % share of total company MTD sales.
-- assumption: ContributionPct = branch revenue / SUM(all branches) × 100.
-- ============================================================================
WITH BranchRev AS (
    SELECT
        s.[BranchAlias] AS Store,
        SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
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


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 29/81 • Compare branch-wise average basket size
-- template_id: compare_branch_wise_average_basket_size
-- explanation: MTD average bill value per branch: total sales divided by distinct bill numbers (XnNo).
-- assumption: MTD period; AvgBillValue = SUM(NetAmount) / COUNT(DISTINCT XnNo).
-- ============================================================================
SELECT TOP (500)
    s.[BranchAlias],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales,
    COUNT(DISTINCT s.[XnNo]) AS BillCount,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS AvgBillValue
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY s.[BranchAlias]
ORDER BY AvgBillValue DESC


-- ============================================================================
-- SECTION: Branch Comparison Questions
-- 30/81 • Compare top-performing branches for womenswear
-- template_id: compare_top_branches_womenswear
-- explanation: Top 10 branches by MTD womenswear sales (DepartmentShortName/Department LIKE '%women%').
-- assumption: Uses LIKE filter — matches Women's, Womenswear, etc.
-- ============================================================================
SELECT TOP (10)
    s.[BranchAlias] AS Store,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS WomenswearMTDSales,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS WomenswearMTDQty,
    COUNT(DISTINCT s.[XnNo]) AS BillCount
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[BranchAlias] IS NOT NULL
  AND (
        s.[DepartmentShortName] LIKE N'%women%'
     OR s.[Department] LIKE N'%women%'
      )
GROUP BY s.[BranchAlias]
ORDER BY WomenswearMTDSales DESC

