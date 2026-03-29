"use client";

import { useEffect, useState } from "react";
import { jobsApi, type Job } from "@/lib/api";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    jobsApi
      .list()
      .then(setJobs)
      .catch((e) => setError(e instanceof Error ? e.message : "読み込みエラー"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">ジョブ履歴</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">読み込み中...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-12 text-gray-400">ジョブがありません</div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-700">ジョブ種別</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">状態</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">dry-run</th>
                <th className="px-4 py-3 text-center font-medium text-gray-700">リトライ</th>
                <th className="px-4 py-3 text-right font-medium text-gray-700">所要時間(秒)</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">開始日時</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">エラー</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.map((j) => (
                <tr key={j.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{j.job_type}</td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={j.status} />
                  </td>
                  <td className="px-4 py-3 text-center text-xs">
                    {j.is_dry_run ? (
                      <span className="text-orange-600 font-medium">dry-run</span>
                    ) : (
                      <span className="text-gray-400">本番</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center text-gray-600">{j.retry_count}</td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {j.duration_seconds != null ? j.duration_seconds.toFixed(1) : "-"}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {j.started_at ? new Date(j.started_at).toLocaleString("ja-JP") : "-"}
                  </td>
                  <td className="px-4 py-3 text-xs text-red-500 max-w-xs truncate">
                    {j.error_message || "-"}
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
