"""
認証API
ログイン・ユーザー情報取得を提供する。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["認証"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str
    display_name: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str

    model_config = {"from_attributes": True}


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """ログイン。JWTトークンを返す。"""
    result = await db.execute(
        select(User).where(User.email == payload.email, User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません",
        )

    token = create_access_token(
        subject=str(user.id),
        extra_data={"role": user.role, "email": user.email},
    )

    return LoginResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        display_name=user.display_name,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """ログイン中のユーザー情報を取得する"""
    return UserResponse.model_validate(current_user)
