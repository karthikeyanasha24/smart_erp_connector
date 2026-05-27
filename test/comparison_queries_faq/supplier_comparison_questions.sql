/*
  Supplier Comparison Questions
  Generated: 2026-05-26T21:22:09.381119+00:00
  Blocks: 10
*/

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

