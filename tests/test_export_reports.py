import sqlite3

from reporting.export_reports import export_reports


def test_export_reports_writes_csv_files(tmp_path):
    database_path = tmp_path / "analytics.db"
    output_dir = tmp_path / "reports"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE mart_daily_sales (
                order_date TEXT,
                order_count INTEGER,
                customer_count INTEGER,
                gross_revenue NUMERIC,
                net_revenue NUMERIC,
                average_order_value NUMERIC
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE mart_product_performance (
                product_name TEXT,
                category TEXT,
                add_to_cart_count INTEGER,
                units_sold INTEGER,
                gross_revenue NUMERIC
            )
            """
        )
        connection.execute(
            "INSERT INTO mart_daily_sales VALUES ('2026-01-01', 8, 3, 847.75, 847.75, 105.97)"
        )
        connection.execute(
            "INSERT INTO mart_product_performance VALUES ('Desk Lamp', 'home', 10, 12, 393.00)"
        )

    counts = export_reports(database_path, output_dir)

    assert counts == {"daily_sales.csv": 1, "product_performance.csv": 1}
    assert "order_date,order_count" in (output_dir / "daily_sales.csv").read_text()
    assert "Desk Lamp,home" in (output_dir / "product_performance.csv").read_text()

