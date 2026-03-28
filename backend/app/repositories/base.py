"""
リポジトリ基底クラス
DBアクセスの共通CRUD操作を提供する。
SQLAlchemyの操作をここに集約し、サービス層から分離する。
"""

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.core.exceptions import NotFoundError

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    汎用リポジトリ基底クラス。
    各モデル専用リポジトリの基底として使用する。
    """

    def __init__(self, model: type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def get_by_id(self, record_id: uuid.UUID) -> ModelType | None:
        """IDでレコードを取得する（存在しない場合はNone）"""
        result = await self.db.execute(
            select(self.model).where(self.model.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, record_id: uuid.UUID) -> ModelType:
        """IDでレコードを取得する（存在しない場合はNotFoundError）"""
        record = await self.get_by_id(record_id)
        if not record:
            raise NotFoundError(self.model.__name__, record_id)
        return record

    async def create(self, **kwargs: Any) -> ModelType:
        """レコードを作成する"""
        record = self.model(**kwargs)
        self.db.add(record)
        await self.db.flush()  # IDを確定させる
        return record

    async def update(self, record: ModelType, **kwargs: Any) -> ModelType:
        """レコードを更新する"""
        for key, value in kwargs.items():
            setattr(record, key, value)
        self.db.add(record)
        await self.db.flush()
        return record

    async def delete(self, record: ModelType) -> None:
        """レコードを削除する（物理削除）"""
        await self.db.delete(record)
        await self.db.flush()

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelType]:
        """全レコードを取得する"""
        result = await self.db.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
