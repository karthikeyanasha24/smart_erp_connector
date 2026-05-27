"""
JWT Engine
Signs and verifies access + refresh tokens using HS256.
Token payload carries user_id, email, role, and branch_ids.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

import jwt as pyjwt

from src.config import cfg
from src.utils.logger import logger

# ─── Payload ──────────────────────────────────────────────────────────────────

@dataclass
class TokenPayload:
    user_id: str
    email: str
    role: str
    branch_ids: List[str]
    exp: int
    iat: int
    token_type: str = "access"   # "access" | "refresh"


# ─── Constants ────────────────────────────────────────────────────────────────

_ALGORITHM = "HS256"
_ACCESS_TTL = 24 * 3600        # 24 h
_REFRESH_TTL = 30 * 24 * 3600  # 30 days


def _secret() -> str:
    return cfg.JWT_SECRET


# ─── Sign ─────────────────────────────────────────────────────────────────────

def sign_access_token(
    user_id: str,
    email: str,
    role: str,
    branch_ids: Optional[List[str]] = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "branch_ids": branch_ids or [],
        "type": "access",
        "iat": now,
        "exp": now + _ACCESS_TTL,
    }
    return pyjwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def sign_refresh_token(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + _REFRESH_TTL,
    }
    return pyjwt.encode(payload, _secret(), algorithm=_ALGORITHM)


# ─── Verify ───────────────────────────────────────────────────────────────────

def verify_token(token: str, expected_type: str = "access") -> Optional[TokenPayload]:
    try:
        raw = pyjwt.decode(token, _secret(), algorithms=[_ALGORITHM])

        if raw.get("type") != expected_type:
            logger.warning("Token type mismatch", expected=expected_type, got=raw.get("type"))
            return None

        return TokenPayload(
            user_id=raw["sub"],
            email=raw.get("email", ""),
            role=raw.get("role", "viewer"),
            branch_ids=raw.get("branch_ids", []),
            exp=raw["exp"],
            iat=raw["iat"],
            token_type=raw.get("type", "access"),
        )

    except pyjwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except pyjwt.InvalidTokenError as exc:
        logger.debug("Invalid token", error=str(exc))
        return None
    except Exception as exc:
        logger.error("Token verification error", error=str(exc))
        return None
