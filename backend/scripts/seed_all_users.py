#!/usr/bin/env python3
"""
Seed all default users (admin, manager, viewer) into PostgreSQL RBAC database.

Usage (from backend/ directory):
    python scripts/seed_all_users.py

Users created:
    admin   → asha24@gmail.com      / 19375862@!@AK  (from env ADMIN_DEFAULT_PASSWORD)
    manager → manager@smarterp.com  / Manager@2026
    viewer  → viewer@smarterp.com   / Viewer@2026

Roles & permissions:
    admin   — full access: create users, adjust settings, view everything
    manager — analytics + AI Query + read access (cannot manage users)
    viewer  — read-only: dashboard, analytics, transactions, reports, branch, product
"""

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from src.db.postgres import get_pg_pool, init_schema
from src.auth.rbac import create_user, get_user_by_email, hash_password
from src.db.postgres import pg_execute


USERS = [
    {
        "email": "asha24@gmail.com",
        "name": "karthikeyan",
        "password": "19375862@!@AK",  # ADMIN_DEFAULT_PASSWORD from env
        "role": "admin",
    },
    {
        "email": "manager@smarterp.com",
        "name": "Manager User",
        "password": "Manager@2026",
        "role": "manager",
    },
    {
        "email": "viewer@smarterp.com",
        "name": "Viewer User",
        "password": "Viewer@2026",
        "role": "viewer",
    },
]


async def upsert_user(email: str, name: str, password: str, role: str) -> None:
    existing = await get_user_by_email(email)
    if existing:
        await pg_execute(
            """UPDATE users
               SET name = $1,
                   password = $2,
                   role = $3,
                   is_active = TRUE,
                   updated_at = NOW()
               WHERE email = $4""",
            name,
            hash_password(password),
            role,
            email.lower().strip(),
        )
        print(f"  ✅ Updated  {role:10s}  {email}  ({name})")
    else:
        await create_user(email, name, password, role)
        print(f"  ✅ Created  {role:10s}  {email}  ({name})")


async def main() -> None:
    print("\n🔐 SmarterP — seeding RBAC users into PostgreSQL\n")

    pool = await get_pg_pool()
    print(f"  PostgreSQL connected: {pool}")

    await init_schema()
    print("  Schema ensured\n")

    for u in USERS:
        await upsert_user(**u)

    print("\n✔ All users seeded.\n")
    print("Login credentials:")
    print("─" * 60)
    for u in USERS:
        print(f"  Role: {u['role']:10s}  Email: {u['email']:30s}  Password: {u['password']}")
    print("─" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())
