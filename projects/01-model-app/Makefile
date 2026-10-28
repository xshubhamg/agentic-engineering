.PHONY: sync test lint fmt ask

sync:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

ask:
	uv run signal ask "$(Q)"
