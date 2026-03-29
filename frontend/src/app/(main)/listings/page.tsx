"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listingsApi, type ListingDraft } from "@/lib/api";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function ListingsPage() {
  const [drafts, setDrafts] = useState<ListingDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");

  useEffect(() => {
    load();
  }, [statusFilter]);

  async function load() {
    try {
      setLoading(true);
      const data = await listingsApi.listDrafts(statusFilter || undefined);
      setDrafts(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "読み込みエラー");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">出品下書き一覧</h1>

      <div className="mb-4 flex gap-2">
        {["", "draft", "pending_review", "approved", "published", "rejected"].map((s) => (
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
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">読み込み中...</div>
      ) : drafts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">出品下書きがありません</div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-700">タイトル</th>
                <th className="px-4 py-3 text-right font-medium text-gray-700">価格(USD)</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">状態</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">有効</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {drafts.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-800">
                    {d.title_selected || (
                      <span className="text-gray-400 italic">タイトル未選択</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {d.listing_price_usd != null ? `$${d.listing_price_usd.toFixed(2)}` : "-"}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={d.status} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    {d.is_valid ? (
                      <span className="text-green-600 text-xs font-medium">OK</span>
                    ) : (
                      <span className="text-red-500 text-xs font-medium">NG</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Link
                      href={`/listings/${d.id}`}
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
