"""
出品情報生成サービスのテスト
バリデーション・禁止語チェック・タイトル長チェックを検証する。
AI APIは使用せず、バリデーションロジックのみをテストする。

注意: AI生成機能のE2Eテストには実際のANTHROPIC_API_KEYが必要。
本テストではモックを使用してAPIを呼ばない。
"""

import pytest

from app.services.listing_generator import EBAY_TITLE_MAX_LENGTH, ListingGeneratorService


class TestTitleValidation:
    """タイトルバリデーションのテスト"""

    def setup_method(self):
        """
        ListingGeneratorServiceのインスタンス作成。
        __init__でAPIキーチェックがあるため、APIキーが不要な
        バリデーションメソッドのみをテストする。
        """
        # APIキーなしでバリデーションメソッドをテストするための工夫
        # validate_title はクラスメソッドでないため、インスタンスが必要
        # → テスト用にAPIキーチェックをスキップする方法:
        #   実際の運用ではAPIキーを環境変数に設定すること
        import os
        os.environ["ANTHROPIC_API_KEY"] = "test_dummy_key"
        self.service = ListingGeneratorService.__new__(ListingGeneratorService)
        self.service._prohibited_words = [
            "guaranteed", "100% authentic", "mint", "perfect",
            "brand new", "replica", "fake", "copy",
        ]

    def test_title_within_limit_passes(self):
        """80文字以内のタイトルはエラーなし"""
        title = "A" * 80
        errors = self.service.validate_title(title)
        assert len(errors) == 0

    def test_title_over_limit_fails(self):
        """81文字のタイトルはエラーになること"""
        title = "A" * 81
        errors = self.service.validate_title(title)
        assert len(errors) == 1
        assert "81" in errors[0]

    def test_prohibited_word_detected(self):
        """禁止語を含むタイトルはエラーになること"""
        title = "Vintage toy - guaranteed authentic condition"
        errors = self.service.validate_title(title)
        assert any("禁止語" in e for e in errors)

    def test_multiple_errors_returned(self):
        """複数のエラーが同時に返ること（タイトル長 + 禁止語）"""
        title = "A" * 81 + " guaranteed"  # 長さ超過 + 禁止語
        errors = self.service.validate_title(title)
        assert len(errors) >= 2

    def test_clean_title_has_no_errors(self):
        """問題のないタイトルはエラーなし"""
        title = "Vintage Japanese Robot Figure Collection 1980s Excellent Used"
        errors = self.service.validate_title(title)
        assert len(errors) == 0

    def test_case_insensitive_prohibited_check(self):
        """禁止語チェックは大文字小文字を区別しないこと"""
        title = "GUARANTEED authentic item"
        errors = self.service.validate_title(title)
        assert any("禁止語" in e for e in errors)


class TestProhibitedWordCheck:
    """禁止語検出のテスト"""

    def setup_method(self):
        self.service = ListingGeneratorService.__new__(ListingGeneratorService)
        self.service._prohibited_words = ["replica", "fake", "copy", "guaranteed"]

    def test_no_prohibited_words_returns_empty(self):
        """禁止語なしは空リストを返すこと"""
        result = self.service._check_prohibited_words("This is a clean description.")
        assert result == []

    def test_prohibited_word_found(self):
        """禁止語が見つかること"""
        result = self.service._check_prohibited_words("This is a replica item.")
        assert "replica" in result

    def test_multiple_prohibited_words_found(self):
        """複数の禁止語が全て検出されること"""
        result = self.service._check_prohibited_words("This fake replica is guaranteed.")
        assert "fake" in result
        assert "replica" in result
        assert "guaranteed" in result
