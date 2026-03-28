"""
出品下書き・承認リポジトリ
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.listing import Approval, ListingDraft
from app.repositories.base import BaseRepository


class ListingDraftRepository(BaseRepository[ListingDraft]):
    """出品下書きのリポジトリ"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ListingDraft, db)

    async def get_by_product_id(self, product_id: uuid.UUID) -> ListingDraft | None:
        """商品IDで下書きを取得する"""
        result = await self.db.execute(
            select(ListingDraft).where(ListingDraft.product_id == product_id)
        )
        return result.scalar_one_or_none()

    async def list_pending_approval(
        self, limit: int = 50
    ) -> list[ListingDraft]:
        """承認待ち下書き一覧を取得する"""
        result = await self.db.execute(
            select(ListingDraft)
            .where(ListingDraft.status == "pending_review")
            .options(selectinload(ListingDraft.approval))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_status(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ListingDraft]:
        """ステータスで下書き一覧を取得する"""
        query = select(ListingDraft)
        if status:
            query = query.where(ListingDraft.status == status)
        result = await self.db.execute(query.limit(limit).offset(offset))
        return list(result.scalars().all())


class ApprovalRepository(BaseRepository[Approval]):
    """承認レコードのリポジトリ"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Approval, db)

    async def list_pending(self, limit: int = 50) -> list[Approval]:
        """承認待ちの一覧を取得する"""
        result = await self.db.execute(
            select(Approval)
            .where(Approval.status == "pending")
            .limit(limit)
        )
        return list(result.scalars().all())
