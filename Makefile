.PHONY: install test lint run-sample

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

run-sample:
	wbsb run -i examples/datasets/dataset_07_extreme_ad_spend.csv --llm-mode off
