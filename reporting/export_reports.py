"""Export reporting-ready CSV files from the analytics database."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


REPORTS = {
    "daily_sales.csv": """
        SELECT
            order_date,
            order_count,
            customer_count,
            gross_revenue,
            net_revenue,
            average_order_value
        FROM mart_daily_sales
        ORDER BY order_date
    """,
    "product_performance.csv": """
        SELECT
            product_name,
            category,
            add_to_cart_count,
            units_sold,
            gross_revenue
        FROM mart_product_performance
        ORDER BY gross_revenue DESC, product_name
    """,
}


def export_query(connection: sqlite3.Connection, query: str, output_path: Path) -> int:
    cursor = connection.execute(query)
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(columns)
        writer.writerows(rows)
    return len(rows)


def export_reports(database_path: Path, output_dir: Path) -> dict[str, int]:
    if not database_path.exists():
        raise FileNotFoundError(f"Analytics database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        return {
            filename: export_query(connection, query, output_dir / filename)
            for filename, query in REPORTS.items()
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-path", type=Path, default=Path("analytics_data/analytics.db"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = export_reports(args.database_path, args.output_dir)
    for filename, row_count in counts.items():
        print(f"Exported {args.output_dir / filename} ({row_count} rows)")


if __name__ == "__main__":
    main()

