"""
監査ログサービス
全ての重要操作を監査ログに記録する。
誰が、いつ、何を、どう変更したかを追跡できるようにする。

使用方法:
  audit_service = AuditService(db)
  await audit_service.log(
      action="listing.publish",
      resource_type="listing_draft",
      resource_id=str(draft.id),
      user_id=current_user.id,
      before_state=before,
      after_state=after,
  )
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.job import AuditLog

logger = get_logger(__name__)


class AuditService:
    """
    監査ログ記録サービス。
    重要操作ごとに必ず呼び出す。
    ログの削除・改竄は禁止（DBレベルで権限を絞ること）。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: uuid.UUID | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        result: str = "success",
        error_message: str | None = None,
    ) -> AuditLog:
        """
        監査ログを記録する。

        action 命名規則: "{resource}.{operation}"
        例: "product.create", "listing.submit_for_review", "listing.publish"
            "price.update", "promotion.execute", "user.login"
        """
        # 差分計算
        diff = self._compute_diff(before_state, after_state)

        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            diff=diff,
            metadata=metadata,
            result=result,
            error_message=error_message,
        )

        self.db.add(audit_log)
        # セッションのコミットは呼び出し元の責任
        # （トランザクション境界を上位で制御するため）

        logger.info(
            "監査ログ記録",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=str(user_id) if user_id else None,
            result=result,
        )

        return audit_log

    async def log_failure(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: uuid.UUID | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """失敗操作の監査ログ（便利メソッド）"""
        return await self.log(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            result="failed",
            error_message=error_message,
            metadata=metadata,
        )

    async def log_blocked(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> AuditLog:
        """ブロックされた操作の監査ログ（権限不足・安全装置発動時）"""
        return await self.log(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            result="blocked",
            error_message=reason,
        )

    @staticmethod
    def _compute_diff(
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """
        変更前後の差分を計算する。
        変更されたキーのみを返す（変更なし / 追加 / 削除 / 更新）。
        """
        if before is None and after is None:
            return None
        if before is None:
            return {"added": after}
        if after is None:
            return {"removed": before}

        changed: dict[str, Any] = {}
        all_keys = set(before.keys()) | set(after.keys())

        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)
            if before_val != after_val:
                changed[key] = {"before": before_val, "after": after_val}

        return changed if changed else None
