#!/usr/bin/env python3
"""Create/update MB India team users. Run from backend/: python scripts/seed_mb_users.py"""

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from src.db.postgres import get_pg_pool, init_schema, pg_execute
from src.auth.rbac import create_user, get_user_by_email, hash_password

USERS = [
    {"email": "manoj.kumar@mbindia.net", "name": "Manoj Kumar", "password": "123456789", "role": "admin"},
    {"email": "karthikeyanasha24@gmail.com", "name": "Karthikeyan", "password": "123456789", "role": "admin"},
    {"email": "karam@mbindia.net", "name": "Karam", "password": "123456789", "role": "admin"},
]


async def upsert_user(email: str, name: str, password: str, role: str) -> None:
    key = email.lower().strip()
    existing = await get_user_by_email(key)
    if existing:
        await pg_execute(
            """UPDATE users
               SET name = $1, password = $2, role = $3, is_active = TRUE, updated_at = NOW()
               WHERE email = $4""",
            name,
            hash_password(password),
            role,
            key,
        )
        print(f"Updated  {role:6s}  {key}  ({name})")
    else:
        await create_user(email, name, password, role)
        print(f"Created  {role:6s}  {key}  ({name})")


async def main() -> None:
    await get_pg_pool()
    await init_schema()
    for u in USERS:
        await upsert_user(**u)


if __name__ == "__main__":
    asyncio.run(main())
