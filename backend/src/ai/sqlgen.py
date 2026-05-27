"""
SQL Generation Engine
Converts a structured intent + date range into a validated T-SQL query
using Claude with few-shot examples and schema context.
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
from src.ai.schema import build_schema_prompt
from src.ai.intent import ExtractedIntent

# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass
class GeneratedSQL:
    sql: str
    params: Dict[str, str]
    description: str
    estimated_rows: str   # "few" | "moderate" | "many"
    uses_date_range: bool


# ─── Few-Shot Examples ────────────────────────────────────────────────────────

_FEW_SHOT = """
## Example 1 — MTD revenue by branch
Query: "Sales by branch this month"
{"sql": "SELECT [BranchAlias] AS Branch, SUM([NetSlsNetAmount]) AS Revenue, COUNT(*) AS Transactions FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [BranchAlias] ORDER BY Revenue DESC OPTION (RECOMPILE)", "description": "Revenue by branch for MTD", "estimatedRows": "few"}

## Example 2 — Daily trend
Query: "Daily sales trend last 30 days"
{"sql": "SELECT CAST([XnDt] AS DATE) AS TransactionDate, SUM([NetSlsNetAmount]) AS Revenue, COUNT(*) AS Transactions FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY CAST([XnDt] AS DATE) ORDER BY TransactionDate ASC OPTION (RECOMPILE)", "description": "Daily revenue trend", "estimatedRows": "moderate"}

## Example 3 — Top 5 categories
Query: "Top 5 categories by revenue YTD"
{"sql": "SELECT TOP 5 [CategoryShortName] AS Category, SUM([NetSlsNetAmount]) AS Revenue FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [CategoryShortName] ORDER BY Revenue DESC OPTION (RECOMPILE)", "description": "Top 5 categories by revenue", "estimatedRows": "few"}

## Example 4 — Total KPI
Query: "Total sales this quarter"
{"sql": "SELECT SUM([NetSlsNetAmount]) AS TotalRevenue, COUNT(*) AS TotalTransactions FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate OPTION (RECOMPILE)", "description": "Total revenue QTD", "estimatedRows": "few"}

## Example 5 — Distribution with percentage
Query: "Revenue breakdown by category this month"
{"sql": "SELECT [CategoryShortName] AS Category, SUM([NetSlsNetAmount]) AS Revenue, CAST(SUM([NetSlsNetAmount]) * 100.0 / SUM(SUM([NetSlsNetAmount])) OVER () AS DECIMAL(10,2)) AS Percentage FROM [dbo].[VW_MB_POWERBI_APP_REPORT] WITH (NOLOCK) WHERE [XnDt] >= @startDate AND [XnDt] <= @endDate GROUP BY [CategoryShortName] ORDER BY Revenue DESC OPTION (RECOMPILE)", "description": "Category breakdown", "estimatedRows": "few"}
"""


def _build_system_prompt(schema_prompt: str) -> str:
    return f"""You are an expert Microsoft SQL Server T-SQL writer for a retail ERP analytics system.

Task: Given a natural language query and its extracted intent, generate a correct T-SQL SELECT query.

STRICT RULES:
1. Output ONLY a JSON object: {{"sql": "...", "description": "...", "estimatedRows": "few|moderate|many"}}
2. No markdown, no extra text outside the JSON.
3. SELECT statements ONLY. No INSERT/UPDATE/DELETE/DROP/EXEC.
4. Use @startDate and @endDate as named parameters for date filtering.
5. Always include WITH (NOLOCK) on base table references.
6. Always end with OPTION (RECOMPILE).
7. Use TOP N only for ranking queries.
8. Use proper T-SQL: CAST, CONVERT, DATEPART, ISNULL, etc.
9. Column aliases must be clean PascalCase with no spaces.
10. Trend queries: GROUP BY date, ORDER BY date ASC.

{schema_prompt}

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
    schema_prompt = build_schema_prompt(intent.tables)
    system = _build_system_prompt(schema_prompt)

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
    lines.append(f"- Relevant tables: {', '.join(intent.tables)}")
    lines.append(f"\n## Parameters\n- @startDate = '{date_range.start}'\n- @endDate = '{date_range.end}'")
    lines.append("\nGenerate the SQL query as JSON.")

    user_msg = "\n".join(lines)

    client = _get_client()
    try:
        response = await client.messages.create(
            model=cfg.ANTHROPIC_MODEL,
            max_tokens=1024,
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


# ─── Template Generator (fast path) ──────────────────────────────────────────

def generate_sql_template(
    intent: ExtractedIntent,
    date_range: DateRange,
) -> Optional[GeneratedSQL]:
    """
    Template-based SQL for common patterns — no AI call needed.
    Returns None if the pattern isn't handled, triggering AI fallback.
    """
    c = cfg
    main_table = f"[{c.SALES_AI_TABLE}]"
    date_col = f"[{c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN}]"
    amount_col = f"[{c.SALES_ANALYTICS_AMOUNT_COLUMN}]"
    branch_col = f"[{c.SALES_ANALYTICS_BRANCH_DIM}]"
    cat_col = f"[{c.SALES_ANALYTICS_CATEGORY_DIM}]"
    dept_col = f"[{c.SALES_ANALYTICS_DEPARTMENT_DIM}]"

    params = {"startDate": date_range.start, "endDate": date_range.end}
    where = f"WHERE {date_col} >= @startDate AND {date_col} <= @endDate"

    # KPI — total revenue
    if intent.intent == "kpi" and intent.metric == "revenue":
        return GeneratedSQL(
            sql=f"SELECT ISNULL(SUM({amount_col}), 0) AS TotalRevenue, COUNT(*) AS TotalTransactions FROM {main_table} WITH (NOLOCK) {where} OPTION (RECOMPILE)",
            params=params,
            description=f"Total revenue for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # Aggregate by branch
    if intent.intent == "aggregate" and intent.dimension == "branch":
        return GeneratedSQL(
            sql=f"SELECT {branch_col} AS Branch, SUM({amount_col}) AS Revenue, COUNT(*) AS Transactions FROM {main_table} WITH (NOLOCK) {where} GROUP BY {branch_col} ORDER BY Revenue DESC OPTION (RECOMPILE)",
            params=params,
            description=f"Revenue by branch for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # Aggregate by category
    if intent.intent == "aggregate" and intent.dimension == "category":
        return GeneratedSQL(
            sql=f"SELECT {cat_col} AS Category, SUM({amount_col}) AS Revenue, COUNT(*) AS Transactions FROM {main_table} WITH (NOLOCK) {where} GROUP BY {cat_col} ORDER BY Revenue DESC OPTION (RECOMPILE)",
            params=params,
            description=f"Revenue by category for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # Aggregate by department
    if intent.intent == "aggregate" and intent.dimension == "department":
        return GeneratedSQL(
            sql=f"SELECT {dept_col} AS Department, SUM({amount_col}) AS Revenue, COUNT(*) AS Transactions FROM {main_table} WITH (NOLOCK) {where} GROUP BY {dept_col} ORDER BY Revenue DESC OPTION (RECOMPILE)",
            params=params,
            description=f"Revenue by department for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    # Daily trend
    if intent.intent == "trend":
        return GeneratedSQL(
            sql=f"SELECT CAST({date_col} AS DATE) AS TransactionDate, SUM({amount_col}) AS Revenue, COUNT(*) AS Transactions FROM {main_table} WITH (NOLOCK) {where} GROUP BY CAST({date_col} AS DATE) ORDER BY TransactionDate ASC OPTION (RECOMPILE)",
            params=params,
            description=f"Daily revenue trend for {date_range.label}",
            estimated_rows="moderate",
            uses_date_range=True,
        )

    # Top-N ranking
    if intent.intent == "ranking" and intent.top_n:
        dim_col = cat_col if intent.dimension == "category" else \
                  dept_col if intent.dimension == "department" else branch_col
        dim_alias = (intent.dimension or "branch").capitalize()
        top = min(intent.top_n, cfg.ANALYTICS_TOP_N_MAX)
        return GeneratedSQL(
            sql=f"SELECT TOP {top} {dim_col} AS {dim_alias}, SUM({amount_col}) AS Revenue FROM {main_table} WITH (NOLOCK) {where} GROUP BY {dim_col} ORDER BY Revenue DESC OPTION (RECOMPILE)",
            params=params,
            description=f"Top {top} {dim_alias.lower()} by revenue for {date_range.label}",
            estimated_rows="few",
            uses_date_range=True,
        )

    return None  # Not handled — fall through to AI
