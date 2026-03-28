"""
管理者ユーザー作成スクリプト
初回セットアップ時に1回だけ実行する。

使用方法:
  cd backend
  python ../scripts/create_admin.py

または:
  docker-compose exec backend python scripts/create_admin.py
"""

import asyncio
import sys
import os

# backend ディレクトリを Python パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


async def main():
    from app.core.database import AsyncSessionLocal, create_tables
    from app.core.security import hash_password
    from app.models.user import User
    from sqlalchemy import select

    print("=== 管理者ユーザー作成 ===")

    email = input("メールアドレス: ").strip()
    if not email:
        print("エラー: メールアドレスが空です")
        sys.exit(1)

    password = input("パスワード（8文字以上）: ").strip()
    if len(password) < 8:
        print("エラー: パスワードは8文字以上にしてください")
        sys.exit(1)

    display_name = input("表示名: ").strip() or "Admin"

    # テーブルが存在しない場合は作成
    await create_tables()

    async with AsyncSessionLocal() as db:
        # 既存確認
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"エラー: '{email}' は既に登録されています")
            sys.exit(1)

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
