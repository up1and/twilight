default:
    @just --list

server:
    uv run --package server server/app.py

worker *args:
    uv run --package worker worker/main.py {{args}}
