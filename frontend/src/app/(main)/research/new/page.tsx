"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { researchApi, type CreateResearchCandidateInput } from "@/lib/api";

export default function ResearchNewPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<CreateResearchCandidateInput>({
    title: "",
    brand: "",
    model_number: "",
    condition: "used_good",
    purchase_price_jpy: undefined,
    domestic_shipping_jpy: undefined,
    international_shipping_usd: undefined,
    other_cost_jpy: undefined,
    target_sale_price_usd: undefined,
    notes: "",
  });

  function set(field: keyof CreateResearchCandidateInput, value: string | number | undefined) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: CreateResearchCandidateInput = {
        title: form.title,
        ...(form.brand && { brand: form.brand }),
        ...(form.model_number && { model_number: form.model_number }),
        condition: form.condition,
        ...(form.purchase_price_jpy != null && { purchase_price_jpy: form.purchase_price_jpy }),
        ...(form.domestic_shipping_jpy != null && { domestic_shipping_jpy: form.domestic_shipping_jpy }),
        ...(form.international_shipping_usd != null && { international_shipping_usd: form.international_shipping_usd }),
        ...(form.other_cost_jpy != null && { other_cost_jpy: form.other_cost_jpy }),
        ...(form.target_sale_price_usd != null && { target_sale_price_usd: form.target_sale_price_usd }),
        ...(form.notes && { notes: form.notes }),
      };
      await researchApi.create(payload);
      router.push("/research");
    } catch (e) {
      setError(e instanceof Error ? e.message : "登録エラー");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">商品候補を登録</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            商品名 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
            required
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="例: Sony WH-1000XM4 ワイヤレスヘッドホン"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ブランド</label>
            <input
              type="text"
              value={form.brand || ""}
              onChange={(e) => set("brand", e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: Sony"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">型番</label>
            <input
              type="text"
              value={form.model_number || ""}
              onChange={(e) => set("model_number", e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: WH-1000XM4"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">コンディション</label>
          <select
            value={form.condition}
            onChange={(e) => set("condition", e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="new">新品</option>
            <option value="used_like_new">中古 - ほぼ新品</option>
            <option value="used_good">中古 - 良品</option>
            <option value="used_acceptable">中古 - 可</option>
          </select>
        </div>

        <hr className="border-gray-200" />
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">価格情報</p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">仕入れ価格（円）</label>
            <input
              type="number"
              value={form.purchase_price_jpy ?? ""}
              onChange={(e) => set("purchase_price_jpy", e.target.value ? Number(e.target.value) : undefined)}
              min={0}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 8000"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">目標販売価格（USD）</label>
            <input
              type="number"
              value={form.target_sale_price_usd ?? ""}
              onChange={(e) => set("target_sale_price_usd", e.target.value ? Number(e.target.value) : undefined)}
              min={0}
              step={0.01}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 89.99"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">国内送料（円）</label>
            <input
              type="number"
              value={form.domestic_shipping_jpy ?? ""}
              onChange={(e) => set("domestic_shipping_jpy", e.target.value ? Number(e.target.value) : undefined)}
              min={0}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 800"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">国際送料（USD）</label>
            <input
              type="number"
              value={form.international_shipping_usd ?? ""}
              onChange={(e) => set("international_shipping_usd", e.target.value ? Number(e.target.value) : undefined)}
              min={0}
              step={0.01}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="例: 15.00"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">メモ</label>
          <textarea
            value={form.notes || ""}
            onChange={(e) => set("notes", e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="仕入れ先・状態詳細など"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-6 py-2 rounded text-sm font-medium"
          >
            {loading ? "登録中..." : "登録する"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/research")}
            className="bg-white border border-gray-300 text-gray-700 px-6 py-2 rounded text-sm font-medium hover:bg-gray-50"
          >
            キャンセル
          </button>
        </div>
      </form>
    </div>
  );
}
