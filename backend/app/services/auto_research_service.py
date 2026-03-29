"""
自動リサーチサービス
楽天市場から商品を取得 → eBay相場を調査 → 利益計算 → 候補自動登録
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ebay.finding_client import EbayFindingClient
from app.clients.rakuten.client import RakutenClient, RakutenItem
from app.core.config import settings
from app.core.logging_config import get_logger
from app.repositories.research_repo import ResearchCandidateRepository, ResearchScoreRepository
from app.services.profit_calculator import ProfitCalculator
from app.services.scoring_service import ScoringInput, ScoringService

logger = get_logger(__name__)

# 日本語キーワード → 英語検索キーワードのマッピング（eBay検索用）
KEYWORD_TRANSLATION: dict[str, str] = {
    "ゲーム機": "game console Nintendo Sony",
    "カメラ": "camera digital mirrorless Japan",
    "ヘッドホン": "headphones Sony Audio Japan",
    "腕時計": "watch Japanese vintage",
    "フィギュア": "anime figure Japan",
    "レンズ": "camera lens Japan",
    "オーディオ": "audio equipment Japan",
    "キーボード": "mechanical keyboard Japan",
}


@dataclass
class AutoResearchResult:
    """自動リサーチ実行結果"""
    keyword: str
    rakuten_found: int
    ebay_price_found: int
    profit_calculated: int
    candidates_created: int
    skipped_low_profit: int
    skipped_duplicate: int
    errors: int


class AutoResearchService:
    """
    楽天市場 × eBay相場で自動リサーチを行うサービス。

    処理フロー:
    1. 楽天市場でキーワード検索（仕入れ候補の取得）
    2. 同商品をeBayで検索して相場価格を確認
    3. 利益計算・スコアリング
    4. 最低スコア以上の商品をリサーチ候補として登録
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.rakuten = RakutenClient()
        self.ebay_finding = EbayFindingClient()
        self.calculator = ProfitCalculator()
        self.scoring = ScoringService()
        self.repo = ResearchCandidateRepository(db)
        self.score_repo = ResearchScoreRepository(db)

    async def run_for_keyword(
        self,
        keyword: str,
        min_price_jpy: int | None = None,
        max_price_jpy: int | None = None,
        min_score: float | None = None,
    ) -> AutoResearchResult:
        """
        1キーワードに対して自動リサーチを実行する。

        Args:
            keyword: 楽天検索キーワード
            min_price_jpy: 仕入れ価格下限（円）
            max_price_jpy: 仕入れ価格上限（円）
            min_score: 候補登録の最低スコア
        """
        min_price = min_price_jpy or settings.AUTO_RESEARCH_MIN_PURCHASE_PRICE_JPY
        max_price = max_price_jpy or settings.AUTO_RESEARCH_MAX_PURCHASE_PRICE_JPY
        min_score_threshold = min_score or settings.AUTO_RESEARCH_MIN_SCORE

        result = AutoResearchResult(
            keyword=keyword,
            rakuten_found=0,
            ebay_price_found=0,
            profit_calculated=0,
            candidates_created=0,
            skipped_low_profit=0,
            skipped_duplicate=0,
            errors=0,
        )

        # Step 1: 楽天市場で商品検索
        rakuten_items = await self.rakuten.search_items(
            keyword=keyword,
            min_price=min_price,
            max_price=max_price,
            hits=30,
            sort="-reviewCount",
        )
        result.rakuten_found = len(rakuten_items)

        if not rakuten_items:
            logger.info("楽天で商品が見つかりませんでした", keyword=keyword)
            return result

        # eBay検索用の英語キーワードを決定
        ebay_keyword = KEYWORD_TRANSLATION.get(keyword, keyword)

        # Step 2: eBay相場を取得（キーワード単位で1回だけ）
        ebay_summary = await self.ebay_finding.get_price_summary(
            keyword=ebay_keyword,
            max_results=30,
        )

        if ebay_summary:
            result.ebay_price_found = ebay_summary.sold_count
            # 相場価格として中央値を使用（平均より外れ値の影響を受けにくい）
            market_price_usd = ebay_summary.median_price_usd
            logger.info(
                "eBay相場取得",
                keyword=ebay_keyword,
                median_usd=market_price_usd,
                sold_count=ebay_summary.sold_count,
            )
        else:
            # eBayデータなし → 楽天価格から推定（円 ÷ レート × 1.5 で粗利確保）
            logger.warning(
                "eBay相場データなし。楽天価格から推定します",
                keyword=keyword,
            )
            market_price_usd = None

        # Step 3: 各楽天商品に対して利益計算 → 候補登録
        for item in rakuten_items:
            try:
                await self._process_item(
                    item=item,
                    market_price_usd=market_price_usd,
                    min_score_threshold=min_score_threshold,
                    result=result,
                )
            except Exception as e:
                logger.error(
                    "商品処理エラー",
                    item_title=item.title[:50],
                    error=str(e),
                )
                result.errors += 1

        logger.info(
            "自動リサーチ完了",
            keyword=keyword,
            rakuten_found=result.rakuten_found,
            candidates_created=result.candidates_created,
            skipped_low_profit=result.skipped_low_profit,
        )
        return result

    async def _process_item(
        self,
        item: RakutenItem,
        market_price_usd: float | None,
        min_score_threshold: float,
        result: AutoResearchResult,
    ) -> None:
        """1商品を処理して候補登録するかどうかを判定する"""

        purchase_price = item.price_jpy

        # eBay相場がない場合は楽天価格から目標価格を推定
        if market_price_usd is None:
            # 楽天価格（円）→ USD換算 × 利益係数（最低限の利益を確保する倍率）
            estimated_usd = (purchase_price / settings.DEFAULT_EXCHANGE_RATE_JPY_USD) * 2.0
            target_price_usd = round(estimated_usd, 2)
        else:
            # eBay相場の95%を目標価格とする（競争力のある価格設定）
            target_price_usd = round(market_price_usd * 0.95, 2)

        # 国際送料の推定（重量・サイズ不明のため固定値）
        estimated_shipping_usd = 15.0

        # 利益計算
        profit_result = self.calculator.calculate(
            sale_price_usd=target_price_usd,
            purchase_price_jpy=purchase_price,
            domestic_shipping_jpy=0,
            international_shipping_usd=estimated_shipping_usd,
            other_cost_jpy=0,
        )
        result.profit_calculated += 1

        # 利益率・利益額チェック
        if (
            profit_result.gross_profit_rate < settings.DEFAULT_PROFIT_RATE_MIN
            or profit_result.gross_profit_jpy < settings.DEFAULT_PROFIT_AMOUNT_MIN
        ):
            result.skipped_low_profit += 1
            return

        # スコアリング
        score_input = ScoringInput(
            profit_result=profit_result,
            has_model_number=False,
            has_brand_info=False,
        )
        score_result = self.scoring.score(score_input)

        if score_result.total_score < min_score_threshold:
            result.skipped_low_profit += 1
            return

        # 重複チェック（同じタイトルの候補が既にあればスキップ）
        existing = await self.repo.list_by_status(limit=1000)
        for existing_item in existing:
            if existing_item.title == item.title:
                result.skipped_duplicate += 1
                return

        # リサーチ候補として登録
        candidate = await self.repo.create(
            title=item.title,
            brand=None,
            model_number=None,
            jan_code=item.jan_code,
            condition="used_good",
            notes=f"楽天自動リサーチ: {item.shop_name} | {item.item_url}",
            image_url_memo=item.image_url,
            purchase_price_jpy=purchase_price,
            domestic_shipping_jpy=0,
            international_shipping_usd=estimated_shipping_usd,
            other_cost_jpy=0,
            target_sale_price_usd=target_price_usd,
            estimated_profit_jpy=profit_result.gross_profit_jpy,
            estimated_profit_rate=profit_result.gross_profit_rate,
            estimated_receive_amount_jpy=profit_result.receive_amount_jpy,
            min_profitable_price_usd=profit_result.min_profitable_price_usd,
            profit_calc_detail=profit_result.to_dict(),
            status="new",
        )

        # スコアを保存
        await self.score_repo.create(
            candidate_id=candidate.id,
            profit_score=score_result.profit_score,
            competition_score=score_result.competition_score,
            sellability_score=score_result.sellability_score,
            listing_ease_score=score_result.listing_ease_score,
            risk_score=score_result.risk_score,
            total_score=score_result.total_score,
            return_risk=score_result.return_risk,
            authenticity_risk=score_result.authenticity_risk,
            fragility_risk=score_result.fragility_risk,
            prohibited_risk=score_result.prohibited_risk,
            score_basis=score_result.score_basis,
            scored_by="auto_research",
        )
        await self.repo.update(candidate, total_score=score_result.total_score, status="scored")

        result.candidates_created += 1
        logger.info(
            "候補を自動登録",
            title=item.title[:50],
            purchase_jpy=purchase_price,
            target_usd=target_price_usd,
            profit_rate=f"{profit_result.gross_profit_rate:.1%}",
            score=score_result.total_score,
        )

    async def run_all_keywords(
        self,
        keywords: list[str] | None = None,
    ) -> list[AutoResearchResult]:
        """
        設定された全キーワードに対して自動リサーチを実行する。

        Args:
            keywords: キーワードリスト。Noneの場合は設定値を使用
        """
        if keywords is None:
            keywords = [k.strip() for k in settings.AUTO_RESEARCH_KEYWORDS.split(",") if k.strip()]

        results = []
        for keyword in keywords:
            try:
                result = await self.run_for_keyword(keyword)
                results.append(result)
            except Exception as e:
                logger.error("キーワード処理エラー", keyword=keyword, error=str(e))

        total_created = sum(r.candidates_created for r in results)
        logger.info(
            "全キーワード自動リサーチ完了",
            keywords=keywords,
            total_candidates_created=total_created,
        )
        return results
