"""
eBay APIベースクライアント
OAuth2.0トークン管理とHTTPリクエスト共通処理を担う。

重要な注意事項:
- sandbox と production は URL・認証情報が異なる
- アクセストークンの自動更新はリフレッシュトークン方式を使用
- eBay APIの仕様変更はここ一箇所を修正すれば対応できる設計
- APIレスポンスエラーは全てEbayApiErrorに変換してサービス層に伝達する

未実装・仮実装:
- トークンのRedisキャッシュ（TODO: 現状はメモリキャッシュのみ）
- レート制限への対応（TODO: リトライロジックを追加すること）
"""

import base64
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import EbayApiError, EbayTokenExpiredError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────
# eBay APIのバージョン・マーケットプレイス
# ─────────────────────────────────────
MARKETPLACE_ID = "EBAY_US"
CONTENT_LANGUAGE = "en-US"


class EbayTokenCache:
    """
    アクセストークンのインメモリキャッシュ。
    プロセス再起動でクリアされるため、本番では Redis に移行すること。
    TODO: Redis対応を追加する
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get(self) -> str | None:
        if self._token and time.time() < self._expires_at - 60:  # 60秒余裕
            return self._token
        return None

    def set(self, token: str, expires_in: int) -> None:
        self._token = token
        self._expires_at = time.time() + expires_in


# グローバルトークンキャッシュ（プロセス内で共有）
_token_cache = EbayTokenCache()


class EbayBaseClient:
    """
    eBay APIベースクライアント。
    全eBay APIクライアントの基底クラス。
    OAuth2.0認証とHTTPリクエスト処理を提供する。
    """

    def __init__(self) -> None:
        self._base_url = settings.ebay_api_base_url
        self._auth_url = settings.ebay_auth_url
        self._timeout = httpx.Timeout(30.0)

    async def _get_access_token(self) -> str:
        """
        eBay OAuthアクセストークンを取得する。
        キャッシュが有効なら再利用、期限切れならリフレッシュトークンで更新する。

        前提: EBAY_REFRESH_TOKEN が設定済みであること
        トークンの取得方法: eBay Developer Portal でOAuth同意フローを実行する
        """
        cached = _token_cache.get()
        if cached:
            return cached

        if not settings.EBAY_REFRESH_TOKEN:
            raise EbayTokenExpiredError()

        # Clientクレデンシャルをbase64エンコード
        credentials = f"{settings.EBAY_CLIENT_ID}:{settings.EBAY_CLIENT_SECRET}"
        encoded = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": settings.EBAY_REFRESH_TOKEN,
            "scope": settings.EBAY_SCOPES,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._auth_url,
                headers=headers,
                data=data,
            )

        if response.status_code != 200:
            logger.error(
                "eBayトークン更新失敗",
                status=response.status_code,
            )
            raise EbayApiError(
                "アクセストークンの更新に失敗しました",
                status_code=response.status_code,
            )

        token_data = response.json()
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 7200)

        _token_cache.set(access_token, expires_in)
        logger.info("eBayアクセストークン更新完了", expires_in=expires_in)

        return access_token

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
        params: dict | None = None,
        extra_headers: dict | None = None,
    ) -> dict[str, Any]:
        """
        eBay APIへHTTPリクエストを送信する。
        エラーレスポンスはEbayApiErrorに変換して返す。

        注意: eBay APIのエラーレスポンス形式はAPIごとに異なる場合がある。
        ここでは一般的な形式を想定しているが、個別APIで調整が必要な場合は
        サブクラスでオーバーライドすること。
        """
        access_token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
            "Content-Language": CONTENT_LANGUAGE,
        }
        if extra_headers:
            headers.update(extra_headers)

        url = f"{self._base_url}{path}"

        logger.debug(
            "eBay APIリクエスト",
            method=method,
            path=path,
            has_body=json_body is not None,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body,
                    params=params,
                )
        except httpx.TimeoutException as e:
            raise EbayApiError(f"タイムアウト: {path}", status_code=None) from e
        except httpx.HTTPError as e:
            raise EbayApiError(f"HTTP接続エラー: {e}", status_code=None) from e

        # 204 No Content は空dictを返す
        if response.status_code == 204:
            return {}

        # eBay APIのエラーレスポンス処理
        if response.status_code >= 400:
            try:
                error_body = response.json()
            except Exception:
                error_body = {"raw": response.text}

            error_msg = self._extract_error_message(error_body)
            error_id = self._extract_error_id(error_body)

            logger.error(
                "eBay APIエラー",
                status=response.status_code,
                error_id=error_id,
                error_msg=error_msg,
                path=path,
            )

            raise EbayApiError(
                message=error_msg,
                status_code=response.status_code,
                ebay_error_id=error_id,
                raw_response=error_body,
            )

        try:
            return response.json()
        except Exception:
            # JSONでないレスポンス（テキスト等）はそのまま返す
            return {"raw": response.text}

    def _extract_error_message(self, error_body: dict) -> str:
        """eBay APIエラーレスポンスからエラーメッセージを抽出する"""
        # eBay APIのエラー形式は複数あるため順番に試みる
        if "errors" in error_body and error_body["errors"]:
            return error_body["errors"][0].get("message", "不明なエラー")
        if "error_description" in error_body:
            return error_body["error_description"]
        if "message" in error_body:
            return error_body["message"]
        return str(error_body)

    def _extract_error_id(self, error_body: dict) -> str | None:
        """eBay APIエラーIDを抽出する"""
        if "errors" in error_body and error_body["errors"]:
            return str(error_body["errors"][0].get("errorId", ""))
        return None
