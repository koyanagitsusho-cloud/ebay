"""
FastAPIアプリケーション エントリーポイント
例外ハンドラ・ミドルウェア・ルーター登録を行う。
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import (
    AppBaseException,
    ApprovalRequiredError,
    AuthenticationError,
    DryRunBlockedError,
    EbayApiError,
    NotFoundError,
    PermissionDeniedError,
    ProhibitedWordError,
    ProfitAmountViolationError,
    ProfitRateViolationError,
)
from app.core.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


# ─────────────────────────────────────
# アプリライフサイクル
# ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """アプリ起動・終了時の処理"""
    setup_logging()
    logger.info(
        "アプリ起動",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        ebay_env=settings.EBAY_ENVIRONMENT,
        dry_run_default=settings.DRY_RUN_DEFAULT,
    )
    yield
    logger.info("アプリ終了")


# ─────────────────────────────────────
# FastAPIアプリ作成
# ─────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="eBay販売業務自動化ツール（発送以外）",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# ─────────────────────────────────────
# CORS設定
# ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────
# ルーター登録
# ─────────────────────────────────────
app.include_router(api_router)


# ─────────────────────────────────────
# 例外ハンドラ
# アプリ固有の例外をHTTPレスポンスに変換する
# ─────────────────────────────────────
@app.exception_handler(AuthenticationError)
async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(PermissionDeniedError)
async def permission_error_handler(request: Request, exc: PermissionDeniedError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(ProfitRateViolationError)
async def profit_rate_violation_handler(
    request: Request, exc: ProfitRateViolationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "detail": {
                "actual_rate": f"{exc.actual_rate:.1%}",
                "min_rate": f"{exc.min_rate:.1%}",
            },
        },
    )


@app.exception_handler(ProfitAmountViolationError)
async def profit_amount_violation_handler(
    request: Request, exc: ProfitAmountViolationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(ApprovalRequiredError)
async def approval_required_handler(
    request: Request, exc: ApprovalRequiredError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(DryRunBlockedError)
async def dry_run_blocked_handler(
    request: Request, exc: DryRunBlockedError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(EbayApiError)
async def ebay_api_error_handler(request: Request, exc: EbayApiError) -> JSONResponse:
    logger.error("eBay APIエラー発生", message=exc.message, error_id=exc.ebay_error_id)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "ebay_error_id": exc.ebay_error_id,
        },
    )


@app.exception_handler(ProhibitedWordError)
async def prohibited_word_handler(
    request: Request, exc: ProhibitedWordError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "detail": {"prohibited_words": exc.words},
        },
    )


@app.exception_handler(AppBaseException)
async def app_base_exception_handler(
    request: Request, exc: AppBaseException
) -> JSONResponse:
    """上記でキャッチされなかったアプリ例外のフォールバック"""
    logger.error("アプリ例外", error_code=exc.error_code, message=exc.message)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_code": exc.error_code, "message": exc.message},
    )


# ─────────────────────────────────────
# ヘルスチェック
# ─────────────────────────────────────
@app.get("/health", tags=["システム"])
async def health_check() -> dict:
    """ヘルスチェックエンドポイント（認証不要）"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "ebay_environment": settings.EBAY_ENVIRONMENT,
        "dry_run_default": settings.DRY_RUN_DEFAULT,
    }
