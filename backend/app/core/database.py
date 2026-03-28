"""
データベース接続管理
SQLAlchemy 2.0 非同期エンジンを使用。
FastAPIのリクエスト単位でセッションを管理する。
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# ─────────────────────────────────────
# エンジン作成
# ─────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,  # DEBUGモードでSQL出力（本番は必ずFalse）
    future=True,
)

# セッションファクトリ
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ─────────────────────────────────────
# ベースモデル
# ─────────────────────────────────────
class Base(DeclarativeBase):
    """
    全モデルの基底クラス。
    metadata はここで一元管理する。
    Alembic はこの Base.metadata を参照してマイグレーション生成する。
    """
    pass


# ─────────────────────────────────────
# セッション依存性（FastAPI用）
# ─────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPIの依存性注入で使用するDBセッションジェネレータ。
    リクエスト終了時に自動コミットまたはロールバックする。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─────────────────────────────────────
# 非リクエストコンテキスト用（Celeryワーカー等）
# ─────────────────────────────────────
@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Celeryジョブやスクリプトなど、
    FastAPIのリクエストサイクル外でDBセッションを使う場合に使用。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """
    テーブルを全作成する（開発・テスト用）。
    本番はAlembicマイグレーションを使うこと。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """
    全テーブルを削除する（テスト用のみ）。
    本番環境では絶対に実行しないこと。
    """
    if settings.ENVIRONMENT == "production":
        raise RuntimeError("本番環境でのテーブル削除は禁止されています")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
