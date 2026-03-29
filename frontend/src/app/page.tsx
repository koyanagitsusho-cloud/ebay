import { redirect } from "next/navigation";

/** ルートにアクセスしたらダッシュボードへリダイレクト */
export default function RootPage() {
  redirect("/dashboard");
}
