/*
  Advanced Executive Comparison Questions
  Generated: 2026-05-26T21:22:09.383426+00:00
  Blocks: 10
*/

-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 61/81 • Compare sales growth vs profit growth
-- template_id: compare_sales_growth_vs_profit_growth
-- explanation: MTD vs prior full month: revenue growth % vs gross profit growth % (two rows).
-- assumption: Current = MTD; prior = previous calendar month on XnDt.
-- ============================================================================
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
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
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


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 62/81 • Compare branch efficiency vs inventory holding
-- template_id: compare_branch_efficiency_vs_inventory_holding
-- explanation: Per branch: sales efficiency (avg bill) vs inventory held (qty and MRP value).
-- assumption: RevenuePerStockUnit = MTD revenue / on-hand qty — higher may mean leaner stores.
-- ============================================================================
WITH Sales AS (
    SELECT
        s.[BranchAlias] AS Store,
        CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
        COUNT(DISTINCT s.[XnNo]) AS BillCount
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
),
Stock AS (
    SELECT
        st.[BranchAlias] AS Store,
        CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
        CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
    FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
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


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 63/81 • Compare revenue vs bill count trends
-- template_id: compare_revenue_vs_bill_count_trends
-- explanation: Monthly revenue and distinct bill count for the last 12 months (trend comparison).
-- assumption: Use MonthStart to plot revenue vs bill count over time.
-- ============================================================================
SELECT TOP (24)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalRevenue,
    COUNT(DISTINCT s.[XnNo]) AS BillCount,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS AvgBillValue
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
ORDER BY MonthStart ASC


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 64/81 • Compare GST contribution across states
-- template_id: compare_gst_contribution_across_states
-- explanation: MTD GST totals (CGST+SGST+IGST) and % share by branch state (fallback SupplierState).
-- assumption: Prefer branch state from BRANCH_LIST when join matches BranchAlias.
-- ============================================================================
SELECT TOP (500)
    COALESCE(br.[State], s.[SupplierState], N'(Unknown)') AS StateOrRegion,
    CAST(SUM(s.[CGSTAmount] + s.[SGSTAmount] + s.[IGSTAmount]) AS decimal(18, 2)) AS TotalGST,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalNetSales,
    CAST(
        100.0 * SUM(s.[CGSTAmount] + s.[SGSTAmount] + s.[IGSTAmount])
        / NULLIF(SUM(SUM(s.[CGSTAmount] + s.[SGSTAmount] + s.[IGSTAmount])) OVER (), 0)
        AS decimal(18, 4)
    ) AS GSTContributionPct
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
LEFT JOIN dbo.VW_MB_POWERBI_BRANCH_LIST br WITH (NOLOCK)
    ON br.[ShortName] = s.[BranchAlias]
    OR br.[BranchName] = s.[BranchAlias]
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY COALESCE(br.[State], s.[SupplierState], N'(Unknown)')
ORDER BY TotalGST DESC


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 65/81 • Compare sales trend before and after promotions
-- template_id: compare_sales_before_after_promotions
-- explanation: Proxy: net sales and implied discount last 30 days vs prior 30 days (no promotion calendar).
-- assumption: Not tied to named campaigns — MRP minus net as discount proxy.
-- ============================================================================
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
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
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


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 66/81 • Compare margin percentage across categories
-- template_id: compare_margin_percentage_across_categories
-- explanation: MTD gross margin % by category for side-by-side comparison.
-- assumption: Margin = (NetAmount − CostValue) / NetAmount.
-- ============================================================================
SELECT TOP (500)
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS decimal(18, 2)) AS GrossProfit,
    CAST(
        CASE WHEN SUM(s.[NetAmount]) = 0 THEN NULL
             ELSE 100.0 * (SUM(s.[NetAmount]) - SUM(s.[CostValue])) / SUM(s.[NetAmount])
        END AS decimal(18, 4)
    ) AS GrossMarginPct
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY GrossMarginPct DESC


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 67/81 • Compare purchase cost inflation month over month
-- template_id: compare_purchase_cost_inflation_month_over_month
-- explanation: Monthly average purchase cost per unit (NetPurNetAmount / NetPurQty) for last 6 months.
-- assumption: MoM inflation = compare AvgCostPerUnit between consecutive months.
-- ============================================================================
SELECT TOP (500)
    DATEFROMPARTS(YEAR(p.[PurInvDate]), MONTH(p.[PurInvDate]), 1) AS MonthStart,
    CAST(SUM(p.[NetPurNetAmount]) AS decimal(18, 2)) AS TotalPurchaseCost,
    CAST(SUM(p.[NetPurQty]) AS decimal(18, 4)) AS TotalPurchaseQty,
    CAST(
        SUM(p.[NetPurNetAmount]) / NULLIF(SUM(p.[NetPurQty]), 0)
        AS decimal(18, 4)
    ) AS AvgCostPerUnit
FROM dbo.[VW_MB_POWERBI_PURXNS_REPORT] p WITH (NOLOCK)
WHERE p.[PurInvDate] >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND p.[PurInvDate] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND p.[NetPurQty] > 0
GROUP BY DATEFROMPARTS(YEAR(p.[PurInvDate]), MONTH(p.[PurInvDate]), 1)
ORDER BY MonthStart ASC


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 68/81 • Compare category contribution to total revenue
-- template_id: category_contribution_percentage
-- explanation: Each category's % of total MTD net sales.
-- assumption: MTD on XnDt.
-- ============================================================================
WITH c AS (
    SELECT s.[CategoryShortName] AS Category, SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) AND s.[CategoryShortName] IS NOT NULL
    GROUP BY s.[CategoryShortName]
)
SELECT TOP (500)
    Category,
    CAST(Revenue AS decimal(18, 2)) AS Revenue,
    CAST(100.0 * Revenue / NULLIF(SUM(Revenue) OVER (), 0) AS decimal(18, 4)) AS ContributionPct
FROM c
ORDER BY ContributionPct DESC


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 69/81 • Compare branch sales vs target achievement
-- template_id: compare_branch_sales_vs_target_not_supported
-- explanation: Branch target vs achievement requires a targets dataset not in the ERP views.
-- assumption: Informational single-row result.
-- ============================================================================
SELECT
    N'Not supported' AS Status,
    N'No sales target / budget table in schema_catalog for achievement comparison.' AS Reason,
    N'Load branch targets into a table or use dashboard target API, then re-ask.' AS Suggestion


-- ============================================================================
-- SECTION: Advanced Executive Comparison Questions
-- 70/81 • Compare top-performing concepts by profitability
-- template_id: compare_top_concepts_by_profitability
-- explanation: Top 10 concepts by MTD gross profit with margin % for comparison.
-- assumption: Ranked by GrossProfit; Concept on APP_REPORT.
-- ============================================================================
SELECT TOP (10)
    s.[Concept],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS decimal(18, 2)) AS GrossProfit,
    CAST(
        CASE WHEN SUM(s.[NetAmount]) = 0 THEN NULL
             ELSE 100.0 * (SUM(s.[NetAmount]) - SUM(s.[CostValue])) / SUM(s.[NetAmount])
        END AS decimal(18, 4)
    ) AS GrossMarginPct
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[Concept] IS NOT NULL
GROUP BY s.[Concept]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY GrossProfit DESC

