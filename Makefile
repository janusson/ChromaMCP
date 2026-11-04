# ChromaMCP — developer ergonomics
# =============================================================================
# Mirrors the MSMCP Makefile.  Python targets run through `uv`, so the only
# prerequisite is a working `uv` (https://docs.astral.sh/uv/); the interpreter
# comes from .python-version.

.PHONY: install format lint test check all

install:            ## Create/update the virtualenv and sync all deps (incl. dev extras)
	uv sync --extra dev

format: install     ## Auto-format code and apply safe fixes (ruff)
	uv run ruff format .
	uv run ruff check --fix .

lint: install       ## Static checks: ruff format --check, ruff, mypy, basedpyright (mirrors CI)
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy
	uv run basedpyright

test: install       ## Run the pytest suite
	uv run pytest

check: lint test    ## The unit gate: what a unit of work must pass before hand-off

all: format check   ## Full pipeline: sync, format, gate
