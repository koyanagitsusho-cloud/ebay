"use client";

import { useEffect, useState } from "react";
import { listingsApi, type ListingDraft } from "@/lib/api";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function ApprovalsPage() {
  const [drafts, setDrafts] = useState<ListingDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionNote, setActionNote] = useState<Record<string, string>>({});
  const [processing, setProcessing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      const data = await listingsApi.listPendingApproval();
      setDrafts(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "読み込みエラー");
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(draftId: string, action: "approve" | "reject") {
    const note = actionNote[draftId] || "";
    if (action === "reject" && !note.trim()) {
      alert("却下理由を入力してください");
      return;
    }

    if (action === "approve" && !confirm("この出品を承認しますか？")) return;
    if (action === "reject" && !confirm("この出品を却下しますか？")) return;

    try {
      setProcessing(draftId);
      // 実際には approval_id が必要だが、MVP では draft_id で代用
      // TODO: approvals エンドポイントから approval_id を取得する
      alert(`${action === "approve" ? "承認" : "却下"}しました（TODO: approval_id連携）`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "処理エラー");
    } finally {
      setProcessing(null);
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">承認待ち一覧</h1>

      <div className="mb-4 p-3 bg-yellow-50 border border-yellow-300 rounded text-sm text-yellow-800">
        ⚠️ 承認前に必ずタイトル・説明文・価格を確認してください。承認後に出品公開が可能になります。
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">読み込み中...</div>
      ) : drafts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">承認待ちの出品はありません</div>
      ) : (
        <div className="space-y-4">
          {drafts.map((draft) => (
            <div key={draft.id} className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="font-bold text-gray-800">
                    {draft.title_selected || "タイトル未選択"}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1">
                    商品ID: {draft.product_id} / 下書きID: {draft.id}
                  </p>
                </div>
                <StatusBadge status={draft.status} />
              </div>

              {/* 価格・警告表示 */}
              <div className="flex gap-4 mb-3 text-sm">
                <span className="text-gray-600">
                  出品価格:{" "}
                  <strong>
                    {draft.listing_price_usd ? `$${draft.listing_price_usd.toFixed(2)}` : "未設定"}
                  </strong>
                </span>
                {draft.validation_warnings && draft.validation_warnings.length > 0 && (
                  <span className="text-orange-600">
                    ⚠️ 警告: {draft.validation_warnings.join(", ")}
                  </span>
                )}
              </div>

              {/* 承認・却下操作 */}
              <div className="border-t pt-3 flex gap-3 items-end">
                <div className="flex-1">
                  <label className="block text-xs text-gray-500 mb-1">
                    コメント（却下の場合は必須）
                  </label>
                  <input
                    type="text"
                    value={actionNote[draft.id] || ""}
                    onChange={(e) =>
                      setActionNote((prev) => ({ ...prev, [draft.id]: e.target.value }))
                    }
                    placeholder="承認・却下理由を入力"
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  />
                </div>
                <button
                  onClick={() => handleReview(draft.id, "approve")}
                  disabled={processing === draft.id}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
                >
                  ✅ 承認
                </button>
                <button
                  onClick={() => handleReview(draft.id, "reject")}
                  disabled={processing === draft.id}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
                >
                  ❌ 却下
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
