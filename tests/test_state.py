from ingestion.state import load_state, save_state


def test_state_round_trip(tmp_path):
    path = tmp_path / "metadata" / "state.json"
    state = {
        "postgres_watermarks": {
            "orders": {"timestamp": "2026-01-01T00:00:00+00:00", "primary_key": "order-1"}
        },
        "processed_event_files": {"event_date=2026-01-01/events.jsonl": "checksum"},
    }

    save_state(path, state)

    assert load_state(path) == state

