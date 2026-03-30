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

# 新エンドポイント（2026年移行済み）
RAKUTEN_SEARCH_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"


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

    def __init__(self, app_id: str | None = None, access_key: str | None = None):
        self.app_id = app_id or settings.RAKUTEN_APP_ID
        self.access_key = access_key or settings.RAKUTEN_ACCESS_KEY

    async def search_items(
        self,
        keyword: str,
        min_price: int | None = None,
        max_price: int | None = None,
        hits: int = 30,
        page: int = 1,
        sort: str = "-reviewCount",
    ) -> list[RakutenItem]:
        """楽天市場で商品を検索する。"""
        if not self.app_id:
            logger.error("RAKUTEN_APP_ID が未設定です。Railway Variables を確認してください。")
            return []
        if not self.access_key:
            logger.error("RAKUTEN_ACCESS_KEY が未設定です。Railway Variables を確認してください。")
            return []

        params: dict = {
            "applicationId": self.app_id,
            "accessKey": self.access_key,
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

        logger.info(
            "楽天API リクエスト送信",
            keyword=keyword,
            min_price=min_price,
            max_price=max_price,
            url=RAKUTEN_SEARCH_URL,
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(RAKUTEN_SEARCH_URL, params=params)

            logger.info(
                "楽天API レスポンス受信",
                keyword=keyword,
                http_status=resp.status_code,
            )

            # HTTPエラー確認
            if resp.status_code != 200:
                logger.error(
                    "楽天API HTTPエラー",
                    keyword=keyword,
                    status=resp.status_code,
                    body=resp.text[:500],
                )
                return []

            data = resp.json()

            # APIレベルのエラーチェック
            if "error" in data:
                logger.error(
                    "楽天API エラーレスポンス",
                    keyword=keyword,
                    error=data.get("error"),
                    error_description=data.get("error_description", ""),
                )
                return []

            # Itemsキーの存在確認
            if "Items" not in data:
                logger.error(
                    "楽天API レスポンスに Items キーがありません",
                    keyword=keyword,
                    response_keys=list(data.keys()),
                    response_snippet=str(data)[:300],
                )
                return []

            api_total = data.get("count", 0)
            items_data = data["Items"]

            logger.info(
                "楽天API 検索結果",
                keyword=keyword,
                api_total_count=api_total,
                items_in_response=len(items_data),
            )

            if not items_data:
                logger.warning("楽天API: 検索結果が0件です", keyword=keyword, api_total=api_total)
                return []

            # formatVersion=2 では Items は直接オブジェクトの配列
            items = []
            for raw in items_data:
                try:
                    title = raw.get("itemName", "")
                    price = int(raw.get("itemPrice", 0))
                    item_code = raw.get("itemCode", "")
                    shop_name = raw.get("shopName", "")
                    item_url = raw.get("itemUrl", "")

                    # 画像URL取得
                    image_urls = raw.get("mediumImageUrls", [])
                    image_url = None
                    if image_urls:
                        first = image_urls[0]
                        if isinstance(first, dict):
                            image_url = first.get("imageUrl")
                        elif isinstance(first, str):
                            image_url = first

                    if not title or price <= 0:
                        logger.debug("楽天商品スキップ（タイトルまたは価格なし）", item_code=item_code)
                        continue

                    items.append(RakutenItem(
                        item_code=item_code,
                        title=title,
                        price_jpy=price,
                        shop_name=shop_name,
                        item_url=item_url,
                        image_url=image_url,
                        jan_code=None,
                        category_id=str(raw.get("genreId", "")),
                    ))

                except Exception as e:
                    logger.warning("楽天商品パースエラー", error=str(e), raw=str(raw)[:200])
                    continue

            logger.info(
                "楽天 パース完了",
                keyword=keyword,
                parsed_count=len(items),
                skipped=len(items_data) - len(items),
            )
            return items

        except httpx.TimeoutException:
            logger.error("楽天API タイムアウト", keyword=keyword)
            return []
        except httpx.HTTPError as e:
            logger.error("楽天API HTTPエラー", keyword=keyword, error=str(e))
            return []
        except Exception as e:
            logger.error("楽天API 予期せぬエラー", keyword=keyword, error=str(e))
            return []

    async def test_connection(self) -> dict:
        """
        API接続テスト用メソッド。
        設定ページの診断で使用する。
        """
        if not self.app_id:
            return {"ok": False, "error": "RAKUTEN_APP_ID が未設定"}
        if not self.access_key:
            return {"ok": False, "error": "RAKUTEN_ACCESS_KEY が未設定"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    RAKUTEN_SEARCH_URL,
                    params={
                        "applicationId": self.app_id,
                        "accessKey": self.access_key,
                        "keyword": "テスト",
                        "hits": 1,
                        "format": "json",
                        "formatVersion": "2",
                    }
                )

            data = resp.json()
            if "error" in data:
                return {
                    "ok": False,
                    "http_status": resp.status_code,
                    "error": data.get("error"),
                    "error_description": data.get("error_description", ""),
                }

            count = data.get("count", 0)
            items = data.get("Items", [])
            return {
                "ok": True,
                "http_status": resp.status_code,
                "api_total_count": count,
                "items_returned": len(items),
                "response_keys": list(data.keys()),
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}
