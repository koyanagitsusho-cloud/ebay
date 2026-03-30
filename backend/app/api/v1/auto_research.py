"""
自動リサーチAPI
楽天×eBay自動リサーチの手動トリガー・設定管理を提供する。
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auto-research", tags=["自動リサーチ"])


class AutoResearchRunRequest(BaseModel):
    keywords: list[str] | None = None
    min_price_jpy: int | None = None
    max_price_jpy: int | None = None
    min_score: float | None = None


class AutoResearchRunResponse(BaseModel):
    message: str
    task_id: str | None = None
    keywords: list[str]


class AutoResearchSettingsResponse(BaseModel):
    keywords: list[str]
    min_purchase_price_jpy: int
    max_purchase_price_jpy: int
    min_score: float
    rakuten_configured: bool
    ebay_configured: bool


@router.get("/debug-rakuten", summary="楽天APIキーの詳細診断（認証不要）")
async def debug_rakuten() -> dict:
    """楽天APIキーの実際の値・リクエスト内容を診断する（新エンドポイント対応）"""
    import httpx
    app_id = settings.RAKUTEN_APP_ID
    access_key = settings.RAKUTEN_ACCESS_KEY
    try:
        params = {
            "applicationId": app_id,
            "accessKey": access_key,
            "keyword": "テスト",
            "hits": 1,
            "format": "json",
            "formatVersion": "2",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601",
                params=params,
            )
        return {
            "app_id_length": len(app_id),
            "app_id_first10": app_id[:10],
            "access_key_set": bool(access_key),
            "access_key_length": len(access_key),
            "http_status": resp.status_code,
            "response": resp.json(),
            "request_url": str(resp.url),
        }
    except Exception as e:
        return {"error": str(e), "app_id_length": len(app_id)}


@router.get("/server-ip", summary="このサーバーの外部IPを確認する（認証不要）")
async def get_server_ip() -> dict:
    """Railway サーバーの外部IPアドレスを返す（楽天IP制限設定用・認証不要）"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.ipify.org?format=json")
            ip_data = resp.json()
            return {
                "server_ip": ip_data.get("ip"),
                "note": "この IP を楽天の許可IPリストに追加してください",
            }
    except Exception as e:
        return {"error": str(e)}


@router.get("/diagnose", summary="API接続診断（楽天・eBayの疎通確認）")
async def diagnose(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    楽天APIとeBay APIの実際の疎通をテストする。
    設定済み表示でも実際に動いているかここで確認できる。
    """
    from app.clients.ebay.finding_client import EbayFindingClient
    from app.clients.rakuten.client import RakutenClient

    rakuten = RakutenClient()
    ebay = EbayFindingClient()

    # 楽天API テスト
    rakuten_result = await rakuten.test_connection()

    # eBay Finding API テスト（本番エンドポイント）
    ebay_items = await ebay.find_completed_items("Pokemon cards Japan", max_results=3)
    ebay_result = {
        "ok": len(ebay_items) > 0,
        "items_found": len(ebay_items),
        "sample_price": ebay_items[0].sold_price_usd if ebay_items else None,
        "endpoint": ebay.finding_url,
        "app_id_prefix": settings.EBAY_CLIENT_ID[:15] + "..." if settings.EBAY_CLIENT_ID else None,
    }

    # サーバーIPも確認
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=5.0) as c:
            ip_resp = await c.get("https://api.ipify.org?format=json")
        server_ip = ip_resp.json().get("ip")
    except Exception:
        server_ip = "取得失敗"

    return {
        "rakuten": rakuten_result,
        "ebay": ebay_result,
        "rakuten_app_id_set": bool(settings.RAKUTEN_APP_ID),
        "rakuten_access_key_set": bool(settings.RAKUTEN_ACCESS_KEY),
        "ebay_client_id_set": bool(settings.EBAY_CLIENT_ID),
        "server_ip": server_ip,
    }


@router.get("/settings", response_model=AutoResearchSettingsResponse)
async def get_auto_research_settings(
    current_user: User = Depends(get_current_user),
) -> AutoResearchSettingsResponse:
    """自動リサーチの現在の設定を返す"""
    keywords = [k.strip() for k in settings.AUTO_RESEARCH_KEYWORDS.split(",") if k.strip()]
    return AutoResearchSettingsResponse(
        keywords=keywords,
        min_purchase_price_jpy=settings.AUTO_RESEARCH_MIN_PURCHASE_PRICE_JPY,
        max_purchase_price_jpy=settings.AUTO_RESEARCH_MAX_PURCHASE_PRICE_JPY,
        min_score=settings.AUTO_RESEARCH_MIN_SCORE,
        rakuten_configured=bool(settings.RAKUTEN_APP_ID and settings.RAKUTEN_ACCESS_KEY),
        ebay_configured=bool(settings.EBAY_CLIENT_ID),
    )


@router.post("/run", response_model=AutoResearchRunResponse)
async def run_auto_research(
    payload: AutoResearchRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> AutoResearchRunResponse:
    """
    自動リサーチを手動で実行する。
    Celeryキューに積んで非同期実行する。
    """
    from app.workers.auto_research_tasks import run_auto_research as celery_task

    keywords = payload.keywords or [
        k.strip() for k in settings.AUTO_RESEARCH_KEYWORDS.split(",") if k.strip()
    ]

    task = celery_task.delay(
        keywords=keywords,
        min_price_jpy=payload.min_price_jpy,
        max_price_jpy=payload.max_price_jpy,
        min_score=payload.min_score,
    )

    return AutoResearchRunResponse(
        message=f"{len(keywords)}件のキーワードでリサーチを開始しました",
        task_id=task.id,
        keywords=keywords,
    )


@router.post("/run-sync", summary="同期実行（テスト用）")
async def run_auto_research_sync(
    payload: AutoResearchRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
) -> dict:
    """
    自動リサーチを同期実行する（Celery不要・動作確認用）。
    結果をそのまま返すためレスポンスに時間がかかる場合がある。
    """
    from app.services.auto_research_service import AutoResearchService

    keywords = payload.keywords or [
        k.strip() for k in settings.AUTO_RESEARCH_KEYWORDS.split(",") if k.strip()
    ]

    service = AutoResearchService(db)
    results = await service.run_all_keywords(keywords=keywords)

    return {
        "keywords_processed": len(results),
        "total_candidates_created": sum(r.candidates_created for r in results),
        "total_skipped_low_profit": sum(r.skipped_low_profit for r in results),
        "total_skipped_duplicate": sum(r.skipped_duplicate for r in results),
        "per_keyword": [
            {
                "keyword": r.keyword,
                "rakuten_found": r.rakuten_found,
                "ebay_price_found": r.ebay_price_found,
                "candidates_created": r.candidates_created,
                "skipped_low_profit": r.skipped_low_profit,
                "skipped_duplicate": r.skipped_duplicate,
                "errors": r.errors,
            }
            for r in results
        ],
    }
