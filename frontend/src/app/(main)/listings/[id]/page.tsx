"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { listingsApi, type ListingDraft } from "@/lib/api";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [draft, setDraft] = useState<ListingDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPrice, setEditPrice] = useState("");
  const [reviewNote, setReviewNote] = useState("");

  useEffect(() => {
    load();
  }, [id]);

  async function load() {
    try {
      setLoading(true);
      const data = await listingsApi.getDraft(id);
      setDraft(data);
      setEditTitle(data.title_selected || "");
      setEditDesc(data.description_edited || data.description_generated || "");
      setEditPrice(data.listing_price_usd != null ? String(data.listing_price_usd) : "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "読み込みエラー");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    try {
      setSaving(true);
      const updated = await listingsApi.updateDraft(id, {
        title_selected: editTitle,
        description_edited: editDesc,
        listing_price_usd: editPrice ? Number(editPrice) : undefined,
      });
      setDraft(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存エラー");
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmitForReview() {
    if (!confirm("レビューに提出しますか？")) return;
    try {
      setSubmitting(true);
      const updated = await listingsApi.submitForReview(id, reviewNote || undefined);
      setDraft(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提出エラー");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="p-6 text-gray-500">読み込み中...</div>;
  if (error && !draft) return <div className="p-6 text-red-600">{error}</div>;
  if (!draft) return <div className="p-6 text-gray-500">見つかりません</div>;

  const canEdit = ["draft", "rejected"].includes(draft.status);
  const canSubmit = canEdit && draft.is_valid;

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/listings")}
          className="text-gray-500 hover:text-gray-700 text-sm"
        >
          ← 一覧に戻る
        </button>
      </div>

      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl font-bold text-gray-900">出品下書き詳細</h1>
        <StatusBadge status={draft.status} />
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {draft.validation_warnings && draft.validation_warnings.length > 0 && (
        <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded text-orange-700 text-sm">
          ⚠️ 警告: {draft.validation_warnings.join(" / ")}
        </div>
      )}

      {draft.reviewer_note && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded text-blue-700 text-sm">
          レビューコメント: {draft.reviewer_note}
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">タイトル</label>
          {draft.title_candidates && draft.title_candidates.length > 0 && canEdit && (
            <div className="mb-2 space-y-1">
              {draft.title_candidates.map((t, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setEditTitle(t)}
                  className={`w-full text-left px-3 py-2 rounded border text-sm transition-colors ${
                    editTitle === t
                      ? "border-blue-500 bg-blue-50 text-blue-800"
                      : "border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            disabled={!canEdit}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">説明文</label>
          <textarea
            value={editDesc}
            onChange={(e) => setEditDesc(e.target.value)}
            disabled={!canEdit}
            rows={8}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 font-mono"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">出品価格（USD）</label>
          <input
            type="number"
            value={editPrice}
            onChange={(e) => setEditPrice(e.target.value)}
            disabled={!canEdit}
            step={0.01}
            min={0}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
          />
        </div>

        {canEdit && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded text-sm font-medium"
          >
            {saving ? "保存中..." : "保存"}
          </button>
        )}
      </div>

      {canEdit && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h2 className="font-bold text-gray-800 mb-3">レビューに提出</h2>
          <input
            type="text"
            value={reviewNote}
            onChange={(e) => setReviewNote(e.target.value)}
            placeholder="コメント（任意）"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSubmitForReview}
            disabled={submitting || !canSubmit}
            className="bg-yellow-500 hover:bg-yellow-600 disabled:opacity-50 text-white px-4 py-2 rounded text-sm font-medium"
          >
            {submitting ? "提出中..." : "レビューに提出"}
          </button>
          {!draft.is_valid && (
            <p className="mt-2 text-xs text-red-500">バリデーションエラーがあるため提出できません</p>
          )}
        </div>
      )}
    </div>
  );
}
