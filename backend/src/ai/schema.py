"""
Semantic Schema Engine
Business-meaning layer over raw ERP database views.
The AI sees natural column names and table purposes, not cryptic ERP codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.config import cfg


# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass
class ColumnDef:
    name: str           # actual SQL column name
    alias: str          # human-readable alias used in prompts
    col_type: str       # string | number | date | boolean
    description: str
    filterable: bool = False
    aggregatable: bool = False
    enum_values: List[str] = field(default_factory=list)


@dataclass
class TableDef:
    name: str           # actual SQL object name (e.g. dbo.VwAISalesData)
    alias: str          # human-readable name for prompts
    description: str
    primary_use: str
    columns: List[ColumnDef]
    date_column: Optional[str] = None
    branch_column: Optional[str] = None
    sample_queries: List[str] = field(default_factory=list)


# ─── Schema Builder ───────────────────────────────────────────────────────────

def _build_schema() -> List[TableDef]:
    c = cfg  # shorthand

    return [
        TableDef(
            name=c.SALES_AI_TABLE,
            alias="SalesReport",
            description="Primary sales analytics view — covers all transactions with branch, category, department breakdowns.",
            primary_use="Revenue totals, sales trends, branch comparisons, category/department breakdown.",
            date_column=c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN,
            branch_column=c.MB_POWERBI_APP_REPORT_FILTER_BRANCH_COLUMN,
            sample_queries=[
                "Total sales this month by branch",
                "Top 5 categories by revenue last quarter",
                "Department performance YTD",
            ],
            columns=[
                ColumnDef(c.MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN, "TransactionDate", "date", "Transaction/invoice date", filterable=True),
                ColumnDef(c.MB_POWERBI_APP_REPORT_FILTER_BRANCH_COLUMN, "Branch", "string", "Branch short name", filterable=True, aggregatable=True),
                ColumnDef(c.MB_POWERBI_APP_REPORT_FILTER_CATEGORY_COLUMN, "Category", "string", "Product category short name", filterable=True, aggregatable=True),
                ColumnDef(c.MB_POWERBI_APP_REPORT_FILTER_DEPARTMENT_COLUMN, "Department", "string", "Department short name", filterable=True, aggregatable=True),
                ColumnDef(c.SALES_ANALYTICS_AMOUNT_COLUMN, "NetSalesAmount", "number", "Net sales after discounts", aggregatable=True),
                ColumnDef("GrossAmount", "GrossAmount", "number", "Gross sales before discounts", aggregatable=True),
                ColumnDef("DiscountAmount", "DiscountAmount", "number", "Total discount applied", aggregatable=True),
                ColumnDef("Quantity", "Quantity", "number", "Units sold", aggregatable=True),
                ColumnDef("TransactionCount", "TransactionCount", "number", "Number of transactions", aggregatable=True),
            ],
        ),

        TableDef(
            name=c.ANALYTICS_BASE_TABLE,
            alias="SalesBase",
            description="Broader sales base table with item-level detail for deep-dive analysis.",
            primary_use="Detailed sales, item-level reporting, customer segmentation.",
            date_column=c.SALES_FILTER_DATE_COLUMN,
            branch_column=c.SALES_FILTER_BRANCH_COLUMN,
            sample_queries=[
                "Sales by salesperson this month",
                "Top items by revenue",
            ],
            columns=[
                ColumnDef(c.SALES_FILTER_DATE_COLUMN, "InvoiceDate", "date", "Invoice date", filterable=True),
                ColumnDef(c.SALES_FILTER_BRANCH_COLUMN, "BranchId", "string", "Branch identifier", filterable=True),
                ColumnDef(c.SALES_ANALYTICS_AMOUNT_COLUMN, "NetSalesAmount", "number", "Net sales amount", aggregatable=True),
                ColumnDef("ItemId", "ItemId", "string", "Product item identifier", filterable=True),
                ColumnDef("ItemName", "ItemName", "string", "Product name", filterable=True),
                ColumnDef("CustomerId", "CustomerId", "string", "Customer identifier", filterable=True),
                ColumnDef("Quantity", "Quantity", "number", "Quantity sold", aggregatable=True),
            ],
        ),

        TableDef(
            name=c.SALES_VIEW,
            alias="AISalesData",
            description="AI-optimized sales view, pre-aggregated for fast NLQ queries.",
            primary_use="Quick revenue summaries, growth calculations, time-series analysis.",
            date_column="InvoiceDt",
            branch_column="BranchId",
            sample_queries=[
                "Revenue last 30 days",
                "Daily sales trend this week",
                "MTD vs prior MTD",
            ],
            columns=[
                ColumnDef("InvoiceDt", "InvoiceDate", "date", "Invoice date", filterable=True),
                ColumnDef("BranchId", "BranchId", "string", "Branch ID", filterable=True),
                ColumnDef("BranchName", "BranchName", "string", "Branch full name"),
                ColumnDef("NetAmount", "NetSalesAmount", "number", "Net sales amount", aggregatable=True),
                ColumnDef("GrossAmount", "GrossAmount", "number", "Gross amount", aggregatable=True),
                ColumnDef("TxnCount", "TransactionCount", "number", "Transaction count", aggregatable=True),
                ColumnDef("CustomerCount", "CustomerCount", "number", "Unique customers", aggregatable=True),
            ],
        ),

        TableDef(
            name=c.BRANCH_VIEW,
            alias="BranchInfo",
            description="Branch master data — names, codes, regions.",
            primary_use="Branch lookup, filtering, region-based grouping.",
            sample_queries=["List all branches"],
            columns=[
                ColumnDef("BranchId", "BranchId", "string", "Branch identifier", filterable=True),
                ColumnDef("BranchName", "BranchName", "string", "Full branch name"),
                ColumnDef("BranchAlias", "BranchAlias", "string", "Short alias used in reports"),
                ColumnDef("Region", "Region", "string", "Geographic region", filterable=True),
                ColumnDef("IsActive", "IsActive", "boolean", "Branch is active", filterable=True),
            ],
        ),

        TableDef(
            name=c.CUSTOMER_VIEW,
            alias="CustomerDetails",
            description="Customer master with acquisition date and segmentation.",
            primary_use="New customer trends, customer count, demographics.",
            date_column=c.CUSTOMERS_FILTER_DATE_COLUMN,
            sample_queries=["New customers this month", "Top customers by spend"],
            columns=[
                ColumnDef("CustomerId", "CustomerId", "string", "Customer unique ID", filterable=True),
                ColumnDef("CustomerName", "CustomerName", "string", "Customer full name"),
                ColumnDef(c.CUSTOMERS_FILTER_DATE_COLUMN, "CreatedDate", "date", "Account creation date", filterable=True),
                ColumnDef("BranchId", "BranchId", "string", "Assigned branch", filterable=True),
                ColumnDef("Segment", "Segment", "string", "Customer segment / tier", filterable=True),
                ColumnDef("TotalSpend", "TotalSpend", "number", "Lifetime spend", aggregatable=True),
            ],
        ),

        TableDef(
            name=c.STOCK_VIEW,
            alias="StockData",
            description="Inventory and stock movement data.",
            primary_use="Stock levels, inventory turns, out-of-stock detection.",
            date_column=c.STOCK_FILTER_DATE_COLUMN,
            sample_queries=["Low stock items", "Stock value by category"],
            columns=[
                ColumnDef("ItemId", "ItemId", "string", "Item identifier", filterable=True),
                ColumnDef("ItemName", "ItemName", "string", "Item description"),
                ColumnDef("Category", "Category", "string", "Item category", filterable=True),
                ColumnDef("OnHandQty", "OnHandQuantity", "number", "Current on-hand quantity", aggregatable=True),
                ColumnDef("ReorderLevel", "ReorderLevel", "number", "Minimum stock threshold"),
                ColumnDef(c.STOCK_FILTER_DATE_COLUMN, "EntryDate", "date", "Stock entry date", filterable=True),
                ColumnDef("UnitCost", "UnitCost", "number", "Cost per unit", aggregatable=True),
                ColumnDef("StockValue", "StockValue", "number", "Total inventory value", aggregatable=True),
            ],
        ),

        TableDef(
            name=c.SALESPERSON_TABLE,
            alias="Salesperson",
            description="Salesperson master — names, branch assignments, targets.",
            primary_use="Salesperson lookups, performance ranking.",
            sample_queries=["Top salesperson by revenue"],
            columns=[
                ColumnDef("SalesPersonId", "SalesPersonId", "string", "Salesperson ID", filterable=True),
                ColumnDef("SalesPersonName", "SalesPersonName", "string", "Full name"),
                ColumnDef("BranchId", "BranchId", "string", "Assigned branch", filterable=True),
                ColumnDef("Target", "Target", "number", "Monthly sales target", aggregatable=True),
            ],
        ),
    ]


# ─── Glossary ─────────────────────────────────────────────────────────────────

GLOSSARY: Dict[str, str] = {
    "MTD": "Month-to-Date — from the first of the current month to today",
    "YTD": "Year-to-Date — from January 1st of the current year to today",
    "QTD": "Quarter-to-Date — from the first of the current quarter to today",
    "net sales": "Sales revenue after discounts and returns",
    "gross sales": "Sales revenue before any discounts",
    "branch": "A physical retail/distribution location",
    "category": "Product classification group (CategoryShortName)",
    "department": "Operational division (DepartmentShortName)",
    "transaction count": "Number of invoices/sales transactions",
    "customer count": "Number of unique customers who made purchases",
    "inventory": "Current on-hand stock levels across all items",
    "stock value": "Total monetary value of current inventory (OnHandQty × UnitCost)",
    "reorder": "Stock level that triggers a purchase order",
}


# ─── Singleton ────────────────────────────────────────────────────────────────

_schema_cache: Optional[List[TableDef]] = None


def get_schema() -> List[TableDef]:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = _build_schema()
    return _schema_cache


# ─── Prompt Builder ───────────────────────────────────────────────────────────

def build_schema_prompt(table_aliases: Optional[List[str]] = None) -> str:
    tables = get_schema()
    if table_aliases:
        tables = [t for t in tables if t.alias in table_aliases]

    lines: List[str] = ["## Available Database Views\n"]

    for t in tables:
        lines.append(f"### {t.alias} ({t.name})")
        lines.append(f"**Purpose:** {t.description}")
        lines.append(f"**Best for:** {t.primary_use}")
        if t.date_column:
            lines.append(f"**Date filter column:** `{t.date_column}`")
        if t.branch_column:
            lines.append(f"**Branch filter column:** `{t.branch_column}`")
        lines.append("\n**Columns:**")
        for col in t.columns:
            tags = []
            if col.filterable:
                tags.append("filterable")
            if col.aggregatable:
                tags.append("aggregatable")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            lines.append(f"- `{col.name}` ({col.col_type}){tag_str} — {col.description}")
        if t.sample_queries:
            lines.append("\n**Example queries:** " + ", ".join(f'"{q}"' for q in t.sample_queries))
        lines.append("")

    lines.append("## Business Glossary\n")
    for term, defn in GLOSSARY.items():
        lines.append(f"- **{term}**: {defn}")

    return "\n".join(lines)


# ─── Table Inference ──────────────────────────────────────────────────────────

KEYWORDS: Dict[str, List[str]] = {
    "SalesReport":     ["sale", "revenue", "category", "department", "branch", "report", "performance"],
    "SalesBase":       ["invoice", "item", "customer", "salesperson", "detailed", "product"],
    "AISalesData":     ["trend", "daily", "monthly", "growth", "comparison", "mtd", "ytd", "qtd"],
    "BranchInfo":      ["branch", "location", "region", "store"],
    "CustomerDetails": ["customer", "client", "new customer", "acquisition", "segment"],
    "StockData":       ["stock", "inventory", "item", "on hand", "reorder", "unit", "low stock"],
    "Salesperson":     ["salesperson", "sales rep", "agent", "staff", "target"],
}


def infer_relevant_tables(query: str) -> List[str]:
    q = query.lower()
    scores: Dict[str, int] = {}

    for alias, kws in KEYWORDS.items():
        score = sum(2 for kw in kws if kw in q)
        if score > 0:
            scores[alias] = score

    sorted_tables = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result = [alias for alias, _ in sorted_tables[:3]]
    return result if result else ["SalesReport", "AISalesData"]
