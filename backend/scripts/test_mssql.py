import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.db.mssql import init_mssql, execute_raw, close_mssql


async def main() -> None:
    await init_mssql()
    r = await execute_raw("SELECT 1 AS ping")
    print("OK", r)
    await close_mssql()


if __name__ == "__main__":
    asyncio.run(main())
