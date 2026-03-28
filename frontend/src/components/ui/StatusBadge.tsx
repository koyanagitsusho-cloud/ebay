"use client";

/** ステータスバッジコンポーネント */
const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  // リサーチ候補
  new: { label: "新規", className: "bg-gray-100 text-gray-700" },
  scored: { label: "スコア済", className: "bg-blue-100 text-blue-700" },
  promoted: { label: "出品候補", className: "bg-green-100 text-green-700" },
  rejected: { label: "却下", className: "bg-red-100 text-red-700" },
  archived: { label: "アーカイブ", className: "bg-gray-200 text-gray-500" },

  // 出品下書き
  draft: { label: "下書き", className: "bg-gray-100 text-gray-700" },
  pending_review: { label: "承認待ち", className: "bg-yellow-100 text-yellow-700" },
  approved: { label: "承認済", className: "bg-green-100 text-green-700" },
  published: { label: "公開済", className: "bg-blue-100 text-blue-700" },
  ended: { label: "終了", className: "bg-gray-200 text-gray-500" },

  // ジョブ
  queued: { label: "待機中", className: "bg-gray-100 text-gray-700" },
  running: { label: "実行中", className: "bg-yellow-100 text-yellow-700" },
  success: { label: "成功", className: "bg-green-100 text-green-700" },
  failed: { label: "失敗", className: "bg-red-100 text-red-700" },
  cancelled: { label: "キャンセル", className: "bg-gray-200 text-gray-500" },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || { label: status, className: "bg-gray-100 text-gray-700" };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.className} ${className}`}
    >
      {config.label}
    </span>
  );
}

/** 利益率インジケーター */
export function ProfitRateBadge({ rate }: { rate: number | null }) {
  if (rate === null) return <span className="text-gray-400 text-sm">-</span>;

  const pct = (rate * 100).toFixed(1);
  let className = "text-gray-700";
  if (rate >= 0.3) className = "text-green-700 font-bold";
  else if (rate >= 0.15) className = "text-blue-700";
  else if (rate > 0) className = "text-yellow-700";
  else className = "text-red-700 font-bold";

  return <span className={`text-sm ${className}`}>{pct}%</span>;
}

/** スコアインジケーター */
export function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-400 text-sm">-</span>;

  let className = "bg-gray-100 text-gray-700";
  if (score >= 70) className = "bg-green-100 text-green-700";
  else if (score >= 50) className = "bg-blue-100 text-blue-700";
  else if (score >= 30) className = "bg-yellow-100 text-yellow-700";
  else className = "bg-red-100 text-red-700";

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${className}`}>
      {score.toFixed(1)}点
    </span>
  );
}

/** dry-run / 本番 バッジ */
export function EnvBadge({ isDryRun, environment }: { isDryRun: boolean; environment?: string }) {
  if (isDryRun) {
    return (
      <span className="badge-dry-run">
        🧪 DRY-RUN
      </span>
    );
  }
  return (
    <span className="badge-production">
      🔴 本番 {environment && `(${environment})`}
    </span>
  );
}
