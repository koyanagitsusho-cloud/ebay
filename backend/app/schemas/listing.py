"""
出品下書き・承認関連スキーマ
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ListingGenerateRequest(BaseModel):
    """出品情報生成リクエスト"""

    product_title: str = Field(..., min_length=1)
    brand: str | None = None
    model_number: str | None = None
    condition: str = "USED_GOOD"
    features: str | None = None
    included_items: str | None = None
    missing_items: str | None = None
    scratches_or_stains: str | None = None
    operation_check: str | None = None
    size_info: str | None = None
    color: str | None = None
    category_hint: str | None = None
    cautions: str | None = None


class ListingDraftUpdate(BaseModel):
    """出品下書き更新リクエスト"""

    title_selected: str | None = Field(None, max_length=80, description="採用タイトル（80文字以内）")
    description_edited: str | None = None
    item_specifics_approved: dict | None = None
    condition: str | None = None
    condition_description: str | None = None
    listing_price_usd: float | None = Field(None, gt=0)
    ebay_category_id: str | None = None


class SubmitForReviewRequest(BaseModel):
    """承認依頼リクエスト"""

    note: str | None = None


class ApprovalActionRequest(BaseModel):
    """承認・却下リクエスト"""

    action: str = Field(..., description="approve または reject")
    note: str | None = Field(None, description="却下の場合は必須")


class ListingDraftResponse(BaseModel):
    """出品下書きレスポンス"""

    id: uuid.UUID
    product_id: uuid.UUID
    title_candidates: list | None
    title_selected: str | None
    description_generated: str | None
    description_edited: str | None
    item_specifics_candidates: dict | None
    item_specifics_approved: dict | None
    condition: str | None
    condition_description: str | None
    listing_price_usd: float | None
    ebay_category_id: str | None
    validation_warnings: list | None
    missing_required_fields: list | None
    is_valid: bool
    status: str
    submitted_at: str | None
    reviewed_at: str | None
    reviewer_note: str | None
    ebay_offer_id: str | None
    published_at: str | None
    ebay_listing_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    """承認レコードレスポンス"""

    id: uuid.UUID
    operation_type: str
    target_resource_type: str
    target_resource_id: str | None
    status: str
    requester_note: str | None
    reviewer_note: str | None
    reviewed_at: str | None
    expires_at: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishRequest(BaseModel):
    """出品公開リクエスト"""

    dry_run: bool = Field(default=True, description="dry-runモード（Trueなら実際には公開しない）")
    fulfillment_policy_id: str = Field(..., description="eBay配送ポリシーID")
    payment_policy_id: str = Field(..., description="eBay支払いポリシーID")
    return_policy_id: str = Field(..., description="eBay返品ポリシーID")
