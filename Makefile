.PHONY: help install dev upgrade run clean-test-artifacts syntax-check unit-tests integration-tests verify-test-artifacts test-flow test lint format

PYTHON = uv run python
PYTEST = $(PYTHON) -m pytest

help:
	@echo 'Targets:'
	@echo '  install             Sync runtime dependencies with uv'
	@echo '  dev                 Sync project + dev dependencies with uv'
	@echo '  upgrade             Upgrade and resync project dependencies with uv'
	@echo '  run                 Start the local LangGraph dev server'
	@echo '  clean-test-artifacts Remove generated markdown test artifacts'
	@echo '  syntax-check        Compile src/tests to catch syntax errors'
	@echo '  unit-tests          Run unit tests'
	@echo '  integration-tests   Run live Eastmoney MX integration tests'
	@echo '  verify-test-artifacts Validate generated markdown test artifacts'
	@echo '  test-flow           Run syntax, unit, live integration, and artifact checks'
	@echo '  test                Alias of test-flow'
	@echo '  lint                Run Ruff checks'
	@echo '  format              Format with Ruff'

install:
	uv sync --no-dev

dev:
	uv sync --dev

upgrade:
	uv sync --dev -U

run:
	uv run langgraph dev

clean-test-artifacts:
	$(PYTHON) -c "from pathlib import Path; import shutil; root = Path('reports/test-artifacts'); shutil.rmtree(root, ignore_errors=True); print(f'cleaned {root}')"

syntax-check:
	$(PYTHON) -m compileall -q src tests

unit-tests:
	$(PYTEST) tests/unit_tests -q

integration-tests:
	$(PYTEST) tests/integration_tests -q

verify-test-artifacts:
	$(PYTHON) -m tests.verify_test_artifacts

test-flow: clean-test-artifacts
	$(MAKE) syntax-check
	$(MAKE) unit-tests
	$(MAKE) integration-tests
	$(MAKE) verify-test-artifacts

test: test-flow

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m ruff format src tests
