"""
リサーチ候補リポジトリ
リサーチ候補と関連スコアのDBアクセスを担う。
"""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.research import ResearchCandidate, ResearchScore
from app.repositories.base import BaseRepository


class ResearchCandidateRepository(BaseRepository[ResearchCandidate]):
    """リサーチ候補のリポジトリ"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ResearchCandidate, db)

    async def get_with_scores(self, candidate_id: uuid.UUID) -> ResearchCandidate | None:
        """スコア含めてリサーチ候補を取得する"""
        result = await self.db.execute(
            select(ResearchCandidate)
            .where(ResearchCandidate.id == candidate_id)
            .options(selectinload(ResearchCandidate.scores))
        )
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        order_by_score: bool = True,
    ) -> list[ResearchCandidate]:
        """ステータスでフィルタして一覧取得"""
        query = select(ResearchCandidate)
        if status:
            query = query.where(ResearchCandidate.status == status)
        if order_by_score:
            query = query.order_by(desc(ResearchCandidate.total_score))
        else:
            query = query.order_by(desc(ResearchCandidate.created_at))
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_score(self, candidate_id: uuid.UUID) -> ResearchScore | None:
        """最新スコアを取得する"""
        result = await self.db.execute(
            select(ResearchScore)
            .where(ResearchScore.candidate_id == candidate_id)
            .order_by(desc(ResearchScore.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()


class ResearchScoreRepository(BaseRepository[ResearchScore]):
    """リサーチスコアのリポジトリ"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ResearchScore, db)
