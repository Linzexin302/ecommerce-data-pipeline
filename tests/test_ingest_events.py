from pathlib import Path

from ingestion.ingest_events import ingest_event_files


def write_source_event(source_dir: Path, event_date: str, content: str) -> None:
    partition = source_dir / f"event_date={event_date}"
    partition.mkdir(parents=True, exist_ok=True)
    (partition / "events.jsonl").write_text(content, encoding="utf-8")


def test_event_ingestion_is_idempotent(tmp_path):
    source_dir = tmp_path / "generated_events"
    raw_dir = tmp_path / "raw"
    state = {}
    write_source_event(source_dir, "2026-01-01", '{"event_id": "one"}\n')

    assert ingest_event_files(source_dir, raw_dir, state) == 1
    assert ingest_event_files(source_dir, raw_dir, state) == 0
    assert len(list((raw_dir / "events").rglob("*.jsonl"))) == 1


def test_changed_event_file_creates_new_raw_copy(tmp_path):
    source_dir = tmp_path / "generated_events"
    raw_dir = tmp_path / "raw"
    state = {}
    write_source_event(source_dir, "2026-01-01", '{"event_id": "one"}\n')
    ingest_event_files(source_dir, raw_dir, state)

    write_source_event(
        source_dir,
        "2026-01-01",
        '{"event_id": "one"}\n{"event_id": "late"}\n',
    )

    assert ingest_event_files(source_dir, raw_dir, state) == 2
    assert len(list((raw_dir / "events").rglob("*.jsonl"))) == 2
