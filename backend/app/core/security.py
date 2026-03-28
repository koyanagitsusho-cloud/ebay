"""
認証・認可ユーティリティ
JWTベースの管理者認証（初期MVPのためシンプルに設計）。
将来的にOAuth2やSSO対応に拡張可能。
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

ALGORITHM = "HS256"


# ─────────────────────────────────────
# パスワードハッシュ
# ─────────────────────────────────────
def hash_password(plain_password: str) -> str:
    """bcryptでパスワードをハッシュ化"""
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """パスワード照合"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


# ─────────────────────────────────────
# JWTトークン
# ─────────────────────────────────────
def create_access_token(
    subject: str | int,
    extra_data: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    JWTアクセストークンを生成する。
    subject: ユーザーID
    extra_data: role等の追加情報
    """
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if extra_data:
        payload.update(extra_data)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    JWTトークンをデコードして検証する。
    無効・期限切れの場合はAuthenticationErrorを送出。
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise AuthenticationError("不正なトークンタイプです")
        return payload
    except JWTError as e:
        logger.warning("JWT decode failed", error=str(e))
        raise AuthenticationError("トークンが無効または期限切れです") from e


# ─────────────────────────────────────
# 権限チェック
# ─────────────────────────────────────
ROLE_HIERARCHY = {
    "admin": 3,
    "reviewer": 2,
    "operator": 1,
}


def require_role(user_role: str, required_role: str) -> None:
    """
    ユーザーロールが要求レベルを満たすか確認する。
    満たさない場合はPermissionDeniedErrorを送出。

    ロール階層:
    admin >= reviewer >= operator
    """
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 999)

    if user_level < required_level:
        raise PermissionDeniedError(
            f"この操作には '{required_role}' 以上の権限が必要です（現在: '{user_role}'）"
        )
