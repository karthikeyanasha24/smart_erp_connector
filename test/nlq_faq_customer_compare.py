"""
Customer comparison FAQ SQL templates (extends nlq_faq_sql).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

CUSTOMER_COMPARE_AI_QUERIES: Tuple[str, ...] = (
    "Compare new vs repeat customer sales",
    "Compare customer groups by revenue",
    "Compare city-wise customer spending",
    "Compare customer retention by branch",
    "Compare high-value vs regular customers",
    "Compare customer purchase frequency",
    "Compare male vs female customer sales",
    "Compare festive season customer trends",
    "Compare loyalty customer contribution",
    "Compare average order value by customer segment",
)


def register_customer_compare_faqs(register: Callable[..., None]) -> None:
    from nlq_faq_sql import (
        _APP,
        _CUST,
        _SALES_AI,
        _SALESPERSON,
        _blob,
        _invoice_mtd_where,
        _mtd_where,
        _sql_sales_by_customer_group,
        _top_n_from_question,
    )

    def _sql_new_vs_repeat_customer_sales(_q: str) -> Dict[str, Any]:
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
),
NewCust AS (
    SELECT COUNT(DISTINCT c.[CustomerId]) AS Cnt
    FROM {_CUST} c WITH (NOLOCK)
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
        FROM {_SALES_AI} s WITH (NOLOCK)
        INNER JOIN {_CUST} c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
        WHERE {_invoice_mtd_where("s")}
          AND c.[CreatedOn] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
          AND c.[CreatedOn] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
    ) AS decimal(18, 2))
"""
        return _blob(
            "compare_new_vs_repeat_customer_sales",
            sql,
            "MTD sales split: repeat vs one-time buyers, plus new customer profiles (CreatedOn MTD).",
            [
                "Repeat = >1 invoice in MTD on VwAISalesData.",
                "New profiles row uses CreatedOn — may overlap repeat/one-time.",
            ],
        )

    def _sql_city_wise_customer_spending(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    COALESCE(NULLIF(LTRIM(RTRIM(c.[City])), N''), N'(Unknown city)') AS City,
    COUNT(DISTINCT c.[CustomerId]) AS UniqueCustomers,
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS MTDSpending,
    CAST(SUM(s.[SaleNetAmount]) / NULLIF(COUNT(DISTINCT c.[CustomerId]), 0) AS decimal(18, 2)) AS AvgSpendPerCustomer
FROM {_SALES_AI} s WITH (NOLOCK)
INNER JOIN {_CUST} c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
WHERE {_invoice_mtd_where("s")}
GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(c.[City])), N''), N'(Unknown city)')
ORDER BY MTDSpending DESC
"""
        return _blob(
            "compare_city_wise_customer_spending",
            sql,
            "MTD customer spending by city from customer master joined to VwAISalesData.",
            ["City from VwAICustomerDetails; revenue = SUM(SaleNetAmount)."],
        )

    def _sql_retention_by_branch(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Bills AS (
    SELECT
        COALESCE(c.[BranchName], sp.[BranchAlias], N'(Unknown branch)') AS Store,
        s.[CustomerId],
        COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount
    FROM {_SALES_AI} s WITH (NOLOCK)
    LEFT JOIN {_CUST} c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
    LEFT JOIN {_SALESPERSON} sp WITH (NOLOCK)
        ON sp.[CustomerId] = s.[CustomerId]
       AND CAST(sp.[CashmemoDt] AS DATE) = CAST(s.[InvoiceDt] AS DATE)
    WHERE {_invoice_mtd_where("s")}
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
"""
        return _blob(
            "compare_customer_retention_by_branch",
            sql,
            "MTD repeat-customer % by store (branch name / alias proxy).",
            [
                "Retention proxy = share of customers with >1 MTD invoice.",
                "Branch from customer BranchName or salesperson BranchAlias.",
            ],
        )

    def _sql_high_value_vs_regular(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH CustRev AS (
    SELECT
        s.[CustomerId],
        SUM(s.[SaleNetAmount]) AS Revenue
    FROM {_SALES_AI} s WITH (NOLOCK)
    WHERE {_invoice_mtd_where("s")}
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
"""
        return _blob(
            "compare_high_value_vs_regular_customers",
            sql,
            "MTD spend split: top revenue quartile vs remaining customers.",
            ["High-value = NTILE(4) = 1 by SUM(SaleNetAmount) in MTD."],
        )

    def _sql_purchase_frequency(_q: str) -> Dict[str, Any]:
        sql = f"""
WITH Cust AS (
    SELECT
        c.[CustomerGroupName],
        s.[CustomerId],
        COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount,
        SUM(s.[SaleNetAmount]) AS Revenue
    FROM {_SALES_AI} s WITH (NOLOCK)
    INNER JOIN {_CUST} c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
    WHERE {_invoice_mtd_where("s")}
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
"""
        return _blob(
            "compare_customer_purchase_frequency",
            sql,
            "Average MTD invoices per customer by customer group (frequency comparison).",
            ["InvoiceCount = DISTINCT InvoiceId per customer in MTD."],
        )

    def _sql_male_vs_female_sales(_q: str) -> Dict[str, Any]:
        sql = f"""
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
FROM {_SALES_AI} s WITH (NOLOCK)
INNER JOIN {_CUST} c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
WHERE {_invoice_mtd_where("s")}
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
"""
        return _blob(
            "compare_male_vs_female_customer_sales",
            sql,
            "MTD sales by gender segment inferred from CustomerTitle (no gender column in catalog).",
            [
                "Weak proxy — many customers have blank or non-standard titles.",
                "Prefer a dedicated Gender field if added to VwAICustomerDetails.",
            ],
        )

    def _sql_festive_customer_trends(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT
    DATEFROMPARTS(YEAR(s.[InvoiceDt]), MONTH(s.[InvoiceDt]), 1) AS MonthStart,
    CASE WHEN MONTH(s.[InvoiceDt]) IN (10, 11) THEN N'Festive (Oct-Nov proxy)'
         ELSE N'Non-festive month' END AS SeasonTag,
    COUNT(DISTINCT s.[CustomerId]) AS UniqueCustomers,
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS TotalRevenue
FROM {_SALES_AI} s WITH (NOLOCK)
WHERE s.[InvoiceDt] >= DATEADD(MONTH, -12, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND s.[InvoiceDt] < DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
  AND s.[CustomerId] IS NOT NULL
GROUP BY
    DATEFROMPARTS(YEAR(s.[InvoiceDt]), MONTH(s.[InvoiceDt]), 1),
    CASE WHEN MONTH(s.[InvoiceDt]) IN (10, 11) THEN N'Festive (Oct-Nov proxy)'
         ELSE N'Non-festive month' END
ORDER BY MonthStart ASC
"""
        return _blob(
            "compare_festive_season_customer_trends",
            sql,
            "Monthly unique customers and revenue with festive season tag (Oct–Nov proxy).",
            ["Last 12 months on InvoiceDt; no festival calendar table."],
        )

    def _sql_loyalty_contribution(_q: str) -> Dict[str, Any]:
        sql = f"""
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
    FROM {_SALES_AI} s WITH (NOLOCK)
    INNER JOIN {_CUST} c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
    WHERE {_invoice_mtd_where("s")}
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
"""
        return _blob(
            "compare_loyalty_customer_contribution",
            sql,
            "MTD revenue: loyalty/VIP/Gold customer groups vs all other customers.",
            ["LIKE match on CustomerGroupName — align codes with your CRM setup."],
        )

    def _sql_aov_by_customer_segment(_q: str) -> Dict[str, Any]:
        sql = f"""
SELECT TOP (500)
    COALESCE(NULLIF(LTRIM(RTRIM(c.[CustomerGroupName])), N''), N'(No group)') AS CustomerSegment,
    COUNT(DISTINCT s.[InvoiceId]) AS InvoiceCount,
    COUNT(DISTINCT s.[CustomerId]) AS UniqueCustomers,
    CAST(SUM(s.[SaleNetAmount]) AS decimal(18, 2)) AS MTDRevenue,
    CAST(
        SUM(s.[SaleNetAmount]) / NULLIF(COUNT(DISTINCT s.[InvoiceId]), 0)
        AS decimal(18, 2)
    ) AS AvgOrderValue
FROM {_SALES_AI} s WITH (NOLOCK)
INNER JOIN {_CUST} c WITH (NOLOCK) ON c.[CustomerId] = s.[CustomerId]
WHERE {_invoice_mtd_where("s")}
GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(c.[CustomerGroupName])), N''), N'(No group)')
ORDER BY AvgOrderValue DESC
"""
        return _blob(
            "compare_aov_by_customer_segment",
            sql,
            "MTD average order value (revenue / distinct invoices) by customer group.",
            ["AOV = SUM(SaleNetAmount) / COUNT(DISTINCT InvoiceId) per segment."],
        )

    specs: List[tuple] = [
        (
            "compare_new_vs_repeat_customer_sales",
            [
                r"compare\s+new\s+vs\.?\s+repeat\s+customer\s+sales?",
                r"new\s+vs\.?\s+repeat\s+customer\s+sales?",
            ],
            _sql_new_vs_repeat_customer_sales,
        ),
        (
            "compare_customer_groups_by_revenue",
            [
                r"compare\s+customer\s+groups?\s+by\s+revenue",
                r"customer\s+groups?\s+by\s+revenue",
            ],
            _sql_sales_by_customer_group,
        ),
        (
            "compare_city_wise_customer_spending",
            [
                r"compare\s+city[\s-]?wise\s+customer\s+spending",
                r"city[\s-]?wise\s+customer\s+spending",
            ],
            _sql_city_wise_customer_spending,
        ),
        (
            "compare_customer_retention_by_branch",
            [
                r"compare\s+customer\s+retention\s+by\s+branch",
                r"customer\s+retention\s+by\s+branch",
            ],
            _sql_retention_by_branch,
        ),
        (
            "compare_high_value_vs_regular_customers",
            [
                r"compare\s+high[\s-]?value\s+vs\.?\s+regular\s+customers?",
                r"high[\s-]?value\s+vs\.?\s+regular\s+customers?",
            ],
            _sql_high_value_vs_regular,
        ),
        (
            "compare_customer_purchase_frequency",
            [
                r"compare\s+customer\s+purchase\s+frequency",
                r"customer\s+purchase\s+frequency",
            ],
            _sql_purchase_frequency,
        ),
        (
            "compare_male_vs_female_customer_sales",
            [
                r"compare\s+male\s+vs\.?\s+female\s+customer\s+sales?",
                r"male\s+vs\.?\s+female\s+customer",
            ],
            _sql_male_vs_female_sales,
        ),
        (
            "compare_festive_season_customer_trends",
            [
                r"compare\s+festive\s+season\s+customer\s+trends?",
                r"festive\s+season\s+customer\s+trends?",
            ],
            _sql_festive_customer_trends,
        ),
        (
            "compare_loyalty_customer_contribution",
            [
                r"compare\s+loyalty\s+customer\s+contribution",
                r"loyalty\s+customer\s+contribution",
            ],
            _sql_loyalty_contribution,
        ),
        (
            "compare_aov_by_customer_segment",
            [
                r"compare\s+average\s+order\s+value\s+by\s+customer\s+segment",
                r"average\s+order\s+value\s+by\s+customer\s+segment",
                r"aov\s+by\s+customer\s+segment",
            ],
            _sql_aov_by_customer_segment,
        ),
    ]

    for tid, patterns, builder in specs:
        register(tid, patterns, builder)
