"""
ジョブ管理API
非同期ジョブの状態確認・手動再実行・キャンセルを管理する。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.user import User
from app.repositories.job_repo import AuditLogRepository, JobRepository

router = APIRouter(prefix="/jobs", tags=["ジョブ管理"])


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    retry_count: int
    max_retries: int
    started_at: str | None
    finished_at: str | None
    duration_seconds: float | None
    error_message: str | None
    triggered_by: str | None
    is_dry_run: bool
    related_resource_type: str | None
    related_resource_id: str | None

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None
    user_id: str | None
    result: str
    error_message: str | None
    diff: dict | None
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    status: str | None = Query(None),
    job_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobResponse]:
    """ジョブ一覧を取得する"""
    repo = JobRepository(db)
    jobs = await repo.list_by_status(
        status=status,
        job_type=job_type,
        limit=limit,
        offset=offset,
    )
    return [JobResponse.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    repo = JobRepository(db)
    job = await repo.get_by_id_or_raise(job_id)
    return JobResponse.model_validate(job)


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[AuditLogResponse]:
    """
    監査ログを取得する。
    admin権限が必要。
    """
    repo = AuditLogRepository(db)
    if resource_type:
        logs = await repo.list_by_resource(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
    else:
        logs = await repo.list_all(limit=limit)
    return [AuditLogResponse.model_validate(log) for log in logs]
