"""
アプリケーション固有の例外クラス
HTTPステータスコードと日本語エラーメッセージを持つ。
FastAPIのexception_handlerでHTTPレスポンスに変換される。
"""

from typing import Any


class AppBaseException(Exception):
    """全カスタム例外の基底クラス"""

    def __init__(
        self,
        message: str,
        detail: Any = None,
        error_code: str = "UNKNOWN_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.error_code = error_code


# ─────────────────────────────────────
# 認証・認可
# ─────────────────────────────────────
class AuthenticationError(AppBaseException):
    """認証失敗"""
    def __init__(self, message: str = "認証に失敗しました") -> None:
        super().__init__(message, error_code="AUTH_FAILED")


class PermissionDeniedError(AppBaseException):
    """権限不足"""
    def __init__(self, message: str = "この操作を実行する権限がありません") -> None:
        super().__init__(message, error_code="PERMISSION_DENIED")


# ─────────────────────────────────────
# リソース
# ─────────────────────────────────────
class NotFoundError(AppBaseException):
    """リソースが見つからない"""
    def __init__(self, resource: str, identifier: Any) -> None:
        super().__init__(
            f"{resource}（ID: {identifier}）が見つかりません",
            error_code="NOT_FOUND",
        )


class DuplicateError(AppBaseException):
    """重複エラー"""
    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="DUPLICATE")


# ─────────────────────────────────────
# ビジネスルール違反
# ─────────────────────────────────────
class ProfitRateViolationError(AppBaseException):
    """
    最低利益率を下回る操作を試みた場合。
    価格改定・値下げ・セール時に必ずチェックする。
    """
    def __init__(
        self,
        actual_rate: float,
        min_rate: float,
        sku: str = "",
    ) -> None:
        msg = (
            f"最低利益率違反: 実際の利益率 {actual_rate:.1%} が"
            f"最低利益率 {min_rate:.1%} を下回っています"
        )
        if sku:
            msg += f"（SKU: {sku}）"
        super().__init__(msg, error_code="PROFIT_RATE_VIOLATION")
        self.actual_rate = actual_rate
        self.min_rate = min_rate


class ProfitAmountViolationError(AppBaseException):
    """最低利益額を下回る操作"""
    def __init__(
        self,
        actual_amount: float,
        min_amount: float,
        sku: str = "",
    ) -> None:
        msg = (
            f"最低利益額違反: 実際の利益額 ¥{actual_amount:,.0f} が"
            f"最低利益額 ¥{min_amount:,.0f} を下回っています"
        )
        if sku:
            msg += f"（SKU: {sku}）"
        super().__init__(msg, error_code="PROFIT_AMOUNT_VIOLATION")


class ApprovalRequiredError(AppBaseException):
    """承認が必要な操作を未承認で実行しようとした場合"""
    def __init__(self, operation: str) -> None:
        super().__init__(
            f"この操作（{operation}）には承認が必要です",
            error_code="APPROVAL_REQUIRED",
        )


class DryRunBlockedError(AppBaseException):
    """dry-runモードで本番操作を試みた場合"""
    def __init__(self, operation: str) -> None:
        super().__init__(
            f"dry-runモードのため実行できません: {operation}",
            error_code="DRY_RUN_BLOCKED",
        )


class ExcludedSkuError(AppBaseException):
    """除外SKUを操作しようとした場合"""
    def __init__(self, sku: str) -> None:
        super().__init__(
            f"SKU '{sku}' は除外リストに含まれており操作できません",
            error_code="EXCLUDED_SKU",
        )


class InvalidStatusTransitionError(AppBaseException):
    """許可されていないステータス遷移"""
    def __init__(self, current: str, target: str, resource: str = "") -> None:
        msg = f"ステータスを {current} から {target} に変更することはできません"
        if resource:
            msg += f"（{resource}）"
        super().__init__(msg, error_code="INVALID_STATUS_TRANSITION")


# ─────────────────────────────────────
# 外部API
# ─────────────────────────────────────
class EbayApiError(AppBaseException):
    """eBay API呼び出しエラー"""
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        ebay_error_id: str | None = None,
        raw_response: dict | None = None,
    ) -> None:
        super().__init__(
            f"eBay APIエラー: {message}",
            detail=raw_response,
            error_code="EBAY_API_ERROR",
        )
        self.status_code = status_code
        self.ebay_error_id = ebay_error_id


class EbayTokenExpiredError(EbayApiError):
    """eBay OAuthトークン期限切れ"""
    def __init__(self) -> None:
        super().__init__(
            "eBayのアクセストークンが期限切れです。再認証してください",
            error_code="EBAY_TOKEN_EXPIRED",  # type: ignore[call-arg]
        )


class AiGenerationError(AppBaseException):
    """AI生成エラー"""
    def __init__(self, message: str) -> None:
        super().__init__(
            f"AI生成に失敗しました: {message}",
            error_code="AI_GENERATION_ERROR",
        )


# ─────────────────────────────────────
# バリデーション
# ─────────────────────────────────────
class ValidationError(AppBaseException):
    """入力値バリデーションエラー"""
    def __init__(self, message: str, field: str = "") -> None:
        super().__init__(message, detail={"field": field}, error_code="VALIDATION_ERROR")


class ProhibitedWordError(ValidationError):
    """禁止語検出"""
    def __init__(self, words: list[str]) -> None:
        super().__init__(
            f"禁止語が含まれています: {', '.join(words)}",
            field="content",
        )
        self.error_code = "PROHIBITED_WORD"
        self.words = words
