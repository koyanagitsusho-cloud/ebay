"""
出品情報生成サービス
Anthropic Claude APIを使って、商品データからeBay出品情報を生成する。
生成結果は必ず人が確認・編集できる形で保存し、自動公開しない。

重要な設計方針:
- AI生成文はあくまで「候補」であり、最終公開前に必ず人が確認する
- 禁止語チェック・必須項目チェックは生成後に自動実行する
- タイトル文字数制限（80文字）、誇大表現禁止はプロンプトで制御する
"""

import json
from typing import Any

import anthropic

from app.core.config import settings
from app.core.exceptions import AiGenerationError, ProhibitedWordError, ValidationError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────
# デフォルト禁止語リスト（最低限）
# 実際の運用では DB の listing_rules テーブルから取得すること
# ─────────────────────────────────────
DEFAULT_PROHIBITED_WORDS = [
    "guaranteed",
    "100% authentic",
    "mint",          # 誤用されやすい
    "perfect",       # 誇大表現
    "brand new",     # 中古品への誤適用
    "replica",
    "fake",
    "copy",
]

# ─────────────────────────────────────
# eBayタイトル制限
# ─────────────────────────────────────
EBAY_TITLE_MAX_LENGTH = 80


class ListingGeneratorInput:
    """
    出品情報生成の入力データ。
    全てのフィールドは任意だが、多いほど生成品質が上がる。
    """

    def __init__(
        self,
        product_title: str,
        brand: str | None = None,
        model_number: str | None = None,
        condition: str = "USED_GOOD",
        features: str | None = None,
        included_items: str | None = None,
        missing_items: str | None = None,
        scratches_or_stains: str | None = None,
        operation_check: str | None = None,
        size_info: str | None = None,
        color: str | None = None,
        material: str | None = None,
        compatible_models: str | None = None,
        category_hint: str | None = None,
        image_notes: str | None = None,
        cautions: str | None = None,
        extra_info: str | None = None,
    ) -> None:
        self.product_title = product_title
        self.brand = brand
        self.model_number = model_number
        self.condition = condition
        self.features = features
        self.included_items = included_items
        self.missing_items = missing_items
        self.scratches_or_stains = scratches_or_stains
        self.operation_check = operation_check
        self.size_info = size_info
        self.color = color
        self.material = material
        self.compatible_models = compatible_models
        self.category_hint = category_hint
        self.image_notes = image_notes
        self.cautions = cautions
        self.extra_info = extra_info

    def to_dict(self) -> dict[str, Any]:
        """入力データを辞書化（ログ・DB保存用）"""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class ListingGeneratorOutput:
    """出品情報生成結果"""

    def __init__(
        self,
        title_candidates: list[str],
        description: str,
        item_specifics: dict[str, str],
        condition_description: str,
        return_policy_text: str,
        warnings: list[str],
        missing_fields: list[str],
        is_valid: bool,
        model_used: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        self.title_candidates = title_candidates
        self.description = description
        self.item_specifics = item_specifics
        self.condition_description = condition_description
        self.return_policy_text = return_policy_text
        self.warnings = warnings
        self.missing_fields = missing_fields
        self.is_valid = is_valid
        self.model_used = model_used
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class ListingGeneratorService:
    """
    eBay出品情報生成サービス。
    Claude APIを使用してタイトル・説明文・item specificsを生成する。

    依存: Anthropic Claude API（ANTHROPIC_API_KEY設定必須）
    """

    def __init__(
        self,
        prohibited_words: list[str] | None = None,
    ) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise AiGenerationError(
                "ANTHROPIC_API_KEY が設定されていません。.envファイルを確認してください"
            )
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._prohibited_words = prohibited_words or DEFAULT_PROHIBITED_WORDS

    async def generate(
        self,
        inp: ListingGeneratorInput,
    ) -> ListingGeneratorOutput:
        """
        出品情報を生成する。
        生成後に禁止語チェック・必須項目チェックを自動実行する。
        """
        logger.info("出品情報生成開始", product_title=inp.product_title)

        # プロンプト構築
        prompt = self._build_prompt(inp)

        # Claude API呼び出し
        try:
            response = self._client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
        except anthropic.APIError as e:
            logger.error("Claude API呼び出しエラー", error=str(e))
            raise AiGenerationError(f"Claude API エラー: {e}") from e

        # レスポンスをパース
        raw_text = response.content[0].text
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as e:
            logger.error("Claude APIレスポンスJSONパースエラー", raw_text=raw_text[:200])
            raise AiGenerationError(f"生成結果のJSON解析に失敗: {e}") from e

        # 抽出
        title_candidates: list[str] = parsed.get("title_candidates", [])
        description: str = parsed.get("description", "")
        item_specifics: dict = parsed.get("item_specifics", {})
        condition_description: str = parsed.get("condition_description", "")
        return_policy_text: str = parsed.get("return_policy_text", "")

        # バリデーション
        warnings: list[str] = []
        missing_fields: list[str] = []

        # タイトル長チェック
        for i, title in enumerate(title_candidates):
            if len(title) > EBAY_TITLE_MAX_LENGTH:
                warnings.append(
                    f"タイトル候補{i+1}が{len(title)}文字（上限{EBAY_TITLE_MAX_LENGTH}文字）"
                )

        # 禁止語チェック
        prohibited_found = self._check_prohibited_words(
            description + " " + " ".join(title_candidates)
        )
        if prohibited_found:
            warnings.append(f"禁止語検出: {', '.join(prohibited_found)}")

        # 必須項目チェック
        if not title_candidates:
            missing_fields.append("タイトル候補")
        if not description:
            missing_fields.append("商品説明文")
        if not condition_description:
            missing_fields.append("状態説明文")

        is_valid = len(missing_fields) == 0 and len(prohibited_found) == 0

        logger.info(
            "出品情報生成完了",
            title_count=len(title_candidates),
            warnings=len(warnings),
            is_valid=is_valid,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        )

        return ListingGeneratorOutput(
            title_candidates=title_candidates,
            description=description,
            item_specifics=item_specifics,
            condition_description=condition_description,
            return_policy_text=return_policy_text,
            warnings=warnings,
            missing_fields=missing_fields,
            is_valid=is_valid,
            model_used=settings.CLAUDE_MODEL,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        )

    def _build_prompt(self, inp: ListingGeneratorInput) -> str:
        """
        eBay出品情報生成プロンプトを構築する。
        出力はJSON形式で要求する（パースしやすさ優先）。
        """
        # 商品情報をテキストで整形
        product_info_parts = [f"商品名: {inp.product_title}"]
        if inp.brand:
            product_info_parts.append(f"ブランド: {inp.brand}")
        if inp.model_number:
            product_info_parts.append(f"型番: {inp.model_number}")
        if inp.condition:
            product_info_parts.append(f"状態: {inp.condition}")
        if inp.features:
            product_info_parts.append(f"特徴: {inp.features}")
        if inp.included_items:
            product_info_parts.append(f"付属品: {inp.included_items}")
        if inp.missing_items:
            product_info_parts.append(f"欠品: {inp.missing_items}")
        if inp.scratches_or_stains:
            product_info_parts.append(f"キズ・汚れ: {inp.scratches_or_stains}")
        if inp.operation_check:
            product_info_parts.append(f"動作確認: {inp.operation_check}")
        if inp.size_info:
            product_info_parts.append(f"サイズ: {inp.size_info}")
        if inp.color:
            product_info_parts.append(f"色: {inp.color}")
        if inp.material:
            product_info_parts.append(f"素材: {inp.material}")
        if inp.compatible_models:
            product_info_parts.append(f"対応機種: {inp.compatible_models}")
        if inp.category_hint:
            product_info_parts.append(f"カテゴリ: {inp.category_hint}")
        if inp.cautions:
            product_info_parts.append(f"注意点: {inp.cautions}")
        if inp.extra_info:
            product_info_parts.append(f"その他: {inp.extra_info}")

        product_info = "\n".join(product_info_parts)

        prompt = f"""You are an expert eBay seller from Japan specializing in creating high-quality, accurate product listings.

## 商品情報
{product_info}

## 指示
以下の出品情報をJSON形式で生成してください。

### 制約と注意事項
1. タイトルは必ず80文字以内にすること（eBay制限）
2. SEOを意識した重要キーワードをタイトルに含めること
3. 誇大表現・虚偽表現は絶対に使用しないこと
4. 中古品の場合、状態を正直に記載すること
5. 禁止語（replica, fake, copy, guaranteed perfect等）を使用しないこと
6. 英語で記載すること（item specificsも英語）
7. 状態説明は具体的かつ正確に
8. 返品ポリシー文は短く標準的なものにすること

### 出力JSON形式
{{
  "title_candidates": [
    "候補1（最もSEO最適化）",
    "候補2（代替キーワード重視）",
    "候補3（簡潔版）"
  ],
  "description": "HTMLまたはプレーンテキストの商品説明文。状態・付属品・注意事項を含める",
  "item_specifics": {{
    "Brand": "ブランド名",
    "Model": "型番",
    "Type": "商品タイプ",
    "Condition": "状態（詳細）"
  }},
  "condition_description": "状態の詳細説明（100〜300文字程度の英文）",
  "return_policy_text": "返品ポリシー文（例: Returns accepted within 30 days）"
}}

JSONのみ出力してください。説明文は不要です。"""

        return prompt

    def _check_prohibited_words(self, text: str) -> list[str]:
        """テキスト内の禁止語を検出して返す"""
        text_lower = text.lower()
        found = [word for word in self._prohibited_words if word.lower() in text_lower]
        return found

    def validate_title(self, title: str) -> list[str]:
        """タイトルのバリデーション（単体呼び出し用）"""
        errors = []
        if len(title) > EBAY_TITLE_MAX_LENGTH:
            errors.append(f"タイトルが{len(title)}文字（上限{EBAY_TITLE_MAX_LENGTH}文字）")
        prohibited = self._check_prohibited_words(title)
        if prohibited:
            errors.append(f"禁止語: {', '.join(prohibited)}")
        return errors
