"""Ingest unseen or changed JSONL event files using SHA-256 checksums."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_event_files(
    source_dir: Path,
    raw_dir: Path,
    processed_files: dict[str, str],
) -> int:
    event_count = 0
    for source_path in sorted(source_dir.glob("event_date=*/events.jsonl")):
        relative_path = source_path.relative_to(source_dir).as_posix()
        checksum = file_checksum(source_path)
        if processed_files.get(relative_path) == checksum:
            continue

        partition = source_path.parent.name
        output_path = raw_dir / "events" / partition / f"events_{checksum[:12]}.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not output_path.exists():
            shutil.copyfile(source_path, output_path)
        with source_path.open(encoding="utf-8") as source_file:
            event_count += sum(1 for line in source_file if line.strip())
        processed_files[relative_path] = checksum
    return event_count

