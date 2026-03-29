"use client";

import { useEffect, useState } from "react";
import { jobsApi } from "@/lib/api";

interface AuditLog {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  actor_id: string;
  created_at: string;
  diff: unknown;
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    jobsApi
      .getAuditLogs()
      .then((data) => setLogs(data as AuditLog[]))
      .catch((e) => setError(e instanceof Error ? e.message : "読み込みエラー"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">監査ログ</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">読み込み中...</div>
      ) : logs.length === 0 ? (
        <div className="text-center py-12 text-gray-400">監査ログがありません</div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-700">日時</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">アクション</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">リソース種別</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">リソースID</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">実行者ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(log.created_at).toLocaleString("ja-JP")}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{log.action}</td>
                  <td className="px-4 py-3 text-xs text-gray-600">{log.resource_type}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{log.resource_id}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{log.actor_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
