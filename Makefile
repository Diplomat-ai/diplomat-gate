.PHONY: install test lint format bench cov clean

install:
	pip install -e ".[dev,yaml]"

test:
	pytest -q

cov:
	pytest --cov=diplomat_gate --cov-report=term-missing --cov-fail-under=80 -q

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

bench:
	python benchmarks/run.py

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info coverage.xml .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
