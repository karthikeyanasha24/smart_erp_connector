/*
  Frequent AI queries — FAQ-generated T-SQL bundle
  Generated: 2026-05-31T11:29:08.137184+00:00
  Source: nlq_faq_kpi.FREQUENT_AI_QUERIES + nlq_faq_sql.try_faq_template
  Execute per block as needed (read-only analytical queries).
*/

-- ============================================================================
-- 1/50 • Store Wise MTD Sales, Unique Customer Count, ATS
-- template_id: store_mtd_sales_customers_ats
-- explanation: Store-wise MTD sales, invoice count, ATS (sales per bill), and unique customers.
-- assumption: Sales/ATS from APP_REPORT (NetAmount, XnNo).
-- assumption: Unique customers from salesperson view (CustomerId, CashmemoDt MTD).
-- ============================================================================
SELECT TOP (500)
    s.[BranchAlias] AS Store,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT s.[XnNo]) AS UniqueInvoices,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS ATS,
    ISNULL(cust.UniqueCustomers, 0) AS UniqueCustomers
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
LEFT JOIN (
    SELECT sp.[BranchAlias], COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
    FROM dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] sp WITH (NOLOCK)
    WHERE sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND sp.[CustomerId] IS NOT NULL
    GROUP BY sp.[BranchAlias]
) cust ON cust.[BranchAlias] = s.[BranchAlias]
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[BranchAlias], cust.UniqueCustomers
ORDER BY MTDSales DESC


-- ============================================================================
-- 2/50 • Department Wise MTD Sales, Unique Customer Count, ATS
-- template_id: department_mtd_sales_customers_ats
-- explanation: Department-wise MTD sales, invoices, ATS, and unique customers.
-- assumption: Same KPI definitions as store-wise, grouped by DepartmentShortName.
-- ============================================================================
SELECT TOP (500)
    s.[DepartmentShortName] AS Department,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT s.[XnNo]) AS UniqueInvoices,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS ATS,
    ISNULL(cust.UniqueCustomers, 0) AS UniqueCustomers
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
LEFT JOIN (
    SELECT sp.[DepartmentShortName], COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
    FROM dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] sp WITH (NOLOCK)
    WHERE sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND sp.[CustomerId] IS NOT NULL
    GROUP BY sp.[DepartmentShortName]
) cust ON cust.[DepartmentShortName] = s.[DepartmentShortName]
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[DepartmentShortName] IS NOT NULL
GROUP BY s.[DepartmentShortName], cust.UniqueCustomers
ORDER BY MTDSales DESC


-- ============================================================================
-- 3/50 • Category Wise MTD Sales, Unique Customer Count, ATS
-- template_id: category_mtd_sales_customers_ats
-- explanation: Category-wise MTD sales, invoices, ATS, and unique customers.
-- assumption: Same KPI definitions as store-wise, grouped by CategoryShortName.
-- ============================================================================
SELECT TOP (500)
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT s.[XnNo]) AS UniqueInvoices,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS ATS,
    ISNULL(cust.UniqueCustomers, 0) AS UniqueCustomers
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
LEFT JOIN (
    SELECT sp.[CategoryShortName], COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
    FROM dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] sp WITH (NOLOCK)
    WHERE sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND sp.[CustomerId] IS NOT NULL
    GROUP BY sp.[CategoryShortName]
) cust ON cust.[CategoryShortName] = s.[CategoryShortName]
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName], cust.UniqueCustomers
ORDER BY MTDSales DESC


-- ============================================================================
-- 4/50 • Month-wise Sales Comparison since Apr'24
-- template_id: monthly_sales_since_apr_2024
-- explanation: Month-wise total net sales from April 2024 through today.
-- assumption: Fixed start: 2024-04-01; end is exclusive tomorrow on XnDt.
-- ============================================================================
SELECT TOP (500)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    DATENAME(MONTH, DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1))
        + N' ' + CAST(YEAR(DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)) AS varchar(4)) AS MonthLabel,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(2024, 4, 1)
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
ORDER BY MonthStart ASC


-- ============================================================================
-- 5/50 • Last 5 Years Sales Analysis at Department and Category Level
-- template_id: five_year_sales_dept_category
-- explanation: Monthly sales for the last 5 years by department and category.
-- assumption: Full 5-year monthly grain; chart aggregates to monthly totals.
-- ============================================================================
SELECT
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    s.[DepartmentShortName] AS Department,
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(YEAR, -5, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1),
    s.[DepartmentShortName],
    s.[CategoryShortName]
ORDER BY MonthStart ASC, TotalSales DESC


-- ============================================================================
-- 6/50 • Average Sales at MTD Level
-- template_id: average_sales_mtd_level
-- explanation: MTD total sales and average daily sales (total / distinct sale days).
-- assumption: Average = MTD revenue spread across days with at least one transaction.
-- ============================================================================
SELECT
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDTotalSales,
    COUNT(DISTINCT CAST(s.[XnDt] AS DATE)) AS TradingDays,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT CAST(s.[XnDt] AS DATE)), 0) AS decimal(18, 2)) AS AvgDailySales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))


-- ============================================================================
-- 7/50 • Today's Sales with Unique Customer Count and Unique Invoices Billed
-- template_id: today_sales_customers_invoices
-- explanation: Today sales and invoice count from APP_REPORT; unique customers from VwAISalesData.
-- assumption: Two views — customer count may not match invoice grain exactly.
-- ============================================================================
SELECT
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TodaySales,
    COUNT(DISTINCT s.[XnNo]) AS UniqueInvoices,
    (
        SELECT COUNT(DISTINCT x.[CustomerId])
        FROM dbo.[VwAISalesData] x WITH (NOLOCK)
        WHERE CAST(x.[InvoiceDt] AS DATE) = CAST(GETDATE() AS DATE)
          AND x.[CustomerId] IS NOT NULL
    ) AS UniqueCustomers
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE CAST(s.[XnDt] AS DATE) = CAST(GETDATE() AS DATE)


-- ============================================================================
-- 8/50 • Current Year YTD Growth vs Last Year YTD Growth
-- template_id: ytd_growth_vs_last_year
-- explanation: Current year YTD sales vs same YTD window last year (two rows).
-- assumption: Compare growth manually: (Current - Last) / Last.
-- ============================================================================
SELECT
    N'CurrentYTD' AS PeriodLabel,
    CAST(SUM(CASE WHEN s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2)) AS TotalSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE (s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) OR (s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()) - 1, 1, 1) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))))
UNION ALL
SELECT
    N'LastYearYTD',
    CAST(SUM(CASE WHEN s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()) - 1, 1, 1) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2))
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE (s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) OR (s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()) - 1, 1, 1) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))))


-- ============================================================================
-- 9/50 • Current Year QTD Growth vs Last Year QTD Growth
-- template_id: qtd_growth_vs_last_year
-- explanation: Current quarter QTD vs same quarter last year.
-- assumption: Calendar quarter based on GETDATE().
-- ============================================================================
SELECT
    N'CurrentQTD' AS PeriodLabel,
    CAST(SUM(CASE WHEN s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2)) AS TotalSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE (s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) OR (s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1)) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))))
UNION ALL
SELECT
    N'LastYearQTD',
    CAST(SUM(CASE WHEN s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1)) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2))
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE (s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) OR (s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1)) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))))


-- ============================================================================
-- 10/50 • Current Year MTD Growth vs Last Year MTD Growth
-- template_id: mtd_growth_vs_last_year
-- explanation: Current month MTD vs same MTD dates last year.
-- assumption: Aligned day-for-day MTD windows using DATEADD(YEAR,-1).
-- ============================================================================
SELECT
    N'CurrentMTD' AS PeriodLabel,
    CAST(SUM(CASE WHEN s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2)) AS TotalSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE (s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) OR (s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))))
UNION ALL
SELECT
    N'LastYearMTD',
    CAST(SUM(CASE WHEN s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) THEN s.[NetAmount] ELSE 0 END) AS decimal(18, 2))
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE (s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))) OR (s.[XnDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AND s.[XnDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE))))


-- ============================================================================
-- 11/50 • Which Store has the Highest Sales in the Current Month?
-- template_id: highest_store_current_month
-- explanation: Single branch with highest MTD net sales.
-- assumption: Current month = MTD on XnDt.
-- ============================================================================
SELECT TOP (1)
    s.[BranchAlias],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY s.[BranchAlias]
ORDER BY TotalSales DESC


-- ============================================================================
-- 12/50 • Which Department has the Highest Sales in the Current Month?
-- template_id: highest_department_sales_mtd
-- explanation: Department with highest MTD net sales.
-- assumption: Current month on XnDt.
-- ============================================================================
SELECT TOP (1)
    s.[DepartmentShortName] AS Department,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[DepartmentShortName] IS NOT NULL
GROUP BY s.[DepartmentShortName]
ORDER BY MTDSales DESC


-- ============================================================================
-- 13/50 • Which Category has the Highest Sales in the Current Month?
-- template_id: highest_category_sales_mtd
-- explanation: Category with highest MTD net sales.
-- assumption: Current month on XnDt.
-- ============================================================================
SELECT TOP (1)
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName]
ORDER BY MTDSales DESC


-- ============================================================================
-- 14/50 • Most Selling Product in the Current Month or Year
-- template_id: most_selling_product_current_month_year
-- explanation: Top 20 products (Itemcode) by MTD net revenue.
-- assumption: MTD on XnDt; product grain = Itemcode.
-- ============================================================================
SELECT TOP (20)
    s.[Itemcode],
    MAX(s.[ArticleNo]) AS ArticleNo,
    MAX(s.[CategoryShortName]) AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS QtySold
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[Itemcode] IS NOT NULL
GROUP BY s.[Itemcode]
ORDER BY Revenue DESC


-- ============================================================================
-- 15/50 • Least Selling Product in the Current Month or Year
-- template_id: least_selling_product_mtd
-- explanation: Bottom 20 products by MTD revenue (among items with sales > 0).
-- assumption: Use YTD by rephrasing with 'year' if needed — template defaults to MTD.
-- ============================================================================
SELECT TOP (20)
    s.[Itemcode],
    MAX(s.[ArticleNo]) AS ArticleNo,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDQty
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[Itemcode] IS NOT NULL
GROUP BY s.[Itemcode]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY MTDSales ASC


-- ============================================================================
-- 16/50 • Which Supplier has the Highest Sales in the Current Month?
-- template_id: highest_supplier_sales_mtd
-- explanation: Supplier with highest MTD net sales on APP_REPORT.
-- assumption: MTD on XnDt; metric SUM(NetAmount).
-- ============================================================================
SELECT TOP (1)
    s.[SupplierName],
    s.[SupplierAlias],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName], s.[SupplierAlias]
ORDER BY Revenue DESC


-- ============================================================================
-- 17/50 • Which Supplier has the Lowest Sales in the Current Month?
-- template_id: lowest_supplier_sales_mtd
-- explanation: Supplier with lowest MTD sales among suppliers with positive sales.
-- assumption: Current month.
-- ============================================================================
SELECT TOP (1)
    s.[SupplierName],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY MTDSales ASC


-- ============================================================================
-- 18/50 • Top 10 Performing Stores based on Growth %
-- template_id: top_stores_by_growth_pct
-- explanation: Top 10 stores by % growth: MTD vs previous full calendar month.
-- assumption: GrowthPct = (MTD - prior month) / prior month.
-- ============================================================================
WITH Bounds AS (
    SELECT
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AS CurrStart,
        DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS PrevStart
),
B AS (
    SELECT
        s.[BranchAlias],
        SUM(CASE WHEN s.[XnDt] >= b.CurrStart AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
            THEN s.[NetAmount] ELSE 0 END) AS Curr,
        SUM(CASE WHEN s.[XnDt] >= b.PrevStart AND s.[XnDt] < b.CurrStart
            THEN s.[NetAmount] ELSE 0 END) AS Prev
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    CROSS JOIN Bounds b
    WHERE s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
)
SELECT TOP (10)
    [BranchAlias] AS Store,
    CAST(Curr AS decimal(18, 2)) AS MTDSales,
    CAST(Prev AS decimal(18, 2)) AS PriorMonthSales,
    CAST(CASE WHEN Prev = 0 THEN NULL ELSE 100.0 * (Curr - Prev) / Prev END AS decimal(18, 4)) AS GrowthPct
FROM B
WHERE Curr > 0
ORDER BY GrowthPct DESC


-- ============================================================================
-- 19/50 • Bottom 10 Performing Stores based on Sales Decline
-- template_id: bottom_stores_sales_decline
-- explanation: Bottom 10 stores by sales decline (MTD vs prior month).
-- assumption: SalesDecline = Curr - Prev (most negative first).
-- ============================================================================
WITH Bounds AS (
    SELECT
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AS CurrStart,
        DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS PrevStart
),
B AS (
    SELECT
        s.[BranchAlias],
        SUM(CASE WHEN s.[XnDt] >= b.CurrStart AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
            THEN s.[NetAmount] ELSE 0 END) AS Curr,
        SUM(CASE WHEN s.[XnDt] >= b.PrevStart AND s.[XnDt] < b.CurrStart
            THEN s.[NetAmount] ELSE 0 END) AS Prev
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    CROSS JOIN Bounds b
    WHERE s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
)
SELECT TOP (10)
    [BranchAlias] AS Store,
    CAST(Curr AS decimal(18, 2)) AS MTDSales,
    CAST(Prev AS decimal(18, 2)) AS PriorMonthSales,
    CAST(Curr - Prev AS decimal(18, 2)) AS SalesDecline
FROM B
ORDER BY SalesDecline ASC


-- ============================================================================
-- 20/50 • Which Products are Growing Fastest Month-over-Month?
-- template_id: products_fastest_mom_growth
-- explanation: Products with highest month-over-month revenue growth (last 3 complete months).
-- assumption: Uses last complete months only (excludes current partial month).
-- ============================================================================
WITH M AS (
    SELECT
        s.[Itemcode],
        DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
        SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(MONTH, -3, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND s.[XnDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
      AND s.[Itemcode] IS NOT NULL
    GROUP BY s.[Itemcode], DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
),
L AS (
    SELECT *,
        LAG(Revenue, 1) OVER (PARTITION BY Itemcode ORDER BY MonthStart) AS PrevRev
    FROM M
)
SELECT TOP (50)
    Itemcode,
    MonthStart AS LatestMonth,
    CAST(Revenue AS decimal(18, 2)) AS LatestRevenue,
    CAST(PrevRev AS decimal(18, 2)) AS PriorMonthRevenue,
    CAST(CASE WHEN PrevRev = 0 THEN NULL ELSE 100.0 * (Revenue - PrevRev) / PrevRev END AS decimal(18, 4)) AS MoMGrowthPct
FROM L
WHERE PrevRev IS NOT NULL AND PrevRev > 0
ORDER BY MoMGrowthPct DESC


-- ============================================================================
-- 21/50 • Which Categories are Showing Negative Growth Trends?
-- template_id: categories_negative_growth_trends
-- explanation: Categories with negative month-over-month revenue (latest complete month vs prior).
-- assumption: Broader than 3-month consecutive decline template.
-- ============================================================================
WITH M AS (
    SELECT
        s.[CategoryShortName] AS Category,
        DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
        SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(MONTH, -4, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND s.[XnDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
      AND s.[CategoryShortName] IS NOT NULL
    GROUP BY s.[CategoryShortName], DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
),
L AS (
    SELECT *,
        LAG(Revenue, 1) OVER (PARTITION BY Category ORDER BY MonthStart) AS PrevRev
    FROM M
)
SELECT TOP (100)
    Category,
    MonthStart AS LatestMonth,
    CAST(Revenue AS decimal(18, 2)) AS LatestRevenue,
    CAST(PrevRev AS decimal(18, 2)) AS PriorMonthRevenue,
    CAST(100.0 * (Revenue - PrevRev) / NULLIF(PrevRev, 0) AS decimal(18, 4)) AS MoMGrowthPct
FROM L
WHERE PrevRev IS NOT NULL AND Revenue < PrevRev
ORDER BY MoMGrowthPct ASC


-- ============================================================================
-- 22/50 • Predict Next Month Sales using AI Forecasting
-- template_id: predict_next_month_sales
-- explanation: Simple next-month forecast: average revenue of the last 3 complete calendar months.
-- assumption: Heuristic only — not ML; excludes current partial month from history.
-- assumption: Single-row forecast for speed (avoids large SLSXNS scans).
-- ============================================================================
WITH Hist AS (
    SELECT
        DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
        SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND s.[XnDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
    GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
),
Avg3 AS (
    SELECT AVG(CAST(Revenue AS decimal(18, 4))) AS AvgRevenue
    FROM (
        SELECT TOP (3) Revenue
        FROM Hist
        ORDER BY MonthStart DESC
    ) x
)
SELECT
    DATEADD(MONTH, 1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS ForecastMonthStart,
    CAST(a.AvgRevenue AS decimal(18, 2)) AS ForecastRevenue,
    N'Average of last 3 complete months on APP_REPORT' AS ForecastMethod
FROM Avg3 a


-- ============================================================================
-- 23/50 • Expected Stock Requirement for Next 30 Days
-- template_id: expected_stock_requirement_30_days
-- explanation: Expected stock need next 30 days = avg daily qty sold (last 30d) × 30 per item.
-- assumption: Heuristic demand plan — not on-hand stock adjusted.
-- ============================================================================
WITH DailySales AS (
    SELECT
        s.[Itemcode],
        SUM(s.[AppQty]) / 30.0 AS AvgDailyQty
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(DAY, -30, CAST(GETDATE() AS DATE))
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[Itemcode] IS NOT NULL
    GROUP BY s.[Itemcode]
)
SELECT TOP (100)
    d.[Itemcode],
    CAST(d.AvgDailyQty AS decimal(18, 4)) AS AvgDailyQtySold,
    CAST(d.AvgDailyQty * 30 AS decimal(18, 4)) AS ExpectedQtyNext30Days
FROM DailySales d
ORDER BY ExpectedQtyNext30Days DESC


-- ============================================================================
-- 24/50 • Potential Stock-Out Products Prediction
-- template_id: potential_stockout_prediction
-- explanation: Items where on-hand stock is less than 7 days of average daily sales (last 14d).
-- assumption: Simple stock-out risk proxy.
-- ============================================================================
WITH DailySales AS (
    SELECT s.[Itemcode], SUM(s.[AppQty]) / 14.0 AS AvgDailyQty
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(DAY, -14, CAST(GETDATE() AS DATE))
      AND s.[Itemcode] IS NOT NULL
    GROUP BY s.[Itemcode]
),

Stock AS (
    SELECT
        pm.[Itemcode],
        MAX(st.[ArticleNo]) AS ArticleNo,
        SUM(st.[StockQty]) AS StockQty
    FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
    INNER JOIN dbo.[VW_MB_POWERBI_PRODUCT_MASTER] pm WITH (NOLOCK) ON pm.[ItemId] = st.[ItemId]
    WHERE pm.[Itemcode] IS NOT NULL
    GROUP BY pm.[Itemcode]
)
SELECT TOP (50)
    d.[Itemcode],
    CAST(ISNULL(st.StockQty, 0) AS decimal(18, 4)) AS OnHandQty,
    CAST(d.AvgDailyQty AS decimal(18, 4)) AS AvgDailyQty,
    CAST(d.AvgDailyQty * 7 AS decimal(18, 4)) AS QtyNeeded7Days
FROM DailySales d
LEFT JOIN Stock st ON st.[Itemcode] = d.[Itemcode]
WHERE ISNULL(st.StockQty, 0) < d.AvgDailyQty * 7
ORDER BY OnHandQty ASC


-- ============================================================================
-- 25/50 • Slow-Moving Inventory Identification
-- template_id: slow_moving_inventory_identification
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
-- 26/50 • Fast-Moving Inventory Identification
-- template_id: fast_moving_inventory_identification
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
-- 27/50 • Customer Repeat Purchase Analysis
-- template_id: customer_repeat_purchase_analysis
-- explanation: MTD share of customers with more than one distinct invoice (repeat proxy).
-- assumption: Repeat = COUNT(DISTINCT InvoiceId) > 1 in MTD on VwAISalesData.
-- assumption: Not the same as new-vs-first-purchase-day logic.
-- ============================================================================
WITH CustomerBills AS (
    SELECT
        s.[CustomerId],
        COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount
    FROM dbo.[VwAISalesData] s WITH (NOLOCK)
    WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND s.[CustomerId] IS NOT NULL
    GROUP BY s.[CustomerId]
)
SELECT
    COUNT(*) AS CustomersWithSales,
    SUM(CASE WHEN InvoiceCount > 1 THEN 1 ELSE 0 END) AS RepeatCustomers,
    CAST(
        100.0 * SUM(CASE WHEN InvoiceCount > 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)
        AS decimal(18, 4)
    ) AS RepeatCustomerPct
FROM CustomerBills


-- ============================================================================
-- 28/50 • Peak Sales Hours / Peak Billing Time Analysis
-- template_id: peak_sales_hours_not_supported
-- explanation: Explains why hourly peak analysis is not available on the primary sales view.
-- assumption: Read-only informational row — not a data error.
-- ============================================================================
SELECT
    N'Not supported' AS Status,
    N'Hourly peak / billing time analysis requires a datetime column; APP_REPORT.XnDt is date-only.' AS Reason,
    N'Use daily trends or cashier view (CashmemoDt) for approximate time analysis.' AS Suggestion


-- ============================================================================
-- 29/50 • Festival vs Non-Festival Sales Comparison
-- template_id: festival_vs_non_festival_sales
-- explanation: Average monthly revenue by calendar month with festive season tags (heuristic).
-- assumption: No festival calendar table — Oct/Nov tagged as festive proxy.
-- ============================================================================
WITH M AS (
    SELECT
        MONTH(s.[XnDt]) AS Mo,
        SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(YEAR, -3, DATEFROMPARTS(YEAR(GETDATE()), 1, 1))
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
    GROUP BY MONTH(s.[XnDt])
)
SELECT
    Mo AS CalendarMonth,
    CASE WHEN Mo IN (10, 11) THEN N'Festive (Oct-Nov proxy)'
         WHEN Mo IN (3, 4, 5) THEN N'Summer'
         ELSE N'Non-festive / regular' END AS SeasonTag,
    CAST(Revenue AS decimal(18, 2)) AS AvgMonthlyRevenue
FROM M
ORDER BY Mo


-- ============================================================================
-- 30/50 • Region Wise Sales Performance Comparison
-- template_id: region_wise_sales_performance
-- explanation: MTD sales by BranchRegion from salesperson lines view.
-- assumption: Region = BranchRegion on VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID.
-- ============================================================================
SELECT TOP (500)
    sp.[BranchRegion] AS Region,
    CAST(SUM(sp.[SalesNetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT sp.[CashmemoNo]) AS Bills
FROM dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] sp WITH (NOLOCK)
WHERE sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND sp.[BranchRegion] IS NOT NULL
GROUP BY sp.[BranchRegion]
ORDER BY MTDSales DESC


-- ============================================================================
-- 31/50 • Supplier Contribution % in Overall Sales
-- template_id: supplier_contribution_percentage
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
-- 32/50 • Average Basket Size by Store
-- template_id: average_basket_size_by_store
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
-- 33/50 • Average Invoice Value Trend Analysis
-- template_id: average_invoice_value_trend
-- explanation: Monthly average invoice value (ATS) over the last 24 months.
-- assumption: AvgInvoiceValue = SUM(NetAmount) / COUNT(DISTINCT XnNo).
-- ============================================================================
SELECT TOP (24)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS AvgInvoiceValue,
    COUNT(DISTINCT s.[XnNo]) AS InvoiceCount
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -24, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
ORDER BY MonthStart ASC


-- ============================================================================
-- 34/50 • Discount Impact on Sales Performance
-- template_id: discount_impact_sales
-- explanation: Directs narrative 'insights' requests to KPI queries plus optional OpenAI summary.
-- assumption: Informational single-row result.
-- ============================================================================
SELECT
    N'Not available as SQL' AS Status,
    N'AI-generated narrative insights require a separate LLM summary step after KPI SQL runs.' AS Reason,
    N'Run specific KPI questions (MTD sales, top branch, stock, etc.) then ask for interpretation.' AS Suggestion


-- ============================================================================
-- 35/50 • Store Ranking based on Sales, ATS, and Customer Count
-- template_id: store_ranking_sales_ats_customers
-- explanation: Store-wise MTD sales, invoice count, ATS (sales per bill), and unique customers.
-- assumption: Sales/ATS from APP_REPORT (NetAmount, XnNo).
-- assumption: Unique customers from salesperson view (CustomerId, CashmemoDt MTD).
-- ============================================================================
SELECT TOP (500)
    s.[BranchAlias] AS Store,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT s.[XnNo]) AS UniqueInvoices,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS ATS,
    ISNULL(cust.UniqueCustomers, 0) AS UniqueCustomers
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
LEFT JOIN (
    SELECT sp.[BranchAlias], COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
    FROM dbo.[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] sp WITH (NOLOCK)
    WHERE sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
      AND sp.[CustomerId] IS NOT NULL
    GROUP BY sp.[BranchAlias]
) cust ON cust.[BranchAlias] = s.[BranchAlias]
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[BranchAlias] IS NOT NULL
GROUP BY s.[BranchAlias], cust.UniqueCustomers
ORDER BY MTDSales DESC


-- ============================================================================
-- 36/50 • Product Recommendation based on Customer Buying Pattern
-- template_id: product_recommendation_customer
-- explanation: Directs narrative 'insights' requests to KPI queries plus optional OpenAI summary.
-- assumption: Informational single-row result.
-- ============================================================================
SELECT
    N'Not available as SQL' AS Status,
    N'AI-generated narrative insights require a separate LLM summary step after KPI SQL runs.' AS Reason,
    N'Run specific KPI questions (MTD sales, top branch, stock, etc.) then ask for interpretation.' AS Suggestion


-- ============================================================================
-- 37/50 • AI-based Demand Forecasting by Store and Category
-- template_id: demand_forecast_store_category
-- explanation: Next-month forecast per store+category (avg last 3 complete months).
-- assumption: SLS_DATA_WITHOUT_ITEMID CashmemoDt; no TOP — all active store×category pairs.
-- ============================================================================
-- See nlq_faq_kpi._sql_demand_forecast_store_category (kept in Python for maintainability).


-- ============================================================================
-- 38/50 • Daily Sales Target vs Achievement Tracking
-- template_id: daily_sales_target_achievement
-- explanation: Directs narrative 'insights' requests to KPI queries plus optional OpenAI summary.
-- assumption: Informational single-row result.
-- ============================================================================
SELECT
    N'Not available as SQL' AS Status,
    N'AI-generated narrative insights require a separate LLM summary step after KPI SQL runs.' AS Reason,
    N'Run specific KPI questions (MTD sales, top branch, stock, etc.) then ask for interpretation.' AS Suggestion


-- ============================================================================
-- 39/50 • Weather/Festival Impact on Sales Trend
-- template_id: weather_festival_impact
-- explanation: Average monthly revenue by calendar month with festive season tags (heuristic).
-- assumption: No festival calendar table — Oct/Nov tagged as festive proxy.
-- ============================================================================
WITH M AS (
    SELECT
        MONTH(s.[XnDt]) AS Mo,
        SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(YEAR, -3, DATEFROMPARTS(YEAR(GETDATE()), 1, 1))
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
    GROUP BY MONTH(s.[XnDt])
)
SELECT
    Mo AS CalendarMonth,
    CASE WHEN Mo IN (10, 11) THEN N'Festive (Oct-Nov proxy)'
         WHEN Mo IN (3, 4, 5) THEN N'Summer'
         ELSE N'Non-festive / regular' END AS SeasonTag,
    CAST(Revenue AS decimal(18, 2)) AS AvgMonthlyRevenue
FROM M
ORDER BY Mo


-- ============================================================================
-- 40/50 • High Return / Low Conversion Product Identification
-- template_id: high_return_low_conversion_products
-- explanation: Items with high return qty vs MTD sales qty (return rate >= 10%).
-- assumption: Conversion proxy — returns from SLSXNS SlrQty.
-- ============================================================================
WITH Ret AS (
    SELECT [Itemcode], SUM([SlrQty]) AS ReturnQty
    FROM dbo.[VW_MB_POWERBI_SLSXNS_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) AND [SlrQty] > 0 AND [Itemcode] IS NOT NULL
    GROUP BY [Itemcode]
),
Sales AS (
    SELECT [Itemcode], SUM([AppQty]) AS SoldQty
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) AND [Itemcode] IS NOT NULL
    GROUP BY [Itemcode]
)
SELECT TOP (50)
    r.[Itemcode],
    CAST(r.ReturnQty AS decimal(18, 4)) AS ReturnQty,
    CAST(ISNULL(sa.SoldQty, 0) AS decimal(18, 4)) AS MTDQtySold,
    CAST(100.0 * r.ReturnQty / NULLIF(ISNULL(sa.SoldQty, 0), 0) AS decimal(18, 4)) AS ReturnRatePct
FROM Ret r
LEFT JOIN Sales sa ON sa.[Itemcode] = r.[Itemcode]
WHERE ISNULL(sa.SoldQty, 0) > 0 AND r.ReturnQty / NULLIF(sa.SoldQty, 0) >= 0.1
ORDER BY ReturnRatePct DESC


-- ============================================================================
-- 41/50 • AI-based Alerts for Sudden Sales Drop or Spike
-- template_id: sales_spike_drop_alert
-- explanation: Compares average daily sales last 7 days vs prior 7 days with alert flag.
-- assumption: Simple 25% threshold — not ML alerting.
-- ============================================================================
WITH Daily AS (
    SELECT CAST(s.[XnDt] AS DATE) AS SaleDate, SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(DAY, -14, CAST(GETDATE() AS DATE))
      AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
    GROUP BY CAST(s.[XnDt] AS DATE)
),
Stats AS (
    SELECT
        AVG(CASE WHEN SaleDate >= DATEADD(DAY, -7, CAST(GETDATE() AS DATE)) THEN Revenue END) AS AvgLast7,
        AVG(CASE WHEN SaleDate < DATEADD(DAY, -7, CAST(GETDATE() AS DATE)) THEN Revenue END) AS AvgPrev7
    FROM Daily
)
SELECT
    CAST(AvgLast7 AS decimal(18, 2)) AS AvgDailySalesLast7Days,
    CAST(AvgPrev7 AS decimal(18, 2)) AS AvgDailySalesPrior7Days,
    CAST(100.0 * (AvgLast7 - AvgPrev7) / NULLIF(AvgPrev7, 0) AS decimal(18, 4)) AS ChangePct,
    CASE
        WHEN AvgPrev7 IS NULL OR AvgPrev7 = 0 THEN N'Insufficient history'
        WHEN AvgLast7 > AvgPrev7 * 1.25 THEN N'Possible sales spike'
        WHEN AvgLast7 < AvgPrev7 * 0.75 THEN N'Possible sales drop'
        ELSE N'Within normal range'
    END AS AlertFlag
FROM Stats


-- ============================================================================
-- 42/50 • Top Customers based on Purchase Value
-- template_id: top_customers_purchase_value
-- explanation: Top 20 customers by MTD SUM(SaleNetAmount) on invoice lines.
-- assumption: MTD on InvoiceDt; metric SaleNetAmount from VwAISalesData.
-- ============================================================================
SELECT TOP (20)
    c.[CustomerId],
    c.[CustomerFirstName],
    c.[CustomerLastName],
    c.[ContactMobile],
    c.[City],
    c.[CustomerGroupName],
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS TotalPurchaseValue,
    COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount
FROM dbo.[VwAISalesData] s WITH (NOLOCK)
INNER JOIN dbo.[VwAICustomerDetails] c WITH (NOLOCK)
    ON s.[CustomerId] = c.[CustomerId]
WHERE s.[InvoiceDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY
    c.[CustomerId],
    c.[CustomerFirstName],
    c.[CustomerLastName],
    c.[ContactMobile],
    c.[City],
    c.[CustomerGroupName]
ORDER BY TotalPurchaseValue DESC


-- ============================================================================
-- 43/50 • New vs Repeat Customer Analysis
-- template_id: new_vs_repeat_customer_analysis
-- explanation: MTD customers split: repeat (>1 invoice) vs one-time (single invoice).
-- assumption: Repeat proxy — not first-purchase-day logic.
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
)
SELECT N'Repeat' AS CustomerType, COUNT(*) AS CustomerCount, CAST(SUM(Revenue) AS decimal(18, 2)) AS Revenue
FROM Bills WHERE InvoiceCount > 1
UNION ALL
SELECT N'One-time', COUNT(*), CAST(SUM(Revenue) AS decimal(18, 2))
FROM Bills WHERE InvoiceCount = 1


-- ============================================================================
-- 44/50 • Category Contribution % in Total Revenue
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
-- 45/50 • Gross Margin Analysis by Department/Category
-- template_id: gross_margin_by_category
-- explanation: MTD gross margin by category (NetAmount - CostValue).
-- assumption: Department variant: ask 'gross margin by department'.
-- ============================================================================
SELECT TOP (500)
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue,
    CAST(SUM(s.[CostValue]) AS decimal(18, 2)) AS CostValue,
    CAST(SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS decimal(18, 2)) AS GrossProfit,
    CAST(100.0 * (SUM(s.[NetAmount]) - SUM(s.[CostValue])) / NULLIF(SUM(s.[NetAmount]), 0) AS decimal(18, 4)) AS GrossMarginPct
FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName]
ORDER BY GrossProfit DESC


-- ============================================================================
-- 46/50 • Inventory Aging Analysis
-- template_id: stock_aging_analysis
-- explanation: Stock quantity and MRP value grouped by age buckets from PurInvoiceDt.
-- assumption: Aging based on PurInvoiceDt on STOCK_REPORT rows.
-- ============================================================================
SELECT TOP (500)
    CASE
        WHEN st.[PurInvoiceDt] IS NULL THEN N'Unknown date'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 30 THEN N'0-30 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 60 THEN N'31-60 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 90 THEN N'61-90 days'
        ELSE N'90+ days'
    END AS AgeBucket,
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS TotalStockQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP,
    COUNT(DISTINCT st.[ItemId]) AS DistinctItems
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
WHERE st.[StockQty] > 0
GROUP BY
    CASE
        WHEN st.[PurInvoiceDt] IS NULL THEN N'Unknown date'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 30 THEN N'0-30 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 60 THEN N'31-60 days'
        WHEN DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) <= 90 THEN N'61-90 days'
        ELSE N'90+ days'
    END
ORDER BY AgeBucket


-- ============================================================================
-- 47/50 • Dead Stock Identification
-- template_id: dead_stock_identification
-- explanation: Stock lines with PurInvoiceDt older than 90 days and positive StockQty.
-- assumption: Proxy for dead stock: aged by last purchase invoice date on stock row.
-- assumption: Does not require sales velocity — use with business validation.
-- ============================================================================
SELECT TOP (500)
    st.[BranchAlias],
    st.[ItemId],
    st.[ArticleNo],
    st.[CategoryShortName] AS Category,
    CAST(st.[StockQty] AS decimal(18, 4)) AS StockQty,
    CAST(st.[PurInvoiceDt] AS DATE) AS PurInvoiceDate,
    DATEDIFF(DAY, st.[PurInvoiceDt], GETDATE()) AS DaysSincePurInvoice
FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
WHERE st.[StockQty] > 0
  AND st.[PurInvoiceDt] IS NOT NULL
  AND st.[PurInvoiceDt] < DATEADD(DAY, -90, CAST(GETDATE() AS DATE))
ORDER BY DaysSincePurInvoice DESC, st.[StockQty] DESC


-- ============================================================================
-- 48/50 • Product-wise Sell Through %
-- template_id: product_sell_through_pct
-- explanation: Sell-through % = MTD sold qty / (MTD sold + on-hand) by item.
-- assumption: Stock ItemId bridged to Itemcode via PRODUCT_MASTER.
-- ============================================================================
WITH Sales AS (
    SELECT s.[Itemcode], SUM(s.[AppQty]) AS SoldQty
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) AND s.[Itemcode] IS NOT NULL
    GROUP BY s.[Itemcode]
),

Stock AS (
    SELECT
        pm.[Itemcode],
        MAX(st.[ArticleNo]) AS ArticleNo,
        SUM(st.[StockQty]) AS StockQty
    FROM dbo.[VW_MB_POWERBI_STOCK_REPORT] st WITH (NOLOCK)
    INNER JOIN dbo.[VW_MB_POWERBI_PRODUCT_MASTER] pm WITH (NOLOCK) ON pm.[ItemId] = st.[ItemId]
    WHERE pm.[Itemcode] IS NOT NULL
    GROUP BY pm.[Itemcode]
)
-- No TOP by default (see nlq_faq_kpi._sql_sell_through); optional TOP when question says "top N".
SELECT
    COALESCE(sa.[Itemcode], st.[Itemcode]) AS Itemcode,
    CAST(ISNULL(sa.SoldQty, 0) AS decimal(18, 4)) AS MTDQtySold,
    CAST(ISNULL(st.StockQty, 0) AS decimal(18, 4)) AS OnHandQty,
    CAST(
        100.0 * ISNULL(sa.SoldQty, 0) / NULLIF(ISNULL(sa.SoldQty, 0) + ISNULL(st.StockQty, 0), 0)
        AS decimal(18, 4)
    ) AS SellThroughPct
FROM Sales sa
FULL OUTER JOIN Stock st ON st.[Itemcode] = sa.[Itemcode]
WHERE ISNULL(sa.SoldQty, 0) + ISNULL(st.StockQty, 0) > 0
ORDER BY SellThroughPct DESC, MTDQtySold DESC, Itemcode


-- ============================================================================
-- 49/50 • Sales Trend Prediction for Upcoming Festivals/Seasons
-- template_id: sales_trend_festivals_seasons
-- explanation: Simple next-month forecast: average revenue of the last 3 complete calendar months.
-- assumption: Heuristic only — not ML; excludes current partial month from history.
-- assumption: Single-row forecast for speed (avoids large SLSXNS scans).
-- ============================================================================
WITH Hist AS (
    SELECT
        DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
        SUM(s.[NetAmount]) AS Revenue
    FROM dbo.[VW_MB_POWERBI_APP_REPORT] s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND s.[XnDt] < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
    GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
),
Avg3 AS (
    SELECT AVG(CAST(Revenue AS decimal(18, 4))) AS AvgRevenue
    FROM (
        SELECT TOP (3) Revenue
        FROM Hist
        ORDER BY MonthStart DESC
    ) x
)
SELECT
    DATEADD(MONTH, 1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS ForecastMonthStart,
    CAST(a.AvgRevenue AS decimal(18, 2)) AS ForecastRevenue,
    N'Average of last 3 complete months on APP_REPORT' AS ForecastMethod
FROM Avg3 a


-- ============================================================================
-- 50/50 • AI-generated Business Insights and Recommendations
-- template_id: ai_business_insights_snapshot
-- explanation: Executive KPI snapshot (~10 rows) for LLM business recommendations.
-- assumption: SLS_DATA_WITHOUT_ITEMID CashmemoDt; see nlq_faq_kpi._sql_ai_business_insights.
-- ============================================================================

