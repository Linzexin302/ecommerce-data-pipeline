"""Incrementally extract PostgreSQL tables using timestamp watermarks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingestion.raw_io import write_jsonl


INITIAL_TIMESTAMP = "1970-01-01T00:00:00+00:00"
INITIAL_KEY = ""


@dataclass(frozen=True)
class TableConfig:
    name: str
    primary_key: str
    watermark_column: str
    select_sql: str


TABLES = [
    TableConfig(
        "customers",
        "customer_id",
        "created_at",
        """
        SELECT customer_id, name, email, country, created_at
        FROM customers
        WHERE (created_at, customer_id) > (%s, %s)
        ORDER BY created_at, customer_id
        """,
    ),
    TableConfig(
        "products",
        "product_id",
        "updated_at",
        """
        SELECT product_id, name, category, price, updated_at
        FROM products
        WHERE (updated_at, product_id) > (%s, %s)
        ORDER BY updated_at, product_id
        """,
    ),
    TableConfig(
        "orders",
        "order_id",
        "updated_at",
        """
        SELECT order_id, customer_id, status, order_total, created_at, updated_at
        FROM orders
        WHERE (updated_at, order_id) > (%s, %s)
        ORDER BY updated_at, order_id
        """,
    ),
    TableConfig(
        "order_items",
        "order_item_id",
        "_source_updated_at",
        """
        SELECT oi.order_item_id, oi.order_id, oi.product_id, oi.quantity,
               oi.unit_price, o.updated_at AS _source_updated_at
        FROM order_items AS oi
        JOIN orders AS o ON o.order_id = oi.order_id
        WHERE (o.updated_at, oi.order_item_id) > (%s, %s)
        ORDER BY o.updated_at, oi.order_item_id
        """,
    ),
]


def extract_all(
    database_url: str,
    raw_dir: Path,
    watermarks: dict[str, dict[str, str]],
    run_id: str,
) -> dict[str, int]:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from exc

    counts: dict[str, int] = {}
    with psycopg.connect(database_url) as connection:
        connection.row_factory = psycopg.rows.dict_row
        with connection.cursor() as cursor:
            for table in TABLES:
                counts[table.name] = extract_table(cursor, table, raw_dir, watermarks, run_id)
    return counts


def extract_table(
    cursor: Any,
    table: TableConfig,
    raw_dir: Path,
    watermarks: dict[str, dict[str, str]],
    run_id: str,
) -> int:
    checkpoint = watermarks.get(table.name, {})
    timestamp = checkpoint.get("timestamp", INITIAL_TIMESTAMP)
    primary_key = checkpoint.get("primary_key", INITIAL_KEY)
    cursor.execute(table.select_sql, (timestamp, primary_key))
    rows = list(cursor.fetchall())
    if not rows:
        return 0

    output_path = raw_dir / "postgres" / table.name / f"extract_{run_id}.jsonl"
    count = write_jsonl(output_path, rows)
    final_row = rows[-1]
    watermarks[table.name] = {
        "timestamp": final_row[table.watermark_column].isoformat(),
        "primary_key": str(final_row[table.primary_key]),
    }
    return count


def create_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

