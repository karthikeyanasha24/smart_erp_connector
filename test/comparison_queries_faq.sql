/*
  NLQ comparison queries — FAQ-generated T-SQL
  Generated: 2026-05-26T21:22:09.375115+00:00
  Source: nlq_faq_* COMPARE_AI_QUERIES + try_faq_template
  Total blocks: 81
*/


-- ############################################################################
-- Sales Comparison Questions
-- ############################################################################

-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 1/81 • Compare this month sales vs last month
-- template_id: compare_this_month_vs_last_month
-- explanation: Total net sales for current calendar month vs previous calendar month.
-- assumption: ThisMonth = MTD through today; LastMonth = full prior calendar month.
-- assumption: Compare growth as (ThisMonth - LastMonth) / LastMonth in your app if needed.
-- ============================================================================
WITH Sales AS (
    SELECT
        CASE
            WHEN s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
             AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
                THEN N'ThisMonth'
            WHEN s.[XnDt] >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
             AND s.[XnDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
                THEN N'LastMonth'
        END AS PeriodLabel,
        s.[NetAmount]
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    PeriodLabel,
    CAST(SUM([NetAmount]) AS decimal(18, 2)) AS TotalSales
FROM Sales
WHERE PeriodLabel IS NOT NULL
GROUP BY PeriodLabel
ORDER BY PeriodLabel


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 2/81 • Compare branch sales for Chennai vs Bangalore
-- template_id: compare_branch_sales_two_cities
-- explanation: MTD branch-level sales in Chennai vs Bangalore (BranchCity on salesperson view).
-- assumption: Cities parsed from question: Chennai, Bangalore.
-- assumption: Uses CashmemoDt MTD and SalesNetAmount.
-- ============================================================================
SELECT
    CASE
        WHEN sp.[BranchCity] LIKE N'%Chennai%' THEN N'Chennai'
        WHEN sp.[BranchCity] LIKE N'%Bangalore%' THEN N'Bangalore'
    END AS City,
    sp.[BranchAlias] AS Store,
    CAST(SUM(sp.[SalesNetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT sp.[CashmemoNo]) AS BillCount
FROM dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] sp WITH (NOLOCK)
WHERE sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND (
        sp.[BranchCity] LIKE N'%Chennai%'
     OR sp.[BranchCity] LIKE N'%Bangalore%'
      )
GROUP BY
    CASE
        WHEN sp.[BranchCity] LIKE N'%Chennai%' THEN N'Chennai'
        WHEN sp.[BranchCity] LIKE N'%Bangalore%' THEN N'Bangalore'
    END,
    sp.[BranchAlias]
HAVING CASE
        WHEN sp.[BranchCity] LIKE N'%Chennai%' THEN N'Chennai'
        WHEN sp.[BranchCity] LIKE N'%Bangalore%' THEN N'Bangalore'
    END IS NOT NULL
ORDER BY City, MTDSales DESC


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 3/81 • Compare department performance year over year
-- template_id: compare_department_performance_yoy
-- explanation: Each department: current YTD sales vs same day-range last year YTD.
-- assumption: Aligned YTD windows using DATEADD(YEAR,-1) on today's date.
-- ============================================================================
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
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
CROSS JOIN Bounds b
WHERE s.[DepartmentShortName] IS NOT NULL
  AND s.[XnDt] >= b.PrevYStart
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY s.[DepartmentShortName]
ORDER BY CurrentYTD DESC


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 4/81 • Compare weekday vs weekend sales
-- template_id: compare_weekday_vs_weekend_sales
-- explanation: MTD total sales and bill count: weekdays vs weekends (SQL Server WEEKDAY 1=Sun, 7=Sat).
-- assumption: Weekend definition follows server DATEFIRST default.
-- ============================================================================
SELECT
    CASE
        WHEN DATEPART(WEEKDAY, s.[XnDt]) IN (1, 7) THEN N'Weekend'
        ELSE N'Weekday'
    END AS DayType,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT s.[XnNo]) AS BillCount
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY CASE
    WHEN DATEPART(WEEKDAY, s.[XnDt]) IN (1, 7) THEN N'Weekend'
    ELSE N'Weekday'
END
ORDER BY DayType


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 5/81 • Compare online vs offline sales
-- template_id: compare_online_vs_offline_not_supported
-- explanation: Online vs offline split requires a channel flag or branch mapping not in the semantic catalog.
-- assumption: Informational single-row result.
-- ============================================================================
SELECT
    N'Not supported' AS Status,
    N'No online/offline or channel column on VW_MB_POWERBI_APP_REPORT in schema_catalog.txt.' AS Reason,
    N'If e-commerce uses dedicated branch aliases, ask: compare branch sales for <OnlineBranch> vs <StoreBranch>.' AS Suggestion


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 6/81 • Compare category sales across branches
-- template_id: compare_category_sales_across_branches
-- explanation: MTD net sales by category and branch (matrix-style rows).
-- assumption: TOP 500 rows — filter to one category in a follow-up if needed.
-- ============================================================================
SELECT TOP (500)
    s.[CategoryShortName] AS Category,
    s.[BranchAlias] AS Store,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[CategoryShortName] IS NOT NULL
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[CategoryShortName], s.[BranchAlias]
ORDER BY s.[CategoryShortName], MTDSales DESC


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 7/81 • Compare top 5 suppliers by revenue
-- template_id: compare_top_suppliers_by_revenue
-- explanation: Top 5 suppliers by MTD net revenue (ranked for comparison).
-- assumption: Use as a comparison list; contribution % available via supplier contribution template.
-- ============================================================================
SELECT TOP (5)
    s.[SupplierName] AS Supplier,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 8/81 • Compare current quarter vs previous quarter
-- template_id: compare_current_quarter_vs_previous_quarter
-- explanation: Net sales for the current calendar quarter vs the immediately prior quarter.
-- assumption: Current quarter is QTD through today; previous quarter is the full prior quarter.
-- assumption: Distinct from 'QTD vs last year QTD' (see ytd_growth templates).
-- ============================================================================
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
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
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


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 9/81 • Compare bill count between branches
-- template_id: compare_bill_count_between_branches
-- explanation: MTD distinct invoice count and sales by branch for side-by-side comparison.
-- assumption: BillCount = COUNT(DISTINCT XnNo) on APP_REPORT lines.
-- ============================================================================
SELECT TOP (500)
    s.[BranchAlias] AS Store,
    COUNT(DISTINCT s.[XnNo]) AS BillCount,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[BranchAlias]
ORDER BY BillCount DESC


-- ============================================================================
-- SECTION: Sales Comparison Questions
-- 10/81 • Compare sales before and after discount campaigns
-- template_id: compare_sales_before_after_discount_proxy
-- explanation: Proxy: implied discount (MRP − net) for last 30 days vs prior 30 days — not campaign-specific.
-- assumption: No campaign calendar in catalog; cannot tie to named discount events.
-- assumption: MrpValue and NetAmount on APP_REPORT.
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
        s.[MrpValue],
        s.[NetAmount]
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
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



-- ############################################################################
-- Product Comparison Questions
-- ############################################################################

-- ============================================================================
-- SECTION: Product Comparison Questions
-- 11/81 • Compare sales of kurtis vs sarees
-- template_id: compare_product_groups_sales
-- explanation: MTD sales comparison: Kurtis vs Sarees (category/department name LIKE).
-- assumption: Terms from question: kurtis, sarees.
-- assumption: Uses CategoryShortName, DepartmentShortName, Category on APP_REPORT.
-- ============================================================================
SELECT
    CASE
        WHEN s.[CategoryShortName] LIKE N'%kurtis%'
          OR s.[DepartmentShortName] LIKE N'%kurtis%'
          OR s.[Category] LIKE N'%kurtis%'
            THEN N'Kurtis'
        WHEN s.[CategoryShortName] LIKE N'%sarees%'
          OR s.[DepartmentShortName] LIKE N'%sarees%'
          OR s.[Category] LIKE N'%sarees%'
            THEN N'Sarees'
    END AS ProductGroup,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND (
        s.[CategoryShortName] LIKE N'%kurtis%'
     OR s.[DepartmentShortName] LIKE N'%kurtis%'
     OR s.[Category] LIKE N'%kurtis%'
     OR s.[CategoryShortName] LIKE N'%sarees%'
     OR s.[DepartmentShortName] LIKE N'%sarees%'
     OR s.[Category] LIKE N'%sarees%'
      )
GROUP BY CASE
    WHEN s.[CategoryShortName] LIKE N'%kurtis%'
      OR s.[DepartmentShortName] LIKE N'%kurtis%'
      OR s.[Category] LIKE N'%kurtis%'
        THEN N'Kurtis'
    WHEN s.[CategoryShortName] LIKE N'%sarees%'
      OR s.[DepartmentShortName] LIKE N'%sarees%'
      OR s.[Category] LIKE N'%sarees%'
        THEN N'Sarees'
END
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 12/81 • Compare fabric performance by season
-- template_id: compare_fabric_performance_by_season
-- explanation: MTD revenue and qty by Fabric and Property (season tag proxy on APP_REPORT).
-- assumption: Property column used as season/assortment tag when populated.
-- ============================================================================
SELECT TOP (500)
    s.[Fabric],
    ISNULL(NULLIF(LTRIM(RTRIM(s.[Property])), N''), N'(No season tag)') AS SeasonTag,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[Fabric] IS NOT NULL
GROUP BY s.[Fabric], ISNULL(NULLIF(LTRIM(RTRIM(s.[Property])), N''), N'(No season tag)')
ORDER BY MTDRevenue DESC, s.[Fabric], SeasonTag


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 13/81 • Compare color-wise sales trends
-- template_id: compare_color_wise_sales_trends
-- explanation: Monthly net sales by Color for the last 12 complete months (trend comparison).
-- assumption: One row per month × color; TOP 500 rows returned.
-- ============================================================================
SELECT TOP (500)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    s.[Color],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[Color] IS NOT NULL
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1), s.[Color]
ORDER BY MonthStart ASC, Revenue DESC


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 14/81 • Compare MRP vs actual selling price
-- template_id: compare_mrp_vs_actual_selling_price
-- explanation: MTD totals: MRP value vs net sales (actual) with implied discount % and average unit prices.
-- assumption: MrpValue and NetAmount are line totals on APP_REPORT; per-unit = sum / sum(AppQty).
-- ============================================================================
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
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 15/81 • Compare top-selling articles between months
-- template_id: compare_top_articles_between_months
-- explanation: Top 20 articles this month vs top 20 last month (full outer join on ArticleNo).
-- assumption: This month = MTD; last month = prior full calendar month.
-- ============================================================================
WITH ThisMonth AS (
    SELECT
        s.[ArticleNo],
        CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[ArticleNo] IS NOT NULL
    GROUP BY s.[ArticleNo]
),
LastMonth AS (
    SELECT
        s.[ArticleNo],
        CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND s.[XnDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
      AND s.[ArticleNo] IS NOT NULL
    GROUP BY s.[ArticleNo]
),
TopThis AS (
    SELECT TOP (20) ArticleNo, Revenue AS ThisMonthRevenue
    FROM ThisMonth
    ORDER BY Revenue DESC
),
TopLast AS (
    SELECT TOP (20) ArticleNo, Revenue AS LastMonthRevenue
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


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 16/81 • Compare product return rates by category
-- template_id: compare_return_rates_by_category
-- explanation: MTD return quantity (SLSXNS SlrQty) vs sold qty (APP AppQty) by category — return rate %.
-- assumption: Returns from SLSXNS_REPORT; sales qty from APP_REPORT.
-- ============================================================================
WITH Ret AS (
    SELECT
        s.[CategoryShortName] AS Category,
        SUM(s.[SlrQty]) AS ReturnQty
    FROM dbo.[VW_MB_POWERBI_SLSXNS_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[SlrQty] > 0
      AND s.[CategoryShortName] IS NOT NULL
    GROUP BY s.[CategoryShortName]
),
Sales AS (
    SELECT
        s.[CategoryShortName] AS Category,
        SUM(s.[AppQty]) AS SoldQty
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
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


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 17/81 • Compare premium vs budget product sales
-- template_id: compare_premium_vs_budget_sales
-- explanation: MTD sales split by ItemMRP bands: Premium >= 2999, Budget < 999, else Mid-range.
-- assumption: Thresholds are heuristics — adjust in ERP config if your price bands differ.
-- ============================================================================
SELECT
    CASE
        WHEN s.[ItemMRP] >= 2999 THEN N'Premium (MRP >= 2999)'
        WHEN s.[ItemMRP] < 999 THEN N'Budget (MRP < 999)'
        ELSE N'Mid-range'
    END AS PriceBand,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold,
    COUNT(DISTINCT s.[Itemcode]) AS DistinctItems
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[ItemMRP] IS NOT NULL
  AND s.[ItemMRP] > 0
GROUP BY CASE
    WHEN s.[ItemMRP] >= 2999 THEN N'Premium (MRP >= 2999)'
    WHEN s.[ItemMRP] < 999 THEN N'Budget (MRP < 999)'
    ELSE N'Mid-range'
END
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 18/81 • Compare size-wise sales distribution
-- template_id: compare_size_wise_sales_distribution
-- explanation: MTD quantity and revenue share by Size (PctOfTotalQty = % of all units sold).
-- assumption: Distribution ranked by quantity sold.
-- ============================================================================
SELECT TOP (500)
    s.[Size],
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(
        100.0 * SUM(s.[AppQty]) / NULLIF(SUM(SUM(s.[AppQty])) OVER (), 0)
        AS decimal(18, 4)
    ) AS PctOfTotalQty
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[Size] IS NOT NULL
  AND LTRIM(RTRIM(s.[Size])) <> N''
GROUP BY s.[Size]
ORDER BY MTDQtySold DESC


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 19/81 • Compare stock turnover by category
-- template_id: compare_stock_turnover_by_category
-- explanation: Simplified turnover proxy by category: MTD quantity sold ÷ current on-hand quantity.
-- assumption: Not annualized — MTD sales qty / snapshot stock qty.
-- assumption: Categories with zero stock show NULL turnover.
-- ============================================================================
WITH CatSales AS (
    SELECT
        s.[CategoryShortName] AS Category,
        SUM(s.[AppQty]) AS MTDQtySold
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[CategoryShortName] IS NOT NULL
    GROUP BY s.[CategoryShortName]
),
CatStock AS (
    SELECT
        st.[CategoryShortName] AS Category,
        SUM(st.[StockQty]) AS OnHandQty
    FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
    WHERE st.[CategoryShortName] IS NOT NULL
    GROUP BY st.[CategoryShortName]
)
SELECT TOP (500)
    COALESCE(cs.Category, ck.Category) AS Category,
    CAST(ISNULL(cs.MTDQtySold, 0) AS decimal(18, 4)) AS MTDQtySold,
    CAST(ISNULL(ck.OnHandQty, 0) AS decimal(18, 4)) AS OnHandQty,
    CAST(
        CASE WHEN ISNULL(ck.OnHandQty, 0) = 0 THEN NULL
             ELSE ISNULL(cs.MTDQtySold, 0) / ck.OnHandQty
        END AS decimal(18, 4)
    ) AS TurnoverRatio
FROM CatSales cs
FULL OUTER JOIN CatStock ck ON cs.Category = ck.Category
ORDER BY TurnoverRatio DESC


-- ============================================================================
-- SECTION: Product Comparison Questions
-- 20/81 • Compare old collection vs new collection performance
-- template_id: compare_old_vs_new_collection_performance
-- explanation: MTD sales by Collection name from product master, else PurDate buckets (new 6M / old 18M+).
-- assumption: Join APP_REPORT to PRODUCT_MASTER on Itemcode.
-- assumption: Collection column preferred when populated.
-- ============================================================================
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
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
INNER JOIN dbo.[VW_MB_POWERBI_PRODUCT_MASTER] pm WITH (NOLOCK) ON pm.[Itemcode] = s.[Itemcode]
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
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



-- ############################################################################
-- Branch Comparison Questions
-- ############################################################################

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



-- ############################################################################
-- Supplier Comparison Questions
-- ############################################################################

-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 31/81 • Compare supplier sales contribution
-- template_id: compare_supplier_sales_contribution
-- explanation: Each supplier's share of total MTD net sales (percent of grand total).
-- assumption: MTD; correct T-SQL window on pre-aggregated supplier revenue.
-- ============================================================================
WITH sup AS (
    SELECT
        s.[SupplierName],
        SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[SupplierName] IS NOT NULL
    GROUP BY s.[SupplierName]
)
SELECT TOP (500)
    [SupplierName],
    CAST(Revenue AS decimal(18, 2)) AS Revenue,
    CAST(100.0 * Revenue / NULLIF(SUM(Revenue) OVER (), 0) AS decimal(18, 4)) AS ContributionPct
FROM sup
ORDER BY ContributionPct DESC


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 32/81 • Compare supplier purchase cost trends
-- template_id: compare_supplier_purchase_cost_trends
-- explanation: Monthly net purchase cost by supplier for the last 6 months (PURXNS).
-- assumption: Metric: SUM(NetPurNetAmount); date: PurInvDate.
-- ============================================================================
SELECT TOP (500)
    p.[SupplierName],
    DATEFROMPARTS(YEAR(p.[PurInvDate]), MONTH(p.[PurInvDate]), 1) AS MonthStart,
    CAST(SUM(p.[NetPurNetAmount]) AS decimal(18, 2)) AS NetPurchaseCost,
    CAST(SUM(p.[NetPurQty]) AS decimal(18, 4)) AS NetPurchaseQty
FROM dbo.[VW_MB_POWERBI_PURXNS_REPORT] p WITH (NOLOCK)
WHERE p.[PurInvDate] >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND p.[PurInvDate] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND p.[SupplierName] IS NOT NULL
GROUP BY p.[SupplierName], DATEFROMPARTS(YEAR(p.[PurInvDate]), MONTH(p.[PurInvDate]), 1)
ORDER BY p.[SupplierName], MonthStart ASC


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 33/81 • Compare suppliers by margin percentage
-- template_id: compare_suppliers_by_margin_percentage
-- explanation: MTD gross margin % by supplier for side-by-side comparison.
-- assumption: Margin = (NetAmount − CostValue) / NetAmount on APP_REPORT.
-- ============================================================================
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
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY GrossMarginPct DESC


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 34/81 • Compare supplier return percentage
-- template_id: compare_supplier_return_percentage
-- explanation: MTD purchase return rate by supplier: PrtQty / (PurQty + PrtQty).
-- assumption: PURXNS_REPORT; compare rates across all suppliers.
-- ============================================================================
SELECT TOP (500)
    p.[SupplierName],
    CAST(SUM(p.[PurQty]) AS decimal(18, 4)) AS PurchaseQty,
    CAST(SUM(p.[PrtQty]) AS decimal(18, 4)) AS ReturnQty,
    CAST(
        100.0 * SUM(p.[PrtQty]) / NULLIF(SUM(p.[PurQty]) + SUM(p.[PrtQty]), 0)
        AS decimal(18, 4)
    ) AS ReturnRatePct
FROM dbo.[VW_MB_POWERBI_PURXNS_REPORT] p WITH (NOLOCK)
WHERE p.[PurInvDate] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND p.[PurInvDate] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND p.[SupplierName] IS NOT NULL
GROUP BY p.[SupplierName]
HAVING SUM(p.[PurQty]) + SUM(p.[PrtQty]) > 0
ORDER BY ReturnRatePct DESC


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 35/81 • Compare local vs outstation suppliers
-- template_id: compare_local_vs_outstation_suppliers
-- explanation: MTD sales split: local suppliers (TN / Chennai / Coimbatore proxy) vs outstation.
-- assumption: Heuristic geography — adjust SupplierState list for your HQ region.
-- assumption: Uses SupplierState and SupplierCity on APP_REPORT.
-- ============================================================================
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
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
GROUP BY CASE
    WHEN s.[SupplierState] IN (N'Tamil Nadu', N'TN', N'Tamilnadu')
      OR s.[SupplierCity] LIKE N'%Chennai%'
      OR s.[SupplierCity] LIKE N'%Coimbatore%'
        THEN N'Local (TN / major city proxy)'
    ELSE N'Outstation'
END
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 36/81 • Compare supplier performance by category
-- template_id: compare_supplier_performance_by_category
-- explanation: MTD revenue and quantity by supplier and category (comparison matrix).
-- assumption: Grain: SupplierName × CategoryShortName.
-- ============================================================================
SELECT TOP (500)
    s.[SupplierName],
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQtySold
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[SupplierName], s.[CategoryShortName]
ORDER BY s.[SupplierName], MTDRevenue DESC


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 37/81 • Compare top suppliers over last 6 months
-- template_id: compare_top_suppliers_last_6_months
-- explanation: Top 10 suppliers by total net sales over the last 6 months.
-- assumption: Rolling 6-month window on APP_REPORT XnDt.
-- ============================================================================
SELECT TOP (10)
    s.[SupplierName],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS RevenueLast6Months,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS QtyLast6Months
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -6, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
ORDER BY RevenueLast6Months DESC


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 38/81 • Compare supplier delivery efficiency
-- template_id: compare_supplier_delivery_efficiency_not_supported
-- explanation: Delivery efficiency needs procurement lead-time fields; shows GIT snapshot as related proxy.
-- assumption: Informational — GitQty/GitCostValue is in-transit stock, not OTIF.
-- ============================================================================
SELECT
    N'Not supported' AS Status,
    N'No supplier delivery lead-time or GRN date column in schema_catalog for efficiency KPI.' AS Reason,
    N'Proxy: goods-in-transit by supplier from CBS_WITH_GIT — run stock/GIT report separately.' AS Suggestion,
    CAST(SUM(c.[GitQty]) AS decimal(18, 4)) AS TotalGitQtySnapshot,
    CAST(SUM(c.[GitCostValue]) AS decimal(18, 2)) AS TotalGitCostSnapshot
FROM dbo.[VW_MB_POWERBI_CBS_WITH_GIT] c WITH (NOLOCK)
WHERE c.[SupplierName] IS NOT NULL


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 39/81 • Compare supplier stock movement
-- template_id: compare_supplier_stock_movement
-- explanation: On-hand stock vs MTD quantity sold by supplier (movement proxy).
-- assumption: Snapshot stock from STOCK_REPORT joined to MTD APP sales.
-- ============================================================================
SELECT TOP (500)
    st.[SupplierName],
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP,
    CAST(ISNULL(sa.MTDQtySold, 0) AS decimal(18, 4)) AS MTDQtySold
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
LEFT JOIN (
    SELECT s.[SupplierName], SUM(s.[AppQty]) AS MTDQtySold
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[SupplierName] IS NOT NULL
    GROUP BY s.[SupplierName]
) sa ON sa.[SupplierName] = st.[SupplierName]
WHERE st.[SupplierName] IS NOT NULL
GROUP BY st.[SupplierName], sa.MTDQtySold
ORDER BY OnHandQty DESC


-- ============================================================================
-- SECTION: Supplier Comparison Questions
-- 40/81 • Compare supplier profitability contribution
-- template_id: compare_supplier_profitability_contribution
-- explanation: Each supplier's share of total MTD gross profit (not just revenue).
-- assumption: GrossProfit = SUM(NetAmount) − SUM(CostValue); % of company MTD profit pool.
-- ============================================================================
WITH sup AS (
    SELECT
        s.[SupplierName],
        SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS GrossProfit
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
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



-- ############################################################################
-- Customer Comparison Questions
-- ############################################################################

-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 41/81 • Compare new vs repeat customer sales
-- template_id: compare_new_vs_repeat_customer_sales
-- explanation: MTD sales split: repeat vs one-time buyers, plus new customer profiles (CreatedOn MTD).
-- assumption: Repeat = >1 invoice in MTD on VwAISalesData.
-- assumption: New profiles row uses CreatedOn — may overlap repeat/one-time.
-- ============================================================================
WITH Bills AS (
    SELECT
        s.[CustomerId],
        COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount,
        SUM(s.[SaleNetAmount]) AS Revenue
    FROM dbo.[VwAISalesData] s WITH (NOLOCK)
    WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[CustomerId] IS NOT NULL
    GROUP BY s.[CustomerId]
),
NewCust AS (
    SELECT COUNT(DISTINCT c.[CustomerId]) AS Cnt
    FROM dbo.[VwAICustomerDetails] c WITH (NOLOCK)
    WHERE c.[CreatedOn] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
      AND c.[CreatedOn] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT N'Repeat (MTD >1 invoice)' AS Segment,
    SUM(CASE WHEN b.InvoiceCount > 1 THEN 1 ELSE 0 END) AS CustomerCount,
    CAST(SUM(CASE WHEN b.InvoiceCount > 1 THEN b.Revenue ELSE 0 END) AS decimal(18, 2)) AS Revenue
FROM Bills b
UNION ALL
SELECT N'One-time (single invoice)',
    SUM(CASE WHEN b.InvoiceCount = 1 THEN 1 ELSE 0 END),
    CAST(SUM(CASE WHEN b.InvoiceCount = 1 THEN b.Revenue ELSE 0 END) AS decimal(18, 2))
FROM Bills b
UNION ALL
SELECT N'New profiles (CreatedOn MTD)',
    (SELECT Cnt FROM NewCust),
    CAST((
        SELECT SUM(s.[SaleNetAmount])
        FROM dbo.[VwAISalesData] s WITH (NOLOCK)
        INNER JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
        WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
          AND c.[CreatedOn] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
          AND c.[CreatedOn] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
    ) AS decimal(18, 2))


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 42/81 • Compare customer groups by revenue
-- template_id: compare_customer_groups_by_revenue
-- explanation: MTD net sales from VwAISalesData grouped by customer group.
-- assumption: Join: VwAISalesData.CustomerId = VwAICustomerDetails.CustomerId.
-- ============================================================================
SELECT TOP (500)
    c.[CustomerGroupName],
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS TotalSales,
    COUNT(DISTINCT s.[CustomerId]) AS UniqueCustomers,
    COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount
FROM dbo.[VwAISalesData] s WITH (NOLOCK)
INNER JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK)
    ON s.[CustomerId] = c.[CustomerId]
WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND c.[CustomerGroupName] IS NOT NULL
GROUP BY c.[CustomerGroupName]
ORDER BY TotalSales DESC


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 43/81 • Compare city-wise customer spending
-- template_id: compare_city_wise_customer_spending
-- explanation: MTD customer spending by city from customer master joined to VwAISalesData.
-- assumption: City from VwAICustomerDetails; revenue = SUM(SaleNetAmount).
-- ============================================================================
SELECT TOP (500)
    COALESCE(NULLIF(LTRIM(RTRIM(c.[City])), N''), N'(Unknown city)') AS City,
    COUNT(DISTINCT c.[CustomerId]) AS UniqueCustomers,
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS MTDSpending,
    CAST(SUM(s.[SaleNetAmount]) / NULLIF(COUNT(DISTINCT c.[CustomerId]), 0) AS decimal(18, 2)) AS AvgSpendPerCustomer
FROM dbo.[VwAISalesData] s WITH (NOLOCK)
INNER JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(c.[City])), N''), N'(Unknown city)')
ORDER BY MTDSpending DESC


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 44/81 • Compare customer retention by branch
-- template_id: compare_customer_retention_by_branch
-- explanation: MTD repeat-customer % by store (branch name / alias proxy).
-- assumption: Retention proxy = share of customers with >1 MTD invoice.
-- assumption: Branch from customer BranchName or salesperson BranchAlias.
-- ============================================================================
WITH Bills AS (
    SELECT
        COALESCE(c.[BranchName], sp.[BranchAlias], N'(Unknown branch)') AS Store,
        s.[CustomerId],
        COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount
    FROM dbo.[VwAISalesData] s WITH (NOLOCK)
    LEFT JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
    LEFT JOIN dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] sp WITH (NOLOCK)
        ON sp.[CustomerId] = s.[CustomerId]
       AND CAST(sp.[CashmemoDt] AS DATE) = CAST(s.[InvoiceDt] AS DATE)
    WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[CustomerId] IS NOT NULL
    GROUP BY COALESCE(c.[BranchName], sp.[BranchAlias], N'(Unknown branch)'), s.[CustomerId]
)
SELECT TOP (500)
    Store,
    COUNT(*) AS CustomersWithSales,
    SUM(CASE WHEN InvoiceCount > 1 THEN 1 ELSE 0 END) AS RepeatCustomers,
    CAST(
        100.0 * SUM(CASE WHEN InvoiceCount > 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)
        AS decimal(18, 4)
    ) AS RepeatRatePct
FROM Bills
GROUP BY Store
ORDER BY RepeatRatePct DESC


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 45/81 • Compare high-value vs regular customers
-- template_id: compare_high_value_vs_regular_customers
-- explanation: MTD spend split: top revenue quartile vs remaining customers.
-- assumption: High-value = NTILE(4) = 1 by SUM(SaleNetAmount) in MTD.
-- ============================================================================
WITH CustRev AS (
    SELECT
        s.[CustomerId],
        SUM(s.[SaleNetAmount]) AS Revenue
    FROM dbo.[VwAISalesData] s WITH (NOLOCK)
    WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[CustomerId] IS NOT NULL
    GROUP BY s.[CustomerId]
),
Tagged AS (
    SELECT
        CustomerId,
        Revenue,
        NTILE(4) OVER (ORDER BY Revenue DESC) AS SpendQuartile
    FROM CustRev
)
SELECT
    CASE WHEN SpendQuartile = 1 THEN N'High-value (top 25% spend)'
         ELSE N'Regular (other 75%)' END AS Segment,
    COUNT(*) AS CustomerCount,
    CAST(SUM(Revenue) AS decimal(18, 2)) AS TotalRevenue,
    CAST(AVG(Revenue) AS decimal(18, 2)) AS AvgRevenuePerCustomer
FROM Tagged
GROUP BY CASE WHEN SpendQuartile = 1 THEN N'High-value (top 25% spend)'
              ELSE N'Regular (other 75%)' END
ORDER BY TotalRevenue DESC


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 46/81 • Compare customer purchase frequency
-- template_id: compare_customer_purchase_frequency
-- explanation: Average MTD invoices per customer by customer group (frequency comparison).
-- assumption: InvoiceCount = DISTINCT InvoiceId per customer in MTD.
-- ============================================================================
WITH Cust AS (
    SELECT
        c.[CustomerGroupName],
        s.[CustomerId],
        COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount,
        SUM(s.[SaleNetAmount]) AS Revenue
    FROM dbo.[VwAISalesData] s WITH (NOLOCK)
    INNER JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
    WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[CustomerId] IS NOT NULL
    GROUP BY c.[CustomerGroupName], s.[CustomerId]
)
SELECT TOP (500)
    COALESCE(NULLIF(LTRIM(RTRIM([CustomerGroupName])), N''), N'(No group)') AS CustomerSegment,
    COUNT(*) AS Customers,
    CAST(AVG(InvoiceCount * 1.0) AS decimal(18, 4)) AS AvgInvoicesPerCustomer,
    CAST(AVG(Revenue) AS decimal(18, 2)) AS AvgRevenuePerCustomer
FROM Cust
GROUP BY COALESCE(NULLIF(LTRIM(RTRIM([CustomerGroupName])), N''), N'(No group)')
ORDER BY AvgInvoicesPerCustomer DESC


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 47/81 • Compare male vs female customer sales
-- template_id: compare_male_vs_female_customer_sales
-- explanation: MTD sales by gender segment inferred from CustomerTitle (no gender column in catalog).
-- assumption: Weak proxy — many customers have blank or non-standard titles.
-- assumption: Prefer a dedicated Gender field if added to VwAICustomerDetails.
-- ============================================================================
SELECT
    CASE
        WHEN c.[CustomerTitle] LIKE N'%Mrs%'
          OR c.[CustomerTitle] LIKE N'%Ms%'
          OR c.[CustomerTitle] LIKE N'%Miss%'
            THEN N'Female (title proxy)'
        WHEN c.[CustomerTitle] LIKE N'%Mr%'
         AND c.[CustomerTitle] NOT LIKE N'%Mrs%'
            THEN N'Male (title proxy)'
        ELSE N'Unknown / other'
    END AS GenderSegment,
    COUNT(DISTINCT c.[CustomerId]) AS UniqueCustomers,
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS MTDRevenue
FROM dbo.[VwAISalesData] s WITH (NOLOCK)
INNER JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY CASE
    WHEN c.[CustomerTitle] LIKE N'%Mrs%'
      OR c.[CustomerTitle] LIKE N'%Ms%'
      OR c.[CustomerTitle] LIKE N'%Miss%'
        THEN N'Female (title proxy)'
    WHEN c.[CustomerTitle] LIKE N'%Mr%'
     AND c.[CustomerTitle] NOT LIKE N'%Mrs%'
        THEN N'Male (title proxy)'
    ELSE N'Unknown / other'
END
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 48/81 • Compare festive season customer trends
-- template_id: compare_festive_season_customer_trends
-- explanation: Monthly unique customers and revenue with festive season tag (Oct–Nov proxy).
-- assumption: Last 12 months on InvoiceDt; no festival calendar table.
-- ============================================================================
SELECT
    DATEFROMPARTS(YEAR(s.[InvoiceDt]), MONTH(s.[InvoiceDt]), 1) AS MonthStart,
    CASE WHEN MONTH(s.[InvoiceDt]) IN (10, 11) THEN N'Festive (Oct-Nov proxy)'
         ELSE N'Non-festive month' END AS SeasonTag,
    COUNT(DISTINCT s.[CustomerId]) AS UniqueCustomers,
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS TotalRevenue
FROM dbo.[VwAISalesData] s WITH (NOLOCK)
WHERE s.[InvoiceDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[CustomerId] IS NOT NULL
GROUP BY
    DATEFROMPARTS(YEAR(s.[InvoiceDt]), MONTH(s.[InvoiceDt]), 1),
    CASE WHEN MONTH(s.[InvoiceDt]) IN (10, 11) THEN N'Festive (Oct-Nov proxy)'
         ELSE N'Non-festive month' END
ORDER BY MonthStart ASC


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 49/81 • Compare loyalty customer contribution
-- template_id: compare_loyalty_customer_contribution
-- explanation: MTD revenue: loyalty/VIP/Gold customer groups vs all other customers.
-- assumption: LIKE match on CustomerGroupName — align codes with your CRM setup.
-- ============================================================================
WITH Tagged AS (
    SELECT
        s.[SaleNetAmount],
        CASE
            WHEN c.[CustomerGroupName] LIKE N'%loyal%'
              OR c.[CustomerGroupName] LIKE N'%VIP%'
              OR c.[CustomerGroupName] LIKE N'%Gold%'
                THEN N'Loyalty / VIP segment'
            ELSE N'Other customers'
        END AS Segment
    FROM dbo.[VwAISalesData] s WITH (NOLOCK)
    INNER JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
    WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    Segment,
    CAST(SUM([SaleNetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(
        100.0 * SUM([SaleNetAmount]) / NULLIF(SUM(SUM([SaleNetAmount])) OVER (), 0)
        AS decimal(18, 4)
    ) AS ContributionPct
FROM Tagged
GROUP BY Segment
ORDER BY MTDRevenue DESC


-- ============================================================================
-- SECTION: Customer Comparison Questions
-- 50/81 • Compare average order value by customer segment
-- template_id: compare_aov_by_customer_segment
-- explanation: MTD average order value (revenue / distinct invoices) by customer group.
-- assumption: AOV = SUM(SaleNetAmount) / COUNT(DISTINCT InvoiceId) per segment.
-- ============================================================================
SELECT TOP (500)
    COALESCE(NULLIF(LTRIM(RTRIM(c.[CustomerGroupName])), N''), N'(No group)') AS CustomerSegment,
    COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount,
    COUNT(DISTINCT s.[CustomerId]) AS UniqueCustomers,
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(
        SUM(s.[SaleNetAmount]) / NULLIF(COUNT(DISTINCT s.[InvoiceId]), 0)
        AS decimal(18, 2)
    ) AS AvgOrderValue
FROM dbo.[VwAISalesData] s WITH (NOLOCK)
INNER JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(c.[CustomerGroupName])), N''), N'(No group)')
ORDER BY AvgOrderValue DESC



-- ############################################################################
-- Inventory Comparison Questions
-- ############################################################################

-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 51/81 • Compare stock quantity vs sales quantity
-- template_id: compare_stock_quantity_vs_sales_quantity
-- explanation: Company totals: on-hand stock qty (snapshot) vs MTD quantity sold.
-- assumption: Single-row comparison; stock is point-in-time, sales are MTD.
-- ============================================================================
WITH Stock AS (
    SELECT CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS TotalStockQty
    FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
    WHERE st.[StockQty] > 0
),
Sales AS (
    SELECT CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDSalesQty
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    st.TotalStockQty,
    sa.MTDSalesQty,
    CAST(st.TotalStockQty - sa.MTDSalesQty AS decimal(18, 4)) AS StockMinusMTDSales,
    CAST(sa.MTDSalesQty / NULLIF(st.TotalStockQty, 0) AS decimal(18, 4)) AS SalesToStockRatio
FROM Stock st
CROSS JOIN Sales sa


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 52/81 • Compare inventory across warehouses
-- template_id: compare_inventory_across_warehouses
-- explanation: On-hand stock by branch/location with warehouse flag from BRANCH_LIST (IsWarehouse).
-- assumption: Join ShortName/BranchName to BranchAlias on STOCK_REPORT.
-- ============================================================================
SELECT TOP (500)
    st.[BranchAlias] AS Location,
    CASE WHEN br.[IsWarehouse] = 1 THEN N'Warehouse' ELSE N'Store / other' END AS LocationType,
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
LEFT JOIN dbo.VW_MB_POWERBI_BRANCH_LIST br WITH (NOLOCK)
    ON br.[ShortName] = st.[BranchAlias]
    OR br.[BranchName] = st.[BranchAlias]
WHERE st.[BranchAlias] IS NOT NULL
GROUP BY st.[BranchAlias], CASE WHEN br.[IsWarehouse] = 1 THEN N'Warehouse' ELSE N'Store / other' END
ORDER BY OnHandQty DESC


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 53/81 • Compare fast-moving vs slow-moving items
-- template_id: fast_vs_slow_moving_inventory
-- explanation: Up to 50 fast-moving and 50 slow-moving items by MTD sold qty ÷ on-hand stock.
-- assumption: STOCK_REPORT uses ItemId — joined to APP Itemcode via PRODUCT_MASTER.
-- assumption: TurnoverRatio = MTD AppQty / StockQty; snapshot stock.
-- ============================================================================
WITH SalesMtd AS (
    SELECT s.[Itemcode], SUM(s.[AppQty]) AS MTDQtySold
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[Itemcode] IS NOT NULL
    GROUP BY s.[Itemcode]
),

StockByItem AS (
    SELECT
        pm.[Itemcode],
        MAX(st.[ArticleNo]) AS ArticleNo,
        SUM(st.[StockQty]) AS StockQty
    FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
    INNER JOIN dbo.[VW_MB_POWERBI_PRODUCT_MASTER] pm WITH (NOLOCK) ON pm.[ItemId] = st.[ItemId]
    WHERE pm.[Itemcode] IS NOT NULL
    GROUP BY pm.[Itemcode]
),
ItemMetrics AS (
    SELECT
        st.[Itemcode],
        st.[ArticleNo],
        st.StockQty AS OnHandQty,
        ISNULL(sl.MTDQtySold, 0) AS MTDQtySold,
        CASE
            WHEN st.StockQty = 0 THEN NULL
            ELSE ISNULL(sl.MTDQtySold, 0) / st.StockQty
        END AS TurnoverRatio
    FROM StockByItem st
    LEFT JOIN SalesMtd sl ON sl.[Itemcode] = st.[Itemcode]
    WHERE st.StockQty > 0
),
Ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY TurnoverRatio DESC, MTDQtySold DESC) AS FastRank,
        ROW_NUMBER() OVER (ORDER BY TurnoverRatio ASC, OnHandQty DESC) AS SlowRank
    FROM ItemMetrics
)
SELECT TOP (100)
    CASE WHEN FastRank <= 50 THEN N'FastMoving' ELSE N'SlowMoving' END AS MovementClass,
    [Itemcode],
    [ArticleNo],
    CAST(OnHandQty AS decimal(18, 4)) AS OnHandQty,
    CAST(MTDQtySold AS decimal(18, 4)) AS MTDQtySold,
    CAST(TurnoverRatio AS decimal(18, 4)) AS TurnoverRatio
FROM Ranked
WHERE FastRank <= 50 OR SlowRank <= 50
ORDER BY MovementClass, TurnoverRatio DESC


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 54/81 • Compare stock aging by category
-- template_id: compare_stock_aging_by_category
-- explanation: Stock quantity by category and age bucket (PurInvoiceDt) for side-by-side comparison.
-- assumption: Aging buckets match global stock_aging_analysis logic.
-- ============================================================================
SELECT TOP (500)
    st.[CategoryShortName] AS Category,
    CASE
        WHEN st.[PurInvoiceDt] IS NULL THEN N'Unknown date'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 30 THEN N'0-30 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 60 THEN N'31-60 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 90 THEN N'61-90 days'
        ELSE N'90+ days'
    END AS AgeBucket,
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS StockQty
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
WHERE st.[StockQty] > 0
  AND st.[CategoryShortName] IS NOT NULL
GROUP BY
    st.[CategoryShortName],
    CASE
        WHEN st.[PurInvoiceDt] IS NULL THEN N'Unknown date'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 30 THEN N'0-30 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 60 THEN N'31-60 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 90 THEN N'61-90 days'
        ELSE N'90+ days'
    END
ORDER BY Category, AgeBucket


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 55/81 • Compare opening vs closing stock
-- template_id: compare_opening_vs_closing_stock
-- explanation: Closing = current on-hand; opening estimate = closing + MTD sold − MTD purchased qty.
-- assumption: No historical stock snapshot table — opening is a movement estimate only.
-- assumption: Validate against your stock ledger before financial use.
-- ============================================================================
WITH Closing AS (
    SELECT CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS ClosingQty,
           CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS ClosingValueMRP
    FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
    WHERE st.[StockQty] > 0
),
MtdSales AS (
    SELECT CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDSoldQty
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
),
MtdPurch AS (
    SELECT CAST(SUM(p.[NetPurQty]) AS decimal(18, 4)) AS MTDPurchasedQty
    FROM dbo.[VW_MB_POWERBI_PURXNS_REPORT] p WITH (NOLOCK)
    WHERE p.[PurInvDate] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND p.[PurInvDate] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    N'Closing (snapshot)' AS StockPosition,
    c.ClosingQty AS Quantity,
    c.ClosingValueMRP AS ValueAtMRP
FROM Closing c
UNION ALL
SELECT
    N'Opening (estimate)',
    c.ClosingQty + sa.MTDSoldQty - pu.MTDPurchasedQty,
    NULL
FROM Closing c
CROSS JOIN MtdSales sa
CROSS JOIN MtdPurch pu


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 56/81 • Compare stock transfer efficiency
-- template_id: compare_stock_transfer_efficiency
-- explanation: MTD transfer in vs out quantities (company total) with inbound share %.
-- assumption: Efficiency proxy — not transit-time or fill-rate KPI.
-- ============================================================================
WITH Inbound AS (
    SELECT CAST(SUM(sti.[StiQty]) AS decimal(18, 4)) AS TransferInQty
    FROM dbo.[VW_MB_POWERBI_STI_REPORT] sti WITH (NOLOCK)
    WHERE sti.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sti.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
),
Outbound AS (
    SELECT CAST(SUM(sto.[StoQty]) AS decimal(18, 4)) AS TransferOutQty
    FROM dbo.[VW_MB_POWERBI_STO_REPORT] sto WITH (NOLOCK)
    WHERE sto.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sto.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    i.TransferInQty,
    o.TransferOutQty,
    CAST(i.TransferInQty - o.TransferOutQty AS decimal(18, 4)) AS NetTransferQty,
    CAST(
        100.0 * i.TransferInQty / NULLIF(i.TransferInQty + o.TransferOutQty, 0)
        AS decimal(18, 4)
    ) AS InboundSharePct
FROM Inbound i
CROSS JOIN Outbound o


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 57/81 • Compare stock availability across cities
-- template_id: compare_stock_availability_across_cities
-- explanation: On-hand stock qty and SKU count by branch city (BRANCH_LIST.City).
-- assumption: Availability proxy = physical on-hand units in catalog.
-- ============================================================================
SELECT TOP (500)
    COALESCE(br.[City], N'(Unknown city)') AS City,
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
    COUNT(DISTINCT st.[ItemId]) AS DistinctItems,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
LEFT JOIN dbo.VW_MB_POWERBI_BRANCH_LIST br WITH (NOLOCK)
    ON br.[ShortName] = st.[BranchAlias]
    OR br.[BranchName] = st.[BranchAlias]
WHERE st.[StockQty] > 0
GROUP BY COALESCE(br.[City], N'(Unknown city)')
ORDER BY OnHandQty DESC


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 58/81 • Compare stock value by supplier
-- template_id: compare_stock_value_by_supplier
-- explanation: On-hand stock quantity and MRP value by supplier for comparison.
-- assumption: Snapshot STOCK_REPORT; StockValueAtMRP = SUM(StockQty × ItemMRP).
-- ============================================================================
SELECT TOP (500)
    st.[SupplierName],
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
WHERE st.[SupplierName] IS NOT NULL
GROUP BY st.[SupplierName]
ORDER BY StockValueAtMRP DESC


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 59/81 • Compare purchase quantity vs sales quantity
-- template_id: compare_purchase_quantity_vs_sales_quantity
-- explanation: Company MTD net purchase qty (PURXNS) vs MTD sold qty (APP AppQty).
-- assumption: Different grains — compare trends, not strict inventory balance.
-- ============================================================================
WITH Purch AS (
    SELECT CAST(SUM(p.[NetPurQty]) AS decimal(18, 4)) AS MTDPurchaseQty
    FROM dbo.[VW_MB_POWERBI_PURXNS_REPORT] p WITH (NOLOCK)
    WHERE p.[PurInvDate] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND p.[PurInvDate] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
),
Sales AS (
    SELECT CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDSalesQty
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
)
SELECT
    pu.MTDPurchaseQty,
    sa.MTDSalesQty,
    CAST(pu.MTDPurchaseQty - sa.MTDSalesQty AS decimal(18, 4)) AS PurchaseMinusSales,
    CAST(sa.MTDSalesQty / NULLIF(pu.MTDPurchaseQty, 0) AS decimal(18, 4)) AS SalesToPurchaseRatio
FROM Purch pu
CROSS JOIN Sales sa


-- ============================================================================
-- SECTION: Inventory Comparison Questions
-- 60/81 • Compare inventory turnover between branches
-- template_id: compare_inventory_turnover_between_branches
-- explanation: MTD qty sold ÷ on-hand stock by branch (turnover proxy for comparison).
-- assumption: Not annualized; snapshot stock vs MTD sales.
-- ============================================================================
WITH Sales AS (
    SELECT
        s.[BranchAlias] AS Store,
        SUM(s.[AppQty]) AS MTDQtySold
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
),
Stock AS (
    SELECT
        st.[BranchAlias] AS Store,
        SUM(st.[StockQty]) AS OnHandQty
    FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
    WHERE st.[BranchAlias] IS NOT NULL
    GROUP BY st.[BranchAlias]
)
SELECT TOP (500)
    COALESCE(sa.Store, st.Store) AS Store,
    CAST(ISNULL(sa.MTDQtySold, 0) AS decimal(18, 4)) AS MTDQtySold,
    CAST(ISNULL(st.OnHandQty, 0) AS decimal(18, 4)) AS OnHandQty,
    CAST(
        CASE WHEN ISNULL(st.OnHandQty, 0) = 0 THEN NULL
             ELSE ISNULL(sa.MTDQtySold, 0) / st.OnHandQty
        END AS decimal(18, 4)
    ) AS TurnoverRatio
FROM Sales sa
FULL OUTER JOIN Stock st ON st.Store = sa.Store
ORDER BY TurnoverRatio DESC



-- ############################################################################
-- Advanced Executive Comparison Questions
-- ############################################################################

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



-- ############################################################################
-- Conversational Comparison Queries
-- ############################################################################

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

