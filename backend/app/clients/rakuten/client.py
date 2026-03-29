"""
楽天市場APIクライアント
楽天Ichiba Item Search APIを使って商品を検索する。
https://webservice.rakuten.co.jp/documentation/ichiba-item-search
"""

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

RAKUTEN_SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"


@dataclass
class RakutenItem:
    """楽天市場の商品データ"""
    item_code: str
    title: str
    price_jpy: int
    shop_name: str
    item_url: str
    image_url: str | None
    jan_code: str | None
    category_id: str | None


class RakutenClient:
    """楽天市場APIクライアント"""

    def __init__(self, app_id: str | None = None):
        self.app_id = app_id or settings.RAKUTEN_APP_ID

    async def search_items(
        self,
        keyword: str,
        min_price: int | None = None,
        max_price: int | None = None,
        hits: int = 30,
        page: int = 1,
        sort: str = "-reviewCount",  # レビュー数降順（人気順）
    ) -> list[RakutenItem]:
        """
        楽天市場で商品を検索する。

        Args:
            keyword: 検索キーワード
            min_price: 最低価格（円）
            max_price: 最高価格（円）
            hits: 取得件数（最大30）
            page: ページ番号
            sort: ソート順 (-reviewCount=人気順, +itemPrice=安い順, -itemPrice=高い順)

        Returns:
            RakutenItemのリスト
        """
        if not self.app_id:
            logger.warning("RAKUTEN_APP_ID が設定されていません")
            return []

        params: dict = {
            "applicationId": self.app_id,
            "keyword": keyword,
            "hits": min(hits, 30),
            "page": page,
            "sort": sort,
            "format": "json",
            "formatVersion": "2",
        }

        if min_price:
            params["minPrice"] = min_price
        if max_price:
            params["maxPrice"] = max_price

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(RAKUTEN_SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            items = []
            for item_data in data.get("Items", []):
                item = item_data.get("Item", item_data)
                jan = None
                # JANコードをitemCodeから抽出を試みる（形式: shopCode:itemCode）
                item_code = item.get("itemCode", "")

                image_urls = item.get("mediumImageUrls", [])
                image_url = image_urls[0] if image_urls else None
                if isinstance(image_url, dict):
                    image_url = image_url.get("imageUrl")

                items.append(RakutenItem(
                    item_code=item_code,
                    title=item.get("itemName", ""),
                    price_jpy=int(item.get("itemPrice", 0)),
                    shop_name=item.get("shopName", ""),
                    item_url=item.get("itemUrl", ""),
                    image_url=image_url,
                    jan_code=jan,
                    category_id=str(item.get("genreId", "")),
                ))

            logger.info(
                "楽天検索完了",
                keyword=keyword,
                count=len(items),
                total=data.get("count", 0),
            )
            return items

        except httpx.HTTPError as e:
            logger.error("楽天API HTTPエラー", keyword=keyword, error=str(e))
            return []
        except Exception as e:
            logger.error("楽天API 予期せぬエラー", keyword=keyword, error=str(e))
            return []
