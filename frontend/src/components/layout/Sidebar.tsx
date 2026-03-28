"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/dashboard", label: "ダッシュボード", icon: "📊" },
  { href: "/research", label: "リサーチ候補", icon: "🔍" },
  { href: "/listings", label: "出品下書き", icon: "📝" },
  { href: "/approvals", label: "承認待ち", icon: "✅" },
  { href: "/jobs", label: "ジョブ状況", icon: "⚙️" },
  { href: "/audit", label: "監査ログ", icon: "📋" },
  { href: "/settings", label: "設定", icon: "🔧" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 min-h-screen bg-gray-900 text-white flex flex-col">
      {/* ロゴ */}
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold text-white">eBay Auto Tool</h1>
        <p className="text-xs text-gray-400 mt-1">販売業務自動化</p>
      </div>

      {/* ナビゲーション */}
      <nav className="flex-1 py-4">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                isActive
                  ? "bg-blue-700 text-white font-medium"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* フッター */}
      <div className="p-4 border-t border-gray-700">
        <p className="text-xs text-gray-500">v0.1.0 MVP</p>
      </div>
    </aside>
  );
}
