"""Helpers for immutable JSONL raw files."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID


def json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Cannot serialize value of type {type(value).__name__}")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("x", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, default=json_default, sort_keys=True) + "\n")
            count += 1
    return count

