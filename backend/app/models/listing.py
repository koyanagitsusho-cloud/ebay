"""
出品下書き・生成コンテンツ・テンプレートモデル
AI生成テキスト、編集履歴、承認フローを管理する。
"""

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ListingDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    出品下書き。
    商品1件に対して1つの有効な下書きを持つ（1:1）。
    承認→公開の流れを管理する。
    AI生成文は必ずここに保存し、手動確認後に公開する。
    """

    __tablename__ = "listing_drafts"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="商品ID",
    )

    # ─── 出品タイトル ───
    title_candidates: Mapped[list | None] = mapped_column(
        JSONB, comment="AIが生成したタイトル候補（JSON配列）"
    )
    title_selected: Mapped[str | None] = mapped_column(
        String(80), comment="採用されたタイトル（eBayは80文字制限）"
    )

    # ─── 説明文 ───
    description_generated: Mapped[str | None] = mapped_column(
        Text, comment="AI生成の説明文（未編集）"
    )
    description_edited: Mapped[str | None] = mapped_column(
        Text, comment="人が編集した説明文（こちらを公開する）"
    )

    # ─── Item Specifics ───
    item_specifics_candidates: Mapped[dict | None] = mapped_column(
        JSONB, comment="AI生成のitem specifics候補（JSON）"
    )
    item_specifics_approved: Mapped[dict | None] = mapped_column(
        JSONB, comment="承認済みitem specifics（こちらを公開する）"
    )

    # ─── Condition ───
    condition: Mapped[str | None] = mapped_column(String(50), comment="商品状態（eBay形式）")
    condition_description: Mapped[str | None] = mapped_column(Text, comment="状態説明文")

    # ─── 価格 ───
    listing_price_usd: Mapped[float | None] = mapped_column(Float, comment="出品価格（ドル）")
    buy_it_now_price_usd: Mapped[float | None] = mapped_column(Float, comment="即決価格（ドル）")

    # ─── eBay出品設定 ───
    ebay_category_id: Mapped[str | None] = mapped_column(String(20), comment="eBayカテゴリID")
    ebay_category_name: Mapped[str | None] = mapped_column(String(200), comment="eBayカテゴリ名（表示用）")
    listing_format: Mapped[str] = mapped_column(
        String(20), default="FIXED_PRICE",
        comment="出品形式: FIXED_PRICE / AUCTION"
    )
    listing_duration: Mapped[str] = mapped_column(
        String(20), default="GTC",
        comment="出品期間: GTC（Good 'Til Cancelled）/ DAY_3 / DAY_7 等"
    )
    shipping_policy_id: Mapped[str | None] = mapped_column(String(50), comment="配送ポリシーID")
    return_policy_id: Mapped[str | None] = mapped_column(String(50), comment="返品ポリシーID")
    payment_policy_id: Mapped[str | None] = mapped_column(String(50), comment="支払いポリシーID")

    # ─── バリデーション結果 ───
    validation_warnings: Mapped[list | None] = mapped_column(JSONB, comment="バリデーション警告（禁止語等）")
    missing_required_fields: Mapped[list | None] = mapped_column(JSONB, comment="必須項目不足リスト")
    is_valid: Mapped[bool] = mapped_column(default=False, comment="バリデーション通過フラグ")

    # ─── ステータス ───
    status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        index=True,
        comment="状態: draft / pending_review / approved / rejected / published / ended",
    )

    # ─── 承認関連 ───
    submitted_at: Mapped[str | None] = mapped_column(comment="承認依頼日時")
    reviewed_at: Mapped[str | None] = mapped_column(comment="承認日時")
    reviewer_note: Mapped[str | None] = mapped_column(Text, comment="レビュアーのコメント")

    # ─── eBay公開情報 ───
    ebay_offer_id: Mapped[str | None] = mapped_column(String(50), comment="eBay OfferID")
    published_at: Mapped[str | None] = mapped_column(comment="公開日時")
    ebay_listing_id: Mapped[str | None] = mapped_column(String(50), comment="eBay ListingID（公開後）")

    # ─── リレーション ───
    product: Mapped["Product"] = relationship("Product", back_populates="listing_draft")  # noqa: F821
    generated_contents: Mapped[list["GeneratedContent"]] = relationship(
        "GeneratedContent",
        back_populates="listing_draft",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    approval: Mapped["Approval | None"] = relationship(
        "Approval",
        back_populates="listing_draft",
        uselist=False,
        lazy="noload",
    )
    ebay_offer: Mapped["EbayOffer | None"] = relationship(  # noqa: F821
        "EbayOffer",
        back_populates="listing_draft",
        uselist=False,
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<ListingDraft product={self.product_id} status={self.status}>"


class GeneratedContent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    AI生成コンテンツの履歴。
    生成ごとにレコードを作成し、変更履歴を追跡する。
    「何を入力して何が生成されたか」を必ず保存する。
    """

    __tablename__ = "generated_contents"

    listing_draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listing_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="対応する出品下書きID",
    )

    content_type: Mapped[str] = mapped_column(
        String(50),
        comment="生成種別: title / description / item_specifics / condition_description",
    )
    input_data: Mapped[dict | None] = mapped_column(JSONB, comment="生成に使用した入力データ")
    generated_output: Mapped[dict | None] = mapped_column(JSONB, comment="生成結果（JSON）")
    model_used: Mapped[str | None] = mapped_column(String(100), comment="使用AIモデル")
    prompt_tokens: Mapped[int | None] = mapped_column(comment="入力トークン数（コスト管理用）")
    completion_tokens: Mapped[int | None] = mapped_column(comment="出力トークン数（コスト管理用）")
    generation_status: Mapped[str] = mapped_column(
        String(20), default="success",
        comment="生成ステータス: success / failed / partial"
    )
    error_message: Mapped[str | None] = mapped_column(Text, comment="生成失敗時のエラー内容")

    # ─── リレーション ───
    listing_draft: Mapped["ListingDraft"] = relationship(
        "ListingDraft",
        back_populates="generated_contents",
    )


class ListingTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    出品情報生成テンプレート。
    カテゴリ・ブランドごとの説明文テンプレートを管理する。
    将来的に増やしやすい設計にする。
    """

    __tablename__ = "listing_templates"

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="テンプレート名")
    category: Mapped[str | None] = mapped_column(String(200), comment="対象カテゴリ")
    brand: Mapped[str | None] = mapped_column(String(100), comment="対象ブランド")
    template_type: Mapped[str] = mapped_column(
        String(30), comment="種別: description / title / item_specifics"
    )
    template_body: Mapped[str] = mapped_column(Text, comment="テンプレート本文（プレースホルダー使用可）")
    variables: Mapped[list | None] = mapped_column(JSONB, comment="プレースホルダー変数一覧")
    is_active: Mapped[bool] = mapped_column(default=True, comment="有効フラグ")
    priority: Mapped[int] = mapped_column(default=0, comment="優先度（高い方が優先）")
    notes: Mapped[str | None] = mapped_column(Text, comment="テンプレート説明・注意事項")


class ListingRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    出品ルール。
    禁止語、タイトルルール、カテゴリ別ルール等を管理する。
    """

    __tablename__ = "listing_rules"

    rule_type: Mapped[str] = mapped_column(
        String(50), comment="ルール種別: prohibited_word / title_rule / category_rule / brand_rule"
    )
    target: Mapped[str | None] = mapped_column(String(200), comment="対象（カテゴリ名・ブランド名等）")
    rule_content: Mapped[str] = mapped_column(Text, comment="ルール内容")
    severity: Mapped[str] = mapped_column(
        String(20), default="warning",
        comment="重要度: error（公開ブロック）/ warning（警告のみ）"
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(Text, comment="ルールの説明")


class Approval(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    承認レコード。
    出品・価格変更・セール実行等の重要操作に対する承認を管理する。
    承認なしの本番操作は禁止。
    """

    __tablename__ = "approvals"

    listing_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("listing_drafts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="対応する出品下書きID（出品承認の場合）",
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="承認者のユーザーID",
    )

    operation_type: Mapped[str] = mapped_column(
        String(50), comment="操作種別: publish / price_change / sale_execution / bulk_update"
    )
    target_resource_type: Mapped[str | None] = mapped_column(String(50), comment="対象リソース種別")
    target_resource_id: Mapped[str | None] = mapped_column(String(100), comment="対象リソースID")
    request_payload: Mapped[dict | None] = mapped_column(JSONB, comment="承認依頼内容（変更前後の差分等）")

    status: Mapped[str] = mapped_column(
        String(20), default="pending",
        index=True,
        comment="状態: pending / approved / rejected / expired",
    )
    requester_note: Mapped[str | None] = mapped_column(Text, comment="依頼者のメモ")
    reviewer_note: Mapped[str | None] = mapped_column(Text, comment="承認者のコメント")
    reviewed_at: Mapped[str | None] = mapped_column(comment="審査完了日時")
    expires_at: Mapped[str | None] = mapped_column(comment="承認有効期限（過ぎたら再申請必要）")

    # ─── リレーション ───
    listing_draft: Mapped["ListingDraft | None"] = relationship(
        "ListingDraft",
        back_populates="approval",
    )
    reviewer: Mapped["User | None"] = relationship("User", back_populates="approvals")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Approval {self.operation_type} ({self.status})>"


class EbayOffer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    eBay Offerレコード。
    eBay Inventory API の offer を管理する。
    下書きから公開までの流れを追跡する。
    """

    __tablename__ = "ebay_offers"

    listing_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("listing_drafts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    ebay_offer_id: Mapped[str | None] = mapped_column(
        String(50), comment="eBay側のofferID"
    )
    ebay_listing_id: Mapped[str | None] = mapped_column(
        String(50), comment="公開後のeBay listingID"
    )
    marketplace_id: Mapped[str] = mapped_column(
        String(20), default="EBAY_US",
        comment="マーケットプレイスID（例: EBAY_US, EBAY_GB）"
    )
    listing_status: Mapped[str] = mapped_column(
        String(30), default="draft",
        comment="出品状態: draft / active / ended / sold"
    )
    current_price_usd: Mapped[float | None] = mapped_column(Float, comment="現在の出品価格（ドル）")
    last_price_updated_at: Mapped[str | None] = mapped_column(comment="最終価格更新日時")
    published_at: Mapped[str | None] = mapped_column(comment="公開日時")
    ended_at: Mapped[str | None] = mapped_column(comment="終了日時")
    ebay_url: Mapped[str | None] = mapped_column(String(500), comment="eBay商品ページURL")
    last_api_response: Mapped[dict | None] = mapped_column(JSONB, comment="最終APIレスポンス（要点のみ）")
    is_dry_run: Mapped[bool] = mapped_column(
        default=True, comment="dry-run実行フラグ（Trueなら実際のAPI呼び出し未実施）"
    )

    # ─── リレーション ───
    listing_draft: Mapped["ListingDraft | None"] = relationship(
        "ListingDraft", back_populates="ebay_offer"
    )
    inventory_item: Mapped["InventoryItem | None"] = relationship(  # noqa: F821
        "InventoryItem", back_populates="ebay_offers"
    )
