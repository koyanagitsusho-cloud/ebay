"""
管理者ユーザー作成スクリプト
初回セットアップ時に1回だけ実行する。

使用方法（ローカル）:
  cd backend
  python create_admin.py

使用方法（Docker Compose）:
  docker-compose exec backend python create_admin.py

使用方法（環境変数で自動作成 / Railway）:
  ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=password123 python create_admin.py
"""

import asyncio
import os
import sys


async def main() -> None:
    from app.core.database import AsyncSessionLocal, create_tables
    from app.core.security import hash_password
    from app.models.user import User
    from sqlalchemy import select

    print("=== 管理者ユーザー作成 ===")

    # 環境変数から取得（Railway等の非対話環境用）
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    display_name = os.environ.get("ADMIN_DISPLAY_NAME", "Admin").strip()

    # 環境変数がなければ対話入力
    if not email:
        email = input("メールアドレス: ").strip()
    if not email:
        print("エラー: メールアドレスが空です")
        sys.exit(1)

    if not password:
        password = input("パスワード（8文字以上）: ").strip()
    if len(password) < 8:
        print("エラー: パスワードは8文字以上にしてください")
        sys.exit(1)

    if not display_name:
        display_name = input("表示名 [Admin]: ").strip() or "Admin"

    # テーブルが存在しない場合は作成（開発環境フォールバック）
    await create_tables()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"既に登録済み: '{email}' — スキップします")
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            display_name=display_name,
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"\n管理者ユーザーを作成しました")
        print(f"  メール: {email}")
        print(f"  ロール: admin")
        print(f"  表示名: {display_name}")


if __name__ == "__main__":
    asyncio.run(main())
