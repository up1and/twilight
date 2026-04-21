default:
    @just --list

server:
    uv run --package server server/app.py

worker *args:
    uv run --package worker worker/main.py {{args}}

docs:
	rm -rf docs/_build && uv run sphinx-build -b html docs docs/_build/html
