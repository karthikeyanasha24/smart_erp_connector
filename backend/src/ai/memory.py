"""
Conversational Memory Engine
Stores and retrieves multi-turn NLQ conversation history so the AI can
resolve anaphoric references ("now compare with Bangalore", "same but last month").

In-memory cache for the current session; optionally persisted to PostgreSQL.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.config import cfg
from src.utils.logger import logger

# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass
class Turn:
    role: str               # "user" | "assistant"
    content: str
    sql: Optional[str] = None
    intent: Optional[Dict[str, Any]] = None
    result_summary: Optional[str] = None
    ts: float = field(default_factory=time.time)


@dataclass
class Conversation:
    id: str
    user_id: str
    title: str
    turns: List[Turn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


# ─── In-Memory Store ──────────────────────────────────────────────────────────

_conversations: Dict[str, Conversation] = {}
_CONTEXT_WINDOW = 6   # last N turns included in context


def _make_id() -> str:
    import uuid
    return str(uuid.uuid4())


def create_conversation(user_id: str, title: str = "New Conversation") -> Conversation:
    conv_id = _make_id()
    conv = Conversation(id=conv_id, user_id=user_id, title=title)
    _conversations[conv_id] = conv
    return conv


def get_conversation(conv_id: str) -> Optional[Conversation]:
    return _conversations.get(conv_id)


def list_conversations(user_id: str) -> List[Conversation]:
    return sorted(
        [c for c in _conversations.values() if c.user_id == user_id],
        key=lambda c: c.updated_at,
        reverse=True,
    )


def add_turn(
    conv_id: str,
    role: str,
    content: str,
    sql: Optional[str] = None,
    intent: Optional[Dict[str, Any]] = None,
    result_summary: Optional[str] = None,
) -> None:
    conv = _conversations.get(conv_id)
    if conv is None:
        logger.warning("add_turn: conversation not found", conv_id=conv_id)
        return

    turn = Turn(
        role=role,
        content=content,
        sql=sql,
        intent=intent,
        result_summary=result_summary,
    )
    conv.turns.append(turn)
    conv.updated_at = time.time()

    # Persist to PostgreSQL (fire-and-forget) if enabled
    if cfg.RBAC_PERSIST:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_persist_turn(conv_id, turn))
        except RuntimeError:
            pass  # No event loop — skip persistence


async def _persist_turn(conv_id: str, turn: Turn) -> None:
    """Async PostgreSQL persistence, best-effort."""
    import json
    try:
        from src.db.postgres import pg_execute, pg_fetch_one

        # Ensure conversation row exists
        existing = await pg_fetch_one(
            "SELECT id FROM conversations WHERE id = $1", conv_id
        )
        if not existing:
            conv = _conversations.get(conv_id)
            if conv:
                await pg_execute(
                    """INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                       VALUES ($1, $2, $3, NOW(), NOW())
                       ON CONFLICT (id) DO NOTHING""",
                    conv_id, conv.user_id, conv.title,
                )

        await pg_execute(
            """INSERT INTO conversation_turns
               (conversation_id, role, content, sql_query, intent, result_summary)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6)""",
            conv_id,
            turn.role,
            turn.content,
            turn.sql,
            json.dumps(turn.intent) if turn.intent else None,
            turn.result_summary,
        )
    except Exception as exc:
        logger.debug("Failed to persist turn to PostgreSQL", error=str(exc))


def build_context_string(conv_id: str) -> Optional[str]:
    """
    Build a compact natural-language context string from the last N turns.
    This is injected into the intent/SQL prompts so the AI can resolve references.
    """
    conv = _conversations.get(conv_id)
    if conv is None or not conv.turns:
        return None

    recent = conv.turns[-_CONTEXT_WINDOW:]
    lines: List[str] = []
    for t in recent:
        prefix = "User" if t.role == "user" else "AI"
        snippet = t.content[:200]
        if t.sql and t.role == "assistant":
            snippet += f"\n[SQL used: {t.sql[:120]}...]"
        if t.result_summary and t.role == "assistant":
            snippet += f"\n[Result: {t.result_summary}]"
        lines.append(f"{prefix}: {snippet}")

    return "\n".join(lines)


def delete_conversation(conv_id: str) -> bool:
    if conv_id in _conversations:
        del _conversations[conv_id]
        return True
    return False


def clear_user_conversations(user_id: str) -> int:
    to_delete = [c_id for c_id, c in _conversations.items() if c.user_id == user_id]
    for c_id in to_delete:
        del _conversations[c_id]
    return len(to_delete)
