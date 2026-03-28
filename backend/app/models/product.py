"""
商品・在庫モデル
SKU単位での商品管理と、eBay在庫アイテムを管理する。
"""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    商品マスタ。
    SKU単位の商品情報を管理する中心テーブル。
    リサーチ候補から出品まで、この商品IDを軸に繋がる。
    """

    __tablename__ = "products"

    # ─── 識別子 ───
    sku: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="社内管理SKU（重複不可）",
    )
    jan_code: Mapped[str | None] = mapped_column(String(20), comment="JANコード")
    upc_code: Mapped[str | None] = mapped_column(String(20), comment="UPCコード")
    ean_code: Mapped[str | None] = mapped_column(String(20), comment="EANコード")
    model_number: Mapped[str | None] = mapped_column(String(100), comment="型番")

    # ─── 商品情報 ───
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="商品名")
    brand: Mapped[str | None] = mapped_column(String(100), comment="ブランド名")
    category_hint: Mapped[str | None] = mapped_column(String(200), comment="カテゴリヒント（例: Toys & Hobbies > Action Figures）")
    condition: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="USED_EXCELLENT",
        comment="商品状態: NEW / LIKE_NEW / USED_EXCELLENT / USED_GOOD / USED_ACCEPTABLE / FOR_PARTS",
    )
    description_notes: Mapped[str | None] = mapped_column(Text, comment="説明文用メモ（状態詳細・欠品等）")
    image_urls: Mapped[list | None] = mapped_column(JSONB, comment="画像URL一覧（JSON配列）")
    extra_attributes: Mapped[dict | None] = mapped_column(JSONB, comment="その他属性（JSON）")

    # ─── 原価情報 ───
    purchase_price_jpy: Mapped[float | None] = mapped_column(Float, comment="仕入れ価格（円）")
    domestic_shipping_jpy: Mapped[float | None] = mapped_column(Float, comment="国内送料見込み（円）")
    international_shipping_usd: Mapped[float | None] = mapped_column(Float, comment="国際送料見込み（ドル）")
    other_cost_jpy: Mapped[float | None] = mapped_column(Float, comment="その他原価（円）")

    # ─── 状態管理 ───
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="research",
        index=True,
        comment="状態: research / draft / pending_approval / published / ended / excluded",
    )
    is_excluded: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="除外フラグ（価格改定・セール対象から除く）",
    )
    notes: Mapped[str | None] = mapped_column(Text, comment="運用メモ")

    # ─── リレーション ───
    research_candidate: Mapped["ResearchCandidate | None"] = relationship(  # noqa: F821
        "ResearchCandidate",
        back_populates="product",
        uselist=False,
        lazy="noload",
    )
    listing_draft: Mapped["ListingDraft | None"] = relationship(  # noqa: F821
        "ListingDraft",
        back_populates="product",
        uselist=False,
        lazy="noload",
    )
    inventory_item: Mapped["InventoryItem | None"] = relationship(  # noqa: F821
        "InventoryItem",
        back_populates="product",
        uselist=False,
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Product {self.sku}: {self.title[:30]}>"


class InventoryItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    eBay在庫アイテム。
    eBay Inventory APIに登録した在庫データを管理する。
    商品1件に対し1つの在庫アイテム（1:1）。
    """

    __tablename__ = "inventory_items"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="商品ID",
    )

    # ─── eBay在庫情報 ───
    ebay_sku: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="eBay上のSKU（社内SKUと原則一致させる）",
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, comment="在庫数")
    ebay_item_id: Mapped[str | None] = mapped_column(
        String(50),
        comment="eBayのItemID（公開後に取得）",
    )

    # ─── eBay登録ステータス ───
    sync_status: Mapped[str] = mapped_column(
        String(30),
        default="not_synced",
        comment="eBay同期状態: not_synced / synced / sync_failed",
    )
    last_synced_at: Mapped[str | None] = mapped_column(comment="最終eBay同期日時")
    last_sync_response: Mapped[dict | None] = mapped_column(JSONB, comment="最終同期のAPIレスポンス（要点のみ）")

    # ─── リレーション ───
    product: Mapped["Product"] = relationship("Product", back_populates="inventory_item")
    ebay_offers: Mapped[list["EbayOffer"]] = relationship(  # noqa: F821
        "EbayOffer",
        back_populates="inventory_item",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<InventoryItem eBay-SKU:{self.ebay_sku}>"
