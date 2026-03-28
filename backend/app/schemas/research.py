"""
リサーチ候補のPydanticスキーマ（入力バリデーション・出力シリアライズ）
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ─── 入力スキーマ ───

class ResearchCandidateCreate(BaseModel):
    """リサーチ候補作成リクエスト"""

    title: str = Field(..., min_length=1, max_length=500, description="商品名")
    brand: str | None = Field(None, max_length=100)
    model_number: str | None = Field(None, max_length=100)
    jan_code: str | None = Field(None, max_length=20)
    condition: str = Field(default="USED_GOOD", description="商品状態")
    notes: str | None = None
    image_url_memo: str | None = None

    # 原価情報
    purchase_price_jpy: float | None = Field(None, ge=0)
    domestic_shipping_jpy: float = Field(default=0.0, ge=0)
    international_shipping_usd: float = Field(default=0.0, ge=0)
    other_cost_jpy: float = Field(default=0.0, ge=0)

    # 想定価格（利益計算用）
    target_sale_price_usd: float | None = Field(None, gt=0)

    # リスク評価（任意入力）
    competition_level: str = Field(default="medium", description="low / medium / high")
    return_risk: str = Field(default="low", description="low / medium / high")
    authenticity_risk: str = Field(default="low", description="low / medium / high")
    fragility_risk: str = Field(default="low", description="low / medium / high")
    prohibited_risk: str = Field(default="low", description="low / medium / high")

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: str) -> str:
        valid = {"NEW", "LIKE_NEW", "USED_EXCELLENT", "USED_GOOD", "USED_ACCEPTABLE", "FOR_PARTS"}
        if v not in valid:
            raise ValueError(f"conditionは次のいずれかにしてください: {valid}")
        return v


class ResearchCandidateUpdate(BaseModel):
    """リサーチ候補更新リクエスト（部分更新）"""

    title: str | None = None
    brand: str | None = None
    model_number: str | None = None
    condition: str | None = None
    notes: str | None = None
    purchase_price_jpy: float | None = None
    domestic_shipping_jpy: float | None = None
    international_shipping_usd: float | None = None
    other_cost_jpy: float | None = None
    target_sale_price_usd: float | None = None
    status: str | None = None
    score_override: float | None = Field(None, ge=0, le=100)
    score_override_reason: str | None = None


class ScoreOverrideRequest(BaseModel):
    """スコア手動補正リクエスト"""
    score: float = Field(..., ge=0, le=100)
    reason: str = Field(..., min_length=1, description="補正理由（必須）")


class PromoteToListingRequest(BaseModel):
    """出品候補への昇格リクエスト"""
    sku: str = Field(..., min_length=1, max_length=100, description="付与するSKU")
    note: str | None = None


# ─── 出力スキーマ ───

class ProfitCalculationResponse(BaseModel):
    """利益計算結果レスポンス"""

    sale_price_usd: float
    sale_price_jpy: float
    purchase_price_jpy: float
    ebay_fee_jpy: float
    payment_fee_jpy: float
    total_fee_jpy: float
    total_cost_jpy: float
    gross_profit_jpy: float
    gross_profit_rate: float
    receive_amount_jpy: float
    min_profitable_price_usd: float
    is_profitable: bool
    profit_rate_ok: bool
    profit_amount_ok: bool
    exchange_rate: float


class ResearchScoreResponse(BaseModel):
    """スコアレスポンス"""

    id: uuid.UUID
    profit_score: float
    competition_score: float
    sellability_score: float
    listing_ease_score: float
    risk_score: float
    total_score: float
    return_risk: str
    authenticity_risk: str
    fragility_risk: str
    prohibited_risk: str
    score_basis: dict | None
    scored_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchCandidateResponse(BaseModel):
    """リサーチ候補レスポンス"""

    id: uuid.UUID
    title: str
    brand: str | None
    model_number: str | None
    jan_code: str | None
    condition: str
    notes: str | None
    purchase_price_jpy: float | None
    domestic_shipping_jpy: float
    international_shipping_usd: float
    other_cost_jpy: float
    target_sale_price_usd: float | None
    estimated_profit_jpy: float | None
    estimated_profit_rate: float | None
    estimated_receive_amount_jpy: float | None
    min_profitable_price_usd: float | None
    total_score: float | None
    score_override: float | None
    status: str
    product_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResearchCandidateDetailResponse(ResearchCandidateResponse):
    """リサーチ候補詳細レスポンス（スコア詳細含む）"""

    profit_calc_detail: dict | None
    scores: list[ResearchScoreResponse] = []
