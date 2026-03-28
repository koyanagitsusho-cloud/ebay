"""
承認フローサービス
出品公開・価格変更・セール実行などの重要操作に対する承認フローを管理する。

設計方針:
- 承認なしの本番操作は禁止
- 承認は reviewer 以上の権限が必要
- 承認有効期限を設定し、期限切れは再申請必要
- 承認履歴は監査ログとして残す
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ApprovalRequiredError,
    InvalidStatusTransitionError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.logging_config import get_logger
from app.core.security import require_role
from app.models.listing import Approval
from app.models.user import User
from app.services.audit_service import AuditService

logger = get_logger(__name__)

# 承認の有効期限（デフォルト24時間）
APPROVAL_EXPIRY_HOURS = 24


class ApprovalService:
    """
    承認フロー管理サービス。
    承認の作成・審査・有効期限管理を担う。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = AuditService(db)

    async def request_approval(
        self,
        operation_type: str,
        target_resource_type: str,
        target_resource_id: str,
        requester_id: uuid.UUID,
        request_payload: dict[str, Any] | None = None,
        requester_note: str | None = None,
        listing_draft_id: uuid.UUID | None = None,
        expiry_hours: int = APPROVAL_EXPIRY_HOURS,
    ) -> Approval:
        """
        承認依頼を作成する。
        既にpending状態の承認がある場合は新規作成しない（重複防止）。
        """
        # 既存のpending承認チェック
        existing = await self._find_pending_approval(
            target_resource_type, target_resource_id, operation_type
        )
        if existing:
            logger.info(
                "既存のpending承認あり",
                approval_id=str(existing.id),
                operation=operation_type,
            )
            return existing

        expires_at = (
            datetime.now(UTC) + timedelta(hours=expiry_hours)
        ).isoformat()

        approval = Approval(
            listing_draft_id=listing_draft_id,
            operation_type=operation_type,
            target_resource_type=target_resource_type,
            target_resource_id=target_resource_id,
            request_payload=request_payload,
            requester_note=requester_note,
            status="pending",
            expires_at=expires_at,
        )
        self.db.add(approval)
        await self.db.flush()  # IDを確定させる

        await self.audit.log(
            action=f"approval.request.{operation_type}",
            resource_type="approval",
            resource_id=str(approval.id),
            user_id=requester_id,
            after_state={"status": "pending", "operation": operation_type},
        )

        logger.info(
            "承認依頼作成",
            approval_id=str(approval.id),
            operation=operation_type,
            resource=f"{target_resource_type}/{target_resource_id}",
        )

        return approval

    async def approve(
        self,
        approval_id: uuid.UUID,
        reviewer: User,
        reviewer_note: str | None = None,
    ) -> Approval:
        """
        承認する。
        reviewer 以上の権限が必要。
        有効期限切れの場合は承認不可。
        """
        require_role(reviewer.role, "reviewer")

        approval = await self._get_approval(approval_id)

        if approval.status != "pending":
            raise InvalidStatusTransitionError(
                current=approval.status,
                target="approved",
                resource=f"Approval/{approval_id}",
            )

        # 有効期限チェック
        if approval.expires_at:
            expires = datetime.fromisoformat(approval.expires_at)
            if datetime.now(UTC) > expires.replace(tzinfo=UTC):
                approval.status = "expired"
                await self.audit.log(
                    action="approval.expired",
                    resource_type="approval",
                    resource_id=str(approval.id),
                    user_id=reviewer.id,
                )
                raise PermissionDeniedError(
                    f"承認有効期限が切れています（期限: {approval.expires_at}）。再申請してください"
                )

        before_state = {"status": approval.status}

        approval.status = "approved"
        approval.reviewer_id = reviewer.id
        approval.reviewer_note = reviewer_note
        approval.reviewed_at = datetime.now(UTC).isoformat()

        await self.audit.log(
            action=f"approval.approved.{approval.operation_type}",
            resource_type="approval",
            resource_id=str(approval.id),
            user_id=reviewer.id,
            before_state=before_state,
            after_state={"status": "approved", "reviewer": str(reviewer.id)},
        )

        logger.info(
            "承認完了",
            approval_id=str(approval.id),
            operation=approval.operation_type,
            reviewer=reviewer.email,
        )

        return approval

    async def reject(
        self,
        approval_id: uuid.UUID,
        reviewer: User,
        reviewer_note: str,
    ) -> Approval:
        """
        却下する。
        reviewer_note は必須（理由を必ず記録する）。
        """
        require_role(reviewer.role, "reviewer")

        if not reviewer_note.strip():
            raise ValueError("却下理由（reviewer_note）は必須です")

        approval = await self._get_approval(approval_id)

        if approval.status != "pending":
            raise InvalidStatusTransitionError(
                current=approval.status,
                target="rejected",
                resource=f"Approval/{approval_id}",
            )

        before_state = {"status": approval.status}

        approval.status = "rejected"
        approval.reviewer_id = reviewer.id
        approval.reviewer_note = reviewer_note
        approval.reviewed_at = datetime.now(UTC).isoformat()

        await self.audit.log(
            action=f"approval.rejected.{approval.operation_type}",
            resource_type="approval",
            resource_id=str(approval.id),
            user_id=reviewer.id,
            before_state=before_state,
            after_state={"status": "rejected", "reason": reviewer_note},
        )

        logger.info(
            "承認却下",
            approval_id=str(approval.id),
            operation=approval.operation_type,
            reviewer=reviewer.email,
        )

        return approval

    async def assert_approved(
        self,
        operation_type: str,
        target_resource_type: str,
        target_resource_id: str,
    ) -> Approval:
        """
        操作実行前に承認済みかを確認する。
        承認がない・期限切れ・却下の場合は例外を送出する。
        出品公開・価格変更前に必ず呼び出す。
        """
        result = await self.db.execute(
            select(Approval).where(
                Approval.target_resource_type == target_resource_type,
                Approval.target_resource_id == target_resource_id,
                Approval.operation_type == operation_type,
                Approval.status == "approved",
            )
        )
        approval = result.scalar_one_or_none()

        if not approval:
            raise ApprovalRequiredError(
                f"{operation_type}（{target_resource_type}/{target_resource_id}）"
            )

        # 承認後も有効期限チェック
        if approval.expires_at:
            expires = datetime.fromisoformat(approval.expires_at)
            if datetime.now(UTC) > expires.replace(tzinfo=UTC):
                raise ApprovalRequiredError(
                    f"承認が期限切れです（期限: {approval.expires_at}）。再申請してください"
                )

        return approval

    async def _get_approval(self, approval_id: uuid.UUID) -> Approval:
        result = await self.db.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise NotFoundError("Approval", approval_id)
        return approval

    async def _find_pending_approval(
        self,
        resource_type: str,
        resource_id: str,
        operation_type: str,
    ) -> Approval | None:
        result = await self.db.execute(
            select(Approval).where(
                Approval.target_resource_type == resource_type,
                Approval.target_resource_id == resource_id,
                Approval.operation_type == operation_type,
                Approval.status == "pending",
            )
        )
        return result.scalar_one_or_none()
