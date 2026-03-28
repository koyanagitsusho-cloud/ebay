"""
リサーチ候補・スコアリングモデル
仕入れ候補の情報と利益試算、スコアを管理する。
"""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ResearchCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    リサーチ候補商品。
    仕入れ検討中の商品を登録し、利益試算・スコアリングを行う。
    出品候補に昇格すると Product に紐付く。
    """

    __tablename__ = "research_candidates"

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="出品候補に昇格した場合の商品ID",
    )

    # ─── 商品基本情報 ───
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="商品名")
    brand: Mapped[str | None] = mapped_column(String(100), comment="ブランド")
    model_number: Mapped[str | None] = mapped_column(String(100), comment="型番")
    jan_code: Mapped[str | None] = mapped_column(String(20), comment="JANコード")
    condition: Mapped[str] = mapped_column(String(50), default="USED_GOOD", comment="商品状態")
    notes: Mapped[str | None] = mapped_column(Text, comment="メモ")
    image_url_memo: Mapped[str | None] = mapped_column(Text, comment="画像メモ・参照URL")

    # ─── 原価・送料 ───
    purchase_price_jpy: Mapped[float | None] = mapped_column(Float, comment="仕入れ価格（円）")
    domestic_shipping_jpy: Mapped[float] = mapped_column(Float, default=0.0, comment="国内送料見込み（円）")
    international_shipping_usd: Mapped[float] = mapped_column(Float, default=0.0, comment="国際送料見込み（ドル）")
    other_cost_jpy: Mapped[float] = mapped_column(Float, default=0.0, comment="その他原価（円）")

    # ─── 価格・利益（計算結果を保存） ───
    target_sale_price_usd: Mapped[float | None] = mapped_column(Float, comment="想定販売価格（ドル）")
    estimated_profit_jpy: Mapped[float | None] = mapped_column(Float, comment="試算利益額（円）")
    estimated_profit_rate: Mapped[float | None] = mapped_column(Float, comment="試算利益率（0〜1）")
    estimated_receive_amount_jpy: Mapped[float | None] = mapped_column(Float, comment="想定受取額（円）")
    min_profitable_price_usd: Mapped[float | None] = mapped_column(
        Float, comment="利益が出る最低価格（ドル）"
    )
    profit_calc_detail: Mapped[dict | None] = mapped_column(
        JSONB, comment="利益計算の内訳（JSON）"
    )

    # ─── スコアリング ───
    # スコアは research_scores テーブルで管理するが、
    # 集計スコアをここにも保存して一覧表示を高速化する
    total_score: Mapped[float | None] = mapped_column(Float, comment="総合スコア（0〜100）")
    score_override: Mapped[float | None] = mapped_column(Float, comment="手動スコア補正値")
    score_override_reason: Mapped[str | None] = mapped_column(String(500), comment="補正理由")

    # ─── 状態 ───
    status: Mapped[str] = mapped_column(
        String(30),
        default="new",
        index=True,
        comment="状態: new / scoring / scored / promoted / rejected / archived",
    )

    # ─── リレーション ───
    product: Mapped["Product | None"] = relationship(  # noqa: F821
        "Product",
        back_populates="research_candidate",
    )
    scores: Mapped[list["ResearchScore"]] = relationship(
        "ResearchScore",
        back_populates="candidate",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<ResearchCandidate {self.title[:40]} ({self.status})>"


class ResearchScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    リサーチスコア詳細。
    各評価軸のスコアと根拠を保存する。
    スコアの変更履歴を追跡できるよう、新規レコードとして追記する方式。
    """

    __tablename__ = "research_scores"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="リサーチ候補ID",
    )

    # ─── 各評価軸スコア（0〜10） ───
    profit_score: Mapped[float] = mapped_column(Float, default=0.0, comment="利益性スコア（0〜10）")
    competition_score: Mapped[float] = mapped_column(Float, default=0.0, comment="競争弱さスコア（低競争=高スコア）（0〜10）")
    sellability_score: Mapped[float] = mapped_column(Float, default=0.0, comment="売れやすさスコア（0〜10）")
    listing_ease_score: Mapped[float] = mapped_column(Float, default=0.0, comment="出品しやすさスコア（0〜10）")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, comment="リスク低さスコア（低リスク=高スコア）（0〜10）")

    # ─── リスク詳細 ───
    return_risk: Mapped[str] = mapped_column(
        String(20), default="low",
        comment="返品リスク: low / medium / high"
    )
    authenticity_risk: Mapped[str] = mapped_column(
        String(20), default="low",
        comment="真贋トラブルリスク: low / medium / high"
    )
    fragility_risk: Mapped[str] = mapped_column(
        String(20), default="low",
        comment="壊れやすさリスク: low / medium / high"
    )
    prohibited_risk: Mapped[str] = mapped_column(
        String(20), default="low",
        comment="禁止品リスク: low / medium / high"
    )

    # ─── 集計 ───
    total_score: Mapped[float] = mapped_column(Float, comment="加重合計スコア（0〜100）")

    # ─── スコアリング根拠 ───
    score_basis: Mapped[dict | None] = mapped_column(JSONB, comment="スコア根拠JSON（各軸の理由）")
    scored_by: Mapped[str] = mapped_column(
        String(20), default="system",
        comment="スコアリング主体: system / manual / ai"
    )
    version: Mapped[int] = mapped_column(Integer, default=1, comment="スコアリングバージョン")

    # ─── リレーション ───
    candidate: Mapped["ResearchCandidate"] = relationship(
        "ResearchCandidate",
        back_populates="scores",
    )

    def __repr__(self) -> str:
        return f"<ResearchScore candidate={self.candidate_id} total={self.total_score}>"
