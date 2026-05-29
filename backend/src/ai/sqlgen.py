"""
SQL Generation Engine
Converts a structured intent + date range into a validated T-SQL query
using Claude with schema-catalog context and few-shot examples.

Schema context is now driven by schema_catalog.json (28 real ERP views) —
the AI receives exact column names and table names, enabling accurate SQL
for any question about sales, stock, purchases, customers, salespersons, etc.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, Optional

import anthropic

from src.config import cfg
from src.utils.logger import logger
from src.utils.date_utils import DateRange
from src.ai.schema_catalog import build_catalog_schema_prompt
from src.ai.intent import ExtractedIntent

# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass
class GeneratedSQL:
    sql: str
    params: Dict[str, str]
    description: str
    estimated_rows: str   # "few" | "moderate" | "many"
    uses_date_range: bool


# ─── Few-Shot Examples (covers all major query domains) ──────────────────────

_FEW_SHOT = """
## Few-Shot Examples

### Example 1 — MTD revenue by branch
Query: "Sales by branch this month"
{"sql": "SELECT [BranchAlias] AS Branch, SUM([NetSlsNetAmount]) AS Revenue, SUM([BillCount]) AS Transactions FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [BranchAlias] ORDER BY Revenue DESC OPTION (RECOMPILE)", "description": "MTD revenue by branch", "estimatedRows": "few"}

### Example 2 — Daily revenue trend
Query: "Daily sales trend last 30 days"
{"sql": "SELECT CAST([XnDt] AS DATE) AS TransactionDate, SUM([NetSlsNetAmount]) AS Revenue, SUM([BillCount]) AS Transactions FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY CAST([XnDt] AS DATE) ORDER BY TransactionDate ASC OPTION (RECOMPILE)", "description": "Daily revenue trend", "estimatedRows": "moderate"}

### Example 3 — Top 5 categories
Query: "Top 5 categories by revenue YTD"
{"sql": "SELECT TOP 5 [CategoryShortName] AS Category, SUM([NetSlsNetAmount]) AS Revenue, SUM([AppQty]) AS Quantity FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [CategoryShortName] ORDER BY Revenue DESC OPTION (RECOMPILE)", "description": "Top 5 categories YTD", "estimatedRows": "few"}

### Example 4 — Total KPI
Query: "Total sales this quarter"
{"sql": "SELECT ISNULL(SUM([NetSlsNetAmount]), 0) AS TotalRevenue, SUM([BillCount]) AS TotalTransactions, SUM([AppQty]) AS TotalQuantity FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate OPTION (RECOMPILE)", "description": "Total revenue QTD", "estimatedRows": "few"}

### Example 5 — Category breakdown with %
Query: "Revenue breakdown by category this month"
{"sql": "SELECT [CategoryShortName] AS Category, SUM([NetSlsNetAmount]) AS Revenue, CAST(SUM([NetSlsNetAmount]) * 100.0 / NULLIF(SUM(SUM([NetSlsNetAmount])) OVER (), 0) AS DECIMAL(10,2)) AS Percentage FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [CategoryShortName] ORDER BY Revenue DESC OPTION (RECOMPILE)", "description": "Category revenue share MTD", "estimatedRows": "few"}

### Example 6 — Salesperson performance
Query: "Top 10 salespersons by revenue this month"
{"sql": "SELECT TOP 10 [SalesPersonName] AS Salesperson, [BranchAlias] AS Branch, SUM([NetAmount]) AS Revenue, COUNT(DISTINCT [XnId]) AS Transactions FROM [dbo].[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] WITH (NOLOCK) WHERE [XnMemoDate] >= @startDate AND [XnMemoDate] <= @endDate GROUP BY [SalesPersonName], [BranchAlias] ORDER BY Revenue DESC OPTION (RECOMPILE)", "description": "Top 10 salespersons by revenue", "estimatedRows": "few"}

### Example 7 — Stock on hand by category
Query: "Current stock by category"
{"sql": "SELECT [CategoryShortName] AS Category, SUM([ClosingQty]) AS OnHandQty, SUM([ClosingValue]) AS StockValue FROM [dbo].[VW_MB_POWERBI_STOCK_REPORT] WITH (NOLOCK) GROUP BY [CategoryShortName] ORDER BY StockValue DESC OPTION (RECOMPILE)", "description": "Stock on hand by category", "estimatedRows": "few"}

### Example 8 — Purchase by supplier
Query: "Purchases from each supplier this month"
{"sql": "SELECT [SupplierAlias] AS Supplier, [SupplierName] AS SupplierFullName, SUM([NetAmount]) AS PurchaseValue, SUM([Qty]) AS PurchaseQty FROM [dbo].[VW_MB_POWERBI_PUR_REPORT] WITH (NOLOCK) WHERE [PurDate] >= @startDate AND [PurDate] <= @endDate GROUP BY [SupplierAlias], [SupplierName] ORDER BY PurchaseValue DESC OPTION (RECOMPILE)", "description": "Purchase by supplier MTD", "estimatedRows": "few"}

### Example 9 — New customers this month
Query: "How many new customers registered this month?"
{"sql": "SELECT COUNT(DISTINCT [CustomerId]) AS NewCustomers, COUNT(DISTINCT [BranchName]) AS BranchesWithSignups FROM [dbo].[VwAICustomerDetails] WITH (NOLOCK) WHERE [CreatedOn] >= @startDate AND [CreatedOn] <= @endDate OPTION (RECOMPILE)", "description": "New customer signups MTD", "estimatedRows": "few"}

### Example 10 — CTE: negative growth categories
Query: "Which categories are showing negative growth trends?"
{"sql": ";WITH CurPeriod AS (SELECT [CategoryShortName] AS Category, SUM([NetSlsNetAmount]) AS Revenue FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [CategoryShortName]), PriorPeriod AS (SELECT [CategoryShortName] AS Category, SUM([NetSlsNetAmount]) AS Revenue FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= DATEADD(MONTH, -1, @startDate) AND [XnDt] < @startDate GROUP BY [CategoryShortName]) SELECT c.Category, c.Revenue AS CurrentRevenue, ISNULL(p.Revenue, 0) AS PriorRevenue, CAST((c.Revenue - ISNULL(p.Revenue, 0)) * 100.0 / NULLIF(p.Revenue, 0) AS DECIMAL(10,2)) AS GrowthPct FROM CurPeriod c LEFT JOIN PriorPeriod p ON c.Category = p.Category WHERE c.Revenue < ISNULL(p.Revenue, 0) ORDER BY GrowthPct ASC OPTION (RECOMPILE)", "description": "Categories with negative growth vs prior period", "estimatedRows": "few"}

### Example 11 — Peak billing hours
Query: "Peak sales hours / peak billing time analysis"
{"sql": ";WITH HourlyBilling AS (SELECT DATEPART(HOUR, [XnDt]) AS BillHour, SUM([BillCount]) AS TotalBills, SUM([NetSlsNetAmount]) AS Revenue FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY DATEPART(HOUR, [XnDt])) SELECT BillHour, TotalBills, Revenue, CAST(TotalBills * 100.0 / NULLIF(SUM(TotalBills) OVER (), 0) AS DECIMAL(10,2)) AS PctOfDayBills FROM HourlyBilling ORDER BY BillHour ASC OPTION (RECOMPILE)", "description": "Hourly billing distribution", "estimatedRows": "moderate"}

### Example 12 — Stock transfers between branches
Query: "Stock transfers sent out this month"
{"sql": "SELECT [FromBranchAlias] AS FromBranch, [ToBranchAlias] AS ToBranch, [CategoryShortName] AS Category, SUM([TransferQty]) AS Qty, SUM([TransferValue]) AS Value FROM [dbo].[VW_MB_POWERBI_STO_REPORT] WITH (NOLOCK) WHERE [StoDate] >= @startDate AND [StoDate] <= @endDate GROUP BY [FromBranchAlias], [ToBranchAlias], [CategoryShortName] ORDER BY Value DESC OPTION (RECOMPILE)", "description": "Stock transfers out MTD", "estimatedRows": "moderate"}

### Example 13 — Department breakdown
Query: "Revenue by department this year"
{"sql": "SELECT [DepartmentShortName] AS Department, SUM([NetSlsNetAmount]) AS Revenue, SUM([AppQty]) AS Quantity, SUM([BillCount]) AS Transactions FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [DepartmentShortName] ORDER BY Revenue DESC OPTION (RECOMPILE)", "description": "Revenue by department YTD", "estimatedRows": "few"}

### Example 14 — MRP vs Net comparison
Query: "Discount given this month — MRP vs net sales"
{"sql": "SELECT [BranchAlias] AS Branch, SUM([MrpValue]) AS TotalMRP, SUM([NetSlsNetAmount]) AS NetRevenue, SUM([MrpValue] - [NetSlsNetAmount]) AS TotalDiscount, CAST(SUM([MrpValue] - [NetSlsNetAmount]) * 100.0 / NULLIF(SUM([MrpValue]), 0) AS DECIMAL(10,2)) AS DiscountPct FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [BranchAlias] ORDER BY DiscountPct DESC OPTION (RECOMPILE)", "description": "Discount analysis by branch MTD", "estimatedRows": "few"}
"""


def _build_system_prompt(schema_section: str) -> str:
    return f"""You are an expert Microsoft SQL Server T-SQL writer for a retail ERP analytics system (database: zRetailHQ0).

Your task: given a natural language query and its extracted intent, generate a correct, safe T-SQL SELECT query.

STRICT OUTPUT RULES:
1. Output ONLY a single JSON object: {{"sql": "...", "description": "...", "estimatedRows": "few|moderate|many"}}
2. No markdown fences, no extra text outside the JSON.
3. SELECT statements ONLY — no INSERT/UPDATE/DELETE/DROP/EXEC/CREATE/ALTER.
4. Use @startDate and @endDate as named parameters for date ranges.
5. Always add WITH (NOLOCK) on every FROM table reference.
6. Always end with OPTION (RECOMPILE).
7. Use TOP N only for explicit ranking queries.
8. Column aliases must be PascalCase with no spaces (e.g. TotalRevenue, BranchAlias).
9. Trend queries: GROUP BY date expression, ORDER BY date ASC.
10. Use ISNULL(SUM(...), 0) for revenue columns to avoid NULL.
11. For percentage calculations use NULLIF in the denominator.
12. For CTEs: use ;WITH CTE_Name AS (...) SELECT ... pattern.
13. Use the EXACT column names and view names from the schema below — do not invent names.

{schema_section}

{_FEW_SHOT}"""


# ─── AI SQL Generator ─────────────────────────────────────────────────────────

_ai_client: Optional[anthropic.AsyncAnthropic] = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.AsyncAnthropic(api_key=cfg.ANTHROPIC_API_KEY)
    return _ai_client


async def generate_sql(
    intent: ExtractedIntent,
    date_range: DateRange,
    conversation_context: Optional[str] = None,
) -> GeneratedSQL:
    # Use catalog-backed schema: selects up to 4 most relevant views for this query
    schema_section = build_catalog_schema_prompt(intent.raw, max_views=4)
    system = _build_system_prompt(schema_section)

    lines = []
    if conversation_context:
        lines.append(f"## Conversation Context\n{conversation_context}\n")

    lines.append(f'## User Query\n"{intent.raw}"\n')
    lines.append("## Extracted Intent")
    lines.append(f"- Intent type: {intent.intent}")
    lines.append(f"- Period: {intent.period} ({date_range.label}: {date_range.start} → {date_range.end})")
    lines.append(f"- Metric: {intent.metric}")
    if intent.dimension:
        lines.append(f"- Group by: {intent.dimension}")
    if intent.top_n:
        lines.append(f"- Top N: {intent.top_n}")
    if intent.compare_with:
        lines.append(f"- Compare with: {intent.compare_with}")
    if intent.filters:
        lines.append(f"- Filters: {json.dumps(intent.filters)}")
    lines.append(f"- Suggested chart: {intent.chart_type}")
    lines.append(f"\n## Parameters\n- @startDate = '{date_range.start}'\n- @endDate = '{date_range.end}'")
    lines.append("\nGenerate the SQL query as JSON.")

    user_msg = "\n".join(lines)

    client = _get_client()
    try:
        response = await client.messages.create(
            model=cfg.ANTHROPIC_MODEL,
            max_tokens=1200,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )

        text = response.content[0].text if response.content else ""
        json_match = re.search(r"\{[\s\S]*\}", text)
        if not json_match:
            raise ValueError(f"No JSON in SQL gen response. Raw: {text[:200]}")

        parsed = json.loads(json_match.group())
        sql = (parsed.get("sql") or "").strip()
        if not sql:
            raise ValueError("Generated SQL is empty")

        return GeneratedSQL(
            sql=sql,
            params={"startDate": date_range.start, "endDate": date_range.end},
            description=parsed.get("description", intent.raw),
            estimated_rows=parsed.get("estimatedRows", "moderate"),
            uses_date_range="@startDate" in sql,
        )

    except Exception as exc:
        logger.error("SQL generation failed", error=str(exc), intent=intent.intent)
        raise RuntimeError(f"SQL generation failed: {exc}") from exc


# ─── Template Generator (fast path — no AI call) ──────────────────────────────

def generate_sql_template(
    intent: ExtractedIntent,
    date_range: DateRange,
) -> Optional[GeneratedSQL]:
    """
    Template-based SQL for the most common patterns.
    Returns None if pattern isn't handled → AI fallback.
    All column/table names match the real schema_catalog.json.
    """
    c = cfg
    # Primary sales view — covers 90% of analytics queries
    main_table = "[dbo].[VW_MB_POWERBI_APP_REPORT]"
    date_col   = "[XnDt]"
    amount_col = "[NetSlsNetAmount]"
    branch_col = "[BranchAlias]"
    cat_col    = "[CategoryShortName]"
    dept_col   = "[DepartmentShortName]"
    bill_col   = "[BillCount]"
    qty_col    = "[AppQty]"

    params = {"startDate": date_range.start, "endDate": date_range.end}
    where  = f"WHERE {date_col} >= @startDate AND {date_col} <= @endDate"
    opts   = "OPTION (RECOMPILE)"

    # ── KPI — total revenue ───────────────────────────────────────────────
    if intent.intent == "kpi" and intent.metric == "revenue":
        return GeneratedSQL(
            sql=(
                f"SELECT ISNULL(SUM({amount_col}), 0) AS TotalRevenue, "
                f"SUM({bill_col}) AS TotalTransactions, SUM({qty_col}) AS TotalQuantity "
                f"FROM {main_table} WITH (NOLOCK) {where} {opts}"
            ),
            params=params,
            description=f"Total revenue for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # ── KPI — transaction count ───────────────────────────────────────────
    if intent.intent == "kpi" and intent.metric == "transaction_count":
        return GeneratedSQL(
            sql=(
                f"SELECT SUM({bill_col}) AS TotalTransactions, "
                f"ISNULL(SUM({amount_col}), 0) AS TotalRevenue "
                f"FROM {main_table} WITH (NOLOCK) {where} {opts}"
            ),
            params=params,
            description=f"Transaction count for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # ── Aggregate by branch ───────────────────────────────────────────────
    if intent.intent in ("aggregate", "ranking") and intent.dimension == "branch":
        top = f"TOP {min(intent.top_n, 100)} " if intent.top_n else ""
        return GeneratedSQL(
            sql=(
                f"SELECT {top}{branch_col} AS Branch, "
                f"ISNULL(SUM({amount_col}), 0) AS Revenue, "
                f"SUM({bill_col}) AS Transactions, SUM({qty_col}) AS Quantity "
                f"FROM {main_table} WITH (NOLOCK) {where} "
                f"GROUP BY {branch_col} ORDER BY Revenue DESC {opts}"
            ),
            params=params,
            description=f"Revenue by branch for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # ── Aggregate by category ─────────────────────────────────────────────
    if intent.intent in ("aggregate", "ranking") and intent.dimension == "category":
        top = f"TOP {min(intent.top_n, 100)} " if intent.top_n else ""
        return GeneratedSQL(
            sql=(
                f"SELECT {top}{cat_col} AS Category, "
                f"ISNULL(SUM({amount_col}), 0) AS Revenue, "
                f"SUM({bill_col}) AS Transactions, SUM({qty_col}) AS Quantity "
                f"FROM {main_table} WITH (NOLOCK) {where} "
                f"GROUP BY {cat_col} ORDER BY Revenue DESC {opts}"
            ),
            params=params,
            description=f"Revenue by category for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # ── Aggregate by department ───────────────────────────────────────────
    if intent.intent in ("aggregate", "ranking") and intent.dimension == "department":
        top = f"TOP {min(intent.top_n, 100)} " if intent.top_n else ""
        return GeneratedSQL(
            sql=(
                f"SELECT {top}{dept_col} AS Department, "
                f"ISNULL(SUM({amount_col}), 0) AS Revenue, "
                f"SUM({bill_col}) AS Transactions, SUM({qty_col}) AS Quantity "
                f"FROM {main_table} WITH (NOLOCK) {where} "
                f"GROUP BY {dept_col} ORDER BY Revenue DESC {opts}"
            ),
            params=params,
            description=f"Revenue by department for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # ── Aggregate by salesperson ──────────────────────────────────────────
    if intent.dimension == "salesperson":
        sp_table = "[dbo].[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID]"
        top = f"TOP {min(intent.top_n, 100)} " if intent.top_n else ""
        return GeneratedSQL(
            sql=(
                f"SELECT {top}[SalesPersonName] AS Salesperson, [BranchAlias] AS Branch, "
                f"ISNULL(SUM([NetAmount]), 0) AS Revenue, "
                f"COUNT(DISTINCT [XnId]) AS Transactions "
                f"FROM {sp_table} WITH (NOLOCK) "
                f"WHERE [XnMemoDate] >= @startDate AND [XnMemoDate] <= @endDate "
                f"GROUP BY [SalesPersonName], [BranchAlias] ORDER BY Revenue DESC {opts}"
            ),
            params=params,
            description=f"Revenue by salesperson for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # ── Daily trend ───────────────────────────────────────────────────────
    if intent.intent == "trend":
        return GeneratedSQL(
            sql=(
                f"SELECT CAST({date_col} AS DATE) AS TransactionDate, "
                f"ISNULL(SUM({amount_col}), 0) AS Revenue, "
                f"SUM({bill_col}) AS Transactions, SUM({qty_col}) AS Quantity "
                f"FROM {main_table} WITH (NOLOCK) {where} "
                f"GROUP BY CAST({date_col} AS DATE) ORDER BY TransactionDate ASC {opts}"
            ),
            params=params,
            description=f"Daily revenue trend for {date_range.label}",
            estimated_rows="moderate",
            uses_date_range=True,
        )

    return None  # Not handled — fall through to AI
