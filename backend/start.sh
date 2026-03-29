#!/bin/bash
set -e

echo "=== DB マイグレーション実行 ==="
alembic upgrade head

echo "=== アプリ起動 ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
