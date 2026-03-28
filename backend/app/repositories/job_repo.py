"""
ジョブ・監査ログリポジトリ
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import ApiCallLog, AuditLog, Job, JobLog
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    """ジョブのリポジトリ"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Job, db)

    async def list_by_status(
        self,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """ステータス・種別でフィルタ"""
        query = select(Job)
        if status:
            query = query.where(Job.status == status)
        if job_type:
            query = query.where(Job.job_type == job_type)
        query = query.order_by(desc(Job.created_at)).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_running(self, job: Job, celery_task_id: str) -> Job:
        """ジョブを実行中状態にする"""
        job.status = "running"
        job.celery_task_id = celery_task_id
        job.started_at = datetime.now(UTC).isoformat()
        return job

    async def mark_success(self, job: Job, result: dict) -> Job:
        """ジョブを成功状態にする"""
        job.status = "success"
        job.result = result
        job.finished_at = datetime.now(UTC).isoformat()
        if job.started_at:
            started = datetime.fromisoformat(job.started_at)
            job.duration_seconds = (datetime.now(UTC) - started.replace(tzinfo=UTC)).total_seconds()
        return job

    async def mark_failed(self, job: Job, error_message: str, traceback: str | None = None) -> Job:
        """ジョブを失敗状態にする"""
        job.status = "failed"
        job.error_message = error_message
        job.error_traceback = traceback
        job.finished_at = datetime.now(UTC).isoformat()
        job.retry_count += 1
        return job


class AuditLogRepository(BaseRepository[AuditLog]):
    """監査ログのリポジトリ"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(AuditLog, db)

    async def list_by_resource(
        self,
        resource_type: str,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """リソース別監査ログを取得する"""
        query = select(AuditLog).where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        query = query.order_by(desc(AuditLog.created_at)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
    ) -> list[AuditLog]:
        """ユーザー別監査ログを取得する"""
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
