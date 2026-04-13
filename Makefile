.PHONY: help install dev upgrade run unit-tests integration-tests llm-tests test lint format

help:
	@echo 'Targets:'
	@echo '  install             Sync runtime dependencies with uv'
	@echo '  dev                 Sync project + dev dependencies with uv'
	@echo '  upgrade             Upgrade and resync project dependencies with uv'
	@echo '  run                 Start the local LangGraph dev server'
	@echo '  unit-tests          Run unit tests'
	@echo '  integration-tests   Run mocked integration tests'
	@echo '  llm-tests           Run live OpenAI/Zhipu integration tests'
	@echo '  test                Run unit tests + mocked integration tests'
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

unit-tests:
	uv run python -m pytest tests/unit_tests -q

integration-tests:
	uv run python -m pytest tests/integration_tests -q -m "not external_llm"

llm-tests:
	uv run python -m pytest tests/integration_tests/test_live_llm.py -q -m external_llm

test: unit-tests integration-tests

lint:
	uv run python -m ruff check src tests

format:
	uv run python -m ruff format src tests
