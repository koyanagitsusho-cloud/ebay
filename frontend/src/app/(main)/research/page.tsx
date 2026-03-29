"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { researchApi, type ResearchCandidate } from "@/lib/api";
import { StatusBadge, ProfitRateBadge, ScoreBadge } from "@/components/ui/StatusBadge";

export default function ResearchPage() {
  const [candidates, setCandidates] = useState<ResearchCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");

  useEffect(() => {
    loadCandidates();
  }, [statusFilter]);

  async function loadCandidates() {
    try {
      setLoading(true);
      const data = await researchApi.list({
        status: statusFilter || undefined,
        order_by_score: true,
      });
      setCandidates(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "読み込みエラー");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">リサーチ候補一覧</h1>
        <Link
          href="/research/new"
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium"
        >
          ＋ 候補を追加
        </Link>
      </div>

      {/* フィルター */}
      <div className="mb-4 flex gap-2">
        {["", "new", "scored", "promoted", "rejected"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded text-sm border transition-colors ${
              statusFilter === s
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {s === "" ? "全て" : s}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          エラー: {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">読み込み中...</div>
      ) : candidates.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          候補がありません。「候補を追加」から登録してください。
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-700">商品名</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">ブランド</th>
                <th className="px-4 py-3 text-right font-medium text-gray-700">仕入れ</th>
                <th className="px-4 py-3 text-right font-medium text-gray-700">目標価格(USD)</th>
                <th className="px-4 py-3 text-right font-medium text-gray-700">利益率</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">スコア</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">状態</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {candidates.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link href={`/research/${c.id}`} className="text-blue-600 hover:underline font-medium">
                      {c.title.length > 40 ? c.title.slice(0, 40) + "…" : c.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{c.brand || "-"}</td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {c.purchase_price_jpy != null
                      ? `¥${c.purchase_price_jpy.toLocaleString()}`
                      : "-"}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {c.target_sale_price_usd != null ? `$${c.target_sale_price_usd.toFixed(2)}` : "-"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ProfitRateBadge rate={c.estimated_profit_rate} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <ScoreBadge score={c.score_override ?? c.total_score} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Link
                      href={`/research/${c.id}`}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      詳細
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
