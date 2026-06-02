"""Build a local SQLite analytics warehouse from immutable raw JSONL files."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any


POSTGRES_TABLES = ("customers", "products", "orders", "order_items")

STAGING_SCHEMA_SQL = """
CREATE TABLE stg_customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE stg_products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE stg_orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    status TEXT NOT NULL,
    order_total NUMERIC NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE stg_order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC NOT NULL,
    _source_updated_at TEXT NOT NULL
);

CREATE TABLE stg_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    product_id TEXT,
    order_id TEXT,
    event_timestamp TEXT NOT NULL,
    event_date TEXT NOT NULL
);
"""

ANALYTICS_SCHEMA_SQL = """
CREATE TABLE dim_customers AS
SELECT customer_id, name, email, country, created_at
FROM stg_customers;

CREATE TABLE dim_products AS
SELECT product_id, name, category, price, updated_at
FROM stg_products;

CREATE TABLE fct_orders AS
SELECT order_id, customer_id, status, order_total, created_at, updated_at
FROM stg_orders;

CREATE TABLE fct_order_items AS
SELECT
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    quantity * unit_price AS line_total
FROM stg_order_items;

CREATE TABLE fct_events AS
SELECT event_id, event_type, customer_id, product_id, order_id, event_timestamp, event_date
FROM stg_events;

CREATE TABLE mart_daily_sales AS
SELECT
    substr(created_at, 1, 10) AS order_date,
    COUNT(*) AS order_count,
    COUNT(DISTINCT customer_id) AS customer_count,
    ROUND(SUM(order_total), 2) AS gross_revenue,
    ROUND(SUM(CASE WHEN status != 'cancelled' THEN order_total ELSE 0 END), 2) AS net_revenue,
    ROUND(AVG(order_total), 2) AS average_order_value
FROM fct_orders
GROUP BY substr(created_at, 1, 10)
ORDER BY order_date;

CREATE TABLE mart_product_performance AS
WITH cart_events AS (
    SELECT product_id, COUNT(*) AS add_to_cart_count
    FROM fct_events
    WHERE event_type = 'add_to_cart' AND product_id IS NOT NULL
    GROUP BY product_id
),
product_sales AS (
    SELECT
        product_id,
        SUM(quantity) AS units_sold,
        ROUND(SUM(line_total), 2) AS gross_revenue
    FROM fct_order_items
    GROUP BY product_id
)
SELECT
    products.product_id,
    products.name AS product_name,
    products.category,
    COALESCE(cart_events.add_to_cart_count, 0) AS add_to_cart_count,
    COALESCE(product_sales.units_sold, 0) AS units_sold,
    COALESCE(product_sales.gross_revenue, 0) AS gross_revenue,
    CASE
        WHEN COALESCE(cart_events.add_to_cart_count, 0) = 0 THEN 0
        ELSE ROUND(1.0 * product_sales.units_sold / cart_events.add_to_cart_count, 4)
    END AS units_per_cart_add
FROM dim_products AS products
LEFT JOIN cart_events USING (product_id)
LEFT JOIN product_sales USING (product_id)
ORDER BY gross_revenue DESC, product_name;

CREATE INDEX idx_fct_orders_customer_id ON fct_orders(customer_id);
CREATE INDEX idx_fct_order_items_order_id ON fct_order_items(order_id);
CREATE INDEX idx_fct_order_items_product_id ON fct_order_items(product_id);
CREATE INDEX idx_fct_events_event_date ON fct_events(event_date);
"""


def read_jsonl_files(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in sorted(paths):
        with path.open(encoding="utf-8") as jsonl_file:
            for line_number, line in enumerate(jsonl_file, start=1):
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {path}:{line_number}") from exc


def latest_rows(rows: Iterable[dict[str, Any]], primary_key: str, order_by: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row[primary_key])
        if key not in latest or str(row[order_by]) >= str(latest[key][order_by]):
            latest[key] = row
    return list(latest.values())


def load_postgres_rows(raw_dir: Path, table: str) -> list[dict[str, Any]]:
    rows = read_jsonl_files((raw_dir / "postgres" / table).glob("*.jsonl"))
    if table == "customers":
        return latest_rows(rows, "customer_id", "created_at")
    if table == "products":
        return latest_rows(rows, "product_id", "updated_at")
    if table == "orders":
        return latest_rows(rows, "order_id", "updated_at")
    return latest_rows(rows, "order_item_id", "_source_updated_at")


def load_event_rows(raw_dir: Path) -> list[dict[str, Any]]:
    rows = read_jsonl_files((raw_dir / "events").glob("event_date=*/*.jsonl"))
    return latest_rows(rows, "event_id", "timestamp")


def insert_rows(connection: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        [[row.get(column) for column in columns] for row in rows],
    )


def insert_events(connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    normalized = [
        {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "customer_id": row["customer_id"],
            "product_id": row.get("product_id"),
            "order_id": row.get("order_id"),
            "event_timestamp": row["timestamp"],
            "event_date": row["timestamp"][:10],
        }
        for row in rows
    ]
    insert_rows(connection, "stg_events", normalized)


def run_quality_checks(connection: sqlite3.Connection) -> None:
    checks = {
        "orders reference customers": """
            SELECT COUNT(*) FROM stg_orders AS orders
            LEFT JOIN stg_customers AS customers USING (customer_id)
            WHERE customers.customer_id IS NULL
        """,
        "order items reference orders": """
            SELECT COUNT(*) FROM stg_order_items AS items
            LEFT JOIN stg_orders AS orders USING (order_id)
            WHERE orders.order_id IS NULL
        """,
        "order items reference products": """
            SELECT COUNT(*) FROM stg_order_items AS items
            LEFT JOIN stg_products AS products USING (product_id)
            WHERE products.product_id IS NULL
        """,
        "orders have valid statuses": """
            SELECT COUNT(*) FROM stg_orders
            WHERE status NOT IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled')
        """,
        "orders have non-negative totals": "SELECT COUNT(*) FROM stg_orders WHERE order_total < 0",
        "order items have positive quantities": "SELECT COUNT(*) FROM stg_order_items WHERE quantity <= 0",
        "events have known types": """
            SELECT COUNT(*) FROM stg_events
            WHERE event_type NOT IN ('add_to_cart', 'purchase')
        """,
    }
    failures = {name: connection.execute(sql).fetchone()[0] for name, sql in checks.items()}
    failures = {name: count for name, count in failures.items() if count}
    if failures:
        details = ", ".join(f"{name}: {count}" for name, count in failures.items())
        raise ValueError(f"Data quality checks failed: {details}")


def build_analytics(raw_dir: Path, output_path: Path) -> dict[str, int]:
    rows = {table: load_postgres_rows(raw_dir, table) for table in POSTGRES_TABLES}
    events = load_event_rows(raw_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".tmp")
    temporary_path.unlink(missing_ok=True)

    try:
        with sqlite3.connect(temporary_path) as connection:
            connection.executescript(STAGING_SCHEMA_SQL)
            for table in POSTGRES_TABLES:
                insert_rows(connection, f"stg_{table}", rows[table])
            insert_events(connection, events)
            run_quality_checks(connection)
            connection.executescript(ANALYTICS_SCHEMA_SQL)
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "customers": len(rows["customers"]),
        "products": len(rows["products"]),
        "orders": len(rows["orders"]),
        "order_items": len(rows["order_items"]),
        "events": len(events),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("raw_data"))
    parser.add_argument("--output-path", type=Path, default=Path("analytics_data/analytics.db"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = build_analytics(args.raw_dir, args.output_path)
    print(f"Built {args.output_path}")
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
