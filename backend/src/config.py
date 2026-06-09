"""
Configuration -- reads all values from environment variables via pydantic-settings.
Zero hardcoding. Copy .env.example to .env and fill in your values.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Server -------------------------------------------------------------------
    PORT: int = 3000
    NODE_ENV: str = "development"
    TRUST_PROXY: bool = False

    @property
    def is_dev(self) -> bool:
        return self.NODE_ENV == "development"

    # -- SQL Server ---------------------------------------------------------------
    DB_SERVER: str = ""
    DB_PORT: int = 1433
    DB_NAME: str = ""
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_CONNECT_TIMEOUT_MS: int = 60000
    DB_REQUEST_TIMEOUT_MS: int = 300000
    DB_POOL_MAX: int = 20
    DB_POOL_ACQUIRE_TIMEOUT_MS: int = 180000

    # Fallback aliases
    ERP_DB_HOST: str = ""
    ERP_DB_PORT: int = 1433
    ERP_DB_NAME: str = ""
    ERP_DB_USER: str = ""
    ERP_DB_PASSWORD: str = ""

    @property
    def mssql_server(self) -> str:
        return self.DB_SERVER or self.ERP_DB_HOST

    @property
    def mssql_port(self) -> int:
        return self.DB_PORT or self.ERP_DB_PORT

    @property
    def mssql_database(self) -> str:
        return self.DB_NAME or self.ERP_DB_NAME

    @property
    def mssql_user(self) -> str:
        return self.DB_USER or self.ERP_DB_USER

    @property
    def mssql_password(self) -> str:
        return self.DB_PASSWORD or self.ERP_DB_PASSWORD

    @property
    def mssql_connect_timeout(self) -> int:
        return self.DB_CONNECT_TIMEOUT_MS // 1000

    @property
    def mssql_request_timeout(self) -> int:
        return self.DB_REQUEST_TIMEOUT_MS // 1000

    # -- PostgreSQL ---------------------------------------------------------------
    DATABASE_URL: str = ""
    RBAC_DATABASE_URL: str = ""
    RBAC_ENABLED: bool = True
    RBAC_PERSIST: bool = True

    @property
    def rbac_url(self) -> str:
        return self.RBAC_DATABASE_URL or self.DATABASE_URL

    # -- AI / LLM -----------------------------------------------------------------
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_PROJECT: str = "smarterpconnector"
    LANGSMITH_TRACING: bool = False

    # -- Auth ---------------------------------------------------------------------
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRES_IN: str = "24h"
    ADMIN_DEFAULT_PASSWORD: str = ""

    # -- Analytics Views ----------------------------------------------------------
    ANALYTICS_BASE_TABLE: str = "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID"
    SALES_AI_TABLE: str = "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID"
    # Item-level queries (top products, product breakdown) — needs ItemId column
    SALES_ITEMS_AI_TABLE: str = "dbo.VW_MB_POWERBI_SLS_REPORT"
    SALES_ITEMS_DATE_COLUMN: str = "XnMemoDate"
    SALES_ITEMS_AMOUNT_COLUMN: str = "NetAmount"
    SALES_ITEMS_QUANTITY_COLUMN: str = "NetSlsQty"
    # Item master -- same default as test/list_products_db.py (Power BI product dimensions)
    PRODUCT_MASTER_VIEW: str = "dbo.VW_MB_POWERBI_PRODUCT_MASTER"
    SALES_VIEW: str = "dbo.VwAISalesData"
    BRANCH_VIEW: str = "dbo.VwAIBranch"
    CUSTOMER_VIEW: str = "dbo.VwAICustomerDetails"
    STOCK_VIEW: str = "dbo.VwAIStockData"
    STOCK_TABLE: str = "dbo.MstStockUnit"
    SALESPERSON_TABLE: str = "dbo.MstSalesPerson"
    SALESPERSON_TOPN_VIEW: str = "dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID"

    # -- Column Mappings ----------------------------------------------------------
    # VW_MB_POWERBI_APP_REPORT columns
    MB_POWERBI_APP_REPORT_FILTER_DATE_COLUMN: str = "XnMemoDate"
    MB_POWERBI_APP_REPORT_FILTER_BRANCH_COLUMN: str = "BranchAlias"
    MB_POWERBI_APP_REPORT_FILTER_CATEGORY_COLUMN: str = "CategoryShortName"
    MB_POWERBI_APP_REPORT_FILTER_DEPARTMENT_COLUMN: str = "DepartmentShortName"
    # SLS_REPORT: NetAmount, NetSlsQty, row-count bills; APP_REPORT: BillCount, AppQty
    SALES_ANALYTICS_AMOUNT_COLUMN: str = "NetAmount"
    SALES_ANALYTICS_QUANTITY_COLUMN: str = "NetSlsQty"
    SALES_ANALYTICS_BILL_COUNT_COLUMN: str = "BillCount"
    # "rows" = COUNT line items (SLS_REPORT); "column" = SUM(BillCount) on APP_REPORT
    SALES_ANALYTICS_BILL_COUNT_MODE: str = "rows"
    SALES_ANALYTICS_BRANCH_DIM: str = "BranchAlias"
    SALES_ANALYTICS_CATEGORY_DIM: str = "CategoryShortName"
    SALES_ANALYTICS_DEPARTMENT_DIM: str = "DepartmentShortName"
    # VwAISalesData columns
    SALES_FILTER_DATE_COLUMN: str = "InvoiceDt"
    SALES_FILTER_BRANCH_COLUMN: str = "BranchId"
    # VwAICustomerDetails
    CUSTOMERS_FILTER_DATE_COLUMN: str = "CreatedOn"
    # VwAIStockData
    STOCK_FILTER_DATE_COLUMN: str = "EntryDt"
    # Salesperson view (VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID)
    SALESPERSON_DATE_COLUMN: str = "CashmemoDt"
    SALESPERSON_AMOUNT_COLUMN: str = "SalesNetAmount"
    # SLSXNS transaction-level view
    MB_POWERBI_SLSXNS_AMOUNT_COLUMN: str = "NetSlsNetAmount"

    # -- Analytics Behavior -------------------------------------------------------
    ANALYTICS_CACHE_TTL_MS: int = 1800000   # 30 min -- fresh window; revalidates in background after this
    ANALYTICS_STALE_TTL_MULTIPLIER: int = 96  # stale-ok for up to 48 hrs (96 x 30min)
    # 48 hr stale window means overnight/weekend restarts always load from PG instantly
    # instead of hitting SQL Server cold. Background revalidation keeps data current.
    ANALYTICS_NOLOCK: bool = True
    ANALYTICS_RECOMPILE: bool = True
    ANALYTICS_RECOMPILE_THRESHOLD: int = 30
    ANALYTICS_TOP_N: int = 30
    ANALYTICS_TOP_N_MAX: int = 200
    ANALYTICS_SKIP_CUSTOMER_COUNT: bool = False
    ANALYTICS_WARMUP: bool = True
    # Keep startup warmup focused on dashboard-critical keys only.
    # Deep warmup (last_30d/last_6m/qtd/ytd) can run later via scheduled re-warm.
    ANALYTICS_WARMUP_DEEP: bool = False
    ANALYTICS_WARMUP_INTERVAL_MS: int = 900000
    ANALYTICS_WARMUP_PAUSE_MS: int = 3000
    # Minimal delay so DB pool is ready before warmup fires.
    ANALYTICS_WARMUP_INITIAL_DELAY_MS: int = 1_000

    ANALYTICS_WARMUP_PERIODS: str = "mtd,last_30d"
    HOME_KPI_REQUEST_TIMEOUT_MS: int = 180000
    DATASET_HARD_CAP: int = 500000

    @property
    def warmup_periods(self) -> List[str]:
        return [p.strip() for p in self.ANALYTICS_WARMUP_PERIODS.split(",") if p.strip()]

    # -- NLQ Behavior -------------------------------------------------------------
    NLQ_FAST_PATH: bool = True
    NLQ_INTENT_COMPILER: bool = True
    ADAPTIVE_INTENT_STEP: bool = True
    AI_ADAPTIVE_SUMMARY: bool = True
    AI_SCHEMA_DISABLE: bool = False
    AI_SCHEMA_MAX_TABLES: int = 14
    COGNITIVE_COLUMN_DISCOVERY: bool = True

    # -- SQL Server client (pyodbc on Windows; pymssql/FreeTDS on Render/Linux) ----
    ODBC_DRIVER: str = "ODBC Driver 17 for SQL Server"
    # auto = pyodbc when ODBC drivers exist, else pymssql
    MSSQL_DRIVER: str = "auto"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Convenience shorthand -- import `cfg` everywhere
cfg = get_settings()
