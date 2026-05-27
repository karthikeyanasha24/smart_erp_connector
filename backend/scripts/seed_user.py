#!/usr/bin/env python3
"""Create or update app user. Run from backend/: python scripts/seed_user.py"""

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from src.db.postgres import get_pg_pool, init_schema
from src.auth.rbac import create_user, get_user_by_email, update_user, hash_password
from src.db.postgres import pg_execute


async def main() -> None:
    email = "asha24@gmail.com"
    name = "karthikeyan"
    password = "123456789"
    role = "admin"

    await get_pg_pool()
    await init_schema()

    existing = await get_user_by_email(email)
    if existing:
        await pg_execute(
            "UPDATE users SET name = $1, password = $2, role = $3, is_active = TRUE WHERE email = $4",
            name,
            hash_password(password),
            role,
            email.lower().strip(),
        )
        print(f"Updated user: {email} ({name}) role={role}")
    else:
        user = await create_user(email, name, password, role)
        print(f"Created user: {user['email']} ({user['name']}) role={role}")


if __name__ == "__main__":
    asyncio.run(main())
