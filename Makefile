.PHONY: install-mcp test lint

install-mcp:
	uv tool install --force .

test:
	uv run pytest

lint:
	uv run ruff check
	uv run pyright
