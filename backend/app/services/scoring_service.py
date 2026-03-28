"""
リサーチスコアリングサービス
商品候補に対して複数の評価軸でスコアを計算し、出品優先度を決める。
スコアの根拠を必ず保存し、後から追跡できるようにする。

スコア設計:
- 各軸: 0〜10点
- 加重合計で 0〜100点
- 軸: 利益性・競争弱さ・売れやすさ・出品しやすさ・リスク低さ
"""

from dataclasses import dataclass, field

from app.core.logging_config import get_logger
from app.services.profit_calculator import ProfitCalculationResult

logger = get_logger(__name__)

# ─────────────────────────────────────
# 評価軸の重み（合計100）
# ─────────────────────────────────────
SCORE_WEIGHTS = {
    "profit": 35,         # 利益性（最重要）
    "competition": 20,    # 競争の弱さ
    "sellability": 20,    # 売れやすさ
    "listing_ease": 15,   # 出品しやすさ
    "risk": 10,           # リスク低さ
}

# リスクレベルのスコアマッピング
RISK_SCORE_MAP = {
    "low": 10,
    "medium": 5,
    "high": 0,
}


@dataclass
class ScoringInput:
    """スコアリング入力データ"""

    # ─── 利益計算結果（必須） ───
    profit_result: ProfitCalculationResult

    # ─── 市場・競合情報（任意: 未入力は中間スコアで補完） ───
    # TODO: 将来的にeBay Browse APIからの相場データを入力する
    competition_level: str = "medium"       # low / medium / high
    estimated_monthly_sales: int | None = None  # 月間推定販売数（未実装では仮値）

    # ─── 出品しやすさ ───
    has_clear_images: bool = False         # 明確な画像があるか
    has_model_number: bool = False         # 型番があるか
    has_brand_info: bool = False           # ブランド情報があるか
    category_is_clear: bool = False        # カテゴリが明確か
    description_complexity: str = "medium" # easy / medium / hard（説明文作成難易度）

    # ─── リスク ───
    return_risk: str = "low"           # low / medium / high
    authenticity_risk: str = "low"     # low / medium / high
    fragility_risk: str = "low"        # low / medium / high
    prohibited_risk: str = "low"       # low / medium / high

    # ─── 手動メモ ───
    notes: str = ""


@dataclass
class ScoringResult:
    """スコアリング結果"""

    # 各軸スコア（0〜10）
    profit_score: float = 0.0
    competition_score: float = 0.0
    sellability_score: float = 0.0
    listing_ease_score: float = 0.0
    risk_score: float = 0.0

    # 総合スコア（0〜100）
    total_score: float = 0.0

    # スコア根拠（DB保存用）
    score_basis: dict = field(default_factory=dict)

    # リスク詳細
    return_risk: str = "low"
    authenticity_risk: str = "low"
    fragility_risk: str = "low"
    prohibited_risk: str = "low"

    # 判定
    recommendation: str = "hold"  # buy / consider / hold / avoid
    recommendation_reason: str = ""


class ScoringService:
    """
    リサーチ候補スコアリングサービス。

    ★重要な設計注意★:
    現時点では市場データ（eBay Browse API等）は未接続のため、
    競争レベル・売れやすさは入力値をそのまま使用する。
    将来的にeBay APIからの実データで置き換えること。
    """

    def score(self, inp: ScoringInput) -> ScoringResult:
        """
        入力データをもとにスコアを計算する。
        スコアは0〜10の整数で評価し、加重合計で100点満点にする。
        """
        result = ScoringResult()

        # 各軸を評価
        result.profit_score, profit_basis = self._score_profit(inp.profit_result)
        result.competition_score, comp_basis = self._score_competition(inp.competition_level)
        result.sellability_score, sell_basis = self._score_sellability(inp)
        result.listing_ease_score, ease_basis = self._score_listing_ease(inp)
        result.risk_score, risk_basis = self._score_risk(inp)

        # リスク詳細を保存
        result.return_risk = inp.return_risk
        result.authenticity_risk = inp.authenticity_risk
        result.fragility_risk = inp.fragility_risk
        result.prohibited_risk = inp.prohibited_risk

        # 加重合計（各軸を0〜10 → 重みで合計100点）
        result.total_score = round(
            result.profit_score * SCORE_WEIGHTS["profit"] / 10
            + result.competition_score * SCORE_WEIGHTS["competition"] / 10
            + result.sellability_score * SCORE_WEIGHTS["sellability"] / 10
            + result.listing_ease_score * SCORE_WEIGHTS["listing_ease"] / 10
            + result.risk_score * SCORE_WEIGHTS["risk"] / 10,
            1,
        )

        # スコア根拠を保存
        result.score_basis = {
            "profit": profit_basis,
            "competition": comp_basis,
            "sellability": sell_basis,
            "listing_ease": ease_basis,
            "risk": risk_basis,
            "weights": SCORE_WEIGHTS,
        }

        # 推奨判定
        result.recommendation, result.recommendation_reason = self._recommend(
            result, inp.profit_result
        )

        logger.info(
            "スコアリング完了",
            total_score=result.total_score,
            recommendation=result.recommendation,
        )

        return result

    def _score_profit(self, profit: ProfitCalculationResult) -> tuple[float, dict]:
        """
        利益性スコア（0〜10）。
        利益率と利益額の両方を考慮する。
        """
        rate = profit.gross_profit_rate
        amount = profit.gross_profit_jpy

        # 利益率スコア（15%〜40%を0〜10にマッピング）
        if rate >= 0.40:
            rate_score = 10
        elif rate >= 0.30:
            rate_score = 8
        elif rate >= 0.20:
            rate_score = 6
        elif rate >= 0.15:
            rate_score = 4
        elif rate >= 0.10:
            rate_score = 2
        else:
            rate_score = 0

        # 利益額スコア（1000円〜10000円を0〜10にマッピング）
        if amount >= 10000:
            amount_score = 10
        elif amount >= 5000:
            amount_score = 8
        elif amount >= 3000:
            amount_score = 6
        elif amount >= 1500:
            amount_score = 4
        elif amount >= 500:
            amount_score = 2
        else:
            amount_score = 0

        # 利益率:利益額 = 6:4 で加重平均
        score = round(rate_score * 0.6 + amount_score * 0.4, 1)

        basis = {
            "profit_rate": f"{rate:.1%}",
            "profit_amount_jpy": int(amount),
            "rate_score": rate_score,
            "amount_score": amount_score,
            "final_score": score,
        }
        return score, basis

    def _score_competition(self, level: str) -> tuple[float, dict]:
        """
        競争の弱さスコア（競争が弱いほど高得点）。
        TODO: eBay Browse APIで実際の競合出品数を取得して自動判定する
        """
        score_map = {"low": 10, "medium": 5, "high": 2}
        score = float(score_map.get(level, 5))
        return score, {"competition_level": level, "note": "手動入力値（将来はAPI連携）"}

    def _score_sellability(self, inp: ScoringInput) -> tuple[float, dict]:
        """
        売れやすさスコア。
        月間販売数があれば使用、なければ競争レベルと商品状態から推定。
        TODO: eBay APIの sold items dataを活用する
        """
        if inp.estimated_monthly_sales is not None:
            monthly = inp.estimated_monthly_sales
            if monthly >= 20:
                score = 10.0
            elif monthly >= 10:
                score = 8.0
            elif monthly >= 5:
                score = 6.0
            elif monthly >= 2:
                score = 4.0
            elif monthly >= 1:
                score = 2.0
            else:
                score = 0.0
            basis = {"estimated_monthly_sales": monthly, "method": "monthly_sales"}
        else:
            # 月間販売数不明: 競争レベルの逆数から推定（暫定）
            fallback_map = {"low": 7.0, "medium": 5.0, "high": 3.0}
            score = fallback_map.get(inp.competition_level, 5.0)
            basis = {"method": "fallback_from_competition", "competition_level": inp.competition_level}

        return score, basis

    def _score_listing_ease(self, inp: ScoringInput) -> tuple[float, dict]:
        """
        出品しやすさスコア。
        情報の揃い具合・説明文作成難易度・カテゴリ明確さを評価する。
        """
        score = 5.0  # ベーススコア

        # 加点
        if inp.has_model_number:
            score += 1.5
        if inp.has_brand_info:
            score += 1.0
        if inp.has_clear_images:
            score += 1.0
        if inp.category_is_clear:
            score += 1.0

        # 説明文難易度による減点
        if inp.description_complexity == "hard":
            score -= 2.0
        elif inp.description_complexity == "easy":
            score += 0.5

        # 0〜10にクリップ
        score = max(0.0, min(10.0, score))

        basis = {
            "has_model_number": inp.has_model_number,
            "has_brand_info": inp.has_brand_info,
            "has_clear_images": inp.has_clear_images,
            "category_is_clear": inp.category_is_clear,
            "description_complexity": inp.description_complexity,
            "final_score": score,
        }
        return round(score, 1), basis

    def _score_risk(self, inp: ScoringInput) -> tuple[float, dict]:
        """
        リスク低さスコア（リスクが低いほど高得点）。
        全リスク軸の平均をとる。
        """
        risks = {
            "return_risk": inp.return_risk,
            "authenticity_risk": inp.authenticity_risk,
            "fragility_risk": inp.fragility_risk,
            "prohibited_risk": inp.prohibited_risk,
        }
        scores = [RISK_SCORE_MAP.get(v, 5) for v in risks.values()]
        avg_score = round(sum(scores) / len(scores), 1)

        # 禁止品リスクが高い場合は強制的に0点（出品不可）
        if inp.prohibited_risk == "high":
            avg_score = 0.0

        basis = {**risks, "individual_scores": dict(zip(risks.keys(), scores)), "avg_score": avg_score}
        return avg_score, basis

    def _recommend(
        self,
        result: ScoringResult,
        profit: ProfitCalculationResult,
    ) -> tuple[str, str]:
        """
        スコアをもとに推奨アクションを決定する。
        """
        # 禁止品リスクがある場合は即avoid
        if result.prohibited_risk == "high":
            return "avoid", "禁止品リスクがあるため出品不可"

        # 赤字の場合はhold
        if not profit.is_profitable:
            return "avoid", "利益が出ない価格設定"

        # 最低利益率を下回る場合はhold
        if not profit.profit_rate_ok:
            return "hold", f"最低利益率（{profit.min_profit_rate:.0%}）を下回っています"

        total = result.total_score
        if total >= 70:
            return "buy", f"総合スコア {total}点（高スコア）"
        elif total >= 50:
            return "consider", f"総合スコア {total}点（検討余地あり）"
        elif total >= 30:
            return "hold", f"総合スコア {total}点（慎重に判断）"
        else:
            return "avoid", f"総合スコア {total}点（低スコア）"
