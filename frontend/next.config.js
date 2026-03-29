/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  experimental: {
    serverActions: {
      // NEXT_PUBLIC_APP_URL が設定されていれば追加（Railway本番URL対応）
      allowedOrigins: [
        "localhost:3000",
        ...(process.env.NEXT_PUBLIC_APP_URL
          ? [process.env.NEXT_PUBLIC_APP_URL.replace(/^https?:\/\//, "")]
          : []),
      ],
    },
  },
};

module.exports = nextConfig;
