"use client";

import Link from "next/link";

/** ダッシュボードページ */
export default function DashboardPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">ダッシュボード</h1>

      {/* 環境バナー（sandboxの場合に表示） */}
      <div className="mb-6 p-3 bg-yellow-50 border border-yellow-300 rounded-lg flex items-center gap-3">
        <span className="text-yellow-600 font-bold text-sm">🧪 eBay Sandbox モード</span>
        <span className="text-yellow-700 text-sm">
          本番公開には settings 画面で Environment を production に変更してください
        </span>
      </div>

      {/* クイックアクションカード */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <QuickActionCard
          href="/research/new"
          title="商品候補を登録"
          description="仕入れ候補を追加して利益計算・スコアリング"
          icon="➕"
          color="blue"
        />
        <QuickActionCard
          href="/approvals"
          title="承認待ちを確認"
          description="出品下書きの承認・却下"
          icon="✅"
          color="yellow"
        />
        <QuickActionCard
          href="/listings"
          title="出品下書き一覧"
          description="AI生成した出品情報を編集・確認"
          icon="📝"
          color="green"
        />
      </div>

      {/* 重要ルール表示 */}
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <h2 className="text-sm font-bold text-red-800 mb-2">⚠️ 運用上の重要ルール</h2>
        <ul className="text-sm text-red-700 space-y-1">
          <li>• AI生成文は必ず人が確認・編集してから公開すること</li>
          <li>• 出品公開には reviewer 以上の権限と承認が必要</li>
          <li>• 本番操作前に必ず dry-run で動作確認すること</li>
          <li>• 最低利益率（15%）・最低利益額（¥500）を下回る価格は設定不可</li>
        </ul>
      </div>
    </div>
  );
}

function QuickActionCard({
  href,
  title,
  description,
  icon,
  color,
}: {
  href: string;
  title: string;
  description: string;
  icon: string;
  color: "blue" | "yellow" | "green";
}) {
  const colorClass = {
    blue: "border-blue-200 hover:bg-blue-50",
    yellow: "border-yellow-200 hover:bg-yellow-50",
    green: "border-green-200 hover:bg-green-50",
  }[color];

  return (
    <Link
      href={href}
      className={`block p-4 bg-white border-2 rounded-lg transition-colors ${colorClass}`}
    >
      <div className="flex items-center gap-3 mb-2">
        <span className="text-2xl">{icon}</span>
        <h3 className="font-bold text-gray-800">{title}</h3>
      </div>
      <p className="text-sm text-gray-600">{description}</p>
    </Link>
  );
}
