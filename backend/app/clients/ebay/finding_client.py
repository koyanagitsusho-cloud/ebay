"""
eBay Finding APIクライアント
eBayの売れた商品（Completed Items）を検索して相場価格を取得する。
https://developer.ebay.com/Devzone/finding/CallRef/findCompletedItems.html
"""

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

FINDING_API_URL = "https://svcs.ebay.com/services/search/FindingService/v1"


@dataclass
class EbaySoldItem:
    """eBayの売れた商品データ"""
    title: str
    sold_price_usd: float
    currency: str
    condition: str
    sold_date: str
    item_url: str


@dataclass
class EbayPriceSummary:
    """eBay相場価格サマリー"""
    keyword: str
    sold_count: int
    avg_price_usd: float
    min_price_usd: float
    max_price_usd: float
    median_price_usd: float
    items: list[EbaySoldItem]


class EbayFindingClient:
    """eBay Finding APIクライアント（売れた商品の相場調査用）"""

    def __init__(self):
        self.app_id = settings.EBAY_CLIENT_ID

    async def find_completed_items(
        self,
        keyword: str,
        max_results: int = 20,
        condition: str | None = None,
    ) -> list[EbaySoldItem]:
        """
        eBayで売れた商品を検索する（相場価格調査用）。

        Args:
            keyword: 検索キーワード（英語推奨）
            max_results: 最大取得件数
            condition: コンディション（1000=New, 3000=Used等）

        Returns:
            EbaySoldItemのリスト
        """
        if not self.app_id:
            logger.warning("EBAY_CLIENT_ID が未設定のため、eBay相場取得をスキップします")
            return []

        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.0.0",
            "SECURITY-APPNAME": self.app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
            "keywords": keyword,
            "paginationInput.entriesPerPage": str(min(max_results, 100)),
            "sortOrder": "EndTimeSoonest",
            # 売れた商品のみ（sold = true）
            "itemFilter(0).name": "SoldItemsOnly",
            "itemFilter(0).value": "true",
        }

        if condition:
            params["itemFilter(1).name"] = "Condition"
            params["itemFilter(1).value"] = condition

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(FINDING_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            response = data.get("findCompletedItemsResponse", [{}])[0]
            search_result = response.get("searchResult", [{}])[0]
            raw_items = search_result.get("item", [])

            items = []
            for raw in raw_items:
                try:
                    selling = raw.get("sellingStatus", [{}])[0]
                    price_data = selling.get("convertedCurrentPrice", [{}])[0]
                    price = float(price_data.get("__value__", 0))
                    currency = price_data.get("@currencyId", "USD")

                    condition_data = raw.get("condition", [{}])[0]
                    condition_name = condition_data.get("conditionDisplayName", [""])[0]

                    listing_info = raw.get("listingInfo", [{}])[0]
                    end_time = listing_info.get("endTime", [""])[0]

                    view_url = raw.get("viewItemURL", [""])[0]

                    if price > 0:
                        items.append(EbaySoldItem(
                            title=raw.get("title", [""])[0],
                            sold_price_usd=price,
                            currency=currency,
                            condition=condition_name,
                            sold_date=end_time,
                            item_url=view_url,
                        ))
                except (IndexError, KeyError, ValueError):
                    continue

            logger.info("eBay売れ筋検索完了", keyword=keyword, count=len(items))
            return items

        except httpx.HTTPError as e:
            logger.error("eBay Finding API HTTPエラー", keyword=keyword, error=str(e))
            return []
        except Exception as e:
            logger.error("eBay Finding API 予期せぬエラー", keyword=keyword, error=str(e))
            return []

    async def get_price_summary(
        self,
        keyword: str,
        max_results: int = 20,
    ) -> EbayPriceSummary | None:
        """
        キーワードの相場価格サマリーを取得する。

        Returns:
            価格サマリー。データなしの場合はNone
        """
        items = await self.find_completed_items(keyword, max_results=max_results)

        if not items:
            return None

        prices = [item.sold_price_usd for item in items]
        prices.sort()

        avg = sum(prices) / len(prices)
        median = prices[len(prices) // 2]

        return EbayPriceSummary(
            keyword=keyword,
            sold_count=len(items),
            avg_price_usd=round(avg, 2),
            min_price_usd=round(min(prices), 2),
            max_price_usd=round(max(prices), 2),
            median_price_usd=round(median, 2),
            items=items,
        )
