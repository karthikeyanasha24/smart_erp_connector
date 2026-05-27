"""
SQL Safety & Validation Pipeline
Validates generated SQL before execution:
- Safety blocklist (no mutations, no dangerous patterns)
- Structural checks (balanced parentheses/brackets)
- AI self-correction loop on failure
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import anthropic

from src.config import cfg
from src.utils.logger import logger

# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    valid: bool
    sql: Optional[str]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    corrected: bool = False


# ─── Blocked Patterns ─────────────────────────────────────────────────────────

_BLOCKED = [
    (re.compile(r"\bINSERT\b", re.IGNORECASE), "INSERT statement not allowed"),
    (re.compile(r"\bUPDATE\b", re.IGNORECASE), "UPDATE statement not allowed"),
    (re.compile(r"\bDELETE\b", re.IGNORECASE), "DELETE statement not allowed"),
    (re.compile(r"\bDROP\b", re.IGNORECASE), "DROP statement not allowed"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE not allowed"),
    (re.compile(r"\bCREATE\b", re.IGNORECASE), "CREATE not allowed"),
    (re.compile(r"\bALTER\b", re.IGNORECASE), "ALTER not allowed"),
    (re.compile(r"\bEXEC(?:UTE)?\b", re.IGNORECASE), "EXEC not allowed"),
    (re.compile(r"\bSP_\w+", re.IGNORECASE), "System procedure not allowed"),
    (re.compile(r"\bXP_\w+", re.IGNORECASE), "Extended procedure not allowed"),
    (re.compile(r"\bOPENROWSET\b", re.IGNORECASE), "OPENROWSET not allowed"),
    (re.compile(r"\bBULK\s+INSERT\b", re.IGNORECASE), "BULK INSERT not allowed"),
    (re.compile(r";\s*SELECT", re.IGNORECASE), "Stacked queries not allowed"),
    (re.compile(r"\bWAITFOR\s+DELAY\b", re.IGNORECASE), "Time-delay attack pattern"),
    (re.compile(r"\bINFORMATION_SCHEMA\b", re.IGNORECASE), "Schema enumeration not allowed"),
    (re.compile(r"\bsys\.(?:objects|tables|columns)\b", re.IGNORECASE), "System catalog access not allowed"),
]

_WARNINGS = [
    (re.compile(r"\bWHERE\b", re.IGNORECASE), False, "No WHERE clause — full table scan"),
    (re.compile(r"OPTION\s*\(", re.IGNORECASE), False, "Missing OPTION (RECOMPILE)"),
]


def validate_sql_safety(sql: str) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []
    trimmed = sql.strip()

    # Must start with SELECT
    if not re.match(r"^\s*SELECT\b", trimmed, re.IGNORECASE):
        errors.append("Query must be a SELECT statement")

    # Check blocklist
    for pattern, msg in _BLOCKED:
        if pattern.search(trimmed):
            errors.append(msg)

    # Warnings
    if not re.search(r"\bWHERE\b", trimmed, re.IGNORECASE):
        warnings.append("No WHERE clause — this query scans the entire table")
    if not re.search(r"OPTION\s*\(", trimmed, re.IGNORECASE):
        warnings.append("Missing OPTION (RECOMPILE) hint")

    return ValidationResult(valid=len(errors) == 0, sql=trimmed, errors=errors, warnings=warnings)


def validate_sql_structure(sql: str) -> List[str]:
    issues: List[str] = []

    # Balanced parentheses
    depth = 0
    for ch in sql:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth < 0:
            issues.append("Unbalanced parentheses")
            break
    if depth != 0:
        issues.append("Unbalanced parentheses")

    # Balanced square brackets
    bracket = 0
    for ch in sql:
        if ch == "[":
            bracket += 1
        elif ch == "]":
            bracket -= 1
    if bracket != 0:
        issues.append("Unbalanced square brackets")

    # Stray semicolons (not at end)
    if re.search(r";(?!\s*$)", sql):
        issues.append("Stray semicolon — potential stacked query injection")

    return issues


# ─── AI Self-Correction ───────────────────────────────────────────────────────

_CORRECTION_SYSTEM = """You are a Microsoft SQL Server expert.
Given a broken T-SQL query and the error description, return ONLY the fixed SQL.
No markdown, no explanation. Just the corrected SELECT statement.
Rules:
- Keep the same query intent
- Always use WITH (NOLOCK) on table refs
- Always end with OPTION (RECOMPILE)
- Use @startDate and @endDate as parameter placeholders
- Return only SELECT statements"""

_ai_client: Optional[anthropic.AsyncAnthropic] = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.AsyncAnthropic(api_key=cfg.ANTHROPIC_API_KEY)
    return _ai_client


async def correct_sql(
    sql: str,
    errors: List[str],
    original_query: str,
) -> Optional[str]:
    if not cfg.ANTHROPIC_API_KEY:
        return None

    client = _get_client()
    error_list = "\n- ".join(errors)

    try:
        response = await client.messages.create(
            model=cfg.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=_CORRECTION_SYSTEM,
            messages=[{
                "role": "user",
                "content": f'Original query: "{original_query}"\n\nBroken SQL:\n{sql}\n\nErrors:\n- {error_list}\n\nPlease fix the SQL.',
            }],
        )

        corrected = (response.content[0].text or "").strip() if response.content else ""
        if not corrected or not re.match(r"^\s*SELECT\b", corrected, re.IGNORECASE):
            logger.warning("SQL correction returned invalid result")
            return None

        return corrected

    except Exception as exc:
        logger.error("SQL correction AI call failed", error=str(exc))
        return None


# ─── Full Pipeline ────────────────────────────────────────────────────────────

async def validate_and_correct(
    sql: str,
    original_query: str,
    allow_correction: bool = True,
) -> ValidationResult:
    # Step 1: Safety
    safety = validate_sql_safety(sql)
    if not safety.valid:
        return ValidationResult(valid=False, sql=sql, errors=safety.errors, warnings=safety.warnings)

    # Step 2: Structure
    struct_errors = validate_sql_structure(sql)
    all_errors = safety.errors + struct_errors

    if not all_errors:
        return ValidationResult(valid=True, sql=sql, errors=[], warnings=safety.warnings)

    # Step 3: AI correction
    if allow_correction:
        logger.info("Attempting SQL self-correction", errors=all_errors)
        corrected = await correct_sql(sql, all_errors, original_query)

        if corrected:
            re_safety = validate_sql_safety(corrected)
            re_struct = validate_sql_structure(corrected)
            if re_safety.valid and not re_struct:
                return ValidationResult(
                    valid=True,
                    sql=corrected,
                    errors=[],
                    warnings=re_safety.warnings + safety.warnings,
                    corrected=True,
                )

    return ValidationResult(valid=False, sql=sql, errors=all_errors, warnings=safety.warnings)
