"""
リサーチ候補API
商品候補の登録・利益計算・スコアリング・出品候補昇格を管理する。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.core.exceptions import NotFoundError, ProfitRateViolationError
from app.models.user import User
from app.repositories.research_repo import ResearchCandidateRepository, ResearchScoreRepository
from app.schemas.research import (
    PromoteToListingRequest,
    ResearchCandidateCreate,
    ResearchCandidateDetailResponse,
    ResearchCandidateResponse,
    ResearchCandidateUpdate,
    ScoreOverrideRequest,
)
from app.services.audit_service import AuditService
from app.services.profit_calculator import ProfitCalculator
from app.services.scoring_service import ScoringInput, ScoringService

router = APIRouter(prefix="/research", tags=["リサーチ"])


@router.post(
    "/",
    response_model=ResearchCandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="リサーチ候補を登録する",
)
async def create_research_candidate(
    payload: ResearchCandidateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> ResearchCandidateResponse:
    """
    商品候補を新規登録する。
    目標価格が入力されている場合は利益計算も同時に実行する。
    """
    repo = ResearchCandidateRepository(db)
    audit = AuditService(db)

    # 利益計算（目標価格が入力された場合）
    profit_result = None
    if payload.target_sale_price_usd and payload.purchase_price_jpy:
        calculator = ProfitCalculator()
        profit_result = calculator.calculate(
            sale_price_usd=payload.target_sale_price_usd,
            purchase_price_jpy=payload.purchase_price_jpy,
            domestic_shipping_jpy=payload.domestic_shipping_jpy,
            international_shipping_usd=payload.international_shipping_usd,
            other_cost_jpy=payload.other_cost_jpy,
        )

    # 候補作成
    candidate = await repo.create(
        title=payload.title,
        brand=payload.brand,
        model_number=payload.model_number,
        jan_code=payload.jan_code,
        condition=payload.condition,
        notes=payload.notes,
        image_url_memo=payload.image_url_memo,
        purchase_price_jpy=payload.purchase_price_jpy,
        domestic_shipping_jpy=payload.domestic_shipping_jpy,
        international_shipping_usd=payload.international_shipping_usd,
        other_cost_jpy=payload.other_cost_jpy,
        target_sale_price_usd=payload.target_sale_price_usd,
        # 利益計算結果を保存
        estimated_profit_jpy=profit_result.gross_profit_jpy if profit_result else None,
        estimated_profit_rate=profit_result.gross_profit_rate if profit_result else None,
        estimated_receive_amount_jpy=profit_result.receive_amount_jpy if profit_result else None,
        min_profitable_price_usd=profit_result.min_profitable_price_usd if profit_result else None,
        profit_calc_detail=profit_result.to_dict() if profit_result else None,
        status="new",
    )

    await audit.log(
        action="research_candidate.create",
        resource_type="research_candidate",
        resource_id=str(candidate.id),
        user_id=current_user.id,
        after_state={"title": candidate.title, "status": candidate.status},
    )

    return ResearchCandidateResponse.model_validate(candidate)


@router.get(
    "/",
    response_model=list[ResearchCandidateResponse],
    summary="リサーチ候補一覧を取得する",
)
async def list_research_candidates(
    status: str | None = Query(None, description="ステータスでフィルタ"),
    order_by_score: bool = Query(True, description="スコア順に並べる"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResearchCandidateResponse]:
    repo = ResearchCandidateRepository(db)
    candidates = await repo.list_by_status(
        status=status,
        limit=limit,
        offset=offset,
        order_by_score=order_by_score,
    )
    return [ResearchCandidateResponse.model_validate(c) for c in candidates]


@router.get(
    "/{candidate_id}",
    response_model=ResearchCandidateDetailResponse,
    summary="リサーチ候補詳細を取得する",
)
async def get_research_candidate(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearchCandidateDetailResponse:
    repo = ResearchCandidateRepository(db)
    candidate = await repo.get_with_scores(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"候補ID {candidate_id} が見つかりません")
    return ResearchCandidateDetailResponse.model_validate(candidate)


@router.patch(
    "/{candidate_id}",
    response_model=ResearchCandidateResponse,
    summary="リサーチ候補を更新する",
)
async def update_research_candidate(
    candidate_id: uuid.UUID,
    payload: ResearchCandidateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> ResearchCandidateResponse:
    repo = ResearchCandidateRepository(db)
    candidate = await repo.get_by_id_or_raise(candidate_id)

    before_state = {"status": candidate.status, "title": candidate.title}

    update_data = payload.model_dump(exclude_none=True)

    # 価格更新があれば利益再計算
    price_fields = {
        "target_sale_price_usd", "purchase_price_jpy",
        "domestic_shipping_jpy", "international_shipping_usd", "other_cost_jpy"
    }
    if price_fields & set(update_data.keys()):
        sale_price = update_data.get("target_sale_price_usd", candidate.target_sale_price_usd)
        purchase_price = update_data.get("purchase_price_jpy", candidate.purchase_price_jpy)
        if sale_price and purchase_price:
            calculator = ProfitCalculator()
            profit_result = calculator.calculate(
                sale_price_usd=sale_price,
                purchase_price_jpy=purchase_price,
                domestic_shipping_jpy=update_data.get("domestic_shipping_jpy", candidate.domestic_shipping_jpy or 0),
                international_shipping_usd=update_data.get("international_shipping_usd", candidate.international_shipping_usd or 0),
                other_cost_jpy=update_data.get("other_cost_jpy", candidate.other_cost_jpy or 0),
            )
            update_data.update({
                "estimated_profit_jpy": profit_result.gross_profit_jpy,
                "estimated_profit_rate": profit_result.gross_profit_rate,
                "estimated_receive_amount_jpy": profit_result.receive_amount_jpy,
                "min_profitable_price_usd": profit_result.min_profitable_price_usd,
                "profit_calc_detail": profit_result.to_dict(),
            })

    await repo.update(candidate, **update_data)
    await AuditService(db).log(
        action="research_candidate.update",
        resource_type="research_candidate",
        resource_id=str(candidate_id),
        user_id=current_user.id,
        before_state=before_state,
        after_state=update_data,
    )

    return ResearchCandidateResponse.model_validate(candidate)


@router.post(
    "/{candidate_id}/calculate-profit",
    summary="利益を計算する（DBに保存しない試算）",
)
async def calculate_profit(
    candidate_id: uuid.UUID,
    target_price_usd: float = Query(..., gt=0, description="試算する販売価格（USD）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    指定された価格での利益を試算する。
    DBには保存しない（保存はupdate APIを使う）。
    """
    repo = ResearchCandidateRepository(db)
    candidate = await repo.get_by_id_or_raise(candidate_id)

    if not candidate.purchase_price_jpy:
        raise HTTPException(
            status_code=400,
            detail="仕入れ価格が登録されていません。先に登録してください",
        )

    calculator = ProfitCalculator()
    result = calculator.calculate(
        sale_price_usd=target_price_usd,
        purchase_price_jpy=candidate.purchase_price_jpy,
        domestic_shipping_jpy=candidate.domestic_shipping_jpy or 0,
        international_shipping_usd=candidate.international_shipping_usd or 0,
        other_cost_jpy=candidate.other_cost_jpy or 0,
    )
    return result.to_dict()


@router.post(
    "/{candidate_id}/score",
    response_model=ResearchCandidateResponse,
    summary="スコアリングを実行する",
)
async def run_scoring(
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> ResearchCandidateResponse:
    """
    リサーチ候補のスコアリングを実行してDBに保存する。
    利益計算結果が必要なため、先に利益計算を済ませておくこと。
    """
    repo = ResearchCandidateRepository(db)
    score_repo = ResearchScoreRepository(db)
    candidate = await repo.get_by_id_or_raise(candidate_id)

    if not candidate.target_sale_price_usd or not candidate.purchase_price_jpy:
        raise HTTPException(
            status_code=400,
            detail="スコアリングには仕入れ価格と目標販売価格が必要です",
        )

    calculator = ProfitCalculator()
    profit_result = calculator.calculate(
        sale_price_usd=candidate.target_sale_price_usd,
        purchase_price_jpy=candidate.purchase_price_jpy,
        domestic_shipping_jpy=candidate.domestic_shipping_jpy or 0,
        international_shipping_usd=candidate.international_shipping_usd or 0,
        other_cost_jpy=candidate.other_cost_jpy or 0,
    )

    scoring = ScoringService()
    score_input = ScoringInput(
        profit_result=profit_result,
        has_model_number=bool(candidate.model_number),
        has_brand_info=bool(candidate.brand),
    )
    score_result = scoring.score(score_input)

    # スコアをDBに保存
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
    )

    # 候補のスコアを更新
    await repo.update(
        candidate,
        total_score=score_result.total_score,
        status="scored",
    )

    return ResearchCandidateResponse.model_validate(candidate)


@router.post(
    "/{candidate_id}/score-override",
    response_model=ResearchCandidateResponse,
    summary="スコアを手動補正する",
)
async def override_score(
    candidate_id: uuid.UUID,
    payload: ScoreOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> ResearchCandidateResponse:
    """スコアを手動で補正する。補正理由は必須。"""
    repo = ResearchCandidateRepository(db)
    candidate = await repo.get_by_id_or_raise(candidate_id)

    await repo.update(
        candidate,
        score_override=payload.score,
        score_override_reason=payload.reason,
    )

    await AuditService(db).log(
        action="research_candidate.score_override",
        resource_type="research_candidate",
        resource_id=str(candidate_id),
        user_id=current_user.id,
        after_state={"score_override": payload.score, "reason": payload.reason},
    )

    return ResearchCandidateResponse.model_validate(candidate)
