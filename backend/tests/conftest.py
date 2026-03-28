"""
pytest設定・フィクスチャ
テスト用DBはsqliteのインメモリを使用（PostgreSQL不要でテスト実行可能）。
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models import *  # noqa: F401, F403 - 全モデルのインポート（テーブル作成に必要）

# テスト用SQLite（インメモリ）
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """セッションスコープのイベントループ"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """テスト用DBをセッション開始時に作成、終了時に破棄"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """テスト用DBセッション（テストごとにロールバック）"""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """テスト用HTTPクライアント（DBをテスト用にオーバーライド）"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """テスト用adminユーザー"""
    from app.models.user import User
    user = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        hashed_password=hash_password("test_password_123"),
        display_name="Test Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def reviewer_user(db_session: AsyncSession):
    """テスト用reviewerユーザー"""
    from app.models.user import User
    user = User(
        id=uuid.uuid4(),
        email="reviewer@test.com",
        hashed_password=hash_password("test_password_123"),
        display_name="Test Reviewer",
        role="reviewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def operator_user(db_session: AsyncSession):
    """テスト用operatorユーザー"""
    from app.models.user import User
    user = User(
        id=uuid.uuid4(),
        email="operator@test.com",
        hashed_password=hash_password("test_password_123"),
        display_name="Test Operator",
        role="operator",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user
