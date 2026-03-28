"""共通レスポンススキーマ"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel):
    """成功レスポンス"""
    success: bool = True
    message: str = "成功しました"


class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    success: bool = False
    error_code: str
    message: str
    detail: Any = None


class PaginatedResponse(BaseModel, Generic[T]):
    """ページネーションレスポンス"""
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool
