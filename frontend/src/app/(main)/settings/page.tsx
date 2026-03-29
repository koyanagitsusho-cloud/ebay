"use client";

export default function SettingsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">設定</h1>

      <div className="max-w-xl space-y-6">
        <section className="bg-white border border-gray-200 rounded-lg p-4">
          <h2 className="font-bold text-gray-800 mb-3">eBay環境</h2>
          <p className="text-sm text-gray-600 mb-3">
            現在の設定はバックエンドの環境変数（<code className="bg-gray-100 px-1 rounded">EBAY_ENVIRONMENT</code>）で管理されています。
          </p>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
              🧪 sandbox
            </span>
            <span className="text-sm text-gray-500">
              本番切り替えは .env の EBAY_ENVIRONMENT を <code className="bg-gray-100 px-1 rounded">production</code> に変更して再起動
            </span>
          </div>
        </section>

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
          <p className="text-xs text-gray-400 mt-3">
            これらの設定は .env ファイルで変更できます（変更には再起動が必要）。
          </p>
        </section>
      </div>
    </div>
  );
}
