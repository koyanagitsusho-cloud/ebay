"""
スコアリングサービスのテスト
各軸スコア・合計スコア・推奨判定を検証する。
"""

import pytest

from app.services.profit_calculator import ProfitCalculator
from app.services.scoring_service import ScoringInput, ScoringService


def make_profit_result(
    sale_usd: float = 30.0,
    purchase_jpy: float = 1000.0,
    domestic_jpy: float = 200.0,
    intl_usd: float = 5.0,
):
    """テスト用利益計算結果を作成するヘルパー"""
    calc = ProfitCalculator(exchange_rate=150.0)
    return calc.calculate(
        sale_price_usd=sale_usd,
        purchase_price_jpy=purchase_jpy,
        domestic_shipping_jpy=domestic_jpy,
        international_shipping_usd=intl_usd,
    )


class TestScoringService:
    def setup_method(self):
        self.scoring = ScoringService()

    def test_total_score_is_within_range(self):
        """総合スコアが0〜100の範囲に収まること"""
        profit = make_profit_result()
        result = self.scoring.score(ScoringInput(profit_result=profit))
        assert 0 <= result.total_score <= 100

    def test_high_profit_gives_high_profit_score(self):
        """高利益率商品はprofit_scoreが高いこと"""
        # 高利益ケース
        high_profit = make_profit_result(sale_usd=50.0, purchase_jpy=500.0)
        # 低利益ケース
        low_profit = make_profit_result(sale_usd=10.0, purchase_jpy=1400.0)

        high_score = self.scoring.score(ScoringInput(profit_result=high_profit))
        low_score = self.scoring.score(ScoringInput(profit_result=low_profit))

        assert high_score.profit_score > low_score.profit_score

    def test_low_competition_gives_high_competition_score(self):
        """低競争商品はcompetition_scoreが高いこと"""
        profit = make_profit_result()
        low_comp = self.scoring.score(
            ScoringInput(profit_result=profit, competition_level="low")
        )
        high_comp = self.scoring.score(
            ScoringInput(profit_result=profit, competition_level="high")
        )
        assert low_comp.competition_score > high_comp.competition_score

    def test_prohibited_risk_high_gives_avoid(self):
        """禁止品リスクが高い場合は必ずavoid推奨になること"""
        profit = make_profit_result(sale_usd=100.0, purchase_jpy=100.0)  # 超高利益
        result = self.scoring.score(
            ScoringInput(profit_result=profit, prohibited_risk="high")
        )
        assert result.recommendation == "avoid"
        assert "禁止品" in result.recommendation_reason

    def test_unprofitable_item_gives_avoid(self):
        """赤字商品はavoidになること"""
        profit = make_profit_result(sale_usd=5.0, purchase_jpy=5000.0)
        assert profit.is_profitable is False

        result = self.scoring.score(ScoringInput(profit_result=profit))
        assert result.recommendation == "avoid"

    def test_listing_ease_score_increases_with_info(self):
        """情報が揃っているほど出品しやすさスコアが高いこと"""
        profit = make_profit_result()
        no_info = self.scoring.score(ScoringInput(profit_result=profit))
        full_info = self.scoring.score(
            ScoringInput(
                profit_result=profit,
                has_model_number=True,
                has_brand_info=True,
                has_clear_images=True,
                category_is_clear=True,
                description_complexity="easy",
            )
        )
        assert full_info.listing_ease_score > no_info.listing_ease_score

    def test_score_basis_is_saved(self):
        """スコア根拠が保存されること"""
        profit = make_profit_result()
        result = self.scoring.score(ScoringInput(profit_result=profit))
        assert result.score_basis is not None
        assert "profit" in result.score_basis
        assert "weights" in result.score_basis

    def test_high_score_gives_buy_recommendation(self):
        """70点以上はbuy推奨になること"""
        # 非常に有利な商品
        profit = make_profit_result(sale_usd=100.0, purchase_jpy=500.0, intl_usd=3.0)
        result = self.scoring.score(
            ScoringInput(
                profit_result=profit,
                competition_level="low",
                has_model_number=True,
                has_brand_info=True,
                has_clear_images=True,
                category_is_clear=True,
                description_complexity="easy",
                return_risk="low",
                authenticity_risk="low",
                fragility_risk="low",
                prohibited_risk="low",
            )
        )
        assert result.total_score >= 70
        assert result.recommendation == "buy"
