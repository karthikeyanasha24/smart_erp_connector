# SmarterP Connector — Dev Notes for Claude

## SQL Server Driver (CRITICAL — read before touching mssql.py)

**Problem:** Two ODBC drivers installed: `ODBC Driver 18 for SQL Server` and `SQL Server` (legacy).
- `ODBC Driver 18` fails to connect on this Windows machine (network/cert issue) — wastes ~78s on startup
- `SQL Server` (legacy) connects fine but drops long-running queries with error 10054 (ConnectionWrite)
- `pymssql` (FreeTDS) cannot reach port 12866 on this machine — error 20009 / 10060

**Current working config** (`backend/.env`):
```
MSSQL_DRIVER=pyodbc
ODBC_DRIVER=SQL Server
```
`mssql.py` has auto-retry on 10054 errors so the legacy driver reconnects instead of returning 0.

**DO NOT** switch to `MSSQL_DRIVER=pymssql` for local dev — it cannot reach the SQL Server.
On Render (Linux), pymssql IS used and works fine — it's a local-only limitation.

---

## Key Architecture Notes

- **Date timezone**: Backend uses `today_ist()` from `date_utils.py` (UTC+5:30) everywhere. Never use `date.today()` directly — ERP data is in IST.
- **Bills Generated** = `COUNT(DISTINCT CashmemoNo)` — NOT row count. The main view has multiple rows per invoice (one per product line). `SALES_ANALYTICS_BILL_COUNT_MODE=column` in `.env`.
- **Quantity Sold** = `SUM(SalesQuantity)` = actual units. Power BI's "SalesQuantity" card was a row count — our 241K is correct vs their 269K.
- **YTD** = Indian Financial Year starting April 1. `resolve_date_range('ytd')` uses Apr 1, NOT Jan 1.
- **Cache**: Rolling-period keys (`kpi:today`, `bundle:mtd`, `dashboard:*`) are purged from PostgreSQL on startup. Never persist these. Only fixed-period keys (e.g. `kpi:2026-05`) are safe to persist.

## AI Query FAQ Templates

- Templates live in `test/nlq_faq_kpi.py` and `test/nlq_faq_sql.py`
- Registered via `test_faq_loader.py` → `try_verified_faq()` in `db_chat_pipeline.py`
- SQL safety check strips `--` comments before checking first keyword (fixed in `db_chat_pipeline.py`)
- **AI Business Insights** template (`ai_business_insights`): uses CTEs to avoid `TOP 1 ... ORDER BY` inside `UNION ALL` — SQL Server forbids that pattern. LY comparison uses same-day-range (June 1–4 LY, not full June LY) to match analytics dashboard growth %.

## Render Deployment

- Backend: `smart-erp-backend-aa9k.onrender.com` (Web Service, Python)
- Frontend: `smarterpconnector.in` (Static Site, Vite build)
- Free tier spins down — first request after idle takes ~50s
- Push to `main` branch → auto-deploy triggers for both services
