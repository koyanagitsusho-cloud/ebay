"""
自動リサーチCeleryタスク
楽天×eBay自動リサーチを定期実行する。
"""

import asyncio
import traceback

from app.core.logging_config import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=2,
    name="app.workers.auto_research_tasks.run_auto_research",
)
def run_auto_research(
    self,
    keywords: list[str] | None = None,
    min_price_jpy: int | None = None,
    max_price_jpy: int | None = None,
    min_score: float | None = None,
) -> dict:
    """
    自動リサーチタスク。
    楽天市場から商品を検索し、eBay相場と比較して利益が出る候補を自動登録する。

    Args:
        keywords: 検索キーワードリスト（Noneで設定値を使用）
        min_price_jpy: 仕入れ価格下限（円）
        max_price_jpy: 仕入れ価格上限（円）
        min_score: 候補登録の最低スコア
    """

    async def _run() -> dict:
        from app.core.database import get_db_context
        from app.services.auto_research_service import AutoResearchService

        async with get_db_context() as db:
            service = AutoResearchService(db)
            results = await service.run_all_keywords(keywords=keywords)

            summary = {
                "keywords_processed": len(results),
                "total_rakuten_found": sum(r.rakuten_found for r in results),
                "total_ebay_price_found": sum(r.ebay_price_found for r in results),
                "total_candidates_created": sum(r.candidates_created for r in results),
                "total_skipped_low_profit": sum(r.skipped_low_profit for r in results),
                "total_skipped_duplicate": sum(r.skipped_duplicate for r in results),
                "total_errors": sum(r.errors for r in results),
                "per_keyword": [
                    {
                        "keyword": r.keyword,
                        "rakuten_found": r.rakuten_found,
                        "candidates_created": r.candidates_created,
                        "skipped_low_profit": r.skipped_low_profit,
                    }
                    for r in results
                ],
            }
            logger.info("自動リサーチタスク完了", **summary)
            return summary

    try:
        return asyncio.run(_run())
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("自動リサーチタスク失敗", error=str(exc), traceback=tb)
        raise self.retry(exc=exc, countdown=60)
