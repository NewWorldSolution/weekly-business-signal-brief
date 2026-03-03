.PHONY: install test lint run-sample

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

run-sample:
	wbsb --input examples/sample_weekly.csv --output runs --llm off
