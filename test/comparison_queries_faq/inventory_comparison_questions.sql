/*
  Inventory Comparison Questions
  Generated: 2026-05-26T21:22:09.383426+00:00
  Blocks: 10
*/

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

