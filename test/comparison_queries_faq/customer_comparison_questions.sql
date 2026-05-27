/*
  Customer Comparison Questions
  Generated: 2026-05-26T21:22:09.382180+00:00
  Blocks: 10
*/

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

