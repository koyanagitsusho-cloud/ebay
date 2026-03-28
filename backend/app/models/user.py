"""
ユーザーモデル
初期MVPではシンプルなadmin/reviewer/operatorの3ロール構成。
"""

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    管理ユーザー。
    eBay販売担当者が使用する内部管理アカウント。

    ロール:
    - admin: 全操作可能、監査ログ閲覧可
    - reviewer: 出品公開・セール実行・承認操作可
    - operator: 下書き作成・編集可、公開不可
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="メールアドレス（ログインID）",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcryptハッシュ済みパスワード（平文不可）",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="表示名",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="operator",
        comment="ロール: admin / reviewer / operator",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="アカウント有効フラグ",
    )

    # リレーション
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        "AuditLog",
        back_populates="user",
        lazy="noload",
    )
    approvals: Mapped[list["Approval"]] = relationship(  # noqa: F821
        "Approval",
        back_populates="reviewer",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
