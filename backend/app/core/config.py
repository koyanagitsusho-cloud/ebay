"""
アプリケーション設定管理
環境変数から設定を読み込み、型安全に提供する。
pydantic-settings を使用することで、.env ファイルと環境変数の両方に対応。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    アプリケーション全設定。
    環境変数または .env ファイルから読み込む。
    シークレット情報は絶対にコードに直書きしない。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─────────────────────────────────────
    # アプリ基本設定
    # ─────────────────────────────────────
    APP_NAME: str = "eBay Automation Tool"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(..., description="JWT署名用シークレットキー（必須）")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8時間

    # ─────────────────────────────────────
    # データベース
    # ─────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/ebay_automation",
        description="非同期PostgreSQL接続URL。Railway提供の postgresql:// も自動変換する",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    @property
    def async_database_url(self) -> str:
        """
        SQLAlchemy asyncpg用URLを返す。
        RailwayはDATABASE_URLを `postgresql://` 形式で提供するため、
        `postgresql+asyncpg://` に自動変換する。
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            # Heroku互換形式も対応
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    # ─────────────────────────────────────
    # Redis
    # ─────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis接続URL（Celeryブローカー兼キャッシュ）",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celeryジョブ結果保存先",
    )

    # ─────────────────────────────────────
    # eBay API 設定
    # ─────────────────────────────────────
    EBAY_ENVIRONMENT: Literal["sandbox", "production"] = Field(
        default="sandbox",
        description="sandbox または production。本番投入前に必ず確認すること",
    )
    EBAY_CLIENT_ID: str = Field(default="", description="eBay Developer App Client ID")
    EBAY_CLIENT_SECRET: str = Field(default="", description="eBay Developer App Client Secret")
    EBAY_REFRESH_TOKEN: str = Field(default="", description="eBay OAuth2 リフレッシュトークン")
    EBAY_SCOPES: str = Field(
        default=(
            "https://api.ebay.com/oauth/api_scope/sell.inventory "
            "https://api.ebay.com/oauth/api_scope/sell.marketing "
            "https://api.ebay.com/oauth/api_scope/sell.account"
        ),
        description="eBay OAuthスコープ（スペース区切り）",
    )

    # eBay APIベースURL（environmentに応じて自動選択）
    @property
    def ebay_api_base_url(self) -> str:
        if self.EBAY_ENVIRONMENT == "production":
            return "https://api.ebay.com"
        return "https://api.sandbox.ebay.com"

    @property
    def ebay_auth_url(self) -> str:
        if self.EBAY_ENVIRONMENT == "production":
            return "https://api.ebay.com/identity/v1/oauth2/token"
        return "https://api.sandbox.ebay.com/identity/v1/oauth2/token"

    # ─────────────────────────────────────
    # 楽天API設定
    # ─────────────────────────────────────
    RAKUTEN_APP_ID: str = Field(default="", description="楽天デベロッパー アプリID（UUID）")
    RAKUTEN_ACCESS_KEY: str = Field(default="", description="楽天デベロッパー アクセスキー（pk_...）")

    # 自動リサーチ設定
    AUTO_RESEARCH_KEYWORDS: str = Field(
        default="ポケモンカード,ゲーム機,カメラ,ヘッドホン,腕時計,フィギュア,ガンプラ",
        description="自動リサーチ対象キーワード（カンマ区切り）",
    )
    AUTO_RESEARCH_MAX_PURCHASE_PRICE_JPY: int = Field(
        default=30000,
        description="自動リサーチ: 仕入れ価格上限（円）",
    )
    AUTO_RESEARCH_MIN_PURCHASE_PRICE_JPY: int = Field(
        default=500,
        description="自動リサーチ: 仕入れ価格下限（円）",
    )
    AUTO_RESEARCH_MIN_SCORE: float = Field(
        default=30.0,
        description="自動リサーチ: 候補登録の最低スコア閾値",
    )

    # ─────────────────────────────────────
    # AI（Anthropic Claude）設定
    # ─────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic Claude API キー")
    CLAUDE_MODEL: str = Field(
        default="claude-sonnet-4-6",
        description="使用するClaudeモデルID",
    )
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.3  # 出品文生成は一貫性重視で低め

    # ─────────────────────────────────────
    # ビジネスルール（デフォルト値）
    # ─────────────────────────────────────
    DEFAULT_PROFIT_RATE_MIN: float = Field(
        default=0.15,
        description="最低利益率（15%）。これを下回る出品・値下げはブロック",
    )
    DEFAULT_PROFIT_AMOUNT_MIN: float = Field(
        default=500.0,
        description="最低利益額（円）。これを下回る出品・値下げはブロック",
    )
    DEFAULT_EBAY_FEE_RATE: float = Field(
        default=0.1325,
        description="eBay手数料率（13.25%）。カテゴリにより異なるため要確認",
    )
    DEFAULT_PAYPAL_FEE_RATE: float = Field(
        default=0.029,
        description="決済手数料率（2.9%）",
    )
    DEFAULT_EXCHANGE_RATE_JPY_USD: float = Field(
        default=150.0,
        description="円→ドル換算レート（仮値。定期更新推奨）",
    )

    # ─────────────────────────────────────
    # 安全装置
    # ─────────────────────────────────────
    DRY_RUN_DEFAULT: bool = Field(
        default=True,
        description="デフォルトでdry-runモード有効。本番操作には明示的にFalseにする",
    )
    REQUIRE_APPROVAL_FOR_PUBLISH: bool = Field(
        default=True,
        description="出品公開に承認フローを必須化",
    )
    REQUIRE_APPROVAL_FOR_PRICE_CHANGE: bool = Field(
        default=True,
        description="価格変更に承認フローを必須化",
    )

    # ─────────────────────────────────────
    # ジョブ設定
    # ─────────────────────────────────────
    JOB_MAX_RETRIES: int = 3
    JOB_RETRY_DELAY_SECONDS: int = 60

    # ─────────────────────────────────────
    # ログ設定
    # ─────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"
    LOG_SENSITIVE_MASK: bool = Field(
        default=True,
        description="ログにシークレット・個人情報が混入しないようマスクする",
    )

    # ─────────────────────────────────────
    # CORS
    # ─────────────────────────────────────
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="フロントエンドのオリジン（Next.js開発サーバー）",
    )

    @field_validator("DEFAULT_PROFIT_RATE_MIN")
    @classmethod
    def validate_profit_rate(cls, v: float) -> float:
        if not 0 < v < 1:
            raise ValueError("最低利益率は0〜1の間で設定してください（例: 0.15 = 15%）")
        return v

    @field_validator("DEFAULT_EBAY_FEE_RATE")
    @classmethod
    def validate_fee_rate(cls, v: float) -> float:
        if not 0 < v < 1:
            raise ValueError("手数料率は0〜1の間で設定してください")
        return v


@lru_cache
def get_settings() -> Settings:
    """
    設定をシングルトンで返す。
    アプリ起動後は同じインスタンスを再利用するため、
    テスト時は依存性注入でオーバーライドすること。
    """
    return Settings()


# 短縮アクセス用（FastAPI依存性注入でも使用）
settings = get_settings()
