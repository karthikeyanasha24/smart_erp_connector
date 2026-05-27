"""SQL Server object name helpers."""


def sql_table(qualified_name: str) -> str:
    """
    Convert 'dbo.VW_MB_POWERBI_APP_REPORT' → '[dbo].[VW_MB_POWERBI_APP_REPORT]'.
    A single bracket like '[dbo.VW_MB_POWERBI_APP_REPORT]' is invalid in SQL Server.
    """
    name = (qualified_name or "").strip()
    if not name:
        return name
    if "." in name:
        schema, obj = name.split(".", 1)
        return f"[{schema.strip()}].[{obj.strip()}]"
    return f"[{name}]"
