"""
RBAC — Role-Based Access Control
User CRUD, password hashing, role assignment, permission checks, audit logging.
Backed by PostgreSQL (asyncpg).
"""

from __future__ import annotations

import json
import secrets
import uuid
from typing import Any, Dict, List, Optional

import bcrypt

from src.config import cfg
from src.utils.logger import logger
from src.db.postgres import pg_execute, pg_fetch_one, pg_query, pg_fetch_val, init_schema


# ─── Password ─────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ─── User Management ──────────────────────────────────────────────────────────

async def create_user(
    email: str,
    name: str,
    password: str,
    role: str = "viewer",
    branch_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    uid = str(uuid.uuid4())
    pw_hash = hash_password(password)
    branches = branch_ids or []

    await pg_execute(
        """INSERT INTO users (id, email, name, password, role, branch_ids)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        uid, email.lower().strip(), name, pw_hash, role, branches,
    )
    return {"id": uid, "email": email, "name": name, "role": role, "branch_ids": branches}


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return await pg_fetch_one(
        "SELECT * FROM users WHERE email = $1 AND is_active = TRUE",
        email.lower().strip(),
    )


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return await pg_fetch_one(
        "SELECT id, email, name, role, branch_ids, is_active, created_at, updated_at FROM users WHERE id = $1",
        user_id,
    )


async def list_users(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    return await pg_query(
        "SELECT id, email, name, role, branch_ids, is_active, created_at FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit, offset,
    )


async def update_user(
    user_id: str,
    **fields: Any,
) -> Optional[Dict[str, Any]]:
    allowed = {"name", "role", "branch_ids", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return await get_user_by_id(user_id)

    if "password" in fields:
        updates["password"] = hash_password(fields["password"])

    set_clauses = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())

    await pg_execute(
        f"UPDATE users SET {set_clauses}, updated_at = NOW() WHERE id = $1",
        user_id, *values,
    )
    return await get_user_by_id(user_id)


async def delete_user(user_id: str) -> bool:
    result = await pg_execute(
        "UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = $1",
        user_id,
    )
    return "UPDATE 1" in result


# ─── Authentication ───────────────────────────────────────────────────────────

async def authenticate(email: str, password: str) -> Optional[Dict[str, Any]]:
    user = await pg_fetch_one(
        "SELECT * FROM users WHERE email = $1 AND is_active = TRUE",
        email.lower().strip(),
    )
    if user is None:
        return None
    if not verify_password(password, user["password"]):
        return None
    return dict(user)


# ─── Session Management ───────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    user_id: str,
    token: str,
    expires_at: Any,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    sid = str(uuid.uuid4())
    token_hash = _hash_token(token)
    await pg_execute(
        """INSERT INTO sessions (id, user_id, token_hash, expires_at, ip_address, user_agent)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        sid, user_id, token_hash, expires_at, ip_address, user_agent,
    )
    return sid


async def invalidate_session(token: str) -> None:
    token_hash = _hash_token(token)
    await pg_execute("DELETE FROM sessions WHERE token_hash = $1", token_hash)


async def invalidate_all_sessions(user_id: str) -> None:
    await pg_execute("DELETE FROM sessions WHERE user_id = $1", user_id)


# ─── Permissions ──────────────────────────────────────────────────────────────

_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin":   ["*"],
    "manager": ["read:*", "export:*", "query:*"],
    "analyst": ["read:*", "query:*"],
    "viewer":  ["read:own"],
}


def has_permission(role: str, permission: str) -> bool:
    perms = _ROLE_PERMISSIONS.get(role, [])
    if "*" in perms:
        return True
    if permission in perms:
        return True
    # Wildcard match: "read:*" covers "read:sales"
    for p in perms:
        if p.endswith(":*"):
            prefix = p[:-2]
            if permission.startswith(prefix + ":"):
                return True
    return False


# ─── Audit Log ────────────────────────────────────────────────────────────────

async def audit_log(
    action: str,
    user_id: Optional[str] = None,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    try:
        await pg_execute(
            """INSERT INTO audit_log (user_id, action, resource, details, ip_address)
               VALUES ($1, $2, $3, $4::jsonb, $5)""",
            user_id,
            action,
            resource,
            json.dumps(details) if details else None,
            ip_address,
        )
    except Exception as exc:
        logger.error("Audit log write failed", error=str(exc))


# ─── Admin Bootstrap ──────────────────────────────────────────────────────────

async def ensure_app_user() -> None:
    """Ensure the primary app login exists (from env or defaults)."""
    import os

    email = os.getenv("APP_LOGIN_EMAIL", "asha24@gmail.com").lower().strip()
    password = os.getenv("APP_LOGIN_PASSWORD", "123456789")
    name = os.getenv("APP_LOGIN_NAME", "karthikeyan")
    role = os.getenv("APP_LOGIN_ROLE", "admin")

    existing = await get_user_by_email(email)
    if existing:
        await pg_execute(
            "UPDATE users SET name = $1, password = $2, role = $3, is_active = TRUE WHERE email = $4",
            name,
            hash_password(password),
            role,
            email,
        )
        logger.info("App login user synced", email=email)
        return

    try:
        await create_user(email, name, password, role)
        logger.info("App login user created", email=email)
    except Exception as exc:
        if "unique" not in str(exc).lower():
            logger.warning("App user create skipped", error=str(exc))


async def bootstrap_admin() -> None:
    """Create the default admin user if no users exist."""
    count = await pg_fetch_val("SELECT COUNT(*) FROM users")
    if count and count > 0:
        return

    password = cfg.ADMIN_DEFAULT_PASSWORD or secrets.token_urlsafe(16)
    try:
        user = await create_user(
            email="admin@smarterpconnector.com",
            name="Admin",
            password=password,
            role="admin",
        )
        logger.info(
            "Default admin created",
            email=user["email"],
            password="[set from env]" if cfg.ADMIN_DEFAULT_PASSWORD else password,
        )
    except Exception as exc:
        logger.warning("Admin bootstrap skipped", error=str(exc))


# ─── Init ─────────────────────────────────────────────────────────────────────

async def init_rbac() -> None:
    if not cfg.RBAC_ENABLED:
        logger.info("RBAC disabled")
        return
    await init_schema()
    await bootstrap_admin()
    await ensure_app_user()
    logger.info("RBAC initialized")
