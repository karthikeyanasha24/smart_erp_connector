# Frequent AI Queries — Live DB Results

Generated: 2026-06-04T15:56:59
MTD window: `2026-06-01` → `2026-06-04`
Sample rows per query below: **10** (0 = table only)

| # | Status | Rows | Template | Question |
|---|--------|-----:|----------|----------|
| 1 | OK | 93 | `store_mtd_sales_customers_ats` | Store Wise MTD Sales, Unique Customer Count, ATS |
| 2 | OK | 9 | `department_mtd_sales_customers_ats` | Department Wise MTD Sales, Unique Customer Count, ATS |
| 3 | OK | 22 | `category_mtd_sales_customers_ats` | Category Wise MTD Sales, Unique Customer Count, ATS |
| 4 | OK | 27 | `monthly_sales_since_apr_2024` | Month-wise Sales Comparison since Apr'24 |
| 5 | OK | 694 | `five_year_sales_dept_category` | Last 5 Years Sales Analysis at Department and Category Level |
| 6 | OK | 1 | `average_sales_mtd_level` | Average Sales at MTD Level |
| 7 | OK | 1 | `today_sales_customers_invoices` | Today's Sales with Unique Customer Count and Unique Invoices Billed |
| 8 | OK | 2 | `ytd_growth_vs_last_year` | Current Year YTD Growth vs Last Year YTD Growth |
| 9 | OK | 2 | `qtd_growth_vs_last_year` | Current Year QTD Growth vs Last Year QTD Growth |
| 10 | OK | 2 | `mtd_growth_vs_last_year` | Current Year MTD Growth vs Last Year MTD Growth |
| 11 | OK | 1 | `highest_store_current_month` | Which Store has the Highest Sales in the Current Month? |
| 12 | OK | 1 | `highest_department_sales_mtd` | Which Department has the Highest Sales in the Current Month? |
| 13 | OK | 1 | `highest_category_sales_mtd` | Which Category has the Highest Sales in the Current Month? |
| 14 | OK | 20 | `most_selling_product_current_month_year` | Most Selling Product in the Current Month or Year |
| 15 | OK | 20 | `least_selling_product_mtd` | Least Selling Product in the Current Month or Year |
| 16 | OK | 1 | `highest_supplier_sales_mtd` | Which Supplier has the Highest Sales in the Current Month? |
| 17 | OK | 1 | `lowest_supplier_sales_mtd` | Which Supplier has the Lowest Sales in the Current Month? |
| 18 | OK | 10 | `top_stores_by_growth_pct` | Top 10 Performing Stores based on Growth % |
| 19 | OK | 10 | `bottom_stores_sales_decline` | Bottom 10 Performing Stores based on Sales Decline |
| 20 | OK | 3 | `products_fastest_mom_growth` | Which Products are Growing Fastest Month-over-Month? |
| 21 | OK | 3 | `categories_negative_growth_trends` | Which Categories are Showing Negative Growth Trends? |
| 22 | OK | 1 | `predict_next_month_sales` | Predict Next Month Sales using AI Forecasting |
| 23 | OK | 3 | `expected_stock_requirement_30_days` | Expected Stock Requirement for Next 30 Days |
| 24 | OK | 1 | `potential_stockout_prediction` | Potential Stock-Out Products Prediction |
| 25 | OK | 100 | `slow_moving_inventory_identification` | Slow-Moving Inventory Identification |
| 26 | OK | 100 | `fast_moving_inventory_identification` | Fast-Moving Inventory Identification |
| 27 | OK | 1 | `customer_repeat_purchase_analysis` | Customer Repeat Purchase Analysis |
| 28 | OK | 24 | `peak_sales_hours_not_supported` | Peak Sales Hours / Peak Billing Time Analysis |
| 29 | OK | 12 | `festival_vs_non_festival_sales` | Festival vs Non-Festival Sales Comparison |
| 30 | OK | 16 | `region_wise_sales_performance` | Region Wise Sales Performance Comparison |
| 31 | OK | 1 | `supplier_contribution_percentage` | Supplier Contribution % in Overall Sales |
| 32 | OK | 93 | `average_basket_size_by_store` | Average Basket Size by Store |
| 33 | OK | 24 | `average_invoice_value_trend` | Average Invoice Value Trend Analysis |
| 34 | OK | 1 | `discount_impact_sales` | Discount Impact on Sales Performance |
| 35 | OK | 93 | `store_ranking_sales_ats_customers` | Store Ranking based on Sales, ATS, and Customer Count |
| 36 | OK | 4,150 | `product_recommendation_customer` | Product Recommendation based on Customer Buying Pattern |
| 37 | OK | 1,697 | `demand_forecast_store_category` | AI-based Demand Forecasting by Store and Category |
| 38 | OK | 4 | `daily_sales_target_achievement` | Daily Sales Target vs Achievement Tracking |
| 39 | OK | 42 | `festival_sales_trend_prediction` | Weather/Festival Impact on Sales Trend |
| 40 | OK | 728 | `high_return_low_conversion_products` | High Return / Low Conversion Product Identification |
| 41 | OK | 1 | `sales_spike_drop_alert` | AI-based Alerts for Sudden Sales Drop or Spike |
| 42 | OK | 20 | `top_customers_purchase_value` | Top Customers based on Purchase Value |
| 43 | OK | 2 | `new_vs_repeat_customer_analysis` | New vs Repeat Customer Analysis |
| 44 | OK | 1 | `category_contribution_percentage` | Category Contribution % in Total Revenue |
| 45 | OK | 1 | `gross_margin_by_category` | Gross Margin Analysis by Department/Category |
| 46 | OK | 4 | `stock_aging_analysis` | Inventory Aging Analysis |
| 47 | OK | 42,802 | `dead_stock_identification` | Dead Stock Identification |
| 48 | OK | 213,892 | `product_sell_through_pct` | Product-wise Sell Through % |
| 49 | OK | 42 | `festival_sales_trend_prediction` | Sales Trend Prediction for Upcoming Festivals/Seasons |
| 50 | OK | 6 | `ai_business_insights_snapshot` | AI-generated Business Insights and Recommendations |

---

## 1. Store Wise MTD Sales, Unique Customer Count, ATS
**Template:** `store_mtd_sales_customers_ats` · **Status:** OK · **Rows:** 93

_First 10 of 93 rows (open AI Query for full export)._

```json
[
  {
    "Store": "MB-OL4",
    "MTDSales": 1421403.0,
    "UniqueInvoices": 572,
    "ATS": 2484.97,
    "UniqueCustomers": 378
  },
  {
    "Store": "MB-OL3",
    "MTDSales": 656626.0,
    "UniqueInvoices": 404,
    "ATS": 1625.31,
    "UniqueCustomers": 203
  },
  {
    "Store": "08-VK",
    "MTDSales": 644003.0,
    "UniqueInvoices": 88,
    "ATS": 7318.22,
    "UniqueCustomers": 71
  },
  {
    "Store": "76-SKT",
    "MTDSales": 624961.0,
    "UniqueInvoices": 75,
    "ATS": 8332.81,
    "UniqueCustomers": 56
  },
  {
    "Store": "03-RG",
    "MTDSales": 615115.0,
    "UniqueInvoices": 73,
    "ATS": 8426.23,
    "UniqueCustomers": 64
  },
  {
    "Store": "52-AMB",
    "MTDSales": 610436.0,
    "UniqueInvoices": 77,
    "ATS": 7927.74,
    "UniqueCustomers": 63
  },
  {
    "Store": "05-DLF",
    "MTDSales": 565672.0,
    "UniqueInvoices": 83,
    "ATS": 6815.33,
    "UniqueCustomers": 65
  },
  {
    "Store": "01-SE",
    "MTDSales": 565445.0,
    "UniqueInvoices": 71,
    "ATS": 7964.01,
    "UniqueCustomers": 55
  },
  {
    "Store": "06-IP",
    "MTDSales": 504929.0,
    "UniqueInvoices": 85,
    "ATS": 5940.34,
    "UniqueCustomers": 74
  },
  {
    "Store": "47-PSN",
    "MTDSales": 499745.0,
    "UniqueInvoices": 70,
    "ATS": 7139.21,
    "UniqueCustomers": 64
  }
]
```

## 2. Department Wise MTD Sales, Unique Customer Count, ATS
**Template:** `department_mtd_sales_customers_ats` · **Status:** OK · **Rows:** 9

```json
[
  {
    "Department": "SP",
    "MTDSales": 8220878.92,
    "UniqueInvoices": 2017,
    "ATS": 4075.8,
    "UniqueCustomers": 1546
  },
  {
    "Department": "SA",
    "MTDSales": 7846352.0,
    "UniqueInvoices": 1348,
    "ATS": 5820.74,
    "UniqueCustomers": 1170
  },
  {
    "Department": "RM",
    "MTDSales": 3733196.0,
    "UniqueInvoices": 1209,
    "ATS": 3087.84,
    "UniqueCustomers": 981
  },
  {
    "Department": "KUR",
    "MTDSales": 2284155.0,
    "UniqueInvoices": 771,
    "ATS": 2962.59,
    "UniqueCustomers": 691
  },
  {
    "Department": "LPC",
    "MTDSales": 442545.0,
    "UniqueInvoices": 41,
    "ATS": 10793.78,
    "UniqueCustomers": 41
  },
  {
    "Department": "JW",
    "MTDSales": 366775.0,
    "UniqueInvoices": 160,
    "ATS": 2292.34,
    "UniqueCustomers": 149
  },
  {
    "Department": "GF",
    "MTDSales": 49199.0,
    "UniqueInvoices": 69,
    "ATS": 713.03,
    "UniqueCustomers": 66
  },
  {
    "Department": "BG",
    "MTDSales": 35046.0,
    "UniqueInvoices": 15,
    "ATS": 2336.4,
    "UniqueCustomers": 15
  },
  {
    "Department": "SHW",
    "MTDSales": 19559.08,
    "UniqueInvoices": 19,
    "ATS": 1029.43,
    "UniqueCustomers": 18
  }
]
```

## 3. Category Wise MTD Sales, Unique Customer Count, ATS
**Template:** `category_mtd_sales_customers_ats` · **Status:** OK · **Rows:** 22

_First 10 of 22 rows (open AI Query for full export)._

```json
[
  {
    "Category": "SKD",
    "MTDSales": 3634220.0,
    "UniqueInvoices": 1194,
    "ATS": 3043.74,
    "UniqueCustomers": 970
  },
  {
    "Category": "SPP",
    "MTDSales": 3347144.0,
    "UniqueInvoices": 1202,
    "ATS": 2784.65,
    "UniqueCustomers": 930
  },
  {
    "Category": "WOV",
    "MTDSales": 3198605.0,
    "UniqueInvoices": 773,
    "ATS": 4137.91,
    "UniqueCustomers": 693
  },
  {
    "Category": "EMB",
    "MTDSales": 2532907.0,
    "UniqueInvoices": 396,
    "ATS": 6396.23,
    "UniqueCustomers": 375
  },
  {
    "Category": "SPE",
    "MTDSales": 2460981.0,
    "UniqueInvoices": 495,
    "ATS": 4971.68,
    "UniqueCustomers": 457
  },
  {
    "Category": "SPC",
    "MTDSales": 2400757.92,
    "UniqueInvoices": 870,
    "ATS": 2759.49,
    "UniqueCustomers": 687
  },
  {
    "Category": "K2P",
    "MTDSales": 1695522.0,
    "UniqueInvoices": 616,
    "ATS": 2752.47,
    "UniqueCustomers": 571
  },
  {
    "Category": "PTD",
    "MTDSales": 1347167.0,
    "UniqueInvoices": 353,
    "ATS": 3816.34,
    "UniqueCustomers": 327
  },
  {
    "Category": "PLN",
    "MTDSales": 767673.0,
    "UniqueInvoices": 191,
    "ATS": 4019.23,
    "UniqueCustomers": 183
  },
  {
    "Category": "CRS",
    "MTDSales": 440608.0,
    "UniqueInvoices": 142,
    "ATS": 3102.87,
    "UniqueCustomers": 129
  }
]
```

## 4. Month-wise Sales Comparison since Apr'24
**Template:** `monthly_sales_since_apr_2024` · **Status:** OK · **Rows:** 27

_First 10 of 27 rows (open AI Query for full export)._

```json
[
  {
    "MonthStart": "2024-04-01",
    "MonthLabel": "April 2024",
    "TotalSales": 138783586.0
  },
  {
    "MonthStart": "2024-05-01",
    "MonthLabel": "May 2024",
    "TotalSales": 218511806.0
  },
  {
    "MonthStart": "2024-06-01",
    "MonthLabel": "June 2024",
    "TotalSales": 155009697.0
  },
  {
    "MonthStart": "2024-07-01",
    "MonthLabel": "July 2024",
    "TotalSales": 342903898.0
  },
  {
    "MonthStart": "2024-08-01",
    "MonthLabel": "August 2024",
    "TotalSales": 224821748.5
  },
  {
    "MonthStart": "2024-09-01",
    "MonthLabel": "September 2024",
    "TotalSales": 555489545.0
  },
  {
    "MonthStart": "2024-10-01",
    "MonthLabel": "October 2024",
    "TotalSales": 348208533.0
  },
  {
    "MonthStart": "2024-11-01",
    "MonthLabel": "November 2024",
    "TotalSales": 344648037.25
  },
  {
    "MonthStart": "2024-12-01",
    "MonthLabel": "December 2024",
    "TotalSales": 340242557.0
  },
  {
    "MonthStart": "2025-01-01",
    "MonthLabel": "January 2025",
    "TotalSales": 369369720.0
  }
]
```

## 5. Last 5 Years Sales Analysis at Department and Category Level
**Template:** `five_year_sales_dept_category` · **Status:** OK · **Rows:** 694

_First 10 of 694 rows (open AI Query for full export)._

```json
[
  {
    "MonthStart": "2021-07-01",
    "Department": "SA",
    "Category": "PLN",
    "TotalSales": 216336.0
  },
  {
    "MonthStart": "2021-07-01",
    "Department": "SA",
    "Category": "EMB",
    "TotalSales": 113928.0
  },
  {
    "MonthStart": "2021-07-01",
    "Department": "SA",
    "Category": "WOV",
    "TotalSales": 78213.0
  },
  {
    "MonthStart": "2021-07-01",
    "Department": "SP",
    "Category": "SPP",
    "TotalSales": 2980.0
  },
  {
    "MonthStart": "2021-07-01",
    "Department": "JW",
    "Category": "JWL",
    "TotalSales": 720.0
  },
  {
    "MonthStart": "2021-08-01",
    "Department": "SA",
    "Category": "WOV",
    "TotalSales": 139410.0
  },
  {
    "MonthStart": "2021-08-01",
    "Department": "SA",
    "Category": "PLN",
    "TotalSales": 129360.0
  },
  {
    "MonthStart": "2021-08-01",
    "Department": "SA",
    "Category": "EMB",
    "TotalSales": 69690.0
  },
  {
    "MonthStart": "2021-08-01",
    "Department": "LPC",
    "Category": "LAA",
    "TotalSales": 62713.0
  },
  {
    "MonthStart": "2021-08-01",
    "Department": "RM",
    "Category": "SKD",
    "TotalSales": 48589.0
  }
]
```

## 6. Average Sales at MTD Level
**Template:** `average_sales_mtd_level` · **Status:** OK · **Rows:** 1

```json
[
  {
    "MTDTotalSales": 5000.0,
    "TradingDays": 1,
    "AvgDailySales": 5000.0
  }
]
```

## 7. Today's Sales with Unique Customer Count and Unique Invoices Billed
**Template:** `today_sales_customers_invoices` · **Status:** OK · **Rows:** 1

```json
[
  {
    "TodaySales": 2896229.0,
    "UniqueInvoices": 573,
    "UniqueCustomers": 456
  }
]
```

## 8. Current Year YTD Growth vs Last Year YTD Growth
**Template:** `ytd_growth_vs_last_year` · **Status:** OK · **Rows:** 2

```json
[
  {
    "PeriodLabel": "CurrentYTD",
    "TotalSales": 2669368633.01
  },
  {
    "PeriodLabel": "LastYearYTD",
    "TotalSales": 2597112396.0
  }
]
```

## 9. Current Year QTD Growth vs Last Year QTD Growth
**Template:** `qtd_growth_vs_last_year` · **Status:** OK · **Rows:** 2

```json
[
  {
    "PeriodLabel": "CurrentQTD",
    "TotalSales": 638420931.02
  },
  {
    "PeriodLabel": "LastYearQTD",
    "TotalSales": 443441549.0
  }
]
```

## 10. Current Year MTD Growth vs Last Year MTD Growth
**Template:** `mtd_growth_vs_last_year` · **Status:** OK · **Rows:** 2

```json
[
  {
    "PeriodLabel": "CurrentMTD",
    "TotalSales": 23001701.0
  },
  {
    "PeriodLabel": "LastYearMTD",
    "TotalSales": 20184376.0
  }
]
```

## 11. Which Store has the Highest Sales in the Current Month?
**Template:** `highest_store_current_month` · **Status:** OK · **Rows:** 1

```json
[
  {
    "BranchAlias": "MB-OL4",
    "TotalSales": 1421403.0
  }
]
```

## 12. Which Department has the Highest Sales in the Current Month?
**Template:** `highest_department_sales_mtd` · **Status:** OK · **Rows:** 1

```json
[
  {
    "Department": "SP",
    "MTDSales": 8220878.92
  }
]
```

## 13. Which Category has the Highest Sales in the Current Month?
**Template:** `highest_category_sales_mtd` · **Status:** OK · **Rows:** 1

```json
[
  {
    "Category": "SKD",
    "MTDSales": 3634220.0
  }
]
```

## 14. Most Selling Product in the Current Month or Year
**Template:** `most_selling_product_current_month_year` · **Status:** OK · **Rows:** 20

_First 10 of 20 rows (open AI Query for full export)._

```json
[
  {
    "Itemcode": "26HQ2170547",
    "ArticleNo": "SS26-B-03-M-7190A-GGT-EMB",
    "Category": "EMB",
    "Revenue": 35000.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "26HQ5499838",
    "ArticleNo": "BS26-D-02-34832-HLM-EMB",
    "Category": "EMB",
    "Revenue": 32498.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "26HQ5768836",
    "ArticleNo": "SS26-B-03-M-7380-GGT-EMB",
    "Category": "EMB",
    "Revenue": 30000.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "25HQ5556342",
    "ArticleNo": "AW25-B-48-D0002-HLM-LPS",
    "Category": "LPS",
    "Revenue": 25000.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "26HQ3169538",
    "ArticleNo": "SS26-E-14-BS3-MEENA-WOV-HLM-KANJ",
    "Category": "WOV",
    "Revenue": 25000.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "26HQ2161839",
    "ArticleNo": "SS26-B-36-10229-A-ORG-PTD",
    "Category": "PTD",
    "Revenue": 24995.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "26HQ5792151",
    "ArticleNo": "SS26-A-57-NR378-KF126-CRP-DRS",
    "Category": "DRS",
    "Revenue": 24995.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "26HQ2171520",
    "ArticleNo": "SS26-B-04-MMM-100-LYC-EMB",
    "Category": "EMB",
    "Revenue": 22500.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "26HQ5759823",
    "ArticleNo": "SS26-B-03-M-7134-GGT-EMB",
    "Category": "EMB",
    "Revenue": 22500.0,
    "QtySold": 1.0
  },
  {
    "Itemcode": "26HQ5837814",
    "ArticleNo": "SS26-A-39-1306-TISU-SKD",
    "Category": "SKD",
    "Revenue": 22000.0,
    "QtySold": 1.0
  }
]
```

## 15. Least Selling Product in the Current Month or Year
**Template:** `least_selling_product_mtd` · **Status:** OK · **Rows:** 20

_First 10 of 20 rows (open AI Query for full export)._

```json
[
  {
    "Itemcode": "24HQ4389578",
    "ArticleNo": "F-09-RING66G312-AJW",
    "MTDSales": 10.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "20HQ1171871",
    "ArticleNo": "DUPATTA CHIFFON DYED FANCY",
    "MTDSales": 10.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "25HQ1281142",
    "ArticleNo": "SS25-F-09-ERG84GJ059-AJW",
    "MTDSales": 20.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "26HQ5283131",
    "ArticleNo": "BS26-F-09-GJ6601495-AJW",
    "MTDSales": 25.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "23HQ1455727",
    "ArticleNo": "D-05-RING99-AJW",
    "MTDSales": 30.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "26HQ5285461",
    "ArticleNo": "BS26-F-09-GJETC366-AJW",
    "MTDSales": 30.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "26HQ5765097",
    "ArticleNo": "SS26-D-05-BRC-AST01-AJW",
    "MTDSales": 30.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "23HQ1349300",
    "ArticleNo": "F-09-RING69G7887-AJW",
    "MTDSales": 35.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "26HQ5312350",
    "ArticleNo": "BS26-D-05-ERG1498-AJW",
    "MTDSales": 35.0,
    "MTDQty": 1.0
  },
  {
    "Itemcode": "25HQ4318998",
    "ArticleNo": "SS25-A-51-NGPLE3266-AJW",
    "MTDSales": 45.0,
    "MTDQty": 1.0
  }
]
```

## 16. Which Supplier has the Highest Sales in the Current Month?
**Template:** `highest_supplier_sales_mtd` · **Status:** OK · **Rows:** 1

```json
[
  {
    "SupplierName": "SAHIB TEXTILES PVT LTD. (HARYANA)",
    "SupplierAlias": "DEL-SHB",
    "Revenue": 5000.0
  }
]
```

## 17. Which Supplier has the Lowest Sales in the Current Month?
**Template:** `lowest_supplier_sales_mtd` · **Status:** OK · **Rows:** 1

```json
[
  {
    "SupplierName": "SAHIB TEXTILES PVT LTD. (HARYANA)",
    "MTDSales": 5000.0
  }
]
```

## 18. Top 10 Performing Stores based on Growth %
**Template:** `top_stores_by_growth_pct` · **Status:** OK · **Rows:** 10

```json
[
  {
    "Store": "MB-OL4",
    "MTDSales": 1428716.0,
    "PriorPeriodSales": 433328.0,
    "GrowthPct": 229.7078
  },
  {
    "Store": "HQ3-BLR",
    "MTDSales": 9615.0,
    "PriorPeriodSales": 4796.0,
    "GrowthPct": 100.4796
  },
  {
    "Store": "68-BHT",
    "MTDSales": 141388.0,
    "PriorPeriodSales": 228270.0,
    "GrowthPct": -38.0611
  },
  {
    "Store": "70-HDR",
    "MTDSales": 266523.0,
    "PriorPeriodSales": 437887.0,
    "GrowthPct": -39.1343
  },
  {
    "Store": "71-AML",
    "MTDSales": 110743.0,
    "PriorPeriodSales": 184410.0,
    "GrowthPct": -39.9474
  },
  {
    "Store": "69-KUR",
    "MTDSales": 197226.0,
    "PriorPeriodSales": 333701.0,
    "GrowthPct": -40.8974
  },
  {
    "Store": "US-04",
    "MTDSales": 456.0,
    "PriorPeriodSales": 802.0,
    "GrowthPct": -43.1421
  },
  {
    "Store": "52-AMB",
    "MTDSales": 610436.0,
    "PriorPeriodSales": 1078520.0,
    "GrowthPct": -43.4006
  },
  {
    "Store": "86-RNC",
    "MTDSales": 140750.0,
    "PriorPeriodSales": 256232.0,
    "GrowthPct": -45.0693
  },
  {
    "Store": "47-PSN",
    "MTDSales": 499745.0,
    "PriorPeriodSales": 917694.0,
    "GrowthPct": -45.5434
  }
]
```

## 19. Bottom 10 Performing Stores based on Sales Decline
**Template:** `bottom_stores_sales_decline` · **Status:** OK · **Rows:** 10

```json
[
  {
    "Store": "08-VK",
    "MTDSales": 648003.0,
    "PriorPeriodSales": 2194939.0,
    "SalesDecline": -1546936.0,
    "DeclinePct": -70.4774
  },
  {
    "Store": "01-SE",
    "MTDSales": 565445.0,
    "PriorPeriodSales": 2067376.0,
    "SalesDecline": -1501931.0,
    "DeclinePct": -72.6491
  },
  {
    "Store": "11-RP",
    "MTDSales": 448568.0,
    "PriorPeriodSales": 1801367.0,
    "SalesDecline": -1352799.0,
    "DeclinePct": -75.0985
  },
  {
    "Store": "39-LJP",
    "MTDSales": 412082.0,
    "PriorPeriodSales": 1688298.0,
    "SalesDecline": -1276216.0,
    "DeclinePct": -75.5919
  },
  {
    "Store": "05-DLF",
    "MTDSales": 565672.0,
    "PriorPeriodSales": 1708804.0,
    "SalesDecline": -1143132.0,
    "DeclinePct": -66.8966
  },
  {
    "Store": "03-RG",
    "MTDSales": 615115.0,
    "PriorPeriodSales": 1706421.0,
    "SalesDecline": -1091306.0,
    "DeclinePct": -63.9529
  },
  {
    "Store": "23-KPV",
    "MTDSales": 407283.0,
    "PriorPeriodSales": 1443909.0,
    "SalesDecline": -1036626.0,
    "DeclinePct": -71.793
  },
  {
    "Store": "MB-OL3",
    "MTDSales": 656626.0,
    "PriorPeriodSales": 1562831.61,
    "SalesDecline": -906205.61,
    "DeclinePct": -57.9849
  },
  {
    "Store": "06-IP",
    "MTDSales": 504929.0,
    "PriorPeriodSales": 1376676.0,
    "SalesDecline": -871747.0,
    "DeclinePct": -63.3226
  },
  {
    "Store": "12-PTN",
    "MTDSales": 249951.0,
    "PriorPeriodSales": 1082348.0,
    "SalesDecline": -832397.0,
    "DeclinePct": -76.9066
  }
]
```

## 20. Which Products are Growing Fastest Month-over-Month?
**Template:** `products_fastest_mom_growth` · **Status:** OK · **Rows:** 3

```json
[
  {
    "Itemcode": "DESIRE 50ML",
    "LatestMonth": "2026-03-01",
    "LatestRevenue": 11988.0,
    "PriorMonthRevenue": 1998.0,
    "MoMGrowthPct": 500.0
  },
  {
    "Itemcode": "JANNAT 30ML",
    "LatestMonth": "2026-03-01",
    "LatestRevenue": 1398.0,
    "PriorMonthRevenue": 699.0,
    "MoMGrowthPct": 100.0
  },
  {
    "Itemcode": "AGNI 50ML",
    "LatestMonth": "2026-03-01",
    "LatestRevenue": 50400.0,
    "PriorMonthRevenue": 44400.0,
    "MoMGrowthPct": 13.5135
  }
]
```

## 21. Which Categories are Showing Negative Growth Trends?
**Template:** `categories_negative_growth_trends` · **Status:** OK · **Rows:** 3

```json
[
  {
    "Category": "SKD",
    "LatestMonth": "2026-05-01",
    "LatestRevenue": 7000.0,
    "PriorMonthRevenue": 11293357.0,
    "MoMGrowthPct": -99.938
  },
  {
    "Category": "DUP",
    "LatestMonth": "2026-04-01",
    "LatestRevenue": 1998.0,
    "PriorMonthRevenue": 17982.0,
    "MoMGrowthPct": -88.8889
  },
  {
    "Category": "JWL",
    "LatestMonth": "2026-03-01",
    "LatestRevenue": 1359205.0,
    "PriorMonthRevenue": 1678700.0,
    "MoMGrowthPct": -19.0323
  }
]
```

## 22. Predict Next Month Sales using AI Forecasting
**Template:** `predict_next_month_sales` · **Status:** OK · **Rows:** 1

```json
[
  {
    "ForecastMonthStart": "2026-07-01",
    "ForecastRevenue": 27676424.0,
    "ForecastMethod": "Average of last 3 complete months on APP_REPORT"
  }
]
```

## 23. Expected Stock Requirement for Next 30 Days
**Template:** `expected_stock_requirement_30_days` · **Status:** OK · **Rows:** 3

```json
[
  {
    "Itemcode": "26HQ5756792",
    "AvgDailyQtySold": 0.0333,
    "ExpectedQtyNext30Days": 1.0
  },
  {
    "Itemcode": "26HQ5757037",
    "AvgDailyQtySold": 0.0333,
    "ExpectedQtyNext30Days": 1.0
  },
  {
    "Itemcode": "26HQ5805316",
    "AvgDailyQtySold": 0.0333,
    "ExpectedQtyNext30Days": 1.0
  }
]
```

## 24. Potential Stock-Out Products Prediction
**Template:** `potential_stockout_prediction` · **Status:** OK · **Rows:** 1

```json
[
  {
    "Itemcode": "26HQ5805316",
    "OnHandQty": 0.0,
    "AvgDailyQty": 0.0714,
    "QtyNeeded7Days": 0.5
  }
]
```

## 25. Slow-Moving Inventory Identification
**Template:** `slow_moving_inventory_identification` · **Status:** OK · **Rows:** 100

_First 10 of 100 rows (open AI Query for full export)._

```json
[
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5765876",
    "ArticleNo": "SS26-D-08-AST-149-MUS-K2P",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5745433",
    "ArticleNo": "SS26-D-14-8710-LIN-SPP",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26034203716",
    "ArticleNo": "SS26-G-06-3507-AHL-SPC",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5843899",
    "ArticleNo": "SS26-D-02-AST100-COT-SPP",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5711939",
    "ArticleNo": "SS26-D-02-RSHR-30003-LIN-SPP",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5793144",
    "ArticleNo": "SS26-A-60-21866-COT-SPC",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "24HQ1445878",
    "ArticleNo": "DUPATTA CHIFFON DYED FANCY",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5835607",
    "ArticleNo": "SS26-D-08-600066-COT-K2P",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5828588",
    "ArticleNo": "SS26-D-08-260081-COT-SKD",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26034206249",
    "ArticleNo": "SS26-J-120-BP-ZD-1004-LIN-SPP",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  }
]
```

## 26. Fast-Moving Inventory Identification
**Template:** `fast_moving_inventory_identification` · **Status:** OK · **Rows:** 100

_First 10 of 100 rows (open AI Query for full export)._

```json
[
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5827235",
    "ArticleNo": "SS26-C-15-S-033-9A-WOV-COT-WOVN",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5828588",
    "ArticleNo": "SS26-D-08-260081-COT-SKD",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5835607",
    "ArticleNo": "SS26-D-08-600066-COT-K2P",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26034206249",
    "ArticleNo": "SS26-J-120-BP-ZD-1004-LIN-SPP",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5793144",
    "ArticleNo": "SS26-A-60-21866-COT-SPC",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5843899",
    "ArticleNo": "SS26-D-02-AST100-COT-SPP",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5711939",
    "ArticleNo": "SS26-D-02-RSHR-30003-LIN-SPP",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26034203716",
    "ArticleNo": "SS26-G-06-3507-AHL-SPC",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ5745433",
    "ArticleNo": "SS26-D-14-8710-LIN-SPP",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  },
  {
    "MovementClass": "FastMoving",
    "Itemcode": "26HQ3179203",
    "ArticleNo": "SS26-E-07-BROCKET-MIX-AHL-KANJ",
    "OnHandQty": 1.0,
    "MTDQtySold": 0.0,
    "TurnoverRatio": 0.0
  }
]
```

## 27. Customer Repeat Purchase Analysis
**Template:** `customer_repeat_purchase_analysis` · **Status:** OK · **Rows:** 1

```json
[
  {
    "CustomersWithSales": 3323,
    "RepeatCustomers": 554,
    "RepeatCustomerPct": 16.6717
  }
]
```

## 28. Peak Sales Hours / Peak Billing Time Analysis
**Template:** `peak_sales_hours_not_supported` · **Status:** OK · **Rows:** 24

_First 10 of 24 rows (open AI Query for full export)._

```json
[
  {
    "SaleHour": 19,
    "MTDSales": 2824638.0,
    "Bills": 478
  },
  {
    "SaleHour": 18,
    "MTDSales": 2652116.0,
    "Bills": 509
  },
  {
    "SaleHour": 16,
    "MTDSales": 2624680.0,
    "Bills": 493
  },
  {
    "SaleHour": 17,
    "MTDSales": 2355029.0,
    "Bills": 469
  },
  {
    "SaleHour": 15,
    "MTDSales": 2226342.0,
    "Bills": 489
  },
  {
    "SaleHour": 14,
    "MTDSales": 1954687.0,
    "Bills": 399
  },
  {
    "SaleHour": 13,
    "MTDSales": 1886929.0,
    "Bills": 355
  },
  {
    "SaleHour": 20,
    "MTDSales": 1730160.0,
    "Bills": 338
  },
  {
    "SaleHour": 0,
    "MTDSales": 1681294.0,
    "Bills": 270
  },
  {
    "SaleHour": 21,
    "MTDSales": 1154119.0,
    "Bills": 171
  }
]
```

## 29. Festival vs Non-Festival Sales Comparison
**Template:** `festival_vs_non_festival_sales` · **Status:** OK · **Rows:** 12

_First 10 of 12 rows (open AI Query for full export)._

```json
[
  {
    "CalendarMonth": 1,
    "SeasonTag": "Non-festive / regular",
    "AvgMonthlyRevenue": 4766257.0
  },
  {
    "CalendarMonth": 2,
    "SeasonTag": "Non-festive / regular",
    "AvgMonthlyRevenue": 124810644.5
  },
  {
    "CalendarMonth": 3,
    "SeasonTag": "Summer",
    "AvgMonthlyRevenue": 184554571.0
  },
  {
    "CalendarMonth": 4,
    "SeasonTag": "Summer",
    "AvgMonthlyRevenue": 9002099.0
  },
  {
    "CalendarMonth": 5,
    "SeasonTag": "Summer",
    "AvgMonthlyRevenue": 2639884.0
  },
  {
    "CalendarMonth": 6,
    "SeasonTag": "Non-festive / regular",
    "AvgMonthlyRevenue": 2553572.0
  },
  {
    "CalendarMonth": 7,
    "SeasonTag": "Non-festive / regular",
    "AvgMonthlyRevenue": 3973173.0
  },
  {
    "CalendarMonth": 8,
    "SeasonTag": "Non-festive / regular",
    "AvgMonthlyRevenue": 19964789.0
  },
  {
    "CalendarMonth": 9,
    "SeasonTag": "Non-festive / regular",
    "AvgMonthlyRevenue": 57858919.0
  },
  {
    "CalendarMonth": 10,
    "SeasonTag": "Festive (Oct-Nov proxy)",
    "AvgMonthlyRevenue": 4500202.0
  }
]
```

## 30. Region Wise Sales Performance Comparison
**Template:** `region_wise_sales_performance` · **Status:** OK · **Rows:** 16

_First 10 of 16 rows (open AI Query for full export)._

```json
[
  {
    "Region": "ND",
    "MTDSales": 3710389.0,
    "Bills": 600
  },
  {
    "Region": "SD",
    "MTDSales": 2839559.0,
    "Bills": 381
  },
  {
    "Region": "NO",
    "MTDSales": 2827015.0,
    "Bills": 464
  },
  {
    "Region": "MP",
    "MTDSales": 2313283.0,
    "Bills": 371
  },
  {
    "Region": "UK",
    "MTDSales": 1805003.0,
    "Bills": 305
  },
  {
    "Region": "GGN",
    "MTDSales": 1772258.0,
    "Bills": 263
  },
  {
    "Region": "UP",
    "MTDSales": 1461861.0,
    "Bills": 251
  },
  {
    "Region": "JPR",
    "MTDSales": 1428716.0,
    "Bills": 573
  },
  {
    "Region": "PNJ",
    "MTDSales": 1231981.0,
    "Bills": 237
  },
  {
    "Region": "BHR",
    "MTDSales": 1131738.0,
    "Bills": 189
  }
]
```

## 31. Supplier Contribution % in Overall Sales
**Template:** `supplier_contribution_percentage` · **Status:** OK · **Rows:** 1

```json
[
  {
    "SupplierName": "SAHIB TEXTILES PVT LTD. (HARYANA)",
    "Revenue": 5000.0,
    "ContributionPct": 100.0
  }
]
```

## 32. Average Basket Size by Store
**Template:** `average_basket_size_by_store` · **Status:** OK · **Rows:** 93

_First 10 of 93 rows (open AI Query for full export)._

```json
[
  {
    "BranchAlias": "MB-OL1",
    "TotalSales": 68471.0,
    "BillCount": 6,
    "AvgBillValue": 11411.83
  },
  {
    "BranchAlias": "75-BB4",
    "TotalSales": 112947.0,
    "BillCount": 11,
    "AvgBillValue": 10267.91
  },
  {
    "BranchAlias": "53-SE1",
    "TotalSales": 261615.0,
    "BillCount": 26,
    "AvgBillValue": 10062.12
  },
  {
    "BranchAlias": "70-HDR",
    "TotalSales": 266523.0,
    "BillCount": 31,
    "AvgBillValue": 8597.52
  },
  {
    "BranchAlias": "29-BSP",
    "TotalSales": 282969.0,
    "BillCount": 33,
    "AvgBillValue": 8574.82
  },
  {
    "BranchAlias": "91-LK4",
    "TotalSales": 273442.0,
    "BillCount": 32,
    "AvgBillValue": 8545.06
  },
  {
    "BranchAlias": "03-RG",
    "TotalSales": 615115.0,
    "BillCount": 73,
    "AvgBillValue": 8426.23
  },
  {
    "BranchAlias": "76-SKT",
    "TotalSales": 624961.0,
    "BillCount": 75,
    "AvgBillValue": 8332.81
  },
  {
    "BranchAlias": "01-SE",
    "TotalSales": 565445.0,
    "BillCount": 71,
    "AvgBillValue": 7964.01
  },
  {
    "BranchAlias": "31-BL1",
    "TotalSales": 134895.0,
    "BillCount": 17,
    "AvgBillValue": 7935.0
  }
]
```

## 33. Average Invoice Value Trend Analysis
**Template:** `average_invoice_value_trend` · **Status:** OK · **Rows:** 24

_First 10 of 24 rows (open AI Query for full export)._

```json
[
  {
    "MonthStart": "2024-06-01",
    "AvgInvoiceValue": 86972.71,
    "InvoiceCount": 7
  },
  {
    "MonthStart": "2024-07-01",
    "AvgInvoiceValue": 138748.36,
    "InvoiceCount": 14
  },
  {
    "MonthStart": "2024-08-01",
    "AvgInvoiceValue": 94998.25,
    "InvoiceCount": 8
  },
  {
    "MonthStart": "2024-09-01",
    "AvgInvoiceValue": 11887.03,
    "InvoiceCount": 2281
  },
  {
    "MonthStart": "2024-10-01",
    "AvgInvoiceValue": 139203.45,
    "InvoiceCount": 11
  },
  {
    "MonthStart": "2024-11-01",
    "AvgInvoiceValue": 40314.89,
    "InvoiceCount": 38
  },
  {
    "MonthStart": "2024-12-01",
    "AvgInvoiceValue": 48555.4,
    "InvoiceCount": 30
  },
  {
    "MonthStart": "2025-01-01",
    "AvgInvoiceValue": 175769.75,
    "InvoiceCount": 4
  },
  {
    "MonthStart": "2025-02-01",
    "AvgInvoiceValue": 12684.3,
    "InvoiceCount": 2991
  },
  {
    "MonthStart": "2025-03-01",
    "AvgInvoiceValue": 10793.21,
    "InvoiceCount": 6780
  }
]
```

## 34. Discount Impact on Sales Performance
**Template:** `discount_impact_sales` · **Status:** OK · **Rows:** 1

```json
[
  {
    "Category": "K2P",
    "TotalMRP": 6995.0,
    "NetSales": 5000.0,
    "ImpliedDiscountValue": 1995.0,
    "ImpliedDiscountPct": 28.5204
  }
]
```

## 35. Store Ranking based on Sales, ATS, and Customer Count
**Template:** `store_ranking_sales_ats_customers` · **Status:** OK · **Rows:** 93

_First 10 of 93 rows (open AI Query for full export)._

```json
[
  {
    "Store": "MB-OL4",
    "MTDSales": 1428716.0,
    "UniqueInvoices": 573,
    "ATS": 2493.4,
    "UniqueCustomers": 378
  },
  {
    "Store": "MB-OL3",
    "MTDSales": 656626.0,
    "UniqueInvoices": 404,
    "ATS": 1625.31,
    "UniqueCustomers": 203
  },
  {
    "Store": "08-VK",
    "MTDSales": 648003.0,
    "UniqueInvoices": 89,
    "ATS": 7280.93,
    "UniqueCustomers": 72
  },
  {
    "Store": "76-SKT",
    "MTDSales": 624961.0,
    "UniqueInvoices": 75,
    "ATS": 8332.81,
    "UniqueCustomers": 56
  },
  {
    "Store": "03-RG",
    "MTDSales": 615115.0,
    "UniqueInvoices": 73,
    "ATS": 8426.23,
    "UniqueCustomers": 64
  },
  {
    "Store": "52-AMB",
    "MTDSales": 610436.0,
    "UniqueInvoices": 77,
    "ATS": 7927.74,
    "UniqueCustomers": 63
  },
  {
    "Store": "05-DLF",
    "MTDSales": 565672.0,
    "UniqueInvoices": 83,
    "ATS": 6815.33,
    "UniqueCustomers": 65
  },
  {
    "Store": "01-SE",
    "MTDSales": 565445.0,
    "UniqueInvoices": 71,
    "ATS": 7964.01,
    "UniqueCustomers": 55
  },
  {
    "Store": "06-IP",
    "MTDSales": 504929.0,
    "UniqueInvoices": 85,
    "ATS": 5940.34,
    "UniqueCustomers": 74
  },
  {
    "Store": "47-PSN",
    "MTDSales": 499745.0,
    "UniqueInvoices": 70,
    "ATS": 7139.21,
    "UniqueCustomers": 64
  }
]
```

## 36. Product Recommendation based on Customer Buying Pattern
**Template:** `product_recommendation_customer` · **Status:** OK · **Rows:** 4,150

_First 10 of 4,150 rows (open AI Query for full export)._

```json
[
  {
    "Itemcode": "JANNAT 30ML",
    "ArticleNo": "JANNAT 30ML",
    "Category": "PRF",
    "RepeatBuyerCount": 14,
    "RevenueFromRepeatBuyers": 7150.0
  },
  {
    "Itemcode": "FEARLESS 50ML",
    "ArticleNo": "FEARLESS 50ML",
    "Category": "PRF",
    "RepeatBuyerCount": 8,
    "RevenueFromRepeatBuyers": 6400.0
  },
  {
    "Itemcode": "AGNI 50ML",
    "ArticleNo": "AGNI 50ML",
    "Category": "PRF",
    "RepeatBuyerCount": 6,
    "RevenueFromRepeatBuyers": 2800.0
  },
  {
    "Itemcode": "DESIRE 50ML",
    "ArticleNo": "DESIRE 50ML",
    "Category": "PRF",
    "RepeatBuyerCount": 3,
    "RevenueFromRepeatBuyers": 2400.0
  },
  {
    "Itemcode": "26HQ5826420",
    "ArticleNo": "SS26-G-13-5088-WOV-ATS-WOVN",
    "Category": "WOV",
    "RepeatBuyerCount": 2,
    "RevenueFromRepeatBuyers": 3000.0
  },
  {
    "Itemcode": "26HQ5768642",
    "ArticleNo": "SS26-D-08-AST-99-MUS-K2P",
    "Category": "K2P",
    "RepeatBuyerCount": 2,
    "RevenueFromRepeatBuyers": 2000.0
  },
  {
    "Itemcode": "26OL4107496",
    "ArticleNo": "SS26-D-02-OL4-RSMP-15247-CHD-SPP",
    "Category": "SPP",
    "RepeatBuyerCount": 2,
    "RevenueFromRepeatBuyers": 61.0
  },
  {
    "Itemcode": "26HQ5250507",
    "ArticleNo": "BS26-J-06-5130-CHD-SPP",
    "Category": "SPP",
    "RepeatBuyerCount": 2,
    "RevenueFromRepeatBuyers": 0.0
  },
  {
    "Itemcode": "26HQ5509162",
    "ArticleNo": "CD26-J-18-SPECIAL-202F-AGT-EMB",
    "Category": "EMB",
    "RepeatBuyerCount": 2,
    "RevenueFromRepeatBuyers": -190.0
  },
  {
    "Itemcode": "26HQ2170547",
    "ArticleNo": "SS26-B-03-M-7190A-GGT-EMB",
    "Category": "EMB",
    "RepeatBuyerCount": 1,
    "RevenueFromRepeatBuyers": 35000.0
  }
]
```

## 37. AI-based Demand Forecasting by Store and Category
**Template:** `demand_forecast_store_category` · **Status:** OK · **Rows:** 1,697

_First 10 of 1,697 rows (open AI Query for full export)._

```json
[
  {
    "Store": "MB-OL3",
    "Category": "SPC",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 4951522.99,
    "ForecastNextMonthRevenue": 4951522.99
  },
  {
    "Store": "MB-OL3",
    "Category": "SPP",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 4865809.68,
    "ForecastNextMonthRevenue": 4865809.68
  },
  {
    "Store": "05-DLF",
    "Category": "WOV",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 3195393.67,
    "ForecastNextMonthRevenue": 3195393.67
  },
  {
    "Store": "01-SE",
    "Category": "WOV",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 3042360.0,
    "ForecastNextMonthRevenue": 3042360.0
  },
  {
    "Store": "08-VK",
    "Category": "WOV",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 2907773.33,
    "ForecastNextMonthRevenue": 2907773.33
  },
  {
    "Store": "08-VK",
    "Category": "SPP",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 2806724.0,
    "ForecastNextMonthRevenue": 2806724.0
  },
  {
    "Store": "MB-OL3",
    "Category": "SKD",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 2727867.03,
    "ForecastNextMonthRevenue": 2727867.03
  },
  {
    "Store": "03-RG",
    "Category": "SPP",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 2627108.33,
    "ForecastNextMonthRevenue": 2627108.33
  },
  {
    "Store": "06-IP",
    "Category": "WOV",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 2515207.33,
    "ForecastNextMonthRevenue": 2515207.33
  },
  {
    "Store": "08-VK",
    "Category": "SPE",
    "MonthsInAverage": 3,
    "AvgMonthlyRevenueLast3Mo": 2431477.0,
    "ForecastNextMonthRevenue": 2431477.0
  }
]
```

## 38. Daily Sales Target vs Achievement Tracking
**Template:** `daily_sales_target_achievement` · **Status:** OK · **Rows:** 4

```json
[
  {
    "SaleDate": "2026-06-01",
    "DaySales": 6436147.0,
    "DailyBenchmarkTarget": 5760003.5,
    "AchievementPct": 111.7386
  },
  {
    "SaleDate": "2026-06-02",
    "DaySales": 6406059.0,
    "DailyBenchmarkTarget": 5760003.5,
    "AchievementPct": 111.2162
  },
  {
    "SaleDate": "2026-06-03",
    "DaySales": 7263266.0,
    "DailyBenchmarkTarget": 5760003.5,
    "AchievementPct": 126.0983
  },
  {
    "SaleDate": "2026-06-04",
    "DaySales": 2934542.0,
    "DailyBenchmarkTarget": 5760003.5,
    "AchievementPct": 50.9469
  }
]
```

## 39. Weather/Festival Impact on Sales Trend
**Template:** `festival_sales_trend_prediction` · **Status:** OK · **Rows:** 42

_First 10 of 42 rows (open AI Query for full export)._

```json
[
  {
    "MonthStart": "2023-01-01",
    "TotalSales": 1647142.0,
    "BillCount": 10,
    "SalesRank": 18,
    "PctOfAvg": 15.7
  },
  {
    "MonthStart": "2023-02-01",
    "TotalSales": 3728375.0,
    "BillCount": 15,
    "SalesRank": 12,
    "PctOfAvg": 35.6
  },
  {
    "MonthStart": "2023-03-01",
    "TotalSales": 202822.0,
    "BillCount": 6,
    "SalesRank": 37,
    "PctOfAvg": 1.9
  },
  {
    "MonthStart": "2023-04-01",
    "TotalSales": 2593230.0,
    "BillCount": 10,
    "SalesRank": 14,
    "PctOfAvg": 24.8
  },
  {
    "MonthStart": "2023-05-01",
    "TotalSales": 743459.0,
    "BillCount": 5,
    "SalesRank": 31,
    "PctOfAvg": 7.1
  },
  {
    "MonthStart": "2023-06-01",
    "TotalSales": 1633864.0,
    "BillCount": 11,
    "SalesRank": 19,
    "PctOfAvg": 15.6
  },
  {
    "MonthStart": "2023-07-01",
    "TotalSales": 1262082.0,
    "BillCount": 9,
    "SalesRank": 27,
    "PctOfAvg": 12.0
  },
  {
    "MonthStart": "2023-08-01",
    "TotalSales": 1348674.0,
    "BillCount": 10,
    "SalesRank": 25,
    "PctOfAvg": 12.9
  },
  {
    "MonthStart": "2023-09-01",
    "TotalSales": 985173.0,
    "BillCount": 5,
    "SalesRank": 28,
    "PctOfAvg": 9.4
  },
  {
    "MonthStart": "2023-10-01",
    "TotalSales": 2804504.0,
    "BillCount": 9,
    "SalesRank": 13,
    "PctOfAvg": 26.8
  }
]
```

## 40. High Return / Low Conversion Product Identification
**Template:** `high_return_low_conversion_products` · **Status:** OK · **Rows:** 728

_First 10 of 728 rows (open AI Query for full export)._

```json
[
  {
    "Itemcode": "26HQ5830323",
    "ReturnQty": 2.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5782593",
    "ReturnQty": 2.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5802836",
    "ReturnQty": 2.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5803117",
    "ReturnQty": 1.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5804421",
    "ReturnQty": 1.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5804660",
    "ReturnQty": 1.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5805656",
    "ReturnQty": 1.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5805675",
    "ReturnQty": 1.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5806265",
    "ReturnQty": 1.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  },
  {
    "Itemcode": "26HQ5806675",
    "ReturnQty": 1.0,
    "MTDQtySold": 0.0,
    "ReturnRatePct": null
  }
]
```

## 41. AI-based Alerts for Sudden Sales Drop or Spike
**Template:** `sales_spike_drop_alert` · **Status:** OK · **Rows:** 1

```json
[
  {
    "AvgDailySalesLast7Days": 5000.0,
    "AvgDailySalesPrior7Days": null,
    "ChangePct": null,
    "AlertFlag": "Insufficient history"
  }
]
```

## 42. Top Customers based on Purchase Value
**Template:** `top_customers_purchase_value` · **Status:** OK · **Rows:** 20

_First 10 of 20 rows (open AI Query for full export)._

```json
[
  {
    "CustomerId": "SLS_OL1000000011468",
    "CustomerFirstName": "MYNTRA-UTTAR  PRADESH",
    "CustomerLastName": "",
    "ContactMobile": "2000000004",
    "City": "Noida",
    "CustomerGroupName": "ONLINE",
    "TotalPurchaseValue": 250703.0,
    "InvoiceCount": 60
  },
  {
    "CustomerId": "SLS_OL1000000011473",
    "CustomerFirstName": "MYNTRA-DELHI",
    "CustomerLastName": "",
    "ContactMobile": "2000000009",
    "City": "DELHI",
    "CustomerGroupName": "ONLINE",
    "TotalPurchaseValue": 206701.0,
    "InvoiceCount": 28
  },
  {
    "CustomerId": "SLS_OL1000000011465",
    "CustomerFirstName": "MYNTRA-HARYANA",
    "CustomerLastName": "",
    "ContactMobile": "2000000001",
    "City": "Haryana",
    "CustomerGroupName": "[Default]",
    "TotalPurchaseValue": 173207.0,
    "InvoiceCount": 15
  },
  {
    "CustomerId": "SLS_003000000053437",
    "CustomerFirstName": "Deepak",
    "CustomerLastName": "Narayani",
    "ContactMobile": "9990096000",
    "City": "110027 New Delhi DL",
    "CustomerGroupName": "[Default]",
    "TotalPurchaseValue": 119500.0,
    "InvoiceCount": 3
  },
  {
    "CustomerId": "SLS_076000000009821",
    "CustomerFirstName": "VANDANA",
    "CustomerLastName": "",
    "ContactMobile": "9810756981",
    "City": "",
    "CustomerGroupName": "[Default]",
    "TotalPurchaseValue": 117990.0,
    "InvoiceCount": 3
  },
  {
    "CustomerId": "SLS_046000000012111",
    "CustomerFirstName": "mbdd3",
    "CustomerLastName": "",
    "ContactMobile": "4612345678",
    "City": "UTTRAKHAND",
    "CustomerGroupName": "[Default]",
    "TotalPurchaseValue": 91780.0,
    "InvoiceCount": 4
  },
  {
    "CustomerId": "SLS_061000000000762",
    "CustomerFirstName": "shipra singh",
    "CustomerLastName": "",
    "ContactMobile": "9565748438",
    "City": "",
    "CustomerGroupName": "[Default]",
    "TotalPurchaseValue": 90490.0,
    "InvoiceCount": 1
  },
  {
    "CustomerId": "SLS_047000000022380",
    "CustomerFirstName": "Balesh",
    "CustomerLastName": "",
    "ContactMobile": "7011002597",
    "City": "",
    "CustomerGroupName": "[Default]",
    "TotalPurchaseValue": 89970.0,
    "InvoiceCount": 2
  },
  {
    "CustomerId": "SLS_052000000020878",
    "CustomerFirstName": "MBAMB",
    "CustomerLastName": "",
    "ContactMobile": "5212345678",
    "City": "GURGAON",
    "CustomerGroupName": "[Default]",
    "TotalPurchaseValue": 76486.0,
    "InvoiceCount": 7
  },
  {
    "CustomerId": "SLS_058000000006188",
    "CustomerFirstName": "rakesh",
    "CustomerLastName": "",
    "ContactMobile": "9934289997",
    "City": "MUMBAI",
    "CustomerGroupName": "[Default]",
    "TotalPurchaseValue": 74095.0,
    "InvoiceCount": 5
  }
]
```

## 43. New vs Repeat Customer Analysis
**Template:** `new_vs_repeat_customer_analysis` · **Status:** OK · **Rows:** 2

```json
[
  {
    "CustomerType": "One-time",
    "CustomerCount": 2770,
    "Revenue": 15493393.0
  },
  {
    "CustomerType": "Repeat",
    "CustomerCount": 555,
    "Revenue": 7550283.0
  }
]
```

## 44. Category Contribution % in Total Revenue
**Template:** `category_contribution_percentage` · **Status:** OK · **Rows:** 1

```json
[
  {
    "Category": "K2P",
    "Revenue": 5000.0,
    "ContributionPct": 100.0
  }
]
```

## 45. Gross Margin Analysis by Department/Category
**Template:** `gross_margin_by_category` · **Status:** OK · **Rows:** 1

```json
[
  {
    "Category": "K2P",
    "Revenue": 5000.0,
    "CostValue": 2675.0,
    "GrossProfit": 2325.0,
    "GrossMarginPct": 46.5
  }
]
```

## 46. Inventory Aging Analysis
**Template:** `stock_aging_analysis` · **Status:** OK · **Rows:** 4

```json
[
  {
    "AgeBucket": "0-30 days",
    "TotalStockQty": 106576.0,
    "StockValueAtMRP": 547165965.0,
    "DistinctItems": 104699
  },
  {
    "AgeBucket": "31-60 days",
    "TotalStockQty": 47325.0,
    "StockValueAtMRP": 273902240.0,
    "DistinctItems": 47325
  },
  {
    "AgeBucket": "61-90 days",
    "TotalStockQty": 19448.0,
    "StockValueAtMRP": 118571560.0,
    "DistinctItems": 19448
  },
  {
    "AgeBucket": "90+ days",
    "TotalStockQty": 43646.0,
    "StockValueAtMRP": 277828697.0,
    "DistinctItems": 42451
  }
]
```

## 47. Dead Stock Identification
**Template:** `dead_stock_identification` · **Status:** OK · **Rows:** 42,802

_First 10 of 42,802 rows (open AI Query for full export)._

```json
[
  {
    "BranchAlias": "US-03",
    "ItemId": "1200538038",
    "ArticleNo": "$126-496-EMB-GGT-60GM",
    "Category": "EMB",
    "StockQty": 1.0,
    "PurInvoiceDate": "2012-11-10",
    "DaysSincePurInvoice": 4954
  },
  {
    "BranchAlias": "HQ0-SJE",
    "ItemId": "1300708501",
    "ArticleNo": "1026-BPC-BNS-BSCR",
    "Category": "BLS",
    "StockQty": 1.0,
    "PurInvoiceDate": "2013-04-10",
    "DaysSincePurInvoice": 4803
  },
  {
    "BranchAlias": "US-03",
    "ItemId": "13CC101193",
    "ArticleNo": "$MTM-930-EMB-NET",
    "Category": "EMB",
    "StockQty": 1.0,
    "PurInvoiceDate": "2013-05-20",
    "DaysSincePurInvoice": 4763
  },
  {
    "BranchAlias": "US-03",
    "ItemId": "14UV140802",
    "ArticleNo": "$MIX-1236-EMB-BNS-BSNE",
    "Category": "EMB",
    "StockQty": 1.0,
    "PurInvoiceDate": "2014-02-24",
    "DaysSincePurInvoice": 4483
  },
  {
    "BranchAlias": "HQ0-SJE",
    "ItemId": "14hq2101604",
    "ArticleNo": "ADD-COST",
    "Category": "OTH",
    "StockQty": 1.0,
    "PurInvoiceDate": "2014-04-12",
    "DaysSincePurInvoice": 4436
  },
  {
    "BranchAlias": "05-DLF",
    "ItemId": "14HQ1142063",
    "ArticleNo": "FABRIC BOTTAM-PC",
    "Category": "OTH",
    "StockQty": 1.0,
    "PurInvoiceDate": "2014-05-26",
    "DaysSincePurInvoice": 4392
  },
  {
    "BranchAlias": "US-01",
    "ItemId": "14HQ1291778",
    "ArticleNo": "BBZ-LEG002-CHR-COT.",
    "Category": "BOT",
    "StockQty": 1.0,
    "PurInvoiceDate": "2014-11-05",
    "DaysSincePurInvoice": 4229
  },
  {
    "BranchAlias": "US-01",
    "ItemId": "14HQ1314638",
    "ArticleNo": "KPK-PLAZO01-WOO",
    "Category": "BOT",
    "StockQty": 1.0,
    "PurInvoiceDate": "2014-12-06",
    "DaysSincePurInvoice": 4198
  },
  {
    "BranchAlias": "HQ0-SJE",
    "ItemId": "14HQ1316977",
    "ArticleNo": "5402-BLS-HLM-DUPI",
    "Category": "BLS",
    "StockQty": 1.0,
    "PurInvoiceDate": "2014-12-11",
    "DaysSincePurInvoice": 4193
  },
  {
    "BranchAlias": "US-01",
    "ItemId": "14HQ1318526",
    "ArticleNo": "KPK-LOWER PLAZO01-WOO",
    "Category": "BOT",
    "StockQty": 1.0,
    "PurInvoiceDate": "2014-12-13",
    "DaysSincePurInvoice": 4191
  }
]
```

## 48. Product-wise Sell Through %
**Template:** `product_sell_through_pct` · **Status:** OK · **Rows:** 213,892

_First 10 of 213,892 rows (open AI Query for full export)._

```json
[
  {
    "Itemcode": "26HQ5805316",
    "MTDQtySold": 1.0,
    "OnHandQty": 0.0,
    "SellThroughPct": 100.0
  },
  {
    "Itemcode": "1200538038",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  },
  {
    "Itemcode": "1300708501",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  },
  {
    "Itemcode": "13CC101193",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  },
  {
    "Itemcode": "14HQ1142063",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  },
  {
    "Itemcode": "14HQ1291778",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  },
  {
    "Itemcode": "14HQ1314638",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  },
  {
    "Itemcode": "14HQ1316977",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  },
  {
    "Itemcode": "14HQ1318526",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  },
  {
    "Itemcode": "14HQ2101604",
    "MTDQtySold": 0.0,
    "OnHandQty": 1.0,
    "SellThroughPct": 0.0
  }
]
```

## 49. Sales Trend Prediction for Upcoming Festivals/Seasons
**Template:** `festival_sales_trend_prediction` · **Status:** OK · **Rows:** 42

_First 10 of 42 rows (open AI Query for full export)._

```json
[
  {
    "MonthStart": "2023-01-01",
    "TotalSales": 1647142.0,
    "BillCount": 10,
    "SalesRank": 18,
    "PctOfAvg": 15.7
  },
  {
    "MonthStart": "2023-02-01",
    "TotalSales": 3728375.0,
    "BillCount": 15,
    "SalesRank": 12,
    "PctOfAvg": 35.6
  },
  {
    "MonthStart": "2023-03-01",
    "TotalSales": 202822.0,
    "BillCount": 6,
    "SalesRank": 37,
    "PctOfAvg": 1.9
  },
  {
    "MonthStart": "2023-04-01",
    "TotalSales": 2593230.0,
    "BillCount": 10,
    "SalesRank": 14,
    "PctOfAvg": 24.8
  },
  {
    "MonthStart": "2023-05-01",
    "TotalSales": 743459.0,
    "BillCount": 5,
    "SalesRank": 31,
    "PctOfAvg": 7.1
  },
  {
    "MonthStart": "2023-06-01",
    "TotalSales": 1633864.0,
    "BillCount": 11,
    "SalesRank": 19,
    "PctOfAvg": 15.6
  },
  {
    "MonthStart": "2023-07-01",
    "TotalSales": 1262082.0,
    "BillCount": 9,
    "SalesRank": 27,
    "PctOfAvg": 12.0
  },
  {
    "MonthStart": "2023-08-01",
    "TotalSales": 1348674.0,
    "BillCount": 10,
    "SalesRank": 25,
    "PctOfAvg": 12.9
  },
  {
    "MonthStart": "2023-09-01",
    "TotalSales": 985173.0,
    "BillCount": 5,
    "SalesRank": 28,
    "PctOfAvg": 9.4
  },
  {
    "MonthStart": "2023-10-01",
    "TotalSales": 2804504.0,
    "BillCount": 9,
    "SalesRank": 13,
    "PctOfAvg": 26.8
  }
]
```

## 50. AI-generated Business Insights and Recommendations
**Template:** `ai_business_insights_snapshot` · **Status:** OK · **Rows:** 6

```json
[
  {
    "Metric": "MTD Sales (Lakhs)",
    "Value": 230.58,
    "Detail": null
  },
  {
    "Metric": "MTD Bills (Unique Invoices)",
    "Value": 4397.0,
    "Detail": null
  },
  {
    "Metric": "MTD YoY Growth %",
    "Value": 14.24,
    "Detail": null
  },
  {
    "Metric": "Top Branch MTD",
    "Value": 14.27,
    "Detail": "MB-OL4"
  },
  {
    "Metric": "Top Category MTD",
    "Value": 36.42,
    "Detail": "SKD"
  },
  {
    "Metric": "Fastest Growing Branch (vs LY)",
    "Value": 220.9,
    "Detail": "71-AML"
  }
]
```

---

**Summary:** 50 OK with data · 0 empty · 0 error/no-match · total 50