# CLAUDE.md — Claude Code 向け作業ガイド

このファイルはClaude Codeがこのリポジトリで作業するときに参照するルールと文脈です。

## プロジェクト概要

日本からeBay販売を行うための半自動化ツール。
発送・梱包・倉庫作業以外の業務を自動化する社内管理ツール。

- **バックエンド**: FastAPI + Python 3.11 + SQLAlchemy 2.0 (async) + Celery
- **フロントエンド**: Next.js 14 (App Router) + TypeScript + Tailwind CSS
- **DB**: PostgreSQL 15（asyncpg）
- **キュー**: Redis 7 + Celery
- **AI**: Anthropic Claude API（出品文生成）
- **デプロイ先**: Railway（GitHub連携による自動デプロイ）

## ブランチ運用ルール

- `main` への直接コミット禁止
- 作業は必ず新しいブランチで行う
- ブランチ命名規則: `feature/xxx`, `fix/xxx`, `chore/xxx`

## 絶対にやってはいけないこと

- `.env` やシークレット情報をコミットしない
- `main` に直接 push しない
- eBay `production` 環境での操作は十分なテスト後にのみ行う
- AI生成文をそのまま自動公開しない（必ず人間が確認）

## ディレクトリ構成の要点

```
backend/
  app/
    core/         # 設定(config.py)・DB・ログ・例外・認証
    models/       # SQLAlchemyモデル（User, Product, ResearchCandidate, ListingDraft等）
    services/     # ビジネスロジック（profit_calculator, scoring_service, listing_generator等）
    clients/ebay/ # eBay API クライアント（Inventory, Offer）
    workers/      # Celeryタスク
    api/v1/       # FastAPIルーター（auth, research, listings, jobs）
  alembic/        # DBマイグレーション（async対応）
  create_admin.py # 管理者ユーザー初期作成スクリプト（初回のみ実行）

frontend/
  src/app/
    (main)/       # Sidebar付きレイアウトグループ（要認証）
      dashboard/  # ダッシュボード
      research/   # リサーチ候補一覧
      approvals/  # 承認待ち一覧
      listings/   # 出品下書き一覧
      jobs/       # ジョブ履歴
      audit/      # 監査ログ
      settings/   # 設定
    login/        # ログインページ（認証不要）
    page.tsx      # / → /dashboard リダイレクト
  src/lib/api.ts  # バックエンドAPIクライアント（JWT自動付与）
  src/components/
    layout/
      Sidebar.tsx    # ナビゲーションサイドバー
      AuthGuard.tsx  # 認証ガード（未認証 → /login リダイレクト）
    ui/
      StatusBadge.tsx # ステータス・スコア・利益率バッジ
```

## Railway デプロイ構成

Railwayプロジェクト内のサービス：
- `backend` — FastAPI（Dockerfile: `backend/Dockerfile`）
- `frontend` — Next.js（Dockerfile: `frontend/Dockerfile`）
- `celery-worker` — Celeryワーカー（backendと同じDockerイメージ、コマンド違い）
- `postgres` — RailwayのPostgreSQLプラグイン
- `redis` — RailwayのRedisプラグイン

## 環境変数の扱い

- ローカル開発: `backend/.env` または ルートの `.env`
- Railway: Railway環境変数UIで設定（絶対にコミットしない）
- テンプレート: `.env.example` を参照

## よくある作業パターン

### モデル変更後
```bash
cd backend
alembic revision --autogenerate -m "変更内容"
alembic upgrade head
```

### ローカル起動（Docker）
```bash
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

### ローカル起動（native）
```bash
# backend
cd backend && uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm run dev
```

## 安全装置

- `DRY_RUN_DEFAULT=true` がデフォルト（本番操作前に必ず確認）
- `REQUIRE_APPROVAL_FOR_PUBLISH=true` がデフォルト（AI生成文の自動公開禁止）
- 最低利益率15%・最低利益額¥500 を下回る価格設定はシステムでブロック

## HTTPBearer の挙動（重要）

FastAPIの `HTTPBearer` はデフォルトでAuthorizationヘッダー不在時に403を返す。
このプロジェクトでは `HTTPBearer(auto_error=False)` + 手動401を使用している（`backend/app/api/deps.py`）。
フロントエンド側では401と403の両方でログインリダイレクトを行う（`frontend/src/lib/api.ts`）。
