"""Generate reproducible operational e-commerce data and JSONL web events."""

from __future__ import annotations

import argparse
import json
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


PRODUCT_CATALOG = [
    ("Wireless Headphones", "electronics", "79.99"),
    ("Mechanical Keyboard", "electronics", "94.50"),
    ("Cotton T-Shirt", "apparel", "18.00"),
    ("Running Shoes", "apparel", "65.00"),
    ("Coffee Beans", "grocery", "14.25"),
    ("Water Bottle", "home", "21.00"),
    ("Desk Lamp", "home", "32.75"),
    ("Notebook Set", "stationery", "11.50"),
]
FIRST_NAMES = ["Alex", "Jordan", "Morgan", "Taylor", "Casey", "Riley", "Jamie", "Avery"]
LAST_NAMES = ["Chen", "Smith", "Garcia", "Patel", "Kim", "Brown", "Nguyen", "Davis"]
COUNTRIES = ["US", "CA", "GB", "DE", "AU"]
ORDER_STATUSES = ["paid", "shipped", "delivered", "cancelled"]


@dataclass
class GeneratedData:
    customers: list[dict[str, Any]]
    products: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    order_items: list[dict[str, Any]]
    events: list[dict[str, Any]]


def stable_id(namespace: str, value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ecommerce-demo:{namespace}:{value}"))


def timestamp_for_day(day: date, rng: random.Random) -> datetime:
    seconds = rng.randrange(8 * 60 * 60, 22 * 60 * 60)
    return datetime.combine(day, time.min, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def build_products(start_date: date) -> list[dict[str, Any]]:
    return [
        {
            "product_id": stable_id("product", name),
            "name": name,
            "category": category,
            "price": Decimal(price),
            "updated_at": datetime.combine(start_date, time.min, tzinfo=timezone.utc),
        }
        for name, category, price in PRODUCT_CATALOG
    ]


def generate_data(
    start_date: date,
    days: int,
    seed: int,
    customers_per_day: int = 4,
    orders_per_day: int = 8,
) -> GeneratedData:
    if days < 1:
        raise ValueError("days must be at least 1")

    rng = random.Random(seed)
    products = build_products(start_date)
    customers: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    order_items: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for day_offset in range(days):
        current_day = start_date + timedelta(days=day_offset)

        for customer_number in range(customers_per_day):
            sequence = day_offset * customers_per_day + customer_number
            first_name = rng.choice(FIRST_NAMES)
            last_name = rng.choice(LAST_NAMES)
            customer_id = stable_id("customer", str(sequence))
            customers.append(
                {
                    "customer_id": customer_id,
                    "name": f"{first_name} {last_name}",
                    "email": f"{first_name.lower()}.{last_name.lower()}.{sequence}@example.com",
                    "country": rng.choice(COUNTRIES),
                    "created_at": timestamp_for_day(current_day, rng),
                }
            )

        for order_number in range(orders_per_day):
            sequence = day_offset * orders_per_day + order_number
            order_id = stable_id("order", str(sequence))
            customer = rng.choice(customers)
            created_at = timestamp_for_day(current_day, rng)
            selected_products = rng.sample(products, k=rng.randint(1, 3))
            total = Decimal("0.00")

            for item_number, product in enumerate(selected_products):
                quantity = rng.randint(1, 3)
                total += product["price"] * quantity
                order_items.append(
                    {
                        "order_item_id": stable_id("order_item", f"{sequence}:{item_number}"),
                        "order_id": order_id,
                        "product_id": product["product_id"],
                        "quantity": quantity,
                        "unit_price": product["price"],
                    }
                )
                events.append(
                    make_event(
                        event_type="add_to_cart",
                        customer_id=customer["customer_id"],
                        product_id=product["product_id"],
                        timestamp=created_at - timedelta(minutes=rng.randint(2, 30)),
                        sequence=f"{sequence}:{item_number}",
                    )
                )

            status = rng.choice(ORDER_STATUSES)
            orders.append(
                {
                    "order_id": order_id,
                    "customer_id": customer["customer_id"],
                    "status": status,
                    "order_total": total.quantize(Decimal("0.01")),
                    "created_at": created_at,
                    "updated_at": created_at + timedelta(hours=rng.randint(0, 48)),
                }
            )
            events.append(
                make_event(
                    event_type="purchase",
                    customer_id=customer["customer_id"],
                    product_id=None,
                    timestamp=created_at,
                    sequence=str(sequence),
                    order_id=order_id,
                )
            )

    return GeneratedData(customers, products, orders, order_items, events)


def make_event(
    event_type: str,
    customer_id: str,
    product_id: str | None,
    timestamp: datetime,
    sequence: str,
    order_id: str | None = None,
) -> dict[str, Any]:
    event = {
        "event_id": stable_id("event", f"{event_type}:{sequence}"),
        "event_type": event_type,
        "customer_id": customer_id,
        "product_id": product_id,
        "timestamp": timestamp.isoformat(),
    }
    if order_id:
        event["order_id"] = order_id
    return event


def write_events(events: Iterable[dict[str, Any]], output_dir: Path) -> None:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        event_date = event["timestamp"][:10]
        by_date.setdefault(event_date, []).append(event)

    for event_date, daily_events in by_date.items():
        partition_dir = output_dir / f"event_date={event_date}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        with (partition_dir / "events.jsonl").open("w", encoding="utf-8") as output_file:
            for event in daily_events:
                output_file.write(json.dumps(event, sort_keys=True) + "\n")


def load_postgres(data: GeneratedData, database_url: str) -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from exc

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            insert_rows(cursor, "customers", data.customers)
            insert_rows(cursor, "products", data.products)
            insert_rows(cursor, "orders", data.orders)
            insert_rows(cursor, "order_items", data.order_items)


def insert_rows(cursor: Any, table_name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in columns[1:])
    sql = (
        f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({columns[0]}) DO UPDATE SET {updates}"
    )
    cursor.executemany(sql, [[row[column] for column in columns] for row in rows])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("generated_data/events"))
    parser.add_argument("--database-url", help="PostgreSQL URL. Omit it to generate JSONL only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = generate_data(args.start_date, args.days, args.seed)
    write_events(data.events, args.output_dir)
    if args.database_url:
        load_postgres(data, args.database_url)
    print(
        f"Generated {len(data.customers)} customers, {len(data.products)} products, "
        f"{len(data.orders)} orders, {len(data.order_items)} order items, "
        f"and {len(data.events)} events."
    )


if __name__ == "__main__":
    main()

