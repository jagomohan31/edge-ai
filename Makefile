.PHONY: install test lint qa demo

install:
	pip install -e .[dev]

test:
	pytest -q

lint:
	ruff check src tests

qa: lint test
	python -m edge_ai demo
	@echo "QA complete"

demo:
	python -m edge_ai demo