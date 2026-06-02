"""Run incremental PostgreSQL extraction and JSONL event ingestion."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingestion.extract_postgres import create_run_id, extract_all
from ingestion.ingest_events import ingest_event_files
from ingestion.state import load_state, save_state


DEFAULT_DATABASE_URL = "postgresql://ecommerce:ecommerce@localhost:5432/ecommerce"


def append_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as metadata_file:
        metadata_file.write(json.dumps(metadata, sort_keys=True) + "\n")


def run_pipeline(
    database_url: str,
    event_source_dir: Path,
    raw_dir: Path,
    state_path: Path,
) -> dict[str, Any]:
    run_id = create_run_id()
    started_at = datetime.now(timezone.utc).isoformat()
    state = load_state(state_path)
    metadata: dict[str, Any] = {"run_id": run_id, "started_at": started_at}

    try:
        postgres_counts = extract_all(
            database_url,
            raw_dir,
            state["postgres_watermarks"],
            run_id,
        )
        event_count = ingest_event_files(
            event_source_dir,
            raw_dir,
            state["processed_event_files"],
        )
        save_state(state_path, state)
        metadata.update(
            {
                "status": "success",
                "postgres_records": postgres_counts,
                "event_records": event_count,
            }
        )
        return metadata
    except Exception as exc:
        metadata.update({"status": "failed", "error": str(exc)})
        raise
    finally:
        metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
        append_metadata(raw_dir / "metadata" / "pipeline_runs.jsonl", metadata)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--event-source-dir", type=Path, default=Path("generated_data/events"))
    parser.add_argument("--raw-dir", type=Path, default=Path("raw_data"))
    parser.add_argument("--state-path", type=Path, default=Path("raw_data/metadata/state.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = run_pipeline(
        args.database_url,
        args.event_source_dir,
        args.raw_dir,
        args.state_path,
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

