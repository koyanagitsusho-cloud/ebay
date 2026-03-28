"""
出品関連Celeryタスク
AI生成・eBay公開を非同期で処理する。
重要: タスクの失敗は必ずJobテーブルに記録する。
"""

import asyncio
import traceback
import uuid
from datetime import UTC, datetime

from app.core.logging_config import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.workers.listing_tasks.generate_listing_content",
)
def generate_listing_content(
    self,
    job_id: str,
    product_id: str,
    generation_params: dict,
) -> dict:
    """
    出品情報をAI生成するCeleryタスク。
    JobテーブルのステータスをDBに更新しながら処理する。
    """
    logger.info("AI生成タスク開始", job_id=job_id, product_id=product_id)

    async def _run() -> dict:
        from app.core.database import get_db_context
        from app.repositories.job_repo import JobRepository
        from app.services.listing_generator import ListingGeneratorInput, ListingGeneratorService

        async with get_db_context() as db:
            job_repo = JobRepository(db)
            job = await job_repo.get_by_id_or_raise(uuid.UUID(job_id))

            try:
                await job_repo.mark_running(job, self.request.id)

                generator = ListingGeneratorService()
                inp = ListingGeneratorInput(
                    product_title=generation_params.get("product_title", ""),
                    brand=generation_params.get("brand"),
                    model_number=generation_params.get("model_number"),
                    condition=generation_params.get("condition", "USED_GOOD"),
                    features=generation_params.get("features"),
                    included_items=generation_params.get("included_items"),
                    category_hint=generation_params.get("category_hint"),
                )
                output = await generator.generate(inp)

                result = {
                    "title_candidates": output.title_candidates,
                    "description": output.description,
                    "item_specifics": output.item_specifics,
                    "condition_description": output.condition_description,
                    "warnings": output.warnings,
                    "is_valid": output.is_valid,
                    "token_usage": {
                        "prompt": output.prompt_tokens,
                        "completion": output.completion_tokens,
                    },
                }

                await job_repo.mark_success(job, result)
                logger.info("AI生成タスク完了", job_id=job_id)
                return result

            except Exception as exc:
                tb = traceback.format_exc()
                await job_repo.mark_failed(job, str(exc), tb)
                raise

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("AI生成タスク失敗", job_id=job_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=2,          # 公開は慎重にリトライ回数を少なく
    default_retry_delay=120,
    name="app.workers.listing_tasks.publish_to_ebay",
)
def publish_to_ebay(
    self,
    job_id: str,
    draft_id: str,
    publish_params: dict,
) -> dict:
    """
    eBayに出品するCeleryタスク。
    dry-runフラグを必ずチェックすること。
    重要: このタスクは本番操作のため、エラー時に冪等性を保証する必要がある。
    TODO: 冪等性キー（idempotency key）の実装を追加すること
    """
    logger.info(
        "eBay公開タスク開始",
        job_id=job_id,
        draft_id=draft_id,
        dry_run=publish_params.get("dry_run", True),
    )

    async def _run() -> dict:
        from app.core.database import get_db_context
        from app.repositories.job_repo import JobRepository
        from app.repositories.listing_repo import ListingDraftRepository

        async with get_db_context() as db:
            job_repo = JobRepository(db)
            job = await job_repo.get_by_id_or_raise(uuid.UUID(job_id))
            await job_repo.mark_running(job, self.request.id)

            try:
                # dry-runの場合は実際のAPIを呼ばない
                if publish_params.get("dry_run", True):
                    result = {
                        "dry_run": True,
                        "message": "dry-runのため実際には公開しませんでした",
                        "draft_id": draft_id,
                    }
                    await job_repo.mark_success(job, result)
                    return result

                # 実際の公開処理は listings.py の publish_listing を参照
                # TODO: ここに公開ロジックを移動する（現在はAPI層に実装済み）
                result = {"message": "TODO: 公開ロジックをここに移動する"}
                await job_repo.mark_success(job, result)
                return result

            except Exception as exc:
                tb = traceback.format_exc()
                await job_repo.mark_failed(job, str(exc), tb)
                raise

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("eBay公開タスク失敗", job_id=job_id, error=str(exc))
        raise self.retry(exc=exc)
