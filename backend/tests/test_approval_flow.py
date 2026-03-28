"""
承認フローのテスト
承認依頼・承認・却下・権限チェックを検証する。
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApprovalRequiredError, InvalidStatusTransitionError, PermissionDeniedError
from app.models.listing import Approval
from app.models.user import User
from app.services.approval_service import ApprovalService


class TestApprovalFlow:
    """承認フローの正常系・異常系テスト"""

    @pytest.mark.asyncio
    async def test_request_approval_creates_record(self, db_session: AsyncSession, operator_user: User):
        """承認依頼でレコードが作成されること"""
        service = ApprovalService(db_session)
        approval = await service.request_approval(
            operation_type="publish",
            target_resource_type="listing_draft",
            target_resource_id="draft-001",
            requester_id=operator_user.id,
            requester_note="出品したいです",
        )

        assert approval.status == "pending"
        assert approval.operation_type == "publish"
        assert approval.target_resource_id == "draft-001"

    @pytest.mark.asyncio
    async def test_duplicate_request_returns_existing(
        self, db_session: AsyncSession, operator_user: User
    ):
        """同一リソースへの重複依頼は既存レコードを返すこと"""
        service = ApprovalService(db_session)

        approval1 = await service.request_approval(
            operation_type="publish",
            target_resource_type="listing_draft",
            target_resource_id="draft-002",
            requester_id=operator_user.id,
        )
        approval2 = await service.request_approval(
            operation_type="publish",
            target_resource_type="listing_draft",
            target_resource_id="draft-002",
            requester_id=operator_user.id,
        )

        assert approval1.id == approval2.id

    @pytest.mark.asyncio
    async def test_approve_by_reviewer_succeeds(
        self,
        db_session: AsyncSession,
        operator_user: User,
        reviewer_user: User,
    ):
        """reviewerによる承認が成功すること"""
        service = ApprovalService(db_session)
        approval = await service.request_approval(
            operation_type="publish",
            target_resource_type="listing_draft",
            target_resource_id="draft-003",
            requester_id=operator_user.id,
        )

        approved = await service.approve(
            approval_id=approval.id,
            reviewer=reviewer_user,
            reviewer_note="問題なし",
        )

        assert approved.status == "approved"
        assert approved.reviewer_id == reviewer_user.id
        assert approved.reviewer_note == "問題なし"

    @pytest.mark.asyncio
    async def test_approve_by_operator_fails(
        self,
        db_session: AsyncSession,
        operator_user: User,
    ):
        """operatorによる承認はPermissionDeniedErrorになること"""
        service = ApprovalService(db_session)
        approval = await service.request_approval(
            operation_type="publish",
            target_resource_type="listing_draft",
            target_resource_id="draft-004",
            requester_id=operator_user.id,
        )

        with pytest.raises(PermissionDeniedError):
            await service.approve(
                approval_id=approval.id,
                reviewer=operator_user,  # operatorは承認不可
            )

    @pytest.mark.asyncio
    async def test_reject_requires_note(
        self,
        db_session: AsyncSession,
        operator_user: User,
        reviewer_user: User,
    ):
        """却下時にnoteが空の場合はエラーになること"""
        service = ApprovalService(db_session)
        approval = await service.request_approval(
            operation_type="publish",
            target_resource_type="listing_draft",
            target_resource_id="draft-005",
            requester_id=operator_user.id,
        )

        with pytest.raises(ValueError, match="却下理由"):
            await service.reject(
                approval_id=approval.id,
                reviewer=reviewer_user,
                reviewer_note="",  # 空のnoteはエラー
            )

    @pytest.mark.asyncio
    async def test_assert_approved_raises_without_approval(
        self,
        db_session: AsyncSession,
    ):
        """未承認状態でassert_approvedを呼ぶとエラーになること"""
        service = ApprovalService(db_session)

        with pytest.raises(ApprovalRequiredError):
            await service.assert_approved(
                operation_type="publish",
                target_resource_type="listing_draft",
                target_resource_id="no-approval-draft",
            )

    @pytest.mark.asyncio
    async def test_assert_approved_succeeds_after_approval(
        self,
        db_session: AsyncSession,
        operator_user: User,
        reviewer_user: User,
    ):
        """承認後のassert_approvedは成功すること"""
        service = ApprovalService(db_session)
        approval = await service.request_approval(
            operation_type="publish",
            target_resource_type="listing_draft",
            target_resource_id="draft-006",
            requester_id=operator_user.id,
        )
        await service.approve(approval_id=approval.id, reviewer=reviewer_user)

        # これはエラーにならないこと
        result = await service.assert_approved(
            operation_type="publish",
            target_resource_type="listing_draft",
            target_resource_id="draft-006",
        )
        assert result.status == "approved"
