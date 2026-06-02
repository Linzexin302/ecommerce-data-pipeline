# E-commerce Data Pipeline

This project build a production-style analytics data
pipeline. Step 1 creates a synthetic operational source system:

- PostgreSQL tables for customers, products, orders, and order items
- JSONL web events partitioned by event date
- Reproducible test data controlled by a random seed
- Automated tests for the generator

Step 2 incrementally copies source data into an immutable raw layer:

- Timestamp and primary-key watermarks for PostgreSQL tables
- SHA-256 checksums for idempotent JSONL event ingestion
- Local ingestion state and append-only pipeline-run metadata

Step 3 rebuilds analytics-ready tables from the immutable raw history:

- Deduplicated staging tables for PostgreSQL records and JSONL events
- Customer and product dimensions plus order, item, and event facts
- Daily sales and product-performance marts
- Data-quality checks before publishing a local SQLite analytics database

## Why Start Here?

A data pipeline needs a realistic source. The generator gives us stable data for
development and testing without relying on an external API. Later steps will add
controlled duplicates, malformed values, delayed events, extraction, dbt models,
orchestration, and monitoring.

## Project Structure

```text
.
├── data_generator/
│   └── generate.py
├── ingestion/
│   ├── extract_postgres.py
│   ├── ingest_events.py
│   ├── raw_io.py
│   ├── run_pipeline.py
│   └── state.py
├── transformation/
│   └── build_analytics.py
├── reporting/
│   └── export_reports.py
├── sql/
│   └── init.sql
├── tests/
├── raw_data/                 # created by Step 2 and ignored by Git
├── analytics_data/           # created by Step 3 and ignored by Git
├── reports/                  # created from analytics marts and ignored by Git
├── Makefile
├── docker-compose.yml
└── requirements.txt
```

## Quick Start

Create a virtual environment and install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start PostgreSQL:

```bash
docker compose up -d
```

Generate 30 days of source records and JSONL events:

```bash
python -m data_generator.generate \
  --start-date 2026-01-01 \
  --days 30 \
  --seed 42 \
  --database-url postgresql://ecommerce:ecommerce@localhost:5432/ecommerce
```

Generate JSONL files without loading PostgreSQL:

```bash
python -m data_generator.generate --start-date 2026-01-01 --days 7 --seed 42
```

Run tests:

```bash
pytest
```

Run the complete reproducible workflow:

```bash
make postgres-up
make reproduce
```

If your shell has multiple Python environments active, verify which interpreter is
being used:

```bash
which python
which pytest
```

## Generated Events

Events are written as newline-delimited JSON in date partitions:

```text
generated_data/events/event_date=2026-01-01/events.jsonl
```

This layout mirrors a common object-storage pattern and prepares the project for
incremental file ingestion in Step 2.

## Step 2: Incremental Raw Ingestion

Run the raw ingestion pipeline after PostgreSQL and the generated events are ready:

```bash
python -m ingestion.run_pipeline
```

The first run extracts all source rows and copies all unseen event files. Run the
same command again to test idempotency:

```bash
python -m ingestion.run_pipeline
```

The second run should report zero records because the source has not changed.

Raw files are append-only:

```text
raw_data/
├── postgres/
│   ├── customers/
│   ├── products/
│   ├── orders/
│   └── order_items/
├── events/
└── metadata/
    ├── pipeline_runs.jsonl
    └── state.json
```

The state file stores the last successful checkpoint for each PostgreSQL table and
the checksum of each processed event file. The pipeline uses both timestamp and
primary-key values for PostgreSQL checkpoints so records with identical timestamps
are still extracted safely.

## Step 3: Analytics Transformations

Build the analytics database after Step 2 has populated `raw_data/`:

```bash
python -m transformation.build_analytics
```

The command reads all immutable raw extracts, keeps the latest version of each
record, runs data-quality checks, and atomically publishes:

```text
analytics_data/analytics.db
```

The SQLite database contains:

- `stg_*` tables with cleaned and deduplicated source records
- `dim_customers` and `dim_products`
- `fct_orders`, `fct_order_items`, and `fct_events`
- `mart_daily_sales` for daily order and revenue reporting
- `mart_product_performance` for cart-add, unit-sales, and revenue reporting

Query a mart from the command line:

```bash
sqlite3 -header -column analytics_data/analytics.db \
  "SELECT * FROM mart_daily_sales ORDER BY order_date;"
```

## Reporting Exports

Export the reporting marts to CSV files:

```bash
python -m reporting.export_reports
```

This creates:

```text
reports/
├── daily_sales.csv
└── product_performance.csv
```

The reports are generated outputs, so they are ignored by Git. Recreate them any
time with `make export-reports`.

## Reproducibility Notes

The project is reproducible because source data generation is controlled by:

- `START_DATE`, defaulting to `2026-01-01`
- `DAYS`, defaulting to `30`
- `SEED`, defaulting to `42`
- `DATABASE_URL`, defaulting to the local Docker PostgreSQL service

Use the default workflow:

```bash
make setup
source .venv/bin/activate
make postgres-up
make reproduce
```

Or override values:

```bash
make reproduce START_DATE=2026-02-01 DAYS=14 SEED=7
```

Generated folders are intentionally ignored by Git:

- `generated_data/`
- `raw_data/`
- `analytics_data/`
- `reports/`

This keeps the GitHub repository small while proving that all outputs can be
rebuilt from code.
