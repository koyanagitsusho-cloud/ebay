"""
構造化ログ設定
JSON形式でログを出力し、監査・デバッグ・運用監視に対応する。
シークレット情報のマスク処理も行う。
"""

import logging
import re
import sys
from typing import Any

import structlog

from app.core.config import settings

# ─────────────────────────────────────
# マスク対象パターン
# ─────────────────────────────────────
_SENSITIVE_PATTERNS = [
    r"(?i)(password|secret|token|api_key|apikey|authorization|refresh_token)[\"']?\s*[:=]\s*[\"']?[\w\-\.]+",
    r"(?i)(Bearer\s+)[\w\-\.]+",
]
_SENSITIVE_RE = [re.compile(p) for p in _SENSITIVE_PATTERNS]


def _mask_sensitive(value: str) -> str:
    """ログ文字列内のシークレット情報をマスクする"""
    if not settings.LOG_SENSITIVE_MASK:
        return value
    result = value
    for pattern in _SENSITIVE_RE:
        result = pattern.sub(lambda m: m.group(0)[:20] + "***MASKED***", result)
    return result


# ─────────────────────────────────────
# structlog プロセッサ
# ─────────────────────────────────────
def add_app_context(
    logger: logging.Logger,
    method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """共通コンテキスト情報を全ログに付加する"""
    event_dict["app"] = settings.APP_NAME
    event_dict["env"] = settings.ENVIRONMENT
    event_dict["version"] = settings.APP_VERSION
    return event_dict


def mask_sensitive_data(
    logger: logging.Logger,
    method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """ログイベント内のシークレット情報をマスクする"""
    if not settings.LOG_SENSITIVE_MASK:
        return event_dict
    if "event" in event_dict and isinstance(event_dict["event"], str):
        event_dict["event"] = _mask_sensitive(event_dict["event"])
    return event_dict


# ─────────────────────────────────────
# ログ初期化
# ─────────────────────────────────────
def setup_logging() -> None:
    """
    アプリ起動時に一度だけ呼び出す。
    structlogとPython標準loggingを連携させる。
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 標準ライブラリのloggingを設定
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # サードパーティライブラリのログを抑制
    for noisy_logger in ["uvicorn.access", "sqlalchemy.engine"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # structlogのプロセッサチェーン設定
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_app_context,
        mask_sensitive_data,
    ]

    if settings.LOG_FORMAT == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """モジュール用ロガーを返す"""
    return structlog.get_logger(name)
