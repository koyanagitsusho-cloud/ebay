"""
リサーチAPI統合テスト
エンドポイントの動作・バリデーション・認証を検証する。
"""

import pytest


class TestResearchCandidateAPI:
    """リサーチ候補APIのテスト"""

    @pytest.mark.asyncio
    async def test_create_candidate(self, client, operator_user):
        """商品候補を正常に作成できること"""
        # まず認証トークンを取得
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": operator_user.email, "password": "test_password_123"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]

        # 候補作成
        res = await client.post(
            "/api/v1/research/",
            json={
                "title": "Test Toy Figure",
                "brand": "BANDAI",
                "model_number": "TF-001",
                "condition": "USED_GOOD",
                "purchase_price_jpy": 2000.0,
                "domestic_shipping_jpy": 300.0,
                "international_shipping_usd": 5.0,
                "target_sale_price_usd": 30.0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "Test Toy Figure"
        assert data["brand"] == "BANDAI"
        assert data["status"] == "new"
        # 利益計算が自動実行されていること
        assert data["estimated_profit_jpy"] is not None

    @pytest.mark.asyncio
    async def test_create_candidate_invalid_condition(self, client, operator_user):
        """不正な状態値はバリデーションエラーになること"""
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": operator_user.email, "password": "test_password_123"},
        )
        token = login_res.json()["access_token"]

        res = await client.post(
            "/api/v1/research/",
            json={
                "title": "Test Item",
                "condition": "INVALID_CONDITION",  # 不正な値
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_list_candidates_requires_auth(self, client):
        """認証なしでは一覧取得できないこと"""
        res = await client.get("/api/v1/research/")
        assert res.status_code == 403  # HTTPBearer は認証ヘッダーなしで403

    @pytest.mark.asyncio
    async def test_calculate_profit_endpoint(self, client, operator_user, db_session):
        """利益計算エンドポイントが正しく動作すること"""
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": operator_user.email, "password": "test_password_123"},
        )
        token = login_res.json()["access_token"]

        # 候補を作成
        create_res = await client.post(
            "/api/v1/research/",
            json={
                "title": "Profit Test Item",
                "purchase_price_jpy": 1000.0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        candidate_id = create_res.json()["id"]

        # 利益計算
        calc_res = await client.post(
            f"/api/v1/research/{candidate_id}/calculate-profit?target_price_usd=25.0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert calc_res.status_code == 200
        data = calc_res.json()
        assert "gross_profit_jpy" in data
        assert "gross_profit_rate" in data
        assert data["sale_price_usd"] == 25.0

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """ヘルスチェックエンドポイントが正常に応答すること（認証不要）"""
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
