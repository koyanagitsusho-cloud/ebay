"""
全モデル共通の基底フィールド定義
created_at / updated_at / UUID主キーを全モデルで統一する。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimestampMixin:
    """作成日時・更新日時を自動管理するMixin"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="レコード作成日時",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="レコード更新日時",
    )


class UUIDPrimaryKeyMixin:
    """UUID主キーMixin"""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        comment="主キー（UUID）",
    )
