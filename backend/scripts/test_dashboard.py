import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.db.mssql import init_mssql, close_mssql
from src.analytics.dashboard import get_dashboard


async def main() -> None:
    await init_mssql()
    data = await get_dashboard("mtd")
    print("OK period=", data["period_label"])
    print("sales=", data["summary"]["mtd_sales"])
    print("trend points=", len(data["trend"]))
    await close_mssql()


if __name__ == "__main__":
    asyncio.run(main())
