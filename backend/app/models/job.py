"""
ジョブ・監査ログモデル
非同期ジョブの状態管理と、全操作の監査証跡を保持する。
"""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    非同期ジョブ管理テーブル。
    Celeryタスクと1:1で対応し、実行状態・結果・エラーを追跡する。
    手動再実行・キャンセルも可能。
    """

    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
        comment="ジョブ種別: ai_generate / ebay_publish / price_update / score_recalc / sale_extract 等",
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(200),
        comment="Celeryのtask_id（結果参照・キャンセルに使用）",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="queued",
        nullable=False,
        index=True,
        comment="状態: queued / running / success / failed / cancelled",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=5,
        comment="優先度（1=最高, 10=最低）",
    )

    # ─── 入出力 ───
    payload: Mapped[dict | None] = mapped_column(JSONB, comment="ジョブ入力パラメータ")
    result: Mapped[dict | None] = mapped_column(JSONB, comment="ジョブ実行結果")
    error_message: Mapped[str | None] = mapped_column(Text, comment="失敗時のエラーメッセージ")
    error_traceback: Mapped[str | None] = mapped_column(Text, comment="失敗時のスタックトレース")

    # ─── リトライ ───
    retry_count: Mapped[int] = mapped_column(Integer, default=0, comment="現在のリトライ回数")
    max_retries: Mapped[int] = mapped_column(Integer, default=3, comment="最大リトライ回数")
    next_retry_at: Mapped[str | None] = mapped_column(comment="次回リトライ予定日時")

    # ─── 実行時刻 ───
    started_at: Mapped[str | None] = mapped_column(comment="ジョブ開始日時")
    finished_at: Mapped[str | None] = mapped_column(comment="ジョブ完了日時")
    duration_seconds: Mapped[float | None] = mapped_column(Float, comment="実行時間（秒）")

    # ─── 実行コンテキスト ───
    triggered_by: Mapped[str | None] = mapped_column(String(100), comment="トリガー元（ユーザーID or system）")
    related_resource_type: Mapped[str | None] = mapped_column(String(50), comment="関連リソース種別")
    related_resource_id: Mapped[str | None] = mapped_column(String(100), comment="関連リソースID")
    is_dry_run: Mapped[bool] = mapped_column(
        default=True,
        comment="dry-runフラグ（Trueなら副作用なし）",
    )

    # ─── リレーション ───
    logs: Mapped[list["JobLog"]] = relationship(
        "JobLog",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Job {self.job_type} ({self.status})>"


class JobLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    ジョブの実行ログ（ステップごとの詳細）。
    ジョブの進捗・中間結果を追跡する。
    """

    __tablename__ = "job_logs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    log_level: Mapped[str] = mapped_column(
        String(10), default="INFO",
        comment="ログレベル: DEBUG / INFO / WARNING / ERROR",
    )
    message: Mapped[str] = mapped_column(Text, comment="ログメッセージ")
    data: Mapped[dict | None] = mapped_column(JSONB, comment="追加データ（JSON）")
    step: Mapped[str | None] = mapped_column(String(100), comment="実行ステップ名")

    # ─── リレーション ───
    job: Mapped["Job"] = relationship("Job", back_populates="logs")


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    監査ログ。
    誰が、いつ、何を、どのような状態から変更したかを全て記録する。
    削除禁止（論理削除のみ許容）。
    重要: このテーブルのレコードは絶対に削除・改竄しない。
    """

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="操作者のユーザーID（システム操作の場合はNULL）",
    )

    # ─── 操作内容 ───
    action: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
        comment="操作種別: product.create / listing.submit_for_review / listing.publish 等",
    )
    resource_type: Mapped[str] = mapped_column(String(50), comment="操作対象リソース種別")
    resource_id: Mapped[str | None] = mapped_column(String(100), comment="操作対象リソースID")

    # ─── 変更内容 ───
    before_state: Mapped[dict | None] = mapped_column(JSONB, comment="変更前の状態")
    after_state: Mapped[dict | None] = mapped_column(JSONB, comment="変更後の状態")
    diff: Mapped[dict | None] = mapped_column(JSONB, comment="差分（変更箇所のみ）")
    meta_info: Mapped[dict | None] = mapped_column(JSONB, comment="補足情報（IPアドレス等）")

    # ─── 結果 ───
    result: Mapped[str] = mapped_column(
        String(20), default="success",
        comment="結果: success / failed / blocked",
    )
    error_message: Mapped[str | None] = mapped_column(Text, comment="失敗時のエラー内容")

    # ─── リレーション ───
    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.resource_type}/{self.resource_id}>"


class ApiCallLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    外部API呼び出しログ。
    eBay API・AI API等の全呼び出しを記録する。
    エラー追跡とリトライ管理に使用する。
    注意: レスポンスボディの全文保存はしない（シークレット混入防止・容量削減）。
    """

    __tablename__ = "api_call_logs"

    api_name: Mapped[str] = mapped_column(
        String(50), comment="API名: ebay_inventory / ebay_offer / anthropic 等"
    )
    endpoint: Mapped[str] = mapped_column(String(300), comment="APIエンドポイントURL")
    method: Mapped[str] = mapped_column(String(10), comment="HTTPメソッド: GET / POST / PUT / DELETE")
    request_summary: Mapped[dict | None] = mapped_column(
        JSONB, comment="リクエスト要点（シークレットは除外してから保存）"
    )
    response_status: Mapped[int | None] = mapped_column(comment="HTTPステータスコード")
    response_summary: Mapped[dict | None] = mapped_column(
        JSONB, comment="レスポンス要点（全文は保存しない）"
    )
    duration_ms: Mapped[int | None] = mapped_column(comment="応答時間（ミリ秒）")
    success: Mapped[bool] = mapped_column(default=False)
    error_code: Mapped[str | None] = mapped_column(String(50), comment="エラーコード")
    error_message: Mapped[str | None] = mapped_column(Text, comment="エラーメッセージ")
    retry_attempt: Mapped[int] = mapped_column(Integer, default=0, comment="リトライ試行番号")
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        comment="関連ジョブID",
    )


class Setting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    アプリケーション設定テーブル。
    UIから変更可能な動的設定値を管理する。
    .envの設定は起動時固定、このテーブルの設定はDB経由で動的変更可能。
    重要: APIキー等のシークレットはここに保存しない（.envで管理）。
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True, comment="設定キー"
    )
    value: Mapped[str] = mapped_column(Text, comment="設定値（JSON文字列）")
    value_type: Mapped[str] = mapped_column(
        String(20), default="string",
        comment="値の型: string / number / boolean / json_list / json_object"
    )
    description: Mapped[str | None] = mapped_column(Text, comment="設定説明（管理画面表示用）")
    category: Mapped[str | None] = mapped_column(String(50), comment="設定カテゴリ（UI分類用）")
    is_sensitive: Mapped[bool] = mapped_column(
        default=False, comment="機密フラグ（TrueならUI表示を隠す）"
    )
    is_editable_on_ui: Mapped[bool] = mapped_column(
        default=True, comment="UI編集許可フラグ"
    )
