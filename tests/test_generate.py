from datetime import date

import pytest

from data_generator.generate import generate_data, write_events


def test_generation_is_reproducible():
    first = generate_data(date(2026, 1, 1), days=2, seed=42)
    second = generate_data(date(2026, 1, 1), days=2, seed=42)

    assert first == second
    assert len(first.customers) == 8
    assert len(first.products) == 8
    assert len(first.orders) == 16


def test_order_total_matches_items():
    data = generate_data(date(2026, 1, 1), days=3, seed=7)

    for order in data.orders:
        items = [item for item in data.order_items if item["order_id"] == order["order_id"]]
        expected_total = sum(item["quantity"] * item["unit_price"] for item in items)
        assert order["order_total"] == expected_total


def test_events_are_written_in_date_partitions(tmp_path):
    data = generate_data(date(2026, 1, 1), days=2, seed=42)

    write_events(data.events, tmp_path)

    partitions = sorted(path.name for path in tmp_path.iterdir())
    assert partitions == ["event_date=2026-01-01", "event_date=2026-01-02"]
    assert (tmp_path / "event_date=2026-01-01" / "events.jsonl").read_text()


def test_days_must_be_positive():
    with pytest.raises(ValueError, match="days must be at least 1"):
        generate_data(date(2026, 1, 1), days=0, seed=42)

