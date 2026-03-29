# Railway 環境変数設定一覧

Railway UIの各サービスの「Variables」タブで設定してください。
`.env` ファイルをコミットしたりアップロードしたりしないこと。

---

## backend サービス（FastAPI）

| 変数名 | 値の例 / 設定方法 | 必須 |
|--------|-----------------|------|
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` で生成 | ✅ |
| `DATABASE_URL` | Railwayの PostgreSQL プラグインから自動注入（`${{Postgres.DATABASE_URL}}`） | ✅ |
| `REDIS_URL` | Railwayの Redis プラグインから自動注入（`${{Redis.REDIS_URL}}`） | ✅ |
| `CELERY_RESULT_BACKEND` | `${{Redis.REDIS_URL}}/1` のように設定 | ✅ |
| `ENVIRONMENT` | `production` | ✅ |
| `ANTHROPIC_API_KEY` | Anthropic Console で取得 | ✅ |
| `EBAY_ENVIRONMENT` | `sandbox`（本番移行時に `production`） | ✅ |
| `EBAY_CLIENT_ID` | eBay Developer Portal で取得 | ✅ |
| `EBAY_CLIENT_SECRET` | eBay Developer Portal で取得 | ✅ |
| `EBAY_REFRESH_TOKEN` | eBay OAuth同意フローで取得 | ✅ |
| `CORS_ORIGINS` | `["https://your-frontend.up.railway.app"]` | ✅ |
| `DRY_RUN_DEFAULT` | `true`（本番移行準備が整うまで） | 推奨 |
| `REQUIRE_APPROVAL_FOR_PUBLISH` | `true` | 推奨 |
| `LOG_LEVEL` | `INFO` | - |
| `DEBUG` | `false` | - |

### Railway変数参照の書き方（Service Reference）
```
DATABASE_URL = ${{Postgres.DATABASE_URL}}
REDIS_URL    = ${{Redis.REDIS_URL}}
```
Railway UIの Variables > Add Variable で `${{サービス名.変数名}}` と入力すれば自動解決されます。

---

## frontend サービス（Next.js）

| 変数名 | 値の例 | 必須 |
|--------|--------|------|
| `NEXT_PUBLIC_API_URL` | `https://your-backend.up.railway.app/api/v1` | ✅ |
| `NEXT_PUBLIC_APP_URL` | `https://your-frontend.up.railway.app` | ✅ |

**注意**: `NEXT_PUBLIC_` プレフィックスの変数はビルド時に埋め込まれます。
変更後は必ず **Redeploy** が必要です。

---

## celery-worker サービス

backendサービスと同じ変数をすべて設定してください（`CORS_ORIGINS` は不要）。

| 追加設定 | 値 |
|---------|---|
| `C_FORCE_ROOT` | `true`（Railwayはrootで動くためCeleryの警告を抑制） |

---

## Railway PostgreSQL プラグイン

Railwayがプロビジョニング時に自動生成します。
バックエンドには `DATABASE_URL` として自動注入可能です（Service Reference）。

**初回マイグレーション実行方法:**
```
# Railway CLI を使う場合
railway run --service backend alembic upgrade head

# または Railway UI の「Run Command」から
alembic upgrade head
```

---

## Railway Redis プラグイン

Railwayがプロビジョニング時に自動生成します。
`REDIS_URL` として自動注入可能です（Service Reference）。
