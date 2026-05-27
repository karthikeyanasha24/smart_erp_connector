"""
FastAPI Authentication & Authorization Middleware
Provides reusable dependencies for route protection.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.jwt import verify_token, TokenPayload
from src.auth.rbac import has_permission, get_user_by_id
from src.utils.logger import logger

# ─── Bearer Extractor ─────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def _get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[str]:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    # Also accept from cookie (for browser clients)
    cookie_token = request.cookies.get("access_token")
    return cookie_token


# ─── Current User Dependency ──────────────────────────────────────────────────

def get_current_user(
    request: Request,
    token: Optional[str] = Depends(_get_token_from_request),
) -> TokenPayload:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token, expected_type="access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def get_optional_user(
    request: Request,
    token: Optional[str] = Depends(_get_token_from_request),
) -> Optional[TokenPayload]:
    """Returns None instead of raising if unauthenticated."""
    if not token:
        return None
    return verify_token(token, expected_type="access")


# ─── Role Guard ───────────────────────────────────────────────────────────────

def require_roles(*roles: str):
    """Dependency factory: only users with one of the given roles can proceed."""
    def _dep(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted. Required: {list(roles)}",
            )
        return user
    return _dep


def require_permission(permission: str):
    """Dependency factory: only users with the given permission can proceed."""
    def _dep(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission}' required",
            )
        return user
    return _dep


# ─── Branch Scope ─────────────────────────────────────────────────────────────

def apply_branch_scope(
    requested_branch: Optional[str],
    user: TokenPayload,
) -> Optional[str]:
    """
    Returns the effective branch filter.
    - Admins/managers: use requested_branch (can be None for all)
    - Viewers: restricted to their own branch_ids
    """
    if user.role in ("admin", "manager", "analyst"):
        return requested_branch

    if user.branch_ids:
        if requested_branch and requested_branch in user.branch_ids:
            return requested_branch
        return user.branch_ids[0]   # Default to first allowed branch

    return requested_branch
