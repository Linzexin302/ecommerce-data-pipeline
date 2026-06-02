"""Read and write local ingestion checkpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EMPTY_STATE = {"postgres_watermarks": {}, "processed_event_files": {}}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"postgres_watermarks": {}, "processed_event_files": {}}
    with path.open(encoding="utf-8") as state_file:
        state = json.load(state_file)
    state.setdefault("postgres_watermarks", {})
    state.setdefault("processed_event_files", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2, sort_keys=True)
        state_file.write("\n")
    temporary_path.replace(path)

