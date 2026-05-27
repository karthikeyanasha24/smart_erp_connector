/*
  Conversational Comparison Queries
  Generated: 2026-05-26T21:22:09.386701+00:00
  Blocks: 11
*/

-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 71/81 • Compare this with last year
-- template_id: conversational_compare_this_vs_last_year
-- explanation: MTD net sales this year vs the same calendar MTD window last year (two rows).
-- assumption: Standalone compare — for branch/category filters, ask a follow-up after this run.
-- assumption: Uses APP_REPORT NetAmount and XnDt.
-- ============================================================================
SELECT
    N'CurrentMTD' AS PeriodLabel,
    CAST(SUM(CASE
        WHEN s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
         AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
        THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2)) AS TotalSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
UNION ALL
SELECT
    N'LastYearMTD',
    CAST(SUM(CASE
        WHEN s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
         AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE)))
        THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2))
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 72/81 • Compare only Chennai branches
-- template_id: conversational_compare_only_chennai_branches
-- explanation: MTD sales by branch filtered to Chennai (BranchAlias or BRANCH_LIST.City LIKE).
-- assumption: Modifier template — pair with memory for 'same but only Chennai' follow-ups.
-- ============================================================================
SELECT TOP (500)
    s.[BranchAlias],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT s.[XnNo]) AS BillCount
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND (
        s.[BranchAlias] LIKE N'%chennai%'
     OR EXISTS (
            SELECT 1
            FROM dbo.VW_MB_POWERBI_BRANCH_LIST br WITH (NOLOCK)
            WHERE (br.[ShortName] = s.[BranchAlias] OR br.[BranchName] = s.[BranchAlias])
              AND br.[City] LIKE N'%chennai%'
        )
      )
GROUP BY s.[BranchAlias]
ORDER BY MTDSales DESC


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 73/81 • Compare top 5 categories
-- template_id: conversational_compare_top_categories
-- explanation: Top 5 categories by MTD net sales for comparison.
-- assumption: Change N via 'top 10' in the question.
-- ============================================================================
SELECT TOP (5)
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName]
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 74/81 • Compare excluding returns
-- template_id: conversational_compare_excluding_returns
-- explanation: Compare net billed sales (APP, positive NetAmount) vs return quantity on SLSXNS (reference).
-- assumption: APP_REPORT is net billing — not double-counting returns in revenue.
-- assumption: Use APP-only follow-up for sales comparisons excluding returns.
-- ============================================================================
SELECT
    N'Net sales (APP billing)' AS MetricSource,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDNetSales,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[NetAmount] > 0
UNION ALL
SELECT
    N'Return qty (SLSXNS SlrQty)',
    NULL,
    CAST(SUM(x.[SlrQty]) AS decimal(18, 4))
FROM dbo.[VW_MB_POWERBI_SLSXNS_REPORT] x WITH (NOLOCK)
WHERE x.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND x.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND x.[SlrQty] > 0


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 75/81 • Compare by quantity instead of revenue
-- template_id: conversational_compare_by_quantity_instead_of_revenue
-- explanation: MTD comparison ranked by quantity (AppQty) with revenue shown for context.
-- assumption: Primary sort = SUM(AppQty); use for 'compare by units' requests.
-- ============================================================================
SELECT TOP (500)
    s.[BranchAlias],
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[BranchAlias]
ORDER BY MTDQtySold DESC


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 76/81 • Compare only premium products
-- template_id: conversational_compare_premium_products_only
-- explanation: MTD sales: premium band (ItemMRP >= 2999) vs non-premium for comparison.
-- assumption: Threshold heuristic — align with your price band definitions.
-- ============================================================================
SELECT
    CASE
        WHEN s.[ItemMRP] >= 2999 THEN N'Premium (MRP >= 2999)'
        ELSE N'Non-premium'
    END AS PriceBand,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[ItemMRP] IS NOT NULL
GROUP BY CASE
    WHEN s.[ItemMRP] >= 2999 THEN N'Premium (MRP >= 2999)'
    ELSE N'Non-premium'
END
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 77/81 • Compare supplier-wise
-- template_id: conversational_compare_supplier_wise
-- explanation: MTD net sales by supplier (supplier-wise comparison list).
-- assumption: Uses SupplierName on APP_REPORT.
-- ============================================================================
SELECT TOP (500)
    s.[SupplierName],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 78/81 • Compare trend month over month
-- template_id: conversational_compare_trend_month_over_month
-- explanation: Month-over-month net sales trend for the last 12 months.
-- assumption: One row per calendar month on XnDt.
-- ============================================================================
SELECT TOP (24)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    DATENAME(MONTH, DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1))
        + N' ' + CAST(YEAR(DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)) AS varchar(4)) AS MonthLabel,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
ORDER BY MonthStart ASC


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 79/81 • Compare before and after Diwali
-- template_id: conversational_compare_before_after_diwali
-- explanation: YTD compare: October (pre-Diwali proxy) vs November (festive month) net sales.
-- assumption: No Diwali calendar table — Oct/Nov heuristic for Indian retail.
-- assumption: Refine with exact festival dates when available.
-- ============================================================================
SELECT
    CASE
        WHEN MONTH(s.[XnDt]) = 10 THEN N'Before Diwali (October)'
        WHEN MONTH(s.[XnDt]) = 11 THEN N'Diwali season (November)'
        ELSE N'Other months'
    END AS DiwaliPeriod,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales,
    COUNT(DISTINCT CAST(s.[XnDt] AS DATE)) AS TradingDays
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1)
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND MONTH(s.[XnDt]) IN (10, 11)
GROUP BY CASE
    WHEN MONTH(s.[XnDt]) = 10 THEN N'Before Diwali (October)'
    WHEN MONTH(s.[XnDt]) = 11 THEN N'Diwali season (November)'
    ELSE N'Other months'
END
ORDER BY DiwaliPeriod


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 80/81 • Compare branch contribution percentage
-- template_id: conversational_compare_branch_contribution_percentage
-- explanation: Each branch MTD sales and % share of total (contribution comparison).
-- assumption: Same KPI as branch compare module — works standalone without prior context.
-- ============================================================================
WITH BranchRev AS (
    SELECT s.[BranchAlias] AS Store, SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) AND s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
)
SELECT TOP (500)
    Store,
    CAST(Revenue AS decimal(18, 2)) AS MTDRevenue,
    CAST(100.0 * Revenue / NULLIF(SUM(Revenue) OVER (), 0) AS decimal(18, 4)) AS ContributionPct
FROM BranchRev
ORDER BY ContributionPct DESC


-- ============================================================================
-- SECTION: Conversational Comparison Queries
-- 81/81 • Compare Chennai vs Bangalore sales this month
-- template_id: conversational_compare_chennai_vs_bangalore_sales_mtd
-- explanation: MTD sales by BranchAlias matching Compare Chennai or Bangalore (example NLP compare query).
-- assumption: Parsed cities: Compare Chennai, Bangalore.
-- assumption: Uses dbo.VW_MB_POWERBI_APP_REPORT — NetAmount, XnDt, BranchAlias.
-- assumption: BranchAlias may contain city name as store code; verify alias naming.
-- ============================================================================
SELECT
    s.[BranchAlias],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS TotalQty,
    COUNT(DISTINCT s.[XnNo]) AS BillCount
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND (
        s.[BranchAlias] LIKE N'%comparechennai%'
     OR s.[BranchAlias] LIKE N'%bangalore%'
      )
GROUP BY s.[BranchAlias]
ORDER BY TotalSales DESC

