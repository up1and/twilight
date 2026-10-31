.DEFAULT_GOAL := help
.PHONY: help server worker docs

help:
	@echo "Usage: make <target>"
	@echo "  server  Run the API server"
	@echo "  worker  Run the worker (ARGS=\"--sync --worker\")"
	@echo "  docs    Build the docs"

server:
	uv run --package server server/app.py

worker:
	uv run --package worker worker/main.py $(ARGS)

docs:
	rm -rf docs/_build && uv run --extra docs sphinx-build -b html docs docs/_build/html
