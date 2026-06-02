.PHONY: setup postgres-up generate ingest transform export-reports test reproduce clean-generated

DATABASE_URL ?= postgresql://ecommerce:ecommerce@localhost:5432/ecommerce
START_DATE ?= 2026-01-01
DAYS ?= 30
SEED ?= 42

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

postgres-up:
	docker compose up -d

generate:
	python -m data_generator.generate \
	  --start-date $(START_DATE) \
	  --days $(DAYS) \
	  --seed $(SEED) \
	  --database-url $(DATABASE_URL)

ingest:
	python -m ingestion.run_pipeline --database-url $(DATABASE_URL)

transform:
	python -m transformation.build_analytics

export-reports:
	python -m reporting.export_reports

test:
	pytest

reproduce: generate ingest transform export-reports test

clean-generated:
	rm -rf generated_data raw_data analytics_data reports

