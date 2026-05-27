"""
Auth Routes
POST /auth/login
GET  /auth/me
POST /auth/logout
POST /auth/users          (admin)
GET  /auth/users          (admin)
PATCH /auth/users/{id}    (admin)
DELETE /auth/users/{id}   (admin)
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from src.auth.jwt import sign_access_token, sign_refresh_token
from src.auth.rbac import (
    authenticate, create_user, delete_user, get_user_by_id,
    list_users, update_user, audit_log, init_rbac, create_session, invalidate_session,
)
from src.middleware.auth import get_current_user, require_roles
from src.auth.jwt import TokenPayload
from src.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)
    password: str = Field(min_length=6)
    role: str = "viewer"
    branch_ids: Optional[List[str]] = None


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    branch_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, request: Request) -> Dict[str, Any]:
    from src.config import cfg

    if not cfg.RBAC_ENABLED:
        # Dev bypass — return a mock token
        token = sign_access_token("dev", "dev@local", "admin", [])
        return {
            "success": True,
            "access_token": token,
            "user": {"id": "dev", "email": "dev@local", "role": "admin", "name": "Dev User"},
        }

    user = await authenticate(body.email, body.password)
    if user is None:
        await audit_log("login_failed", resource=body.email, ip_address=request.client.host if request.client else None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    access_token = sign_access_token(
        user_id=str(user["id"]),
        email=user["email"],
        role=user["role"],
        branch_ids=list(user.get("branch_ids") or []),
    )
    refresh_token = sign_refresh_token(str(user["id"]))

    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        await create_session(
            str(user["id"]), refresh_token, expires_at,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as exc:
        logger.warning("Session creation failed", error=str(exc))

    await audit_log("login_success", user_id=str(user["id"]), ip_address=request.client.host if request.client else None)

    return {
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "branch_ids": list(user.get("branch_ids") or []),
        },
    }


@router.get("/me")
async def me(user: TokenPayload = Depends(get_current_user)) -> Dict[str, Any]:
    full = await get_user_by_id(user.user_id)
    return {
        "success": True,
        "user": {
            "id": user.user_id,
            "email": user.email,
            "role": user.role,
            "branch_ids": user.branch_ids,
            "name": full["name"] if full else "",
        },
    }


@router.post("/logout")
async def logout(request: Request, user: TokenPayload = Depends(get_current_user)) -> Dict[str, Any]:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if token:
        try:
            await invalidate_session(token)
        except Exception:
            pass
    return {"success": True, "message": "Logged out"}


# ─── User Management (admin) ──────────────────────────────────────────────────

@router.post("/users", dependencies=[Depends(require_roles("admin"))])
async def create_new_user(body: CreateUserRequest) -> Dict[str, Any]:
    try:
        user = await create_user(
            email=body.email,
            name=body.name,
            password=body.password,
            role=body.role,
            branch_ids=body.branch_ids,
        )
        return {"success": True, "user": user}
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Email already exists")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/users", dependencies=[Depends(require_roles("admin", "manager"))])
async def get_users(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    users = await list_users(limit=limit, offset=offset)
    return {
        "success": True,
        "users": [
            {k: str(v) if hasattr(v, "hex") else v for k, v in u.items() if k != "password"}
            for u in users
        ],
        "count": len(users),
    }


@router.patch("/users/{user_id}", dependencies=[Depends(require_roles("admin"))])
async def update_existing_user(user_id: str, body: UpdateUserRequest) -> Dict[str, Any]:
    updated = await update_user(user_id, **body.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "user": {k: v for k, v in updated.items() if k != "password"}}


@router.delete("/users/{user_id}", dependencies=[Depends(require_roles("admin"))])
async def deactivate_user(user_id: str) -> Dict[str, Any]:
    ok = await delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": "User deactivated"}
