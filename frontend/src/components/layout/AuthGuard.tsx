"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getToken, authApi } from "@/lib/api";

/**
 * 認証ガード
 * トークンがない、または無効な場合はログインページへリダイレクトする。
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
      return;
    }

    // トークンの有効性をサーバーで検証
    authApi
      .me()
      .then(() => setChecked(true))
      .catch(() => {
        router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
      });
  }, [router, pathname]);

  if (!checked) {
    return (
      <div className="flex items-center justify-center min-h-screen text-gray-500">
        読み込み中...
      </div>
    );
  }

  return <>{children}</>;
}
