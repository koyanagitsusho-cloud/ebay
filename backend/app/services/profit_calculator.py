"""
利益計算サービス
仕入れ価格・送料・手数料から利益・利益率・最低価格を計算する。
計算式をここに一元化することで、複数画面での一貫性を保つ。

重要な前提:
- 為替レートは設定値を使用。定期更新推奨（外部レートAPIは未実装）
- eBay手数料率はカテゴリにより異なるが、初期実装では設定値の一律レートを使用
- 消費税は考慮しない（海外販売のため）
"""

from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import ProfitAmountViolationError, ProfitRateViolationError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────
# 定数（設定値で上書き可能だが、デフォルト値をここに明記）
# ─────────────────────────────────────
EBAY_FINAL_VALUE_FEE_RATE = settings.DEFAULT_EBAY_FEE_RATE  # 13.25%（カテゴリ依存）
PAYMENT_FEE_RATE = settings.DEFAULT_PAYPAL_FEE_RATE  # 2.9%
EXCHANGE_RATE_JPY_PER_USD = settings.DEFAULT_EXCHANGE_RATE_JPY_USD  # 150円/ドル（仮）


@dataclass
class ProfitCalculationResult:
    """
    利益計算結果。
    全ての金額・率を保持し、計算根拠を追跡できる。
    """

    # ─── 入力値（計算に使用した値） ───
    sale_price_usd: float
    purchase_price_jpy: float
    domestic_shipping_jpy: float
    international_shipping_usd: float
    other_cost_jpy: float
    exchange_rate: float
    ebay_fee_rate: float
    payment_fee_rate: float

    # ─── 計算結果 ───
    sale_price_jpy: float          # 販売価格（円換算）
    ebay_fee_jpy: float            # eBay手数料（円）
    payment_fee_jpy: float         # 決済手数料（円）
    total_fee_jpy: float           # 総手数料（円）
    total_cost_jpy: float          # 総原価（仕入れ+送料+手数料）
    gross_profit_jpy: float        # 粗利額（円）
    gross_profit_rate: float       # 粗利率（0〜1）
    receive_amount_jpy: float      # 実際の受取額（eBay・決済手数料控除後）

    # ─── 閾値チェック ───
    min_profit_rate: float         # 最低利益率（チェック用）
    min_profit_amount: float       # 最低利益額（チェック用）
    is_profitable: bool            # 利益が出るか
    profit_rate_ok: bool           # 最低利益率を満たすか
    profit_amount_ok: bool         # 最低利益額を満たすか

    # ─── 最低価格計算 ───
    min_profitable_price_usd: float  # 利益が出る最低価格（ドル）

    def to_dict(self) -> dict:
        """JSON保存用に辞書化（DB保存時に使用）"""
        return {
            "sale_price_usd": self.sale_price_usd,
            "purchase_price_jpy": self.purchase_price_jpy,
            "domestic_shipping_jpy": self.domestic_shipping_jpy,
            "international_shipping_usd": self.international_shipping_usd,
            "other_cost_jpy": self.other_cost_jpy,
            "exchange_rate": self.exchange_rate,
            "ebay_fee_rate": self.ebay_fee_rate,
            "payment_fee_rate": self.payment_fee_rate,
            "sale_price_jpy": self.sale_price_jpy,
            "ebay_fee_jpy": self.ebay_fee_jpy,
            "payment_fee_jpy": self.payment_fee_jpy,
            "total_fee_jpy": self.total_fee_jpy,
            "total_cost_jpy": self.total_cost_jpy,
            "gross_profit_jpy": self.gross_profit_jpy,
            "gross_profit_rate": round(self.gross_profit_rate, 4),
            "receive_amount_jpy": self.receive_amount_jpy,
            "is_profitable": self.is_profitable,
            "profit_rate_ok": self.profit_rate_ok,
            "profit_amount_ok": self.profit_amount_ok,
            "min_profitable_price_usd": self.min_profitable_price_usd,
        }


class ProfitCalculator:
    """
    利益計算ロジック。
    全ての計算をこのクラスに集約する。
    設定値のオーバーライドをサポート（テスト・カテゴリ別計算に対応）。
    """

    def __init__(
        self,
        exchange_rate: float | None = None,
        ebay_fee_rate: float | None = None,
        payment_fee_rate: float | None = None,
        min_profit_rate: float | None = None,
        min_profit_amount: float | None = None,
    ) -> None:
        self.exchange_rate = exchange_rate or EXCHANGE_RATE_JPY_PER_USD
        self.ebay_fee_rate = ebay_fee_rate or EBAY_FINAL_VALUE_FEE_RATE
        self.payment_fee_rate = payment_fee_rate or PAYMENT_FEE_RATE
        self.min_profit_rate = min_profit_rate or settings.DEFAULT_PROFIT_RATE_MIN
        self.min_profit_amount = min_profit_amount or settings.DEFAULT_PROFIT_AMOUNT_MIN

    def calculate(
        self,
        sale_price_usd: float,
        purchase_price_jpy: float,
        domestic_shipping_jpy: float = 0.0,
        international_shipping_usd: float = 0.0,
        other_cost_jpy: float = 0.0,
    ) -> ProfitCalculationResult:
        """
        利益を計算する。

        計算式:
        1. 販売価格（円） = 販売価格（USD） × 為替レート
        2. eBay手数料（円） = 販売価格（円） × eBay手数料率
        3. 決済手数料（円） = 販売価格（円） × 決済手数料率
        4. 国際送料（円） = 国際送料（USD） × 為替レート
        5. 総原価 = 仕入れ + 国内送料 + 国際送料（円換算） + その他原価
        6. 受取額 = 販売価格（円） - eBay手数料 - 決済手数料
        7. 粗利 = 受取額 - 総原価
        8. 粗利率 = 粗利 / 販売価格（円）

        注意: eBay手数料の計算ベースはカテゴリにより異なる。
        ここでは一律「販売価格全体」にかかる前提で計算している。
        """
        # 円換算
        sale_price_jpy = sale_price_usd * self.exchange_rate
        intl_shipping_jpy = international_shipping_usd * self.exchange_rate

        # 手数料計算
        ebay_fee_jpy = sale_price_jpy * self.ebay_fee_rate
        payment_fee_jpy = sale_price_jpy * self.payment_fee_rate
        total_fee_jpy = ebay_fee_jpy + payment_fee_jpy

        # 総原価
        total_cost_jpy = (
            purchase_price_jpy
            + domestic_shipping_jpy
            + intl_shipping_jpy
            + other_cost_jpy
        )

        # 受取額・粗利
        receive_amount_jpy = sale_price_jpy - total_fee_jpy
        gross_profit_jpy = receive_amount_jpy - total_cost_jpy

        # 粗利率（販売価格がゼロの場合は0）
        gross_profit_rate = gross_profit_jpy / sale_price_jpy if sale_price_jpy > 0 else 0.0

        # 最低価格計算（逆算）
        min_profitable_price_usd = self._calc_min_price(
            purchase_price_jpy=purchase_price_jpy,
            domestic_shipping_jpy=domestic_shipping_jpy,
            international_shipping_usd=international_shipping_usd,
            other_cost_jpy=other_cost_jpy,
        )

        result = ProfitCalculationResult(
            sale_price_usd=sale_price_usd,
            purchase_price_jpy=purchase_price_jpy,
            domestic_shipping_jpy=domestic_shipping_jpy,
            international_shipping_usd=international_shipping_usd,
            other_cost_jpy=other_cost_jpy,
            exchange_rate=self.exchange_rate,
            ebay_fee_rate=self.ebay_fee_rate,
            payment_fee_rate=self.payment_fee_rate,
            sale_price_jpy=round(sale_price_jpy, 2),
            ebay_fee_jpy=round(ebay_fee_jpy, 2),
            payment_fee_jpy=round(payment_fee_jpy, 2),
            total_fee_jpy=round(total_fee_jpy, 2),
            total_cost_jpy=round(total_cost_jpy, 2),
            gross_profit_jpy=round(gross_profit_jpy, 2),
            gross_profit_rate=round(gross_profit_rate, 4),
            receive_amount_jpy=round(receive_amount_jpy, 2),
            min_profit_rate=self.min_profit_rate,
            min_profit_amount=self.min_profit_amount,
            is_profitable=gross_profit_jpy > 0,
            profit_rate_ok=gross_profit_rate >= self.min_profit_rate,
            profit_amount_ok=gross_profit_jpy >= self.min_profit_amount,
            min_profitable_price_usd=round(min_profitable_price_usd, 2),
        )

        logger.debug(
            "利益計算完了",
            sku="",
            sale_price_usd=sale_price_usd,
            gross_profit_jpy=result.gross_profit_jpy,
            gross_profit_rate=f"{result.gross_profit_rate:.1%}",
        )

        return result

    def _calc_min_price(
        self,
        purchase_price_jpy: float,
        domestic_shipping_jpy: float,
        international_shipping_usd: float,
        other_cost_jpy: float,
    ) -> float:
        """
        最低利益率と最低利益額を両方満たす最低出品価格（USD）を逆算する。

        条件:
        受取額 - 総原価 >= min_profit_amount
        かつ
        (受取額 - 総原価) / 販売価格(円) >= min_profit_rate

        受取額 = P × (1 - ebay_rate - payment_rate)  (P = 販売価格(円))
        粗利 = P × (1 - ebay_rate - payment_rate) - total_cost
        最低利益率条件: P × (1 - rate) - cost >= P × min_rate
        → P × (1 - rate - min_rate) >= cost
        → P >= cost / (1 - rate - min_rate)
        """
        intl_shipping_jpy = international_shipping_usd * self.exchange_rate
        total_cost_jpy = (
            purchase_price_jpy
            + domestic_shipping_jpy
            + intl_shipping_jpy
            + other_cost_jpy
        )

        effective_rate = self.ebay_fee_rate + self.payment_fee_rate

        # 最低利益率から逆算
        denominator_rate = 1 - effective_rate - self.min_profit_rate
        if denominator_rate <= 0:
            # 手数料+最低利益率が100%超の場合は計算不可
            return float("inf")
        min_price_from_rate_jpy = total_cost_jpy / denominator_rate

        # 最低利益額から逆算
        denominator_amount = 1 - effective_rate
        min_price_from_amount_jpy = (
            (total_cost_jpy + self.min_profit_amount) / denominator_amount
            if denominator_amount > 0
            else float("inf")
        )

        # 両条件を満たす大きい方をとる
        min_price_jpy = max(min_price_from_rate_jpy, min_price_from_amount_jpy)
        return min_price_jpy / self.exchange_rate

    def validate_price(
        self,
        sale_price_usd: float,
        purchase_price_jpy: float,
        domestic_shipping_jpy: float = 0.0,
        international_shipping_usd: float = 0.0,
        other_cost_jpy: float = 0.0,
        sku: str = "",
    ) -> ProfitCalculationResult:
        """
        価格バリデーション付き計算。
        最低利益率・最低利益額を下回る場合は例外を送出する。
        価格改定・出品前の必須チェックとして使用する。
        """
        result = self.calculate(
            sale_price_usd=sale_price_usd,
            purchase_price_jpy=purchase_price_jpy,
            domestic_shipping_jpy=domestic_shipping_jpy,
            international_shipping_usd=international_shipping_usd,
            other_cost_jpy=other_cost_jpy,
        )

        if not result.profit_rate_ok:
            raise ProfitRateViolationError(
                actual_rate=result.gross_profit_rate,
                min_rate=self.min_profit_rate,
                sku=sku,
            )

        if not result.profit_amount_ok:
            raise ProfitAmountViolationError(
                actual_amount=result.gross_profit_jpy,
                min_amount=self.min_profit_amount,
                sku=sku,
            )

        return result
