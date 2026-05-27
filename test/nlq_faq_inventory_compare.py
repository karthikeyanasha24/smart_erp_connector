"""
Inventory comparison FAQ SQL templates (extends nlq_faq_sql).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

_BRANCH_LIST = "dbo.VW_MB_POWERBI_BRANCH_LIST"

INVENTORY_COMPARE_AI_QUERIES: Tuple[str, ...] = (
    "Compare stock quantity vs sales quantity",
    "Compare inventory across warehouses",
    "Compare fast-moving vs slow-moving items",
    "Compare stock aging by category",
    "Compare opening vs closing stock",
    "Compare stock transfer efficiency",
    "Compare stock availability across cities",
    "Compare stock value by supplier",
    "Compare purchase quantity vs sales quantity",
    "Compare inventory turnover between branches",
)


def register_inventory_compare_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _PUR,
        _STI,
        _STO,
        _STOCK,
        _blob,
        _mtd_where,
        _pur_mtd_where,
        _sql_fast_vs_slow_moving,
    )

    def _sql_stock_value_by_supplier(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    st.[SupplierName],
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
FROM {_STOCK} st WITH (NOLOCK)
WHERE st.[SupplierName] IS NOT NULL
GROUP BY st.[SupplierName]
ORDER BY StockValueAtMRP DESC
"""
        return _blob(
            "compare_stock_value_by_supplier",
            sql,
            "On-hand stock quantity and MRP value by supplier for comparison.",
            ["Snapshot STOCK_REPORT; StockValueAtMRP = SUM(StockQty × ItemMRP)."],
        )

    def _sql_stock_qty_vs_sales_qty(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Stock AS (
    SELECT CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS TotalStockQty
    FROM {_STOCK} st WITH (NOLOCK)
    WHERE st.[StockQty] > 0
),
Sales AS (
    SELECT CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDSalesQty
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
)
SELECT
    st.TotalStockQty,
    sa.MTDSalesQty,
    CAST(st.TotalStockQty - sa.MTDSalesQty AS decimal(18, 4)) AS StockMinusMTDSales,
    CAST(sa.MTDSalesQty / NULLIF(st.TotalStockQty, 0) AS decimal(18, 4)) AS SalesToStockRatio
FROM Stock st
CROSS JOIN Sales sa
"""
        return _blob(
            "compare_stock_quantity_vs_sales_quantity",
            sql,
            "Company totals: on-hand stock qty (snapshot) vs MTD quantity sold.",
            ["Single-row comparison; stock is point-in-time, sales are MTD."],
        )

    def _sql_inventory_across_warehouses(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    st.[BranchAlias] AS Location,
    CASE WHEN br.[IsWarehouse] = 1 THEN N'Warehouse' ELSE N'Store / other' END AS LocationType,
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
FROM {_STOCK} st WITH (NOLOCK)
LEFT JOIN {_BRANCH_LIST} br WITH (NOLOCK)
    ON br.[ShortName] = st.[BranchAlias]
    OR br.[BranchName] = st.[BranchAlias]
WHERE st.[BranchAlias] IS NOT NULL
GROUP BY st.[BranchAlias], CASE WHEN br.[IsWarehouse] = 1 THEN N'Warehouse' ELSE N'Store / other' END
ORDER BY OnHandQty DESC
"""
        return _blob(
            "compare_inventory_across_warehouses",
            sql,
            "On-hand stock by branch/location with warehouse flag from BRANCH_LIST (IsWarehouse).",
            ["Join ShortName/BranchName to BranchAlias on STOCK_REPORT."],
        )

    def _sql_stock_aging_by_category(_q: str) -> Dict[str, Any]:
        sql = f"""
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
FROM {_STOCK} st WITH (NOLOCK)
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
"""
        return _blob(
            "compare_stock_aging_by_category",
            sql,
            "Stock quantity by category and age bucket (PurInvoiceDt) for side-by-side comparison.",
            ["Aging buckets match global stock_aging_analysis logic."],
        )

    def _sql_opening_vs_closing_stock(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Closing AS (
    SELECT CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS ClosingQty,
           CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS ClosingValueMRP
    FROM {_STOCK} st WITH (NOLOCK)
    WHERE st.[StockQty] > 0
),
MtdSales AS (
    SELECT CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDSoldQty
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
),
MtdPurch AS (
    SELECT CAST(SUM(p.[NetPurQty]) AS decimal(18, 4)) AS MTDPurchasedQty
    FROM {_PUR} p WITH (NOLOCK)
    WHERE {_pur_mtd_where("p")}
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
"""
        return _blob(
            "compare_opening_vs_closing_stock",
            sql,
            "Closing = current on-hand; opening estimate = closing + MTD sold − MTD purchased qty.",
            [
                "No historical stock snapshot table — opening is a movement estimate only.",
                "Validate against your stock ledger before financial use.",
            ],
        )

    def _sql_transfer_efficiency(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Inbound AS (
    SELECT CAST(SUM(sti.[StiQty]) AS decimal(18, 4)) AS TransferInQty
    FROM {_STI} sti WITH (NOLOCK)
    WHERE {_mtd_where("sti")}
),
Outbound AS (
    SELECT CAST(SUM(sto.[StoQty]) AS decimal(18, 4)) AS TransferOutQty
    FROM {_STO} sto WITH (NOLOCK)
    WHERE {_mtd_where("sto")}
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
"""
        return _blob(
            "compare_stock_transfer_efficiency",
            sql,
            "MTD transfer in vs out quantities (company total) with inbound share %.",
            ["Efficiency proxy — not transit-time or fill-rate KPI."],
        )

    def _sql_stock_availability_by_city(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    COALESCE(br.[City], N'(Unknown city)') AS City,
    CAST(SUM(st.[StockQty]) AS decimal(18, 4)) AS OnHandQty,
    COUNT(DISTINCT st.[ItemId]) AS DistinctItems,
    CAST(SUM(st.[StockQty] * st.[ItemMRP]) AS decimal(18, 2)) AS StockValueAtMRP
FROM {_STOCK} st WITH (NOLOCK)
LEFT JOIN {_BRANCH_LIST} br WITH (NOLOCK)
    ON br.[ShortName] = st.[BranchAlias]
    OR br.[BranchName] = st.[BranchAlias]
WHERE st.[StockQty] > 0
GROUP BY COALESCE(br.[City], N'(Unknown city)')
ORDER BY OnHandQty DESC
"""
        return _blob(
            "compare_stock_availability_across_cities",
            sql,
            "On-hand stock qty and SKU count by branch city (BRANCH_LIST.City).",
            ["Availability proxy = physical on-hand units in catalog."],
        )

    def _sql_purchase_vs_sales_qty(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Purch AS (
    SELECT CAST(SUM(p.[NetPurQty]) AS decimal(18, 4)) AS MTDPurchaseQty
    FROM {_PUR} p WITH (NOLOCK)
    WHERE {_pur_mtd_where("p")}
),
Sales AS (
    SELECT CAST(SUM(s.[AppQty]) AS decimal(18, 4)) AS MTDSalesQty
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
)
SELECT
    pu.MTDPurchaseQty,
    sa.MTDSalesQty,
    CAST(pu.MTDPurchaseQty - sa.MTDSalesQty AS decimal(18, 4)) AS PurchaseMinusSales,
    CAST(sa.MTDSalesQty / NULLIF(pu.MTDPurchaseQty, 0) AS decimal(18, 4)) AS SalesToPurchaseRatio
FROM Purch pu
CROSS JOIN Sales sa
"""
        return _blob(
            "compare_purchase_quantity_vs_sales_quantity",
            sql,
            "Company MTD net purchase qty (PURXNS) vs MTD sold qty (APP AppQty).",
            ["Different grains — compare trends, not strict inventory balance."],
        )

    def _sql_turnover_between_branches(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Sales AS (
    SELECT
        s.[BranchAlias] AS Store,
        SUM(s.[AppQty]) AS MTDQtySold
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")}
      AND s.[BranchAlias] IS NOT NULL
    GROUP BY s.[BranchAlias]
),
Stock AS (
    SELECT
        st.[BranchAlias] AS Store,
        SUM(st.[StockQty]) AS OnHandQty
    FROM {_STOCK} st WITH (NOLOCK)
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
"""
        return _blob(
            "compare_inventory_turnover_between_branches",
            sql,
            "MTD qty sold ÷ on-hand stock by branch (turnover proxy for comparison).",
            ["Not annualized; snapshot stock vs MTD sales."],
        )

    specs: List[tuple] = [
        (
            "compare_stock_quantity_vs_sales_quantity",
            [r"compare\s+stock\s+quantity\s+vs\.?\s+sales?\s+quantity", r"stock\s+quantity\s+vs\.?\s+sales?\s+quantity"],
            _sql_stock_qty_vs_sales_qty,
        ),
        (
            "compare_inventory_across_warehouses",
            [r"compare\s+inventory\s+across\s+warehouses?", r"inventory\s+across\s+warehouses?"],
            _sql_inventory_across_warehouses,
        ),
        (
            "compare_fast_vs_slow_moving_items",
            [
                r"compare\s+fast[\s-]?moving\s+vs\.?\s+slow[\s-]?moving",
                r"fast[\s-]?moving\s+vs\.?\s+slow[\s-]?moving\s+items?",
            ],
            _sql_fast_vs_slow_moving,
        ),
        (
            "compare_stock_aging_by_category",
            [r"compare\s+stock\s+aging\s+by\s+categor", r"stock\s+aging\s+by\s+categor"],
            _sql_stock_aging_by_category,
        ),
        (
            "compare_opening_vs_closing_stock",
            [r"compare\s+opening\s+vs\.?\s+closing\s+stock", r"opening\s+vs\.?\s+closing\s+stock"],
            _sql_opening_vs_closing_stock,
        ),
        (
            "compare_stock_transfer_efficiency",
            [r"compare\s+stock\s+transfer\s+efficiency", r"stock\s+transfer\s+efficiency"],
            _sql_transfer_efficiency,
        ),
        (
            "compare_stock_availability_across_cities",
            [r"compare\s+stock\s+availability\s+across\s+cities?", r"stock\s+availability\s+across\s+cities?"],
            _sql_stock_availability_by_city,
        ),
        (
            "compare_stock_value_by_supplier",
            [
                r"compare\s+stock\s+value\s+by\s+supplier",
                r"stock\s+value\s+by\s+supplier",
            ],
            _sql_stock_value_by_supplier,
        ),
        (
            "compare_purchase_quantity_vs_sales_quantity",
            [
                r"compare\s+purchase\s+quantity\s+vs\.?\s+sales?\s+quantity",
                r"purchase\s+quantity\s+vs\.?\s+sales?\s+quantity",
            ],
            _sql_purchase_vs_sales_qty,
        ),
        (
            "compare_inventory_turnover_between_branches",
            [
                r"compare\s+inventory\s+turnover\s+between\s+branches?",
                r"inventory\s+turnover\s+between\s+branches?",
            ],
            _sql_turnover_between_branches,
        ),
    ]

    for tid, patterns, builder in specs:
        register(tid, patterns, builder)
