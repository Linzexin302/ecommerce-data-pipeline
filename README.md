# E-commerce Customer Behavior Data Pipeline

## 1. Executive Summary

This project builds an end-to-end e-commerce analytics pipeline for understanding customer behavior, churn risk, product engagement, and customer value. The business problem is that retail teams often have customer, order, product, and web-event data stored in separate operational systems, making it difficult to answer questions such as which customers are likely to churn, which segments generate the highest lifetime value, and where customers abandon the purchase journey.

The solution is a reproducible data pipeline that generates realistic retail source data, ingests it into an immutable raw layer, transforms it into analytics-ready dimensional tables and marts, and exports CSV reports for dashboarding in Tableau.

## 2. Business Problem

Retail teams need a reliable way to turn raw customer activity into business insights. In this project, the goal is to support analysis for:

- Customer churn prediction
- Customer segmentation
- Customer lifetime value analysis
- Cart abandonment behavior
- Product and sales performance reporting

The pipeline is designed to answer questions such as:

- Which customer segments have the highest churn rate?
- Which customer groups generate the highest lifetime value?
- How do browsing sessions, order frequency, and cart abandonment relate to churn?
- Which product and behavioral signals should be monitored in a retail dashboard?

## 3. Methodology

### 3.1 Source Data Generation

The project starts by creating a synthetic e-commerce source system. This makes the project reproducible and avoids relying on private company data. The generator creates both structured operational data and semi-structured behavioral event data.

The structured source data is loaded into PostgreSQL and includes:

- `customers`
- `products`
- `orders`
- `order_items`

The semi-structured event data is written as newline-delimited JSON files partitioned by event date:

```text
generated_data/events/event_date=YYYY-MM-DD/events.jsonl
```

The generator also creates customer profile snapshots for churn and segmentation analysis:

```text
generated_data/customer_profiles/customer_profiles.jsonl
```

Customer profiles include fields such as:

- `segment`
- `preferred_category`
- `acquisition_channel`
- `device_type`
- `base_churn_risk_score`
- `total_orders`
- `total_spend`
- `days_since_last_order`
- `churn_label`

The behavioral event stream includes customer actions such as:

- page views
- searches
- product views
- add-to-cart events
- cart abandonment
- wishlist additions
- checkout starts
- purchases

The dataset is controlled by configurable parameters, including start date, number of days, random seed, customers per day, and orders per day. This allows the same data to be regenerated consistently.

Example command:

```bash
make generate DAYS=180 CUSTOMERS_PER_DAY=35 ORDERS_PER_DAY=200
```

### 3.2 Incremental Raw Ingestion

After the source data is generated, the ingestion layer copies the source records into an immutable raw data layer. This step simulates a production data engineering pattern where raw source data is preserved before transformation.

The PostgreSQL ingestion process extracts:

- customers
- products
- orders
- order items

The ingestion process uses timestamp and primary-key watermarks to support incremental loading. This prevents the pipeline from repeatedly extracting the same database records and also handles records that share the same timestamp.

The JSONL ingestion process copies event files and customer profile snapshots into the raw layer using SHA-256 checksums. This makes the file ingestion idempotent: if the same file has already been processed, the pipeline will not duplicate it.

Raw data is stored under:

```text
raw_data/
├── postgres/
├── events/
├── customer_profiles/
└── metadata/
```

Pipeline run metadata and ingestion state are stored in:

```text
raw_data/metadata/pipeline_runs.jsonl
raw_data/metadata/state.json
```

This design makes the pipeline auditable because each run records what was processed and whether the run succeeded or failed.

### 3.3 Analytics Transformation

The transformation step reads from the immutable raw layer and builds a local SQLite analytics database:

```text
analytics_data/analytics.db
```

The transformation logic follows a warehouse-style structure:

1. Load raw JSONL extracts.
2. Deduplicate records by primary key.
3. Keep the latest version of each source record.
4. Normalize events and customer profiles into staging tables.
5. Run data quality checks.
6. Build dimensions, fact tables, and reporting marts.
7. Publish the SQLite database atomically.

The analytics database includes staging tables such as:

- `stg_customers`
- `stg_products`
- `stg_orders`
- `stg_order_items`
- `stg_events`
- `stg_customer_profiles`

It then builds dimensional and fact tables:

- `dim_customers`
- `dim_products`
- `dim_customer_profiles`
- `fct_orders`
- `fct_order_items`
- `fct_events`

Finally, it creates business-facing marts:

- `mart_daily_sales`
- `mart_product_performance`
- `mart_customer_churn_features`
- `mart_customer_segments`

The most important output for customer analytics is `mart_customer_churn_features`. It combines customer profile attributes, order behavior, and event activity into one customer-level table. This table supports Tableau analysis and future machine learning work.

Example features include:

- customer segment
- preferred category
- acquisition channel
- device type
- base churn risk score
- order count
- lifetime value
- average order value
- session count
- product view count
- add-to-cart count
- cart abandon count
- wishlist count
- days since last order
- churn label

### 3.4 Data Quality Checks

Before the analytics database is published, the pipeline runs data quality checks to catch broken relationships or invalid values. The checks validate that:

- orders reference valid customers
- order items reference valid orders
- order items reference valid products
- order statuses are valid
- order totals are non-negative
- order item quantities are positive
- event types are known and expected

If a check fails, the transformation step raises an error and does not publish the final analytics database. This protects the reporting layer from bad or incomplete data.

### 3.5 Reporting Export

The reporting step exports analytics marts to CSV files for Tableau:

```text
reports/
├── daily_sales.csv
├── product_performance.csv
├── customer_churn_features.csv
└── customer_segments.csv
```

The main Tableau dataset is:

```text
reports/customer_churn_features.csv
```

This file is customer-level and is used to build KPI cards, churn analysis, customer segment analysis, lifetime value charts, cart abandonment analysis, and customer behavior scatter plots.

### 3.6 Reproducible Workflow

The complete project can be rebuilt from code using Makefile commands:

```bash
make setup
source .venv/bin/activate
make postgres-up
make reproduce
```

The default workflow runs:

1. data generation
2. raw ingestion
3. analytics transformation
4. report export
5. automated tests

Generated files are intentionally ignored by Git so the repository stays lightweight:

- `generated_data/`
- `raw_data/`
- `analytics_data/`
- `reports/`

## 4. Skills

### Data Engineering

- Built a multi-step data pipeline from source generation to reporting output.
- Designed an immutable raw data layer for PostgreSQL extracts, JSONL event files, and customer profile snapshots.
- Implemented incremental ingestion using database watermarks and file checksums.
- Created reproducible source data with configurable generation parameters and deterministic random seeds.
- Used a Makefile to standardize project commands and support repeatable pipeline execution.

### Data Modeling

- Modeled operational source tables for customers, products, orders, and order items.
- Built staging tables, dimension tables, fact tables, and analytics marts.
- Created a customer-level churn feature mart combining profile, transaction, and behavioral event data.
- Designed reporting marts for daily sales, product performance, customer churn, and customer segmentation.

### SQL and Analytics

- Used SQL transformations to aggregate revenue, order counts, customer counts, product performance, and behavioral features.
- Created customer metrics such as lifetime value, average order value, session count, cart abandon count, and days since last order.
- Built churn and segmentation outputs that can be used for dashboarding and future predictive modeling.
- Validated relational integrity between customers, orders, order items, products, and events.

### Python Development

- Used Python to generate synthetic retail data, write JSONL files, load PostgreSQL tables, ingest raw files, transform data, and export CSV reports.
- Used `pathlib`, `json`, `csv`, `sqlite3`, and `argparse` for file processing, command-line workflows, and local analytics storage.
- Used `psycopg` to connect Python pipeline code with PostgreSQL.
- Structured the project into separate modules for generation, ingestion, transformation, reporting, and testing.

### Testing and Reproducibility

- Added automated tests with `pytest` for generator behavior, event partitioning, customer profile fields, ingestion state, analytics transformations, and report exports.
- Tested reproducibility by verifying that the same seed creates the same generated dataset.
- Tested data correctness, including order totals matching order items and transformation logic keeping the latest raw record version.
- Kept generated data out of Git while preserving commands to rebuild all outputs.

### Business Intelligence

- Exported Tableau-ready CSV datasets from analytics marts.
- Prepared customer-level features for dashboard analysis, including churn rate, customer segment, lifetime value, session count, and cart abandonment behavior.
- Supported business questions around customer retention, customer value, behavior patterns, and product performance.

## 5. Results and Business Recommendation

This section will summarize the final dashboard findings and business recommendations after the Tableau analysis is complete.

Potential recommendation areas include:

- retention strategy for high-churn segments
- customer engagement strategy for casual browsers and at-risk users
- product or checkout improvements for high cart abandonment groups
- marketing channel optimization based on churn and customer value

## 6. Next Steps

Future improvements could include:

- Add a machine learning model for churn prediction.
- Replace rule-based customer segments with clustering, such as K-Means.
- Add orchestration with Airflow or Prefect.
- Add dbt models for more production-style transformations.
- Add dashboard screenshots and final business insights to the README.
