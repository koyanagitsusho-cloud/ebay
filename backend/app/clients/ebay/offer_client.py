"""
eBay Offer API クライアント
オファー（出品）の作成・公開・更新・終了を担う。

API仕様参照:
https://developer.ebay.com/api-docs/sell/inventory/resources/offer/methods/createOffer

重要な設計:
- Inventory Item を作成した後に Offer を作成する（2ステップ）
- Offer公開（publishOffer）で実際にeBayに出品される
- 公開前に必ず承認フローを通すこと（サービス層で制御）
"""

from typing import Any

from app.clients.ebay.base_client import EbayBaseClient
from app.core.logging_config import get_logger

logger = get_logger(__name__)

INVENTORY_API_VERSION = "v1"
OFFER_BASE = f"/sell/inventory/{INVENTORY_API_VERSION}"


class EbayOfferClient(EbayBaseClient):
    """
    eBay Offer API クライアント。
    Offer の CRUD と公開を担う。
    """

    async def create_offer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        オファーを作成する（下書き状態）。
        この時点では公開されない。

        payload 構造:
        {
          "sku": "SKU-001",
          "marketplaceId": "EBAY_US",
          "format": "FIXED_PRICE",
          "listingDescription": "...",
          "listingPolicies": {
            "fulfillmentPolicyId": "...",
            "paymentPolicyId": "...",
            "returnPolicyId": "..."
          },
          "pricingSummary": {
            "price": {"currency": "USD", "value": "19.99"}
          },
          "categoryId": "...",
          "listingDuration": "GTC"
        }
        """
        logger.info("Offer作成", sku=payload.get("sku"))
        return await self._request(
            method="POST",
            path=f"{OFFER_BASE}/offer",
            json_body=payload,
        )

    async def get_offer(self, offer_id: str) -> dict[str, Any]:
        """Offer詳細を取得する"""
        return await self._request(
            method="GET",
            path=f"{OFFER_BASE}/offer/{offer_id}",
        )

    async def get_offers_for_sku(self, sku: str) -> dict[str, Any]:
        """SKUに紐付くOfferを取得する"""
        return await self._request(
            method="GET",
            path=f"{OFFER_BASE}/offer",
            params={"sku": sku},
        )

    async def update_offer(
        self,
        offer_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Offerを更新する（価格変更・説明更新等）"""
        logger.info("Offer更新", offer_id=offer_id)
        return await self._request(
            method="PUT",
            path=f"{OFFER_BASE}/offer/{offer_id}",
            json_body=payload,
        )

    async def publish_offer(self, offer_id: str) -> dict[str, Any]:
        """
        Offerを公開する（eBayに実際に出品する）。
        ★ この操作は本番では取り消しが難しい。承認後のみ実行すること。
        ★ dry-runモード時は呼び出さないこと（サービス層で制御）。

        レスポンス: {"listingId": "xxxxxxx"}
        """
        logger.warning(
            "Offer公開実行",
            offer_id=offer_id,
            environment=__import__("app.core.config", fromlist=["settings"]).settings.EBAY_ENVIRONMENT,
        )
        return await self._request(
            method="POST",
            path=f"{OFFER_BASE}/offer/{offer_id}/publish",
        )

    async def withdraw_offer(self, offer_id: str) -> dict[str, Any]:
        """Offerを取り下げる（出品終了）"""
        logger.warning("Offer取り下げ", offer_id=offer_id)
        return await self._request(
            method="POST",
            path=f"{OFFER_BASE}/offer/{offer_id}/withdraw",
        )

    async def delete_offer(self, offer_id: str) -> dict[str, Any]:
        """Offerを削除する"""
        logger.warning("Offer削除", offer_id=offer_id)
        return await self._request(
            method="DELETE",
            path=f"{OFFER_BASE}/offer/{offer_id}",
        )

    def build_offer_payload(
        self,
        sku: str,
        price_usd: float,
        category_id: str,
        listing_description: str,
        fulfillment_policy_id: str,
        payment_policy_id: str,
        return_policy_id: str,
        marketplace_id: str = "EBAY_US",
        listing_duration: str = "GTC",
        listing_format: str = "FIXED_PRICE",
    ) -> dict[str, Any]:
        """
        Offer作成リクエストのペイロードを構築する。

        ポリシーIDはeBay Developer PortalまたはAccount API経由で取得する。
        ★ sandboxでは特定のポリシーIDしか使えない場合がある（要確認）。
        """
        return {
            "sku": sku,
            "marketplaceId": marketplace_id,
            "format": listing_format,
            "listingDescription": listing_description,
            "listingPolicies": {
                "fulfillmentPolicyId": fulfillment_policy_id,
                "paymentPolicyId": payment_policy_id,
                "returnPolicyId": return_policy_id,
            },
            "pricingSummary": {
                "price": {
                    "currency": "USD",
                    "value": str(round(price_usd, 2)),
                }
            },
            "categoryId": category_id,
            "listingDuration": listing_duration,
        }
