#!/bin/bash
set -e

echo "=== DB マイグレーション実行 ==="
alembic upgrade head

# ADMIN_EMAIL と ADMIN_PASSWORD が設定されていれば管理者ユーザーを自動作成
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "=== 管理者ユーザー自動作成 ==="
    python create_admin.py
fi

echo "=== アプリ起動 ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
