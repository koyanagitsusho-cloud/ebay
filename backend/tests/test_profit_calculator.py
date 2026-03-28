"""
利益計算サービスのテスト
計算式の正確性・最低利益率チェック・最低価格逆算を検証する。
"""

import pytest

from app.core.exceptions import ProfitAmountViolationError, ProfitRateViolationError
from app.services.profit_calculator import ProfitCalculator


class TestProfitCalculation:
    """利益計算の正確性テスト"""

    def setup_method(self):
        """テスト用計算機（手数料率・最低利益率を固定）"""
        self.calc = ProfitCalculator(
            exchange_rate=150.0,
            ebay_fee_rate=0.1325,
            payment_fee_rate=0.029,
            min_profit_rate=0.15,
            min_profit_amount=500.0,
        )

    def test_basic_calculation(self):
        """基本的な利益計算が正しく行われること"""
        result = self.calc.calculate(
            sale_price_usd=20.0,
            purchase_price_jpy=1500.0,
            domestic_shipping_jpy=300.0,
            international_shipping_usd=5.0,
            other_cost_jpy=0.0,
        )

        # 販売価格円換算: 20 × 150 = 3000
        assert result.sale_price_jpy == pytest.approx(3000.0)

        # eBay手数料: 3000 × 0.1325 = 397.5
        assert result.ebay_fee_jpy == pytest.approx(397.5)

        # 決済手数料: 3000 × 0.029 = 87.0
        assert result.payment_fee_jpy == pytest.approx(87.0)

        # 国際送料円換算: 5 × 150 = 750
        # 総原価: 1500 + 300 + 750 + 0 = 2550
        assert result.total_cost_jpy == pytest.approx(2550.0)

        # 受取額: 3000 - 397.5 - 87.0 = 2515.5
        assert result.receive_amount_jpy == pytest.approx(2515.5)

        # 粗利: 2515.5 - 2550 = -34.5（赤字）
        assert result.gross_profit_jpy == pytest.approx(-34.5)
        assert result.is_profitable is False

    def test_profitable_item(self):
        """利益が出るケースで is_profitable=True になること"""
        result = self.calc.calculate(
            sale_price_usd=30.0,
            purchase_price_jpy=1000.0,
            domestic_shipping_jpy=200.0,
            international_shipping_usd=4.0,
            other_cost_jpy=0.0,
        )
        assert result.is_profitable is True
        assert result.gross_profit_jpy > 0

    def test_profit_rate_calculated_correctly(self):
        """利益率が（粗利 / 販売価格円換算）で計算されること"""
        result = self.calc.calculate(
            sale_price_usd=50.0,
            purchase_price_jpy=2000.0,
            domestic_shipping_jpy=0.0,
            international_shipping_usd=0.0,
        )
        expected_rate = result.gross_profit_jpy / result.sale_price_jpy
        assert result.gross_profit_rate == pytest.approx(expected_rate, abs=0.001)

    def test_min_profit_rate_check(self):
        """最低利益率を下回る場合にvalidate_priceでエラーになること"""
        with pytest.raises(ProfitRateViolationError) as exc_info:
            self.calc.validate_price(
                sale_price_usd=10.0,  # 低い価格 → 利益率が15%を下回る
                purchase_price_jpy=1400.0,
                domestic_shipping_jpy=200.0,
                international_shipping_usd=3.0,
            )
        assert exc_info.value.min_rate == 0.15
        assert exc_info.value.error_code == "PROFIT_RATE_VIOLATION"

    def test_min_profit_amount_check(self):
        """最低利益額を下回る場合にvalidate_priceでエラーになること"""
        # 高い利益率だが絶対額が500円未満のケース
        calc = ProfitCalculator(
            exchange_rate=150.0,
            ebay_fee_rate=0.1325,
            payment_fee_rate=0.029,
            min_profit_rate=0.05,   # 利益率ルールは緩く
            min_profit_amount=500.0,  # 利益額は¥500必要
        )
        with pytest.raises(ProfitAmountViolationError):
            calc.validate_price(
                sale_price_usd=5.0,  # 低価格 → 利益額が¥500未満
                purchase_price_jpy=200.0,
                domestic_shipping_jpy=0.0,
                international_shipping_usd=0.0,
            )

    def test_min_profitable_price_returns_valid_price(self):
        """最低利益価格が実際に最低利益率を満たすこと"""
        result = self.calc.calculate(
            sale_price_usd=1.0,  # 計算不要（最低価格を計算したい）
            purchase_price_jpy=2000.0,
            domestic_shipping_jpy=300.0,
            international_shipping_usd=5.0,
        )
        min_price = result.min_profitable_price_usd

        # 最低価格で計算して利益率が閾値以上になることを確認
        verify = self.calc.calculate(
            sale_price_usd=min_price,
            purchase_price_jpy=2000.0,
            domestic_shipping_jpy=300.0,
            international_shipping_usd=5.0,
        )
        # 若干の丸め誤差は許容（0.5%以内）
        assert verify.gross_profit_rate >= self.calc.min_profit_rate - 0.005

    def test_zero_purchase_price(self):
        """仕入れ価格0円でも計算できること"""
        result = self.calc.calculate(
            sale_price_usd=10.0,
            purchase_price_jpy=0.0,
        )
        assert result.is_profitable is True
        assert result.gross_profit_jpy > 0

    def test_sku_included_in_error_message(self):
        """validate_price のSKU指定がエラーメッセージに含まれること"""
        with pytest.raises(ProfitRateViolationError) as exc_info:
            self.calc.validate_price(
                sale_price_usd=5.0,
                purchase_price_jpy=2000.0,
                sku="TEST-SKU-001",
            )
        assert "TEST-SKU-001" in exc_info.value.message
