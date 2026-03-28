"""
FastAPI依存性注入
認証・DBセッション・権限チェックを一元管理する。
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token, require_role
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    JWTトークンからログインユーザーを取得する依存性。
    無効トークン・存在しないユーザーはHTTP401を返す。
    """
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザーが見つかりません",
        )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """admin権限チェック依存性"""
    try:
        require_role(current_user.role, "admin")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    return current_user


def require_reviewer(current_user: User = Depends(get_current_user)) -> User:
    """reviewer以上の権限チェック依存性"""
    try:
        require_role(current_user.role, "reviewer")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    return current_user


def require_operator(current_user: User = Depends(get_current_user)) -> User:
    """operator以上の権限チェック依存性"""
    try:
        require_role(current_user.role, "operator")
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    return current_user
