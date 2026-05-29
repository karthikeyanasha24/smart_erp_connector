#!/usr/bin/env python3
"""
Convert backend/schema_catalog.txt → backend/data/schema_catalog.json

Usage (from backend/):
    python scripts/schema_catalog_to_json.py
    python scripts/schema_catalog_to_json.py --input schema_catalog.txt --output data/schema_catalog.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]

OBJECT_HEADER = re.compile(
    r"^(\d+)\.\s+(dbo\.\S+)\s+—\s+(.+)$",
    re.UNICODE,
)
COLUMN_HEADER = "Column\tType\tUsed for"


def parse_schema_catalog(text: str) -> Dict[str, Any]:
    lines = text.splitlines()
    database = ""
    title = lines[0].strip() if lines else ""

    for line in lines[:6]:
        if line.startswith("Database:"):
            database = line.split(":", 1)[1].strip()

    object_counts = {"views": 0, "tables": 0, "total": 0}
    for line in lines[:6]:
        m = re.search(r"Objects:\s*(\d+)\s*\((\d+)\s*views,\s*(\d+)\s*tables\)", line)
        if m:
            object_counts = {
                "total": int(m.group(1)),
                "views": int(m.group(2)),
                "tables": int(m.group(3)),
            }
            break

    objects: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        m = OBJECT_HEADER.match(lines[i].strip())
        if not m:
            i += 1
            continue

        catalog_no = int(m.group(1))
        fqn = m.group(2)
        obj_title = m.group(3).strip()
        i += 1

        description_parts: List[str] = []
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == COLUMN_HEADER or OBJECT_HEADER.match(stripped):
                break
            if stripped and not stripped.startswith("="):
                description_parts.append(stripped)
            i += 1

        description = " ".join(description_parts).strip()

        if i < len(lines) and lines[i].strip() == COLUMN_HEADER:
            i += 1

        columns: List[Dict[str, str]] = []
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped:
                i += 1
                continue
            if OBJECT_HEADER.match(stripped) or stripped.startswith("="):
                break
            if stripped == COLUMN_HEADER:
                i += 1
                continue
            parts = lines[i].split("\t")
            if len(parts) >= 3:
                columns.append({
                    "name": parts[0].strip(),
                    "type": parts[1].strip(),
                    "used_for": parts[2].strip(),
                })
            i += 1

        short_name = fqn.split(".")[-1]
        objects.append({
            "catalog_no": catalog_no,
            "fqn": fqn,
            "short_name": short_name,
            "title": obj_title,
            "description": description,
            "object_type": "view",
            "column_count": len(columns),
            "columns": columns,
        })

    return {
        "title": title,
        "database": database,
        "object_counts": object_counts,
        "objects": objects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert schema_catalog.txt to JSON")
    parser.add_argument(
        "--input",
        type=Path,
        default=BACKEND_ROOT / "schema_catalog.txt",
        help="Source text catalog",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_ROOT / "data" / "schema_catalog.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    text = args.input.read_text(encoding="utf-8")
    payload = parse_schema_catalog(text)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    n = len(payload["objects"])
    cols = sum(o["column_count"] for o in payload["objects"])
    print(f"Wrote {args.output} — {n} objects, {cols} columns")


if __name__ == "__main__":
    main()
