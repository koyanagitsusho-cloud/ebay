"""
eBay Inventory API クライアント
在庫アイテム（Inventory Item）の作成・更新・取得を担う。

API仕様参照:
https://developer.ebay.com/api-docs/sell/inventory/overview.html

重要: このクライアントはeBay APIの呼び出しのみを担う。
ビジネスロジックはサービス層（inventory_service等）で実装すること。
"""

from typing import Any

from app.clients.ebay.base_client import EbayBaseClient
from app.core.logging_config import get_logger

logger = get_logger(__name__)

INVENTORY_API_VERSION = "v1"
INVENTORY_BASE = f"/sell/inventory/{INVENTORY_API_VERSION}"


class EbayInventoryClient(EbayBaseClient):
    """
    eBay Inventory API クライアント。
    在庫アイテムのCRUD操作を提供する。
    """

    async def create_or_replace_inventory_item(
        self,
        sku: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        在庫アイテムを作成または更新する（冪等操作）。
        同一SKUで呼び出すと上書きされる。

        payload 構造（eBay Inventory Item形式）:
        {
          "availability": {"shipToLocationAvailability": {"quantity": 1}},
          "condition": "USED_EXCELLENT",
          "conditionDescription": "...",
          "product": {
            "title": "...",
            "aspects": {...},
            "description": "...",
            "imageUrls": [...]
          }
        }
        """
        logger.info("在庫アイテム作成/更新", sku=sku)
        return await self._request(
            method="PUT",
            path=f"{INVENTORY_BASE}/inventory_item/{sku}",
            json_body=payload,
        )

    async def get_inventory_item(self, sku: str) -> dict[str, Any]:
        """在庫アイテムを取得する"""
        return await self._request(
            method="GET",
            path=f"{INVENTORY_BASE}/inventory_item/{sku}",
        )

    async def delete_inventory_item(self, sku: str) -> dict[str, Any]:
        """在庫アイテムを削除する（終了時に使用）"""
        logger.warning("在庫アイテム削除", sku=sku)
        return await self._request(
            method="DELETE",
            path=f"{INVENTORY_BASE}/inventory_item/{sku}",
        )

    async def get_inventory_items(
        self,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """在庫アイテム一覧を取得する"""
        return await self._request(
            method="GET",
            path=f"{INVENTORY_BASE}/inventory_item",
            params={"limit": limit, "offset": offset},
        )

    def build_inventory_item_payload(
        self,
        title: str,
        condition: str,
        condition_description: str,
        description: str,
        item_specifics: dict[str, str],
        image_urls: list[str],
        quantity: int = 1,
    ) -> dict[str, Any]:
        """
        eBay Inventory Item APIのリクエストペイロードを構築する。

        condition の有効値:
        NEW / LIKE_NEW / USED_EXCELLENT / USED_GOOD / USED_ACCEPTABLE / FOR_PARTS_OR_NOT_WORKING

        ★注意: eBay sandboxとproductionで受け入れるconditionが異なる場合がある。
        sandboxで動作確認してから本番に移行すること。
        """
        return {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": quantity,
                },
            },
            "condition": condition,
            "conditionDescription": condition_description,
            "product": {
                "title": title,
                "description": description,
                "aspects": item_specifics,
                "imageUrls": image_urls,
            },
        }
