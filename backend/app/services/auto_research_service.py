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

# 日本語キーワード → eBay英語検索キーワードのマッピング
KEYWORD_TRANSLATION: dict[str, str] = {
    # ゲーム
    "ゲーム機": "Nintendo Switch PS5 game console Japan",
    "ゲームソフト": "Nintendo Switch game software Japan",
    "ポケモン": "Pokemon cards Japanese sealed",
    "ポケモンカード": "Pokemon cards Japanese booster box",
    "遊戯王": "Yu-Gi-Oh cards Japanese",
    "ニンテンドー": "Nintendo game Japan",
    "プレステ": "PlayStation Japan",
    "Switch": "Nintendo Switch Japan",
    # カメラ・電子機器
    "カメラ": "digital camera mirrorless Japan Sony Canon",
    "レンズ": "camera lens Japan Sony Canon Nikon",
    "一眼レフ": "DSLR camera Japan",
    "ミラーレス": "mirrorless camera Japan",
    # オーディオ
    "ヘッドホン": "headphones Sony Audio Technics Japan",
    "イヤホン": "earphones in-ear Japan",
    "スピーカー": "speaker audio Japan",
    "オーディオ": "audio equipment Japan vintage",
    # 時計・アクセサリー
    "腕時計": "Japanese watch vintage Seiko Casio",
    "時計": "watch Japanese Seiko Orient",
    "ブランド品": "luxury brand Japan authentic",
    # フィギュア・コレクション
    "フィギュア": "anime figure Japan collectible",
    "プラモデル": "Gundam model kit Japan",
    "ガンプラ": "Gundam model Japan Bandai",
    "アニメ": "anime merchandise Japan",
    # 楽器
    "楽器": "musical instrument Japan vintage",
    "ギター": "guitar Japan vintage",
    # PC・スマホ
    "キーボード": "mechanical keyboard Japan",
    "スマホ": "smartphone Japan unlocked",
    "iPad": "iPad Japan Apple",
    # その他
    "本": "Japanese book manga",
    "漫画": "manga Japanese comics",
    "スポーツ": "sports equipment Japan",
    "工具": "tools Japan vintage",
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
    """楽天市場 × eBay相場で自動リサーチを行うサービス。"""

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
        """1キーワードに対して自動リサーチを実行する。"""
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

        logger.info(
            "=== 自動リサーチ開始 ===",
            keyword=keyword,
            min_price_jpy=min_price,
            max_price_jpy=max_price,
            min_score=min_score_threshold,
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

        logger.info(
            "Step1 楽天検索完了",
            keyword=keyword,
            rakuten_found=result.rakuten_found,
        )

        if not rakuten_items:
            logger.warning("楽天検索結果が0件です。検索キーワードや価格範囲を確認してください。", keyword=keyword)
            return result

        # Step 2: eBay相場を取得
        ebay_keyword = KEYWORD_TRANSLATION.get(keyword, f"{keyword} Japan")
        logger.info("Step2 eBay相場検索", keyword=keyword, ebay_keyword=ebay_keyword)

        ebay_summary = await self.ebay_finding.get_price_summary(
            keyword=ebay_keyword,
            max_results=30,
        )

        if ebay_summary and ebay_summary.sold_count > 0:
            result.ebay_price_found = ebay_summary.sold_count
            market_price_usd = ebay_summary.median_price_usd
            logger.info(
                "Step2 eBay相場取得成功",
                ebay_keyword=ebay_keyword,
                median_usd=market_price_usd,
                sold_count=ebay_summary.sold_count,
                avg_usd=ebay_summary.avg_price_usd,
            )
        else:
            logger.warning(
                "Step2 eBay相場データなし。楽天価格から価格を推定します。",
                ebay_keyword=ebay_keyword,
            )
            market_price_usd = None

        # 重複チェック用に既存タイトルをまとめて取得（1回だけ）
        existing_items = await self.repo.list_by_status(limit=2000)
        existing_titles = {item.title for item in existing_items}
        logger.info("既存候補件数", count=len(existing_titles))

        # Step 3: 各楽天商品に対して利益計算 → 候補登録
        logger.info("Step3 利益計算・登録開始", items_count=len(rakuten_items))

        for i, item in enumerate(rakuten_items):
            try:
                await self._process_item(
                    item=item,
                    market_price_usd=market_price_usd,
                    min_score_threshold=min_score_threshold,
                    result=result,
                    existing_titles=existing_titles,
                    index=i + 1,
                    total=len(rakuten_items),
                )
            except Exception as e:
                logger.error(
                    "商品処理エラー",
                    index=i + 1,
                    item_title=item.title[:50],
                    error=str(e),
                )
                result.errors += 1

        logger.info(
            "=== 自動リサーチ完了 ===",
            keyword=keyword,
            rakuten_found=result.rakuten_found,
            ebay_price_found=result.ebay_price_found,
            profit_calculated=result.profit_calculated,
            candidates_created=result.candidates_created,
            skipped_low_profit=result.skipped_low_profit,
            skipped_duplicate=result.skipped_duplicate,
            errors=result.errors,
        )
        return result

    async def _process_item(
        self,
        item: RakutenItem,
        market_price_usd: float | None,
        min_score_threshold: float,
        result: AutoResearchResult,
        existing_titles: set,
        index: int,
        total: int,
    ) -> None:
        """1商品を処理して候補登録するかどうかを判定する"""

        purchase_price = item.price_jpy

        # 国際送料の推定（仕入れ価格帯で分類）
        if purchase_price <= 3000:
            estimated_shipping_usd = 8.0
        elif purchase_price <= 10000:
            estimated_shipping_usd = 15.0
        else:
            estimated_shipping_usd = 25.0

        # eBay目標価格の決定
        if market_price_usd is None:
            # eBay相場なし: 楽天価格から推定（円→USD×3倍）
            target_price_usd = round(
                (purchase_price / settings.DEFAULT_EXCHANGE_RATE_JPY_USD) * 3.0, 2
            )
            price_source = "推定（楽天価格×3）"
        else:
            # eBay相場あり: 相場の90%
            target_price_usd = round(market_price_usd * 0.90, 2)
            price_source = f"eBay相場({market_price_usd:.2f})の90%"

        # 利益計算
        profit_result = self.calculator.calculate(
            sale_price_usd=target_price_usd,
            purchase_price_jpy=purchase_price,
            domestic_shipping_jpy=0,
            international_shipping_usd=estimated_shipping_usd,
            other_cost_jpy=0,
        )
        result.profit_calculated += 1

        logger.info(
            f"[{index}/{total}] 利益計算",
            title=item.title[:40],
            purchase_jpy=purchase_price,
            target_usd=target_price_usd,
            price_source=price_source,
            profit_jpy=profit_result.gross_profit_jpy,
            profit_rate=f"{profit_result.gross_profit_rate:.1%}",
            is_profitable=profit_result.is_profitable,
        )

        # 利益率・利益額チェック
        if (
            profit_result.gross_profit_rate < settings.DEFAULT_PROFIT_RATE_MIN
            or profit_result.gross_profit_jpy < settings.DEFAULT_PROFIT_AMOUNT_MIN
        ):
            logger.info(
                f"[{index}/{total}] 利益不足でスキップ",
                title=item.title[:40],
                profit_rate=f"{profit_result.gross_profit_rate:.1%}",
                profit_jpy=profit_result.gross_profit_jpy,
                min_rate=f"{settings.DEFAULT_PROFIT_RATE_MIN:.1%}",
                min_jpy=settings.DEFAULT_PROFIT_AMOUNT_MIN,
            )
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
            logger.info(
                f"[{index}/{total}] スコア不足でスキップ",
                title=item.title[:40],
                score=score_result.total_score,
                min_score=min_score_threshold,
            )
            result.skipped_low_profit += 1
            return

        # 重複チェック
        if item.title in existing_titles:
            logger.info(f"[{index}/{total}] 重複スキップ", title=item.title[:40])
            result.skipped_duplicate += 1
            return

        # DB登録
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

        # 登録済みタイトルに追加（同一実行内での重複防止）
        existing_titles.add(item.title)
        result.candidates_created += 1

        logger.info(
            f"[{index}/{total}] ★ 候補登録完了",
            title=item.title[:40],
            purchase_jpy=purchase_price,
            target_usd=target_price_usd,
            profit_rate=f"{profit_result.gross_profit_rate:.1%}",
            score=score_result.total_score,
        )

    async def run_all_keywords(
        self,
        keywords: list[str] | None = None,
    ) -> list[AutoResearchResult]:
        """全キーワードに対して自動リサーチを実行する。"""
        if keywords is None:
            keywords = [k.strip() for k in settings.AUTO_RESEARCH_KEYWORDS.split(",") if k.strip()]

        logger.info("全キーワードリサーチ開始", keywords=keywords, count=len(keywords))
        results = []

        for keyword in keywords:
            try:
                result = await self.run_for_keyword(keyword)
                results.append(result)
            except Exception as e:
                logger.error("キーワード処理エラー", keyword=keyword, error=str(e))

        total_created = sum(r.candidates_created for r in results)
        logger.info(
            "全キーワードリサーチ完了",
            keywords_count=len(keywords),
            total_candidates_created=total_created,
        )
        return results
