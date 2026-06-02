import json
import sqlite3
from pathlib import Path

import pytest

from transformation.build_analytics import build_analytics


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def make_raw_data(raw_dir: Path) -> None:
    write_jsonl(
        raw_dir / "postgres/customers/extract_1.jsonl",
        [{"customer_id": "c1", "name": "Alex", "email": "alex@example.com", "country": "US", "created_at": "2026-01-01T00:00:00+00:00"}],
    )
    write_jsonl(
        raw_dir / "postgres/products/extract_1.jsonl",
        [{"product_id": "p1", "name": "Lamp", "category": "home", "price": "10.00", "updated_at": "2026-01-01T00:00:00+00:00"}],
    )
    write_jsonl(
        raw_dir / "postgres/orders/extract_1.jsonl",
        [{"order_id": "o1", "customer_id": "c1", "status": "paid", "order_total": "20.00", "created_at": "2026-01-02T00:00:00+00:00", "updated_at": "2026-01-02T00:00:00+00:00"}],
    )
    write_jsonl(
        raw_dir / "postgres/order_items/extract_1.jsonl",
        [{"order_item_id": "i1", "order_id": "o1", "product_id": "p1", "quantity": 2, "unit_price": "10.00", "_source_updated_at": "2026-01-02T00:00:00+00:00"}],
    )
    write_jsonl(
        raw_dir / "events/event_date=2026-01-02/events_one.jsonl",
        [{"event_id": "e1", "event_type": "add_to_cart", "customer_id": "c1", "product_id": "p1", "timestamp": "2026-01-02T00:00:00+00:00"}],
    )


def test_build_analytics_creates_facts_and_marts(tmp_path):
    raw_dir = tmp_path / "raw"
    output_path = tmp_path / "analytics.db"
    make_raw_data(raw_dir)

    counts = build_analytics(raw_dir, output_path)

    assert counts == {"customers": 1, "products": 1, "orders": 1, "order_items": 1, "events": 1}
    with sqlite3.connect(output_path) as connection:
        assert connection.execute("SELECT line_total FROM fct_order_items").fetchone() == (20,)
        assert connection.execute("SELECT gross_revenue, net_revenue FROM mart_daily_sales").fetchone() == (20, 20)
        assert connection.execute("SELECT add_to_cart_count, units_sold FROM mart_product_performance").fetchone() == (1, 2)


def test_build_analytics_keeps_latest_raw_version(tmp_path):
    raw_dir = tmp_path / "raw"
    output_path = tmp_path / "analytics.db"
    make_raw_data(raw_dir)
    write_jsonl(
        raw_dir / "postgres/orders/extract_2.jsonl",
        [{"order_id": "o1", "customer_id": "c1", "status": "cancelled", "order_total": "20.00", "created_at": "2026-01-02T00:00:00+00:00", "updated_at": "2026-01-03T00:00:00+00:00"}],
    )

    build_analytics(raw_dir, output_path)

    with sqlite3.connect(output_path) as connection:
        assert connection.execute("SELECT status FROM fct_orders").fetchone() == ("cancelled",)
        assert connection.execute("SELECT net_revenue FROM mart_daily_sales").fetchone() == (0,)


def test_build_analytics_rejects_orphaned_order_items(tmp_path):
    raw_dir = tmp_path / "raw"
    output_path = tmp_path / "analytics.db"
    make_raw_data(raw_dir)
    write_jsonl(
        raw_dir / "postgres/order_items/extract_2.jsonl",
        [{"order_item_id": "i2", "order_id": "missing", "product_id": "p1", "quantity": 1, "unit_price": "10.00", "_source_updated_at": "2026-01-03T00:00:00+00:00"}],
    )

    with pytest.raises(ValueError, match="order items reference orders"):
        build_analytics(raw_dir, output_path)

