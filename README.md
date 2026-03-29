# eBay 販売業務自動化ツール

日本から eBay 販売を行うための、**発送以外の業務を自動化・半自動化**する社内管理ツールです。

---

## 目的

eBay 販売業務のうち以下を自動化・半自動化します。

| 機能 | 状態 |
|------|------|
| 商品候補の登録・利益計算・スコアリング | ✅ MVP実装済み |
| AI による出品情報生成（タイトル・説明文・item specifics） | ✅ MVP実装済み |
| 出品下書き保存・編集 | ✅ MVP実装済み |
| 手動承認フロー（承認なし公開禁止） | ✅ MVP実装済み |
| eBay Inventory/Offer API 経由の出品基盤 | ✅ MVP実装済み（sandbox対応） |
| 監査ログ・ジョブ管理 | ✅ MVP実装済み |
| セール候補抽出・販促実行 | 🔜 後続フェーズ |
| 自動値下げ・広告最適化 | 🔜 後続フェーズ |

**対象外**: 発送・梱包・倉庫作業・物理在庫ピッキング・真贋判定

---

## 設計思想

- **完全自動ではなく、安全な半自動**
- AI 生成文は必ず人が確認・編集してから公開
- 重要操作（公開・値下げ・セール）は必ず承認フローを通す
- 最低利益率（15%）・最低利益額（¥500）を下回る操作はシステムでブロック
- 本番操作前は必ず dry-run で確認

---

## 技術構成

```
フロントエンド: Next.js 14 (App Router, TypeScript, Tailwind CSS)
バックエンド:   FastAPI (Python 3.11, Pydantic v2)
ORM:           SQLAlchemy 2.0 (非同期) + Alembic
DB:            PostgreSQL 15
キュー/キャッシュ: Redis 7 + Celery
AI生成:        Anthropic Claude API
認証:          JWT (admin/reviewer/operator の 3ロール)
コンテナ:      Docker + docker-compose
```

---

## ディレクトリ構成

```
ebay-automation-tool/
├── backend/
│   ├── app/
│   │   ├── core/           # 設定・DB・ログ・例外・認証
│   │   ├── models/         # SQLAlchemyモデル
│   │   ├── schemas/        # Pydanticスキーマ（入出力DTO）
│   │   ├── repositories/   # DBアクセス層
│   │   ├── services/       # ビジネスロジック（利益計算・スコア・AI生成等）
│   │   ├── clients/
│   │   │   ├── ebay/       # eBay API クライアント（Inventory, Offer）
│   │   │   └── ai/         # Claude API クライアント
│   │   ├── workers/        # Celery非同期タスク
│   │   └── api/v1/         # FastAPI ルーター
│   ├── tests/              # pytest テストコード
│   ├── alembic/            # DBマイグレーション
│   ├── requirements.txt
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js App Router ページ
│   │   ├── components/     # UIコンポーネント
│   │   └── lib/            # APIクライアント・ユーティリティ
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example            # 環境変数テンプレート
└── README.md
```

---

## 前提条件

- Docker Desktop がインストール済み
- eBay Developer アカウント（sandbox 用アプリが作成済み）
- Anthropic API キー

---

## 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開いて以下を必ず設定してください：

| 変数 | 説明 |
|------|------|
| `SECRET_KEY` | JWTシークレットキー（`python -c "import secrets; print(secrets.token_hex(32))"` で生成） |
| `EBAY_CLIENT_ID` | eBay Developer App Client ID |
| `EBAY_CLIENT_SECRET` | eBay Developer App Client Secret |
| `EBAY_REFRESH_TOKEN` | eBay OAuth2 リフレッシュトークン |
| `ANTHROPIC_API_KEY` | Anthropic Claude API キー |

**最初は必ず `EBAY_ENVIRONMENT=sandbox` のまま使用すること**

---

## 開発環境の立ち上げ方

### Docker Compose（推奨）

```bash
# リポジトリをクローン後
cp .env.example .env
# .env を編集して各APIキーを設定

# コンテナ起動
docker-compose up -d

# DBマイグレーション実行
docker-compose exec backend alembic upgrade head

# 管理者ユーザーの初期作成（スクリプト）
docker-compose exec backend python create_admin.py
```

アクセス先：
- フロントエンド: http://localhost:3000
- バックエンド API: http://localhost:8000
- API ドキュメント（Swagger）: http://localhost:8000/docs

---

### ローカル（Docker なし）

#### バックエンド

```bash
cd backend

# 仮想環境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt

# 環境変数（backendディレクトリに .env を置くか、ルートの .env を参照）
cp ../.env.example .env

# DBマイグレーション
alembic upgrade head

# 起動
uvicorn app.main:app --reload --port 8000
```

#### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

---

## DBマイグレーション

```bash
# 最新まで適用
alembic upgrade head

# 現在の状態確認
alembic current

# マイグレーションファイル生成（モデル変更後）
alembic revision --autogenerate -m "変更内容の説明"

# 1つ戻す
alembic downgrade -1
```

---

## テスト実行

```bash
cd backend

# 全テスト実行（SQLiteインメモリDBを使用するため PostgreSQL 不要）
pytest

# 詳細表示
pytest -v

# 特定ファイル
pytest tests/test_profit_calculator.py

# カバレッジ付き
pytest --cov=app tests/
```

---

## eBay Sandbox の使い方

1. eBay Developer Portal (https://developer.ebay.com/) でアカウント作成
2. **Sandbox 用アプリ**を作成（Production アプリと別に作成すること）
3. OAuth2 同意フローを実行してリフレッシュトークンを取得
4. `.env` に `EBAY_ENVIRONMENT=sandbox` を設定
5. Sandbox でテスト後、`EBAY_ENVIRONMENT=production` に変更

**注意**: Sandbox と Production では API の挙動が一部異なります。Sandbox で十分テストしてから本番移行してください。

---

## ロールと権限

| 権限 | admin | reviewer | operator |
|------|-------|----------|---------|
| 監査ログ閲覧 | ✅ | - | - |
| 出品公開・承認 | ✅ | ✅ | - |
| セール実行 | ✅ | ✅ | - |
| 下書き作成・編集 | ✅ | ✅ | ✅ |

---

## 本番投入前チェック項目

- [ ] `EBAY_ENVIRONMENT=production` を確認
- [ ] `DRY_RUN_DEFAULT=false` を意図的に設定したか確認
- [ ] `SECRET_KEY` に十分なランダム値を設定済み
- [ ] eBay 本番 API の認証情報が正しく設定済み
- [ ] `REQUIRE_APPROVAL_FOR_PUBLISH=true` が設定済み
- [ ] 最低利益率・最低利益額のデフォルト値を確認
- [ ] 除外SKU・除外ブランドの設定を確認
- [ ] バックアップ体制を確認
- [ ] Sandbox で一通りのフローをテスト済み

---

## 今後の拡張ポイント

1. **セール・販促機能**: 売れ行き・在庫期間での自動抽出 + 承認実行
2. **自動値下げ**: 最低利益率を守りつつの段階的値下げ
3. **eBay Browse API 連携**: 競合価格・売れ行きデータの自動取得
4. **為替レート自動更新**: 外部API連携（Open Exchange Rates等）
5. **多マーケットプレイス**: EBAY_JP, EBAY_GB 等への対応
6. **分析ダッシュボード**: 売上・利益・在庫の可視化
7. **完全自動公開**: 信頼度の高い商品カテゴリに限定した自動公開

---

## 既知の制約・仮実装

- **eBay手数料率**: カテゴリにより実際には異なるが、現在は一律13.25%で計算
- **為替レート**: 設定値の固定値（手動更新が必要）
- **Celeryジョブの公開ロジック**: `listing_tasks.py`のpublish_to_ebayは一部未実装（API層に実装済み）
- **承認APIの approval_id**: フロントエンドの承認画面でapproval_idの取得が未実装（TODOコメントあり）
- **eBay sandbox と production の動作差異**: sandbox で十分確認すること

---

## 注意事項

- このツールは **発送・梱包・倉庫作業** には対応しません
- AI生成文を **そのまま自動公開する機能は意図的に実装していません**
- **禁止品リスクが高い商品** のスコアリングはシステムが補助するだけで、最終判断は人間が行うこと
- eBay API の利用規約を必ず確認してください

---

*このツールは個人・小規模事業の eBay 販売業務効率化を目的としています。*
