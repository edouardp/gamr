#!/bin/bash
set -e

echo "=== Python Linting with Ruff ==="

if [[ "$1" == "--fix" ]]; then
    uv run ruff check . --fix
    uv run ruff format .
    echo "✅ Auto-fix complete"
else
    uv run ruff check .
    uv run ruff format --check .
    echo "✅ Python linting complete"
fi
