import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "eBay Automation Tool",
  description: "eBay販売業務自動化ツール",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
