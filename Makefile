.PHONY: help bootstrap install lint fix format typecheck test check precommit-install precommit-run ci

help:
	@echo "Available targets:"
	@echo "  bootstrap  Install deps and pre-commit hooks"
	@echo "  install    Install dependencies via poetry"
	@echo "  lint       Run ruff checks"
	@echo "  fix        Run ruff autofix"
	@echo "  format     Run ruff formatter"
	@echo "  typecheck  Run mypy for src/"
	@echo "  test       Run pytest"
	@echo "  check      Run lint + typecheck + test"
	@echo "  precommit-install  Install pre-commit hooks"
	@echo "  precommit-run      Run pre-commit for all files"
	@echo "  ci         Run pre-commit + check (CI-equivalent)"

bootstrap: install precommit-install

install:
	poetry config virtualenvs.create false
	poetry install --with dev --no-interaction --no-ansi

lint:
	ruff check src tests

fix:
	ruff check src tests --fix

format:
	ruff format src tests

typecheck:
	mypy src

test:
	pytest -q --cov=src

check: lint typecheck test

precommit-install:
	pre-commit install

precommit-run:
	pre-commit run --all-files

ci: precommit-run check
