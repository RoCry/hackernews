.PHONY: format test

format:
	uv run ruff format .

test:
	uv run pytest -s -v tests/
