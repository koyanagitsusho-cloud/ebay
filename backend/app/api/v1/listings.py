"""
出品下書きAPI
AI生成・編集・承認依頼・公開（dry-run含む）を管理する。
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_operator, require_reviewer
from app.clients.ebay.inventory_client import EbayInventoryClient
from app.clients.ebay.offer_client import EbayOfferClient
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ApprovalRequiredError, DryRunBlockedError
from app.models.user import User
from app.repositories.listing_repo import ApprovalRepository, ListingDraftRepository
from app.repositories.research_repo import ResearchCandidateRepository
from app.schemas.listing import (
    ApprovalActionRequest,
    ApprovalResponse,
    ListingDraftResponse,
    ListingDraftUpdate,
    ListingGenerateRequest,
    PublishRequest,
    SubmitForReviewRequest,
)
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.listing_generator import ListingGeneratorInput, ListingGeneratorService

router = APIRouter(prefix="/listings", tags=["出品管理"])


@router.post(
    "/generate",
    summary="出品情報をAI生成する（下書きは作成しない）",
)
async def generate_listing_info(
    payload: ListingGenerateRequest,
    current_user: User = Depends(require_operator),
) -> dict:
    """
    商品情報からAIで出品情報を生成する。
    この時点では下書きは作成しない。
    生成結果を確認してから /drafts エンドポイントで下書き保存する。

    ★ AI生成文は必ず人が確認すること（自動公開禁止）
    """
    try:
        generator = ListingGeneratorService()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    inp = ListingGeneratorInput(
        product_title=payload.product_title,
        brand=payload.brand,
        model_number=payload.model_number,
        condition=payload.condition,
        features=payload.features,
        included_items=payload.included_items,
        missing_items=payload.missing_items,
        scratches_or_stains=payload.scratches_or_stains,
        operation_check=payload.operation_check,
        size_info=payload.size_info,
        color=payload.color,
        category_hint=payload.category_hint,
        cautions=payload.cautions,
    )

    output = await generator.generate(inp)

    return {
        "title_candidates": output.title_candidates,
        "description": output.description,
        "item_specifics": output.item_specifics,
        "condition_description": output.condition_description,
        "return_policy_text": output.return_policy_text,
        "warnings": output.warnings,
        "missing_fields": output.missing_fields,
        "is_valid": output.is_valid,
        "model_used": output.model_used,
        "token_usage": {
            "prompt": output.prompt_tokens,
            "completion": output.completion_tokens,
        },
    }


@router.post(
    "/drafts",
    response_model=ListingDraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="出品下書きを作成する",
)
async def create_listing_draft(
    product_id: uuid.UUID,
    generate_payload: ListingGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> ListingDraftResponse:
    """
    商品の出品下書きを作成する。
    AI生成を実行して結果を下書きとして保存する。
    生成結果はそのまま公開せず、必ず人が確認する。
    """
    from app.models.listing import GeneratedContent, ListingDraft
    from app.models.product import Product
    from sqlalchemy import select

    # 商品の存在確認
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"商品ID {product_id} が見つかりません")

    # 既存下書きチェック（1商品1下書き）
    draft_repo = ListingDraftRepository(db)
    existing = await draft_repo.get_by_product_id(product_id)
    if existing and existing.status not in ("rejected", "ended"):
        raise HTTPException(
            status_code=409,
            detail=f"この商品には既に下書きがあります（ID: {existing.id}, 状態: {existing.status}）",
        )

    # AI生成
    try:
        generator = ListingGeneratorService()
        inp = ListingGeneratorInput(
            product_title=generate_payload.product_title or product.title,
            brand=generate_payload.brand or product.brand,
            model_number=generate_payload.model_number or product.model_number,
            condition=generate_payload.condition or product.condition,
            features=generate_payload.features,
            included_items=generate_payload.included_items,
            category_hint=generate_payload.category_hint or product.category_hint,
        )
        gen_output = await generator.generate(inp)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI生成エラー: {e}") from e

    # 下書き作成
    draft = ListingDraft(
        product_id=product_id,
        title_candidates=gen_output.title_candidates,
        description_generated=gen_output.description,
        condition=product.condition,
        condition_description=gen_output.condition_description,
        item_specifics_candidates=gen_output.item_specifics,
        validation_warnings=gen_output.warnings,
        missing_required_fields=gen_output.missing_fields,
        is_valid=gen_output.is_valid,
        status="draft",
    )
    db.add(draft)
    await db.flush()

    # 生成履歴を保存
    gen_content = GeneratedContent(
        listing_draft_id=draft.id,
        content_type="full_listing",
        input_data=inp.to_dict(),
        generated_output={
            "title_candidates": gen_output.title_candidates,
            "description": gen_output.description,
            "item_specifics": gen_output.item_specifics,
        },
        model_used=gen_output.model_used,
        prompt_tokens=gen_output.prompt_tokens,
        completion_tokens=gen_output.completion_tokens,
        generation_status="success",
    )
    db.add(gen_content)

    await AuditService(db).log(
        action="listing_draft.create",
        resource_type="listing_draft",
        resource_id=str(draft.id),
        user_id=current_user.id,
        after_state={"product_id": str(product_id), "status": "draft"},
    )

    return ListingDraftResponse.model_validate(draft)


@router.get(
    "/drafts",
    response_model=list[ListingDraftResponse],
    summary="出品下書き一覧を取得する",
)
async def list_drafts(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ListingDraftResponse]:
    repo = ListingDraftRepository(db)
    drafts = await repo.list_by_status(status=status, limit=limit, offset=offset)
    return [ListingDraftResponse.model_validate(d) for d in drafts]


@router.get(
    "/drafts/pending-approval",
    response_model=list[ListingDraftResponse],
    summary="承認待ち下書き一覧を取得する",
)
async def list_pending_approval(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ListingDraftResponse]:
    repo = ListingDraftRepository(db)
    drafts = await repo.list_pending_approval()
    return [ListingDraftResponse.model_validate(d) for d in drafts]


@router.patch(
    "/drafts/{draft_id}",
    response_model=ListingDraftResponse,
    summary="出品下書きを編集する",
)
async def update_draft(
    draft_id: uuid.UUID,
    payload: ListingDraftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> ListingDraftResponse:
    """AI生成内容を人が編集する。タイトル・説明文・価格等を更新できる。"""
    repo = ListingDraftRepository(db)
    draft = await repo.get_by_id_or_raise(draft_id)

    if draft.status == "published":
        raise HTTPException(status_code=400, detail="公開済みの下書きは直接編集できません")

    before_state = {"status": draft.status}
    update_data = payload.model_dump(exclude_none=True)

    # タイトル文字数チェック
    if "title_selected" in update_data and len(update_data["title_selected"]) > 80:
        raise HTTPException(
            status_code=400,
            detail=f"タイトルが{len(update_data['title_selected'])}文字です（上限80文字）",
        )

    await repo.update(draft, **update_data)

    await AuditService(db).log(
        action="listing_draft.update",
        resource_type="listing_draft",
        resource_id=str(draft_id),
        user_id=current_user.id,
        before_state=before_state,
        after_state=update_data,
    )

    return ListingDraftResponse.model_validate(draft)


@router.post(
    "/drafts/{draft_id}/submit-for-review",
    response_model=ListingDraftResponse,
    summary="承認依頼を送る",
)
async def submit_for_review(
    draft_id: uuid.UUID,
    payload: SubmitForReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> ListingDraftResponse:
    """
    下書きを承認レビューに送る。
    タイトルが選択されていない・価格未設定の場合はエラー。
    """
    repo = ListingDraftRepository(db)
    draft = await repo.get_by_id_or_raise(draft_id)

    if draft.status not in ("draft", "rejected"):
        raise HTTPException(
            status_code=400,
            detail=f"このステータスでは承認依頼できません（現在: {draft.status}）",
        )

    # 必須項目チェック
    missing = []
    if not draft.title_selected:
        missing.append("タイトル（title_selected）")
    if not draft.listing_price_usd:
        missing.append("出品価格（listing_price_usd）")
    if not draft.description_edited and not draft.description_generated:
        missing.append("説明文")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"承認依頼前に必須項目を入力してください: {', '.join(missing)}",
        )

    approval_service = ApprovalService(db)
    await approval_service.request_approval(
        operation_type="publish",
        target_resource_type="listing_draft",
        target_resource_id=str(draft_id),
        requester_id=current_user.id,
        listing_draft_id=draft_id,
        requester_note=payload.note,
    )

    await repo.update(
        draft,
        status="pending_review",
        submitted_at=datetime.now(UTC).isoformat(),
    )

    await AuditService(db).log(
        action="listing_draft.submit_for_review",
        resource_type="listing_draft",
        resource_id=str(draft_id),
        user_id=current_user.id,
    )

    return ListingDraftResponse.model_validate(draft)


@router.post(
    "/approvals/{approval_id}/review",
    response_model=ApprovalResponse,
    summary="承認または却下する",
)
async def review_approval(
    approval_id: uuid.UUID,
    payload: ApprovalActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
) -> ApprovalResponse:
    """
    承認または却下する。
    却下の場合はnoteが必須。
    reviewer 以上の権限が必要。
    """
    approval_service = ApprovalService(db)

    if payload.action == "approve":
        approval = await approval_service.approve(
            approval_id=approval_id,
            reviewer=current_user,
            reviewer_note=payload.note,
        )
        # 対応する下書きのステータスも更新
        if approval.listing_draft_id:
            draft_repo = ListingDraftRepository(db)
            draft = await draft_repo.get_by_id_or_raise(approval.listing_draft_id)
            await draft_repo.update(
                draft,
                status="approved",
                reviewed_at=datetime.now(UTC).isoformat(),
                reviewer_note=payload.note,
            )

    elif payload.action == "reject":
        if not payload.note:
            raise HTTPException(status_code=400, detail="却下理由（note）は必須です")
        approval = await approval_service.reject(
            approval_id=approval_id,
            reviewer=current_user,
            reviewer_note=payload.note,
        )
        if approval.listing_draft_id:
            draft_repo = ListingDraftRepository(db)
            draft = await draft_repo.get_by_id_or_raise(approval.listing_draft_id)
            await draft_repo.update(draft, status="rejected", reviewer_note=payload.note)
    else:
        raise HTTPException(status_code=400, detail="actionは 'approve' または 'reject' にしてください")

    return ApprovalResponse.model_validate(approval)


@router.post(
    "/drafts/{draft_id}/publish",
    summary="eBayに出品する",
)
async def publish_listing(
    draft_id: uuid.UUID,
    payload: PublishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer),
) -> dict:
    """
    承認済みの下書きをeBayに公開する。

    ★ dry_run=True（デフォルト）の場合は実際には公開しない。
    ★ 本番公開には reviewer 以上の権限と承認済み状態が必要。
    ★ eBay sandboxとproductionで動作を切り替える。
    """
    repo = ListingDraftRepository(db)
    draft = await repo.get_by_id_or_raise(draft_id)
    audit = AuditService(db)

    if draft.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"承認済みの下書きのみ公開できます（現在: {draft.status}）",
        )

    # 承認確認（追加安全チェック）
    if settings.REQUIRE_APPROVAL_FOR_PUBLISH:
        approval_service = ApprovalService(db)
        try:
            await approval_service.assert_approved(
                operation_type="publish",
                target_resource_type="listing_draft",
                target_resource_id=str(draft_id),
            )
        except ApprovalRequiredError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

    # dry-runモードの場合はここで終了
    if payload.dry_run:
        await audit.log(
            action="listing_draft.publish_dry_run",
            resource_type="listing_draft",
            resource_id=str(draft_id),
            user_id=current_user.id,
            metadata={"dry_run": True, "environment": settings.EBAY_ENVIRONMENT},
        )
        return {
            "dry_run": True,
            "message": "dry-runモードのため実際には公開しませんでした",
            "draft_id": str(draft_id),
            "would_publish_to": settings.EBAY_ENVIRONMENT,
        }

    # ── 本番公開処理（dry_run=False の場合のみ） ──
    await audit.log(
        action="listing_draft.publish_start",
        resource_type="listing_draft",
        resource_id=str(draft_id),
        user_id=current_user.id,
        metadata={"dry_run": False, "environment": settings.EBAY_ENVIRONMENT},
    )

    try:
        inv_client = EbayInventoryClient()
        offer_client = EbayOfferClient()

        # 1. Inventory Item 作成
        from app.models.product import Product
        from sqlalchemy import select
        result = await db.execute(select(Product).where(Product.id == draft.product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="商品が見つかりません")

        inv_payload = inv_client.build_inventory_item_payload(
            title=draft.title_selected or "",
            condition=product.condition,
            condition_description=draft.condition_description or "",
            description=draft.description_edited or draft.description_generated or "",
            item_specifics=draft.item_specifics_approved or {},
            image_urls=product.image_urls or [],
            quantity=1,
        )
        await inv_client.create_or_replace_inventory_item(
            sku=product.sku,
            payload=inv_payload,
        )

        # 2. Offer 作成
        offer_payload = offer_client.build_offer_payload(
            sku=product.sku,
            price_usd=draft.listing_price_usd or 0,
            category_id=draft.ebay_category_id or "",
            listing_description=draft.description_edited or draft.description_generated or "",
            fulfillment_policy_id=payload.fulfillment_policy_id,
            payment_policy_id=payload.payment_policy_id,
            return_policy_id=payload.return_policy_id,
        )
        offer_response = await offer_client.create_offer(offer_payload)
        offer_id = offer_response.get("offerId", "")

        # 3. Offer 公開
        publish_response = await offer_client.publish_offer(offer_id)
        listing_id = publish_response.get("listingId", "")

        # 4. DBを更新
        await repo.update(
            draft,
            status="published",
            ebay_offer_id=offer_id,
            published_at=datetime.now(UTC).isoformat(),
            ebay_listing_id=listing_id,
        )

        await audit.log(
            action="listing_draft.published",
            resource_type="listing_draft",
            resource_id=str(draft_id),
            user_id=current_user.id,
            after_state={"ebay_offer_id": offer_id, "listing_id": listing_id},
            result="success",
        )

        return {
            "success": True,
            "offer_id": offer_id,
            "listing_id": listing_id,
            "environment": settings.EBAY_ENVIRONMENT,
            "message": f"eBay({settings.EBAY_ENVIRONMENT})に公開しました",
        }

    except Exception as e:
        await audit.log(
            action="listing_draft.publish_failed",
            resource_type="listing_draft",
            resource_id=str(draft_id),
            user_id=current_user.id,
            result="failed",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"公開処理に失敗しました: {e}") from e
