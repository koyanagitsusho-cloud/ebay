"""
Celeryアプリケーション設定
非同期ジョブワーカーの設定を一元管理する。

起動方法:
  cd backend
  celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

注意:
- タスクの失敗はCeleryのリトライとJobテーブル両方で管理する
- 重要な操作（eBay公開等）は必ずJobテーブルに記録する
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ebay_automation",
    broker=settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.listing_tasks",
        "app.workers.research_tasks",
    ],
)

# ─────────────────────────────────────
# Celery設定
# ─────────────────────────────────────
celery_app.conf.update(
    # タスクシリアライズ
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # タイムゾーン
    timezone="Asia/Tokyo",
    enable_utc=True,

    # リトライ設定
    task_acks_late=True,          # タスク完了後にACKする（失敗時に再キュー）
    task_reject_on_worker_lost=True,

    # 結果の保持期間
    result_expires=60 * 60 * 24 * 7,  # 7日間

    # ワーカー設定
    worker_prefetch_multiplier=1,  # 1タスクずつ処理（重い処理対応）

    # キュー定義
    task_queues={
        "high": {"exchange": "high", "routing_key": "high"},
        "default": {"exchange": "default", "routing_key": "default"},
        "low": {"exchange": "low", "routing_key": "low"},
    },
    task_default_queue="default",

    # タスクルーティング
    task_routes={
        "app.workers.listing_tasks.publish_to_ebay": {"queue": "high"},
        "app.workers.listing_tasks.generate_listing_content": {"queue": "default"},
        "app.workers.research_tasks.recalculate_scores": {"queue": "low"},
    },
)
