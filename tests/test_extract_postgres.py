from datetime import datetime, timezone
from decimal import Decimal

from ingestion.extract_postgres import TABLES, extract_table


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.parameters = None

    def execute(self, sql, parameters):
        self.parameters = parameters

    def fetchall(self):
        return self.rows


def test_extract_table_writes_raw_file_and_advances_watermark(tmp_path):
    timestamp = datetime(2026, 1, 2, tzinfo=timezone.utc)
    rows = [
        {
            "product_id": "product-1",
            "name": "Desk Lamp",
            "category": "home",
            "price": Decimal("32.75"),
            "updated_at": timestamp,
        }
    ]
    cursor = FakeCursor(rows)
    watermarks = {}

    count = extract_table(cursor, TABLES[1], tmp_path, watermarks, "test-run")

    assert count == 1
    assert cursor.parameters == ("1970-01-01T00:00:00+00:00", "")
    assert watermarks["products"] == {
        "timestamp": "2026-01-02T00:00:00+00:00",
        "primary_key": "product-1",
    }
    output = tmp_path / "postgres" / "products" / "extract_test-run.jsonl"
    assert '"price": "32.75"' in output.read_text()


def test_extract_table_does_not_create_file_for_empty_result(tmp_path):
    cursor = FakeCursor([])

    count = extract_table(cursor, TABLES[0], tmp_path, {}, "test-run")

    assert count == 0
    assert not (tmp_path / "postgres").exists()

