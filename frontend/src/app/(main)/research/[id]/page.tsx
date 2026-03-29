"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { researchApi, type ResearchCandidate } from "@/lib/api";
import { StatusBadge, ProfitRateBadge, ScoreBadge } from "@/components/ui/StatusBadge";

export default function ResearchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [candidate, setCandidate] = useState<ResearchCandidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scoring, setScoring] = useState(false);
  const [promoting, setPromoting] = useState(false);

  useEffect(() => {
    load();
  }, [id]);

  async function load() {
    try {
      setLoading(true);
      const data = await researchApi.get(id);
      setCandidate(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "読み込みエラー");
    } finally {
      setLoading(false);
    }
  }

  async function handleScore() {
    if (!confirm("スコアリングを実行しますか？")) return;
    try {
      setScoring(true);
      const updated = await researchApi.runScoring(id);
      setCandidate(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "スコアリングエラー");
    } finally {
      setScoring(false);
    }
  }

  async function handleStatusChange(newStatus: string) {
    try {
      const updated = await researchApi.update(id, { status: newStatus });
      setCandidate(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "更新エラー");
    }
  }

  if (loading) return <div className="p-6 text-gray-500">読み込み中...</div>;
  if (error) return <div className="p-6 text-red-600">{error}</div>;
  if (!candidate) return <div className="p-6 text-gray-500">見つかりません</div>;

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/research")}
          className="text-gray-500 hover:text-gray-700 text-sm"
        >
          ← 一覧に戻る
        </button>
      </div>

      <div className="flex justify-between items-start mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex-1 mr-4">{candidate.title}</h1>
        <StatusBadge status={candidate.status} />
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* 基本情報 */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
        <h2 className="font-bold text-gray-800 mb-3">基本情報</h2>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div>
            <dt className="text-gray-500">ブランド</dt>
            <dd className="text-gray-800">{candidate.brand || "-"}</dd>
          </div>
          <div>
            <dt className="text-gray-500">型番</dt>
            <dd className="text-gray-800">{candidate.model_number || "-"}</dd>
          </div>
          <div>
            <dt className="text-gray-500">コンディション</dt>
            <dd className="text-gray-800">{candidate.condition}</dd>
          </div>
          <div>
            <dt className="text-gray-500">登録日</dt>
            <dd className="text-gray-800">{new Date(candidate.created_at).toLocaleDateString("ja-JP")}</dd>
          </div>
        </dl>
      </div>

      {/* 利益計算 */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
        <h2 className="font-bold text-gray-800 mb-3">価格・利益</h2>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div>
            <dt className="text-gray-500">仕入れ価格</dt>
            <dd className="text-gray-800">
              {candidate.purchase_price_jpy != null ? `¥${candidate.purchase_price_jpy.toLocaleString()}` : "-"}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">目標販売価格</dt>
            <dd className="text-gray-800">
              {candidate.target_sale_price_usd != null ? `$${candidate.target_sale_price_usd.toFixed(2)}` : "-"}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">推定利益</dt>
            <dd className="text-gray-800">
              {candidate.estimated_profit_jpy != null ? `¥${candidate.estimated_profit_jpy.toLocaleString()}` : "-"}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">利益率</dt>
            <dd><ProfitRateBadge rate={candidate.estimated_profit_rate} /></dd>
          </div>
          <div>
            <dt className="text-gray-500">最低採算価格</dt>
            <dd className="text-gray-800">
              {candidate.min_profitable_price_usd != null ? `$${candidate.min_profitable_price_usd.toFixed(2)}` : "-"}
            </dd>
          </div>
        </dl>
      </div>

      {/* スコア */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
        <div className="flex justify-between items-center mb-3">
          <h2 className="font-bold text-gray-800">スコア</h2>
          <button
            onClick={handleScore}
            disabled={scoring}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-1 rounded text-xs font-medium"
          >
            {scoring ? "実行中..." : "スコアリング実行"}
          </button>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div>
            <span className="text-gray-500 mr-2">トータルスコア</span>
            <ScoreBadge score={candidate.score_override ?? candidate.total_score} />
          </div>
          {candidate.score_override != null && (
            <span className="text-xs text-orange-600">（手動補正済み）</span>
          )}
        </div>
      </div>

      {/* ステータス操作 */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="font-bold text-gray-800 mb-3">ステータス変更</h2>
        <div className="flex gap-2 flex-wrap">
          {candidate.status !== "promoted" && (
            <button
              onClick={() => handleStatusChange("promoted")}
              disabled={promoting}
              className="bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50"
            >
              出品候補に昇格
            </button>
          )}
          {candidate.status !== "rejected" && (
            <button
              onClick={() => handleStatusChange("rejected")}
              className="bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded text-sm font-medium"
            >
              却下
            </button>
          )}
          {candidate.status === "rejected" && (
            <button
              onClick={() => handleStatusChange("new")}
              className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-1.5 rounded text-sm font-medium"
            >
              新規に戻す
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
