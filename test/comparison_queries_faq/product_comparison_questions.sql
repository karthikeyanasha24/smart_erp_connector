/*
  Product Comparison Questions
  Generated: 2026-05-26T21:22:09.379116+00:00
  Blocks: 10
*/

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

