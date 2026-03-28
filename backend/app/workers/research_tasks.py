"""
リサーチ関連Celeryタスク
スコア再計算・利益再計算を非同期で処理する。
"""

import asyncio
import traceback
import uuid

from app.core.logging_config import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    name="app.workers.research_tasks.recalculate_scores",
)
def recalculate_scores(self, job_id: str, candidate_ids: list[str] | None = None) -> dict:
    """
    リサーチ候補のスコアを一括再計算するタスク。
    candidate_ids が None の場合は全候補を再計算する。
    """

    async def _run() -> dict:
        from app.core.database import get_db_context
        from app.repositories.job_repo import JobRepository
        from app.repositories.research_repo import ResearchCandidateRepository, ResearchScoreRepository
        from app.services.profit_calculator import ProfitCalculator
        from app.services.scoring_service import ScoringInput, ScoringService

        async with get_db_context() as db:
            job_repo = JobRepository(db)
            job = await job_repo.get_by_id_or_raise(uuid.UUID(job_id))
            await job_repo.mark_running(job, self.request.id)

            try:
                repo = ResearchCandidateRepository(db)
                score_repo = ResearchScoreRepository(db)
                scoring = ScoringService()
                calculator = ProfitCalculator()

                if candidate_ids:
                    candidates = [
                        await repo.get_by_id_or_raise(uuid.UUID(cid))
                        for cid in candidate_ids
                    ]
                else:
                    candidates = await repo.list_by_status(limit=1000)

                success_count = 0
                skip_count = 0

                for candidate in candidates:
                    if not candidate.target_sale_price_usd or not candidate.purchase_price_jpy:
                        skip_count += 1
                        continue

                    profit = calculator.calculate(
                        sale_price_usd=candidate.target_sale_price_usd,
                        purchase_price_jpy=candidate.purchase_price_jpy,
                        domestic_shipping_jpy=candidate.domestic_shipping_jpy or 0,
                        international_shipping_usd=candidate.international_shipping_usd or 0,
                        other_cost_jpy=candidate.other_cost_jpy or 0,
                    )
                    score_input = ScoringInput(
                        profit_result=profit,
                        has_model_number=bool(candidate.model_number),
                        has_brand_info=bool(candidate.brand),
                    )
                    score_result = scoring.score(score_input)

                    await score_repo.create(
                        candidate_id=candidate.id,
                        profit_score=score_result.profit_score,
                        competition_score=score_result.competition_score,
                        sellability_score=score_result.sellability_score,
                        listing_ease_score=score_result.listing_ease_score,
                        risk_score=score_result.risk_score,
                        total_score=score_result.total_score,
                        return_risk=score_result.return_risk,
                        authenticity_risk=score_result.authenticity_risk,
                        fragility_risk=score_result.fragility_risk,
                        prohibited_risk=score_result.prohibited_risk,
                        score_basis=score_result.score_basis,
                        scored_by="system",
                        version=2,
                    )
                    await repo.update(candidate, total_score=score_result.total_score)
                    success_count += 1

                result = {
                    "total": len(candidates),
                    "success": success_count,
                    "skipped": skip_count,
                }
                await job_repo.mark_success(job, result)
                return result

            except Exception as exc:
                tb = traceback.format_exc()
                await job_repo.mark_failed(job, str(exc), tb)
                raise

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("スコア再計算タスク失敗", job_id=job_id, error=str(exc))
        raise self.retry(exc=exc)
