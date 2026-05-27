/*
  Sales Comparison Questions
  Generated: 2026-05-26T21:22:09.378113+00:00
  Blocks: 10
*/

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

