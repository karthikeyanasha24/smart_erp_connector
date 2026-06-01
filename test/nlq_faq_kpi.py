"""
Frequent AI / dashboard KPI FAQ templates (extends nlq_faq_sql).

Loaded at import-finish of nlq_faq_sql via register_kpi_faqs().
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

# Shown in terminal (`faq` command) and erp_semantic_layer.json — all map to FAQ templates when possible.
FREQUENT_AI_QUERIES: Tuple[str, ...] = (
    "Store Wise MTD Sales, Unique Customer Count, ATS",
    "Department Wise MTD Sales, Unique Customer Count, ATS",
    "Category Wise MTD Sales, Unique Customer Count, ATS",
    "Month-wise Sales Comparison since Apr'24",
    "Last 5 Years Sales Analysis at Department and Category Level",
    "Average Sales at MTD Level",
    "Today's Sales with Unique Customer Count and Unique Invoices Billed",
    "Current Year YTD Growth vs Last Year YTD Growth",
    "Current Year QTD Growth vs Last Year QTD Growth",
    "Current Year MTD Growth vs Last Year MTD Growth",
    "Which Store has the Highest Sales in the Current Month?",
    "Which Department has the Highest Sales in the Current Month?",
    "Which Category has the Highest Sales in the Current Month?",
    "Most Selling Product in the Current Month or Year",
    "Least Selling Product in the Current Month or Year",
    "Which Supplier has the Highest Sales in the Current Month?",
    "Which Supplier has the Lowest Sales in the Current Month?",
    "Top 10 Performing Stores based on Growth %",
    "Bottom 10 Performing Stores based on Sales Decline",
    "Which Products are Growing Fastest Month-over-Month?",
    "Which Categories are Showing Negative Growth Trends?",
    "Predict Next Month Sales using AI Forecasting",
    "Expected Stock Requirement for Next 30 Days",
    "Potential Stock-Out Products Prediction",
    "Slow-Moving Inventory Identification",
    "Fast-Moving Inventory Identification",
    "Customer Repeat Purchase Analysis",
    "Peak Sales Hours / Peak Billing Time Analysis",
    "Festival vs Non-Festival Sales Comparison",
    "Region Wise Sales Performance Comparison",
    "Supplier Contribution % in Overall Sales",
    "Average Basket Size by Store",
    "Average Invoice Value Trend Analysis",
    "Discount Impact on Sales Performance",
    "Store Ranking based on Sales, ATS, and Customer Count",
    "Product Recommendation based on Customer Buying Pattern",
    "AI-based Demand Forecasting by Store and Category",
    "Daily Sales Target vs Achievement Tracking",
    "Weather/Festival Impact on Sales Trend",
    "High Return / Low Conversion Product Identification",
    "AI-based Alerts for Sudden Sales Drop or Spike",
    "Top Customers based on Purchase Value",
    "New vs Repeat Customer Analysis",
    "Category Contribution % in Total Revenue",
    "Gross Margin Analysis by Department/Category",
    "Inventory Aging Analysis",
    "Dead Stock Identification",
    "Product-wise Sell Through %",
    "Sales Trend Prediction for Upcoming Festivals/Seasons",
    "AI-generated Business Insights and Recommendations",
)

# Late import inside register_kpi_faqs to avoid circular import during nlq_faq_sql load.


def _cust_count_subquery(dim_col: str, group_col: str) -> str:
    """Unique customers from salesperson lines aligned to a dimension column."""
    from nlq_faq_sql import _SALESPERSON, _cashmemo_mtd_where

    return f"""
    SELECT
        sp.[{dim_col}] AS DimValue,
        COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
    FROM {_SALESPERSON} sp WITH (NOLOCK)
    WHERE {_cashmemo_mtd_where("sp")}
      AND sp.[{dim_col}] IS NOT NULL
      AND sp.[CustomerId] IS NOT NULL
    GROUP BY sp.[{group_col}]
"""


def register_kpi_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _CUST,
        _SALES_AI,
        _SLSXNS,
        _STOCK,
        _SALESPERSON,
        _blob,
        _mtd_where,
        _today_where,
        _invoice_mtd_where,
        _cashmemo_mtd_where,
        _top_n_from_question,
    )

    def _sql_store_mtd_kpi(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    sp.[BranchAlias] AS Store,
    CAST(SUM(sp.[SalesNetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT sp.[CashmemoNo]) AS UniqueInvoices,
    CAST(SUM(sp.[SalesNetAmount]) / NULLIF(COUNT(DISTINCT sp.[CashmemoNo]), 0) AS decimal(18, 2)) AS ATS,
    COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE {_cashmemo_mtd_where("sp")}
  AND sp.[BranchAlias] IS NOT NULL
GROUP BY sp.[BranchAlias]
HAVING SUM(sp.[SalesNetAmount]) <> 0
ORDER BY MTDSales DESC
"""
        return _blob(
            "store_mtd_sales_customers_ats",
            sql,
            "Store-wise MTD sales, invoice count, ATS (sales per bill), and unique customers.",
            [
                "Single source: SLS_DATA_WITHOUT_ITEMID (CashmemoDt) — aligned with dashboard analytics.",
                "Returns no rows when the current month has no posted sales yet.",
            ],
        )

    def _sql_dept_mtd_kpi(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    sp.[DepartmentShortName] AS Department,
    CAST(SUM(sp.[SalesNetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT sp.[CashmemoNo]) AS UniqueInvoices,
    CAST(SUM(sp.[SalesNetAmount]) / NULLIF(COUNT(DISTINCT sp.[CashmemoNo]), 0) AS decimal(18, 2)) AS ATS,
    COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE {_cashmemo_mtd_where("sp")}
  AND sp.[DepartmentShortName] IS NOT NULL
GROUP BY sp.[DepartmentShortName]
HAVING SUM(sp.[SalesNetAmount]) <> 0
ORDER BY MTDSales DESC
"""
        return _blob(
            "department_mtd_sales_customers_ats",
            sql,
            "Department-wise MTD sales, invoices, ATS, and unique customers.",
            ["Single source: SLS_DATA_WITHOUT_ITEMID on CashmemoDt."],
        )

    def _sql_cat_mtd_kpi(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    sp.[CategoryShortName] AS Category,
    CAST(SUM(sp.[SalesNetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT sp.[CashmemoNo]) AS UniqueInvoices,
    CAST(SUM(sp.[SalesNetAmount]) / NULLIF(COUNT(DISTINCT sp.[CashmemoNo]), 0) AS decimal(18, 2)) AS ATS,
    COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE {_cashmemo_mtd_where("sp")}
  AND sp.[CategoryShortName] IS NOT NULL
GROUP BY sp.[CategoryShortName]
HAVING SUM(sp.[SalesNetAmount]) <> 0
ORDER BY MTDSales DESC
"""
        return _blob(
            "category_mtd_sales_customers_ats",
            sql,
            "Category-wise MTD sales, invoices, ATS, and unique customers.",
            ["Single source: SLS_DATA_WITHOUT_ITEMID on CashmemoDt."],
        )

    def _sql_monthly_since_apr_2024(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    DATEFROMPARTS(YEAR(sp.[CashmemoDt]), MONTH(sp.[CashmemoDt]), 1) AS MonthStart,
    DATENAME(MONTH, DATEFROMPARTS(YEAR(sp.[CashmemoDt]), MONTH(sp.[CashmemoDt]), 1))
        + N' ' + CAST(YEAR(DATEFROMPARTS(YEAR(sp.[CashmemoDt]), MONTH(sp.[CashmemoDt]), 1)) AS varchar(4)) AS MonthLabel,
    CAST(SUM(sp.[SalesNetAmount]) AS decimal(18, 2)) AS TotalSales
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE sp.[CashmemoDt] >= DATEFROMPARTS(2024, 4, 1)
  AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY DATEFROMPARTS(YEAR(sp.[CashmemoDt]), MONTH(sp.[CashmemoDt]), 1)
ORDER BY MonthStart ASC
"""
        return _blob(
            "monthly_sales_since_apr_2024",
            sql,
            "Month-wise total net sales from April 2024 through today.",
            ["Uses SLS_DATA_WITHOUT_ITEMID (CashmemoDt) for fast monthly totals."],
        )

    def _sql_five_year_dept_category(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    s.[DepartmentShortName] AS Department,
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS TotalSales
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(YEAR, -5, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1),
    s.[DepartmentShortName],
    s.[CategoryShortName]
ORDER BY MonthStart ASC, TotalSales DESC
"""
        return _blob(
            "five_year_sales_dept_category",
            sql,
            "Monthly sales for the last 5 years by department and category.",
            ["Full 5-year monthly grain; chart aggregates to monthly totals."],
        )

    def _sql_average_sales_mtd(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDTotalSales,
    COUNT(DISTINCT CAST(s.[XnDt] AS DATE)) AS TradingDays,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT CAST(s.[XnDt] AS DATE)), 0) AS decimal(18, 2)) AS AvgDailySales
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
"""
        return _blob(
            "average_sales_mtd_level",
            sql,
            "MTD total sales and average daily sales (total / distinct sale days).",
            ["Average = MTD revenue spread across days with at least one transaction."],
        )

    def _sql_today_sales_customers_invoices(_q: str) -> Dict[str, Any]:
        from nlq_faq_sql import _cashmemo_today_where

        sql = f"""
SELECT
    CAST(ISNULL(SUM(sp.[SalesNetAmount]), 0) AS decimal(18, 2)) AS TodaySales,
    COUNT(DISTINCT sp.[CashmemoNo]) AS UniqueInvoices,
    COUNT(DISTINCT sp.[CustomerId]) AS UniqueCustomers
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE {_cashmemo_today_where("sp")}
"""
        return _blob(
            "today_sales_customers_invoices",
            sql,
            "Today sales, invoice count, and unique customers from cash memo lines.",
            ["Single source: SLS_DATA_WITHOUT_ITEMID on CashmemoDt."],
        )

    def _period_growth_sql(period: str, label_cur: str, label_py: str) -> str:
        if period == "ytd":
            cur = (
                "sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1) "
                "AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))"
            )
            py = (
                "sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()) - 1, 1, 1) "
                "AND sp.[CashmemoDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE)))"
            )
        elif period == "qtd":
            cur = (
                "sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1) "
                "AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))"
            )
            py = (
                "sp.[CashmemoDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE()) - 1) / 3) * 3 + 1, 1)) "
                "AND sp.[CashmemoDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE)))"
            )
        else:  # mtd
            cur = (
                "sp.[CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) "
                "AND sp.[CashmemoDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))"
            )
            py = (
                "sp.[CashmemoDt] >= DATEADD(YEAR, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) "
                "AND sp.[CashmemoDt] < DATEADD(YEAR, -1, DATEADD(DAY, 1, CAST(GETDATE() AS DATE)))"
            )
        return f"""
SELECT
    N'{label_cur}' AS PeriodLabel,
    CAST(ISNULL(SUM(sp.[SalesNetAmount]), 0) AS decimal(18, 2)) AS TotalSales
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE {cur}
UNION ALL
SELECT
    N'{label_py}',
    CAST(ISNULL(SUM(sp.[SalesNetAmount]), 0) AS decimal(18, 2))
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE {py}
"""

    def _sql_ytd_growth(_q: str) -> Dict[str, Any]:
        return _blob(
            "ytd_growth_vs_last_year",
            _period_growth_sql("ytd", "CurrentYTD", "LastYearYTD"),
            "Current year YTD sales vs same YTD window last year (two rows).",
            ["Compare growth manually: (Current - Last) / Last."],
        )

    def _sql_qtd_growth(_q: str) -> Dict[str, Any]:
        return _blob(
            "qtd_growth_vs_last_year",
            _period_growth_sql("qtd", "CurrentQTD", "LastYearQTD"),
            "Current quarter QTD vs same quarter last year.",
            ["Calendar quarter based on GETDATE()."],
        )

    def _sql_mtd_growth(_q: str) -> Dict[str, Any]:
        return _blob(
            "mtd_growth_vs_last_year",
            _period_growth_sql("mtd", "CurrentMTD", "LastYearMTD"),
            "Current month MTD vs same MTD dates last year.",
            ["Aligned day-for-day MTD windows using DATEADD(YEAR,-1)."],
        )

    def _sql_highest_department_mtd(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (1)
    s.[DepartmentShortName] AS Department,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[DepartmentShortName] IS NOT NULL
GROUP BY s.[DepartmentShortName]
ORDER BY MTDSales DESC
"""
        return _blob(
            "highest_department_sales_mtd",
            sql,
            "Department with highest MTD net sales.",
            ["Current month on XnDt."],
        )

    def _sql_highest_category_mtd(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (1)
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName]
ORDER BY MTDSales DESC
"""
        return _blob(
            "highest_category_sales_mtd",
            sql,
            "Category with highest MTD net sales.",
            ["Current month on XnDt."],
        )

    def _sql_least_product_mtd(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (20)
    s.[Itemcode],
    MAX(s.[ArticleNo]) AS ArticleNo,
    CAST(SUM(s.[NetSlsNetAmount]) AS decimal(18, 2)) AS MTDSales,
    CAST(SUM(s.[NetSlsQty]) AS decimal(18, 4)) AS MTDQty
FROM {_SLSXNS} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[Itemcode] IS NOT NULL
GROUP BY s.[Itemcode]
HAVING SUM(s.[NetSlsNetAmount]) > 0
ORDER BY MTDSales ASC
"""
        return _blob(
            "least_selling_product_mtd",
            sql,
            "Bottom 20 products by MTD revenue (among items with sales > 0).",
            ["Use YTD by rephrasing with 'year' if needed — template defaults to MTD."],
        )

    def _sql_lowest_supplier_mtd(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (1)
    s.[SupplierName],
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS MTDSales
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")}
  AND s.[SupplierName] IS NOT NULL
GROUP BY s.[SupplierName]
HAVING SUM(s.[NetAmount]) > 0
ORDER BY MTDSales ASC
"""
        return _blob(
            "lowest_supplier_sales_mtd",
            sql,
            "Supplier with lowest MTD sales among suppliers with positive sales.",
            ["Current month."],
        )

    def _sql_top_stores_growth(_q: str) -> Dict[str, Any]:
        n = _top_n_from_question(_q, 10)
        sql = f"""
WITH Bounds AS (
    SELECT
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AS CurrStart,
        CAST(GETDATE() AS DATE) AS AsOf,
        DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS PrevStart
),
B AS (
    SELECT
        sp.[BranchAlias],
        SUM(CASE WHEN sp.[CashmemoDt] >= b.CurrStart AND sp.[CashmemoDt] < DATEADD(DAY, 1, b.AsOf)
            THEN sp.[SalesNetAmount] ELSE 0 END) AS Curr,
        SUM(CASE WHEN sp.[CashmemoDt] >= b.PrevStart
                 AND sp.[CashmemoDt] < DATEADD(MONTH, -1, DATEADD(DAY, 1, b.AsOf))
            THEN sp.[SalesNetAmount] ELSE 0 END) AS Prev
    FROM {_SALESPERSON} sp WITH (NOLOCK)
    CROSS JOIN Bounds b
    WHERE sp.[BranchAlias] IS NOT NULL
    GROUP BY sp.[BranchAlias]
)
SELECT TOP ({n})
    [BranchAlias] AS Store,
    CAST(Curr AS decimal(18, 2)) AS MTDSales,
    CAST(Prev AS decimal(18, 2)) AS PriorPeriodSales,
    CAST(CASE WHEN Prev = 0 THEN NULL ELSE 100.0 * (Curr - Prev) / Prev END AS decimal(18, 4)) AS GrowthPct
FROM B
WHERE Curr > 0 AND Prev > 0
ORDER BY GrowthPct DESC
"""
        return _blob(
            "top_stores_by_growth_pct",
            sql,
            f"Top {n} stores by % growth: MTD vs same elapsed days last month.",
            ["Uses SLS_DATA_WITHOUT_ITEMID (CashmemoDt)."],
        )

    def _sql_bottom_stores_decline(_q: str) -> Dict[str, Any]:
        n = _top_n_from_question(_q, 10)
        sql = f"""
WITH Bounds AS (
    SELECT
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1) AS CurrStart,
        CAST(GETDATE() AS DATE) AS AsOf,
        DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS PrevStart
),
B AS (
    SELECT
        sp.[BranchAlias],
        SUM(CASE WHEN sp.[CashmemoDt] >= b.CurrStart AND sp.[CashmemoDt] < DATEADD(DAY, 1, b.AsOf)
            THEN sp.[SalesNetAmount] ELSE 0 END) AS Curr,
        SUM(CASE WHEN sp.[CashmemoDt] >= b.PrevStart
                 AND sp.[CashmemoDt] < DATEADD(MONTH, -1, DATEADD(DAY, 1, b.AsOf))
            THEN sp.[SalesNetAmount] ELSE 0 END) AS Prev
    FROM {_SALESPERSON} sp WITH (NOLOCK)
    CROSS JOIN Bounds b
    WHERE sp.[BranchAlias] IS NOT NULL
    GROUP BY sp.[BranchAlias]
)
SELECT TOP ({n})
    [BranchAlias] AS Store,
    CAST(Curr AS decimal(18, 2)) AS MTDSales,
    CAST(Prev AS decimal(18, 2)) AS PriorPeriodSales,
    CAST(Curr - Prev AS decimal(18, 2)) AS SalesDecline,
    CAST(CASE WHEN Prev = 0 THEN NULL ELSE 100.0 * (Curr - Prev) / Prev END AS decimal(18, 4)) AS DeclinePct
FROM B
WHERE Prev > 0 AND Curr > 0 AND Curr < Prev
ORDER BY SalesDecline ASC
"""
        return _blob(
            "bottom_stores_sales_decline",
            sql,
            f"Bottom {n} stores by sales decline: current MTD vs same elapsed days last month.",
            [
                "Only stores with sales in both periods where current MTD declined.",
                "Prior period = same day-count in previous calendar month (not full month).",
            ],
        )

    def _sql_products_mom_growth(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH M AS (
    SELECT
        s.[Itemcode],
        DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
        SUM(s.[NetAmount]) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
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
"""
        return _blob(
            "products_fastest_mom_growth",
            sql,
            "Products with highest month-over-month revenue growth (last 3 complete months).",
            ["Uses last complete months only (excludes current partial month)."],
        )

    def _sql_categories_negative_growth(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH M AS (
    SELECT
        s.[CategoryShortName] AS Category,
        DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
        SUM(s.[NetAmount]) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
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
"""
        return _blob(
            "categories_negative_growth_trends",
            sql,
            "Categories with negative month-over-month revenue (latest complete month vs prior).",
            ["Broader than 3-month consecutive decline template."],
        )

    def _sql_stock_requirement_30d(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH DailySales AS (
    SELECT
        s.[Itemcode],
        SUM(s.[AppQty]) / 30.0 AS AvgDailyQty
    FROM {_APP} s WITH (NOLOCK)
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
"""
        return _blob(
            "expected_stock_requirement_30_days",
            sql,
            "Expected stock need next 30 days = avg daily qty sold (last 30d) × 30 per item.",
            ["Heuristic demand plan — not on-hand stock adjusted."],
        )

    def _sql_stockout_risk(_q: str) -> Dict[str, Any]:
        from nlq_faq_sql import _stock_by_itemcode_cte

        sql = f"""
WITH DailySales AS (
    SELECT s.[Itemcode], SUM(s.[AppQty]) / 14.0 AS AvgDailyQty
    FROM {_APP} s WITH (NOLOCK)
    WHERE s.[XnDt] >= DATEADD(DAY, -14, CAST(GETDATE() AS DATE))
      AND s.[Itemcode] IS NOT NULL
    GROUP BY s.[Itemcode]
),
{_stock_by_itemcode_cte("Stock")}
SELECT TOP (50)
    d.[Itemcode],
    CAST(ISNULL(st.StockQty, 0) AS decimal(18, 4)) AS OnHandQty,
    CAST(d.AvgDailyQty AS decimal(18, 4)) AS AvgDailyQty,
    CAST(d.AvgDailyQty * 7 AS decimal(18, 4)) AS QtyNeeded7Days
FROM DailySales d
LEFT JOIN Stock st ON st.[Itemcode] = d.[Itemcode]
WHERE ISNULL(st.StockQty, 0) < d.AvgDailyQty * 7
ORDER BY OnHandQty ASC
"""
        return _blob(
            "potential_stockout_prediction",
            sql,
            "Items where on-hand stock is less than 7 days of average daily sales (last 14d).",
            ["Simple stock-out risk proxy."],
        )

    def _sql_peak_hours_blocked(_q: str) -> Dict[str, Any]:
        sql = """
SELECT
    N'Not supported' AS Status,
    N'Hourly peak / billing time analysis requires a datetime column; APP_REPORT.XnDt is date-only.' AS Reason,
    N'Use daily trends or cashier view (CashmemoDt) for approximate time analysis.' AS Suggestion
"""
        return _blob(
            "peak_sales_hours_not_supported",
            sql,
            "Explains why hourly peak analysis is not available on the primary sales view.",
            ["Read-only informational row — not a data error."],
        )

    def _sql_festival_sales(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH M AS (
    SELECT
        MONTH(s.[XnDt]) AS Mo,
        SUM(s.[NetAmount]) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
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
"""
        return _blob(
            "festival_vs_non_festival_sales",
            sql,
            "Average monthly revenue by calendar month with festive season tags (heuristic).",
            ["No festival calendar table — Oct/Nov tagged as festive proxy."],
        )

    def _sql_region_sales(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    sp.[BranchRegion] AS Region,
    CAST(SUM(sp.[SalesNetAmount]) AS decimal(18, 2)) AS MTDSales,
    COUNT(DISTINCT sp.[CashmemoNo]) AS Bills
FROM {_SALESPERSON} sp WITH (NOLOCK)
WHERE {_cashmemo_mtd_where("sp")}
  AND sp.[BranchRegion] IS NOT NULL
GROUP BY sp.[BranchRegion]
ORDER BY MTDSales DESC
"""
        return _blob(
            "region_wise_sales_performance",
            sql,
            "MTD sales by BranchRegion from salesperson lines view.",
            ["Region = BranchRegion on VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID."],
        )

    def _sql_invoice_value_trend(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (24)
    DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1) AS MonthStart,
    CAST(SUM(s.[NetAmount]) / NULLIF(COUNT(DISTINCT s.[XnNo]), 0) AS decimal(18, 2)) AS AvgInvoiceValue,
    COUNT(DISTINCT s.[XnNo]) AS InvoiceCount
FROM {_APP} s WITH (NOLOCK)
WHERE s.[XnDt] >= DATEADD(MONTH, -24, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[XnDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
GROUP BY DATEFROMPARTS(YEAR(s.[XnDt]), MONTH(s.[XnDt]), 1)
ORDER BY MonthStart ASC
"""
        return _blob(
            "average_invoice_value_trend",
            sql,
            "Monthly average invoice value (ATS) over the last 24 months.",
            ["AvgInvoiceValue = SUM(NetAmount) / COUNT(DISTINCT XnNo)."],
        )

    def _sql_new_vs_repeat(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Bills AS (
    SELECT
        s.[CustomerId],
        COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount,
        SUM(s.[SaleNetAmount]) AS Revenue
    FROM {_SALES_AI} s WITH (NOLOCK)
    WHERE {_invoice_mtd_where("s")}
      AND s.[CustomerId] IS NOT NULL
    GROUP BY s.[CustomerId]
)
SELECT N'Repeat' AS CustomerType, COUNT(*) AS CustomerCount, CAST(SUM(Revenue) AS decimal(18, 2)) AS Revenue
FROM Bills WHERE InvoiceCount > 1
UNION ALL
SELECT N'One-time', COUNT(*), CAST(SUM(Revenue) AS decimal(18, 2))
FROM Bills WHERE InvoiceCount = 1
"""
        return _blob(
            "new_vs_repeat_customer_analysis",
            sql,
            "MTD customers split: repeat (>1 invoice) vs one-time (single invoice).",
            ["Repeat proxy — not first-purchase-day logic."],
        )

    def _sql_category_contribution(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH c AS (
    SELECT sp.[CategoryShortName] AS Category, SUM(sp.[SalesNetAmount]) AS Revenue
    FROM {_SALESPERSON} sp WITH (NOLOCK)
    WHERE {_cashmemo_mtd_where("sp")} AND sp.[CategoryShortName] IS NOT NULL
    GROUP BY sp.[CategoryShortName]
)
SELECT TOP (500)
    Category,
    CAST(Revenue AS decimal(18, 2)) AS Revenue,
    CAST(100.0 * Revenue / NULLIF(SUM(Revenue) OVER (), 0) AS decimal(18, 4)) AS ContributionPct
FROM c
WHERE Revenue <> 0
ORDER BY ContributionPct DESC
"""
        return _blob(
            "category_contribution_percentage",
            sql,
            "Each category's % of total MTD net sales.",
            ["Uses SLS_DATA_WITHOUT_ITEMID (CashmemoDt, SalesNetAmount)."],
        )

    def _sql_gross_margin_category(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    s.[CategoryShortName] AS Category,
    CAST(SUM(s.[NetAmount]) AS decimal(18, 2)) AS Revenue,
    CAST(SUM(s.[CostValue]) AS decimal(18, 2)) AS CostValue,
    CAST(SUM(s.[NetAmount]) - SUM(s.[CostValue]) AS decimal(18, 2)) AS GrossProfit,
    CAST(100.0 * (SUM(s.[NetAmount]) - SUM(s.[CostValue])) / NULLIF(SUM(s.[NetAmount]), 0) AS decimal(18, 4)) AS GrossMarginPct
FROM {_APP} s WITH (NOLOCK)
WHERE {_mtd_where("s")} AND s.[CategoryShortName] IS NOT NULL
GROUP BY s.[CategoryShortName]
ORDER BY GrossProfit DESC
"""
        return _blob(
            "gross_margin_by_category",
            sql,
            "MTD gross margin by category (NetAmount - CostValue).",
            ["Department variant: ask 'gross margin by department'."],
        )

    def _sql_sell_through(_q: str) -> Dict[str, Any]:
        from nlq_faq_sql import _stock_by_itemcode_cte

        sql = f"""
WITH Sales AS (
    SELECT s.[Itemcode], SUM(s.[AppQty]) AS SoldQty
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")} AND s.[Itemcode] IS NOT NULL
    GROUP BY s.[Itemcode]
),
{_stock_by_itemcode_cte("Stock")}
SELECT TOP (100)
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
ORDER BY SellThroughPct DESC
"""
        return _blob(
            "product_sell_through_pct",
            sql,
            "Sell-through % = MTD sold qty / (MTD sold + on-hand) by item.",
            ["Stock ItemId bridged to Itemcode via PRODUCT_MASTER."],
        )

    def _sql_sales_spike_alert(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Daily AS (
    SELECT CAST(s.[XnDt] AS DATE) AS SaleDate, SUM(s.[NetAmount]) AS Revenue
    FROM {_APP} s WITH (NOLOCK)
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
"""
        return _blob(
            "sales_spike_drop_alert",
            sql,
            "Compares average daily sales last 7 days vs prior 7 days with alert flag.",
            ["Simple 25% threshold — not ML alerting."],
        )

    def _sql_ai_insights_blocked(_q: str) -> Dict[str, Any]:
        sql = """
SELECT
    N'Not available as SQL' AS Status,
    N'AI-generated narrative insights require a separate LLM summary step after KPI SQL runs.' AS Reason,
    N'Run specific KPI questions (MTD sales, top branch, stock, etc.) then ask for interpretation.' AS Suggestion
"""
        return _blob(
            "ai_insights_not_supported",
            sql,
            "Directs narrative 'insights' requests to KPI queries plus optional OpenAI summary.",
            ["Informational single-row result."],
        )

    def _sql_high_return_low_sales(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Ret AS (
    SELECT [Itemcode], SUM([SlrQty]) AS ReturnQty
    FROM {_SLSXNS} s WITH (NOLOCK)
    WHERE {_mtd_where("s")} AND [SlrQty] > 0 AND [Itemcode] IS NOT NULL
    GROUP BY [Itemcode]
),
Sales AS (
    SELECT [Itemcode], SUM([AppQty]) AS SoldQty
    FROM {_APP} s WITH (NOLOCK)
    WHERE {_mtd_where("s")} AND [Itemcode] IS NOT NULL
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
"""
        return _blob(
            "high_return_low_conversion_products",
            sql,
            "Items with high return qty vs MTD sales qty (return rate >= 10%).",
            ["Conversion proxy — returns from SLSXNS SlrQty."],
        )

    # ── Register KPI templates (specific patterns first) ─────────────────────
    kpi_specs: List[tuple] = [
        ("ai_insights_not_supported", [r"ai[\s-]?generated\s+business\s+insights", r"business\s+insights\s+and\s+recommendations"], _sql_ai_insights_blocked),
        ("peak_sales_hours_not_supported", [r"peak\s+sales?\s+hours?", r"peak\s+billing\s+time"], _sql_peak_hours_blocked),
        ("store_mtd_sales_customers_ats", [r"store\s+wise\s+mtd\s+sales", r"store\s+wise.*unique\s+customer.*ats"], _sql_store_mtd_kpi),
        ("department_mtd_sales_customers_ats", [r"department\s+wise\s+mtd\s+sales", r"department\s+wise.*ats"], _sql_dept_mtd_kpi),
        ("category_mtd_sales_customers_ats", [r"category\s+wise\s+mtd\s+sales", r"category\s+wise.*ats"], _sql_cat_mtd_kpi),
        ("store_ranking_sales_ats_customers", [r"store\s+ranking.*sales.*ats", r"ranking.*sales.*ats.*customer"], _sql_store_mtd_kpi),
        ("monthly_sales_since_apr_2024", [r"month[\s-]?wise\s+sales?\s+comparison\s+since\s+apr", r"sales?\s+since\s+apr.*24"], _sql_monthly_since_apr_2024),
        ("five_year_sales_dept_category", [r"last\s+5\s+years?\s+sales?\s+analysis", r"5\s+year.*department.*categor"], _sql_five_year_dept_category),
        ("average_sales_mtd_level", [r"average\s+sales?\s+at\s+mtd", r"average\s+sales?\s+mtd\s+level"], _sql_average_sales_mtd),
        ("today_sales_customers_invoices", [r"today(?:'?s)?\s+sales?.*unique\s+customer", r"today(?:'?s)?\s+sales?.*unique\s+invoices?"], _sql_today_sales_customers_invoices),
        ("ytd_growth_vs_last_year", [r"ytd\s+growth\s+vs\s+last\s+year", r"current\s+year\s+ytd\s+growth"], _sql_ytd_growth),
        ("qtd_growth_vs_last_year", [r"qtd\s+growth\s+vs\s+last\s+year", r"current\s+year\s+qtd\s+growth"], _sql_qtd_growth),
        ("mtd_growth_vs_last_year", [r"mtd\s+growth\s+vs\s+last\s+year", r"current\s+year\s+mtd\s+growth"], _sql_mtd_growth),
        ("highest_department_sales_mtd", [r"which\s+department\s+has\s+(?:the\s+)?highest\s+sales?\s+(?:in\s+)?(?:the\s+)?current\s+month", r"highest\s+department.*current\s+month"], _sql_highest_department_mtd),
        ("highest_category_sales_mtd", [r"which\s+categor(?:y|ies)\s+has\s+(?:the\s+)?highest\s+sales?\s+(?:in\s+)?(?:the\s+)?current\s+month", r"highest\s+categor.*current\s+month"], _sql_highest_category_mtd),
        ("highest_store_current_month", [r"which\s+store\s+has\s+(?:the\s+)?highest\s+sales?\s+(?:in\s+)?(?:the\s+)?current\s+month", r"highest\s+sales?\s+(?:in\s+)?(?:the\s+)?current\s+month.*store"], None),
        (
            "most_selling_product_current_month_year",
            [
                r"most\s+selling\s+product",
                r"best\s+selling\s+product.*current\s+month",
                r"top\s+selling\s+product.*(?:month|year)",
            ],
            None,
        ),
        ("least_selling_product_mtd", [r"least\s+selling\s+product", r"lowest\s+selling\s+product"], _sql_least_product_mtd),
        ("lowest_supplier_sales_mtd", [r"which\s+supplier\s+has\s+(?:the\s+)?lowest\s+sales?\s+(?:in\s+)?(?:the\s+)?current\s+month", r"lowest\s+supplier.*sales"], _sql_lowest_supplier_mtd),
        ("top_stores_by_growth_pct", [r"top\s+10\s+performing\s+stores?.*growth", r"top\s+\d+\s+performing\s+stores?.*growth"], _sql_top_stores_growth),
        ("bottom_stores_sales_decline", [r"bottom\s+10\s+performing\s+stores?.*decline", r"bottom\s+\d+\s+stores?.*sales?\s+decline"], _sql_bottom_stores_decline),
        (
            "products_fastest_mom_growth",
            [
                r"products?\s+(?:are\s+)?growing\s+fastest",
                r"fastest\s+month[\s-]?over[\s-]?month",
                r"which\s+products?.*month[\s-]?over[\s-]?month",
            ],
            _sql_products_mom_growth,
        ),
        (
            "categories_negative_growth_trends",
            [
                r"categor(?:y|ies)\s+(?:are\s+)?showing\s+negative\s+growth",
                r"negative\s+growth\s+trends?.*categor",
                r"which\s+categor(?:y|ies).*negative\s+growth",
            ],
            _sql_categories_negative_growth,
        ),
        ("predict_next_month_ai_forecast", [r"predict\s+next\s+month\s+sales?.*ai", r"ai\s+forecasting.*next\s+month"], None),
        (
            "expected_stock_requirement_30_days",
            [
                r"expected\s+stock\s+requirement.*next\s+30",
                r"stock\s+requirement.*(?:for\s+)?next\s+30\s+days",
            ],
            _sql_stock_requirement_30d,
        ),
        ("potential_stockout_prediction", [r"potential\s+stock[\s-]?out", r"stock[\s-]?out\s+prediction"], _sql_stockout_risk),
        ("slow_moving_inventory_identification", [r"slow[\s-]?moving\s+inventory\s+identification", r"identify\s+slow[\s-]?moving"], None),
        ("fast_moving_inventory_identification", [r"fast[\s-]?moving\s+inventory\s+identification", r"identify\s+fast[\s-]?moving"], None),
        ("customer_repeat_purchase_analysis", [r"customer\s+repeat\s+purchase\s+analysis", r"repeat\s+purchase\s+analysis"], None),
        ("festival_vs_non_festival_sales", [r"festival\s+vs\s+non[\s-]?festival", r"festival.*sales?\s+comparison"], _sql_festival_sales),
        ("region_wise_sales_performance", [r"region\s+wise\s+sales?\s+performance", r"sales?\s+by\s+region"], _sql_region_sales),
        ("supplier_contribution_overall", [r"supplier\s+contribution\s+%?\s+in\s+overall", r"supplier\s+contribution\s+percentage"], None),
        ("average_basket_size_by_store", [r"average\s+basket\s+size\s+by\s+store"], None),
        ("average_invoice_value_trend", [r"average\s+invoice\s+value\s+trend"], _sql_invoice_value_trend),
        ("discount_impact_sales", [r"discount\s+impact\s+on\s+sales"], _sql_ai_insights_blocked),
        ("product_recommendation_customer", [r"product\s+recommendation.*customer", r"customer\s+buying\s+pattern"], _sql_ai_insights_blocked),
        ("demand_forecast_store_category", [r"demand\s+forecasting\s+by\s+store", r"ai[\s-]?based\s+demand\s+forecast"], _sql_ai_insights_blocked),
        ("daily_sales_target_achievement", [r"daily\s+sales?\s+target\s+vs\s+achievement", r"target\s+vs\s+achievement"], _sql_ai_insights_blocked),
        ("weather_festival_impact", [r"weather.*impact\s+on\s+sales", r"weather/festival\s+impact"], _sql_festival_sales),
        ("sales_trend_festivals_seasons", [r"sales?\s+trend\s+prediction.*festival", r"upcoming\s+festivals?/seasons"], None),
        ("new_vs_repeat_customer_analysis", [r"new\s+vs\s+repeat\s+customer\s+analysis"], _sql_new_vs_repeat),
        ("category_contribution_percentage", [r"categor(?:y|ies)\s+contribution\s+%", r"category\s+contribution.*revenue"], _sql_category_contribution),
        ("gross_margin_by_category", [r"gross\s+margin\s+analysis\s+by\s+categor", r"gross\s+margin.*department/categor"], _sql_gross_margin_category),
        ("inventory_aging_analysis", [r"inventory\s+aging\s+analysis"], None),
        ("dead_stock_identification", [r"dead\s+stock\s+identification"], None),
        ("product_sell_through_pct", [r"product[\s-]?wise\s+sell\s+through", r"sell\s+through\s+%"], _sql_sell_through),
        ("sales_spike_drop_alert", [r"alerts?\s+for\s+sudden\s+sales?\s+(?:drop|spike)", r"sudden\s+sales?\s+drop\s+or\s+spike"], _sql_sales_spike_alert),
        ("top_customers_purchase_value", [r"top\s+customers?\s+based\s+on\s+purchase"], None),
        ("high_return_low_conversion_products", [r"high\s+return.*low\s+conversion", r"low\s+conversion\s+product"], _sql_high_return_low_sales),
    ]

    # Aliases to existing builders in nlq_faq_sql (import at call time)
    from nlq_faq_sql import (
        _sql_highest_branch_this_month,
        _sql_predict_next_month_sales,
        _sql_fast_vs_slow_moving,
        _sql_repeat_customer_percentage,
        _sql_supplier_contribution_pct_mtd,
        _sql_avg_bill_by_branch,
        _sql_stock_aging_analysis,
        _sql_dead_stock_90_days,
        _sql_top_customers_by_value,
        _sql_top_products_mtd,
    )

    alias_builders = {
        "most_selling_product_current_month_year": _sql_top_products_mtd,
        "highest_store_current_month": _sql_highest_branch_this_month,
        "predict_next_month_ai_forecast": _sql_predict_next_month_sales,
        "slow_moving_inventory_identification": lambda q: _sql_fast_vs_slow_moving(q),
        "fast_moving_inventory_identification": lambda q: _sql_fast_vs_slow_moving(q),
        "customer_repeat_purchase_analysis": _sql_repeat_customer_percentage,
        "supplier_contribution_overall": _sql_supplier_contribution_pct_mtd,
        "average_basket_size_by_store": _sql_avg_bill_by_branch,
        "inventory_aging_analysis": _sql_stock_aging_analysis,
        "dead_stock_identification": _sql_dead_stock_90_days,
        "sales_trend_festivals_seasons": _sql_predict_next_month_sales,
        "top_customers_purchase_value": _sql_top_customers_by_value,
    }

    for tid, patterns, builder in kpi_specs:
        fn = builder or alias_builders.get(tid)
        if fn is None:
            continue
        register(tid, patterns, fn)
