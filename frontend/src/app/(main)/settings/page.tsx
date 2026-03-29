"use client";

import { useEffect, useState } from "react";

interface AutoResearchSettings {
  keywords: string[];
  min_purchase_price_jpy: number;
  max_purchase_price_jpy: number;
  min_score: number;
  rakuten_configured: boolean;
  ebay_configured: boolean;
}

interface RunResult {
  keywords_processed: number;
  total_candidates_created: number;
  total_skipped_low_profit: number;
  total_skipped_duplicate: number;
  per_keyword: {
    keyword: string;
    rakuten_found: number;
    ebay_price_found: number;
    candidates_created: number;
    skipped_low_profit: number;
  }[];
}

export default function SettingsPage() {
  const [autoSettings, setAutoSettings] = useState<AutoResearchSettings | null>(null);
  const [keywords, setKeywords] = useState("");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/auto-research/settings`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data: AutoResearchSettings = await res.json();
        setAutoSettings(data);
        setKeywords(data.keywords.join(", "));
      }
    } catch {
      // 設定取得失敗は無視
    }
  }

  async function handleRunAutoResearch() {
    setRunning(true);
    setRunResult(null);
    setError(null);
    try {
      const token = localStorage.getItem("access_token");
      const keywordList = keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/auto-research/run-sync`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ keywords: keywordList }),
        }
      );
      if (!res.ok) throw new Error(`エラー: ${res.status}`);
      const data: RunResult = await res.json();
      setRunResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "実行エラー");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">設定</h1>

      {/* 自動リサーチ設定 */}
      <section className="bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="font-bold text-gray-800 mb-1">🔍 自動リサーチ（楽天 × eBay）</h2>
        <p className="text-xs text-gray-500 mb-4">
          楽天市場で商品を検索し、eBay相場と比較して利益が出る商品を自動でリサーチ候補に追加します。
        </p>

        {/* API設定状況 */}
        <div className="flex gap-3 mb-4">
          <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
            autoSettings?.rakuten_configured
              ? "bg-green-100 text-green-700"
              : "bg-red-100 text-red-700"
          }`}>
            楽天API: {autoSettings?.rakuten_configured ? "✓ 設定済み" : "✗ 未設定"}
          </span>
          <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
            autoSettings?.ebay_configured
              ? "bg-green-100 text-green-700"
              : "bg-yellow-100 text-yellow-700"
          }`}>
            eBay API: {autoSettings?.ebay_configured ? "✓ 設定済み" : "△ 未設定（相場取得不可）"}
          </span>
        </div>

        {/* キーワード設定 */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            検索キーワード（カンマ区切り）
          </label>
          <textarea
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="例: ゲーム機, カメラ, ヘッドホン, 腕時計"
          />
          <p className="text-xs text-gray-400 mt-1">
            現在の設定: {autoSettings?.min_purchase_price_jpy?.toLocaleString()}円 〜{" "}
            {autoSettings?.max_purchase_price_jpy?.toLocaleString()}円 ／ 最低スコア:{" "}
            {autoSettings?.min_score}点
          </p>
        </div>

        {error && (
          <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
            {error}
          </div>
        )}

        <button
          onClick={handleRunAutoResearch}
          disabled={running || !autoSettings?.rakuten_configured}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded text-sm font-medium"
        >
          {running ? "⏳ リサーチ実行中..." : "▶ 今すぐリサーチ実行"}
        </button>
        {!autoSettings?.rakuten_configured && (
          <p className="text-xs text-red-500 mt-2">
            楽天APIキーが設定されていません。Railway Variables に RAKUTEN_APP_ID を追加してください。
          </p>
        )}

        {/* 実行結果 */}
        {runResult && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded">
            <p className="font-bold text-green-800 mb-2">✅ リサーチ完了</p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-green-700">
              <div>
                <dt className="text-gray-500">処理キーワード数</dt>
                <dd className="font-medium">{runResult.keywords_processed}件</dd>
              </div>
              <div>
                <dt className="text-gray-500">候補登録数</dt>
                <dd className="font-bold text-green-700">{runResult.total_candidates_created}件</dd>
              </div>
              <div>
                <dt className="text-gray-500">利益不足でスキップ</dt>
                <dd>{runResult.total_skipped_low_profit}件</dd>
              </div>
              <div>
                <dt className="text-gray-500">重複でスキップ</dt>
                <dd>{runResult.total_skipped_duplicate}件</dd>
              </div>
            </dl>

            {runResult.per_keyword.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-medium text-gray-600 mb-1">キーワード別</p>
                <div className="space-y-1">
                  {runResult.per_keyword.map((k) => (
                    <div key={k.keyword} className="flex justify-between text-xs text-gray-600">
                      <span>{k.keyword}</span>
                      <span>楽天{k.rakuten_found}件 → 登録{k.candidates_created}件</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <p className="text-xs text-gray-500 mt-3">
              登録された候補は <a href="/research" className="text-blue-600 underline">リサーチ一覧</a> で確認できます。
            </p>
          </div>
        )}
      </section>

      {/* eBay環境 */}
      <section className="bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="font-bold text-gray-800 mb-3">eBay環境</h2>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            🧪 sandbox
          </span>
          <span className="text-sm text-gray-500">
            本番切り替えは Railway Variables の{" "}
            <code className="bg-gray-100 px-1 rounded">EBAY_ENVIRONMENT</code> を{" "}
            <code className="bg-gray-100 px-1 rounded">production</code> に変更
          </span>
        </div>
      </section>

      {/* 安全設定 */}
      <section className="bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="font-bold text-gray-800 mb-3">安全設定</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-gray-600">Dry-run デフォルト</dt>
            <dd className="font-medium text-orange-600">有効</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-600">公開前承認必須</dt>
            <dd className="font-medium text-green-600">有効</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-600">最低利益率</dt>
            <dd className="font-medium text-gray-800">15%</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-600">最低利益額</dt>
            <dd className="font-medium text-gray-800">¥500</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
