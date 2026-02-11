/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 开发环境直接调用后端，无需 rewrites
  // 如需代理，可取消注释以下配置
  // async rewrites() {
  //   const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:1001";
  //   return [
  //     { source: "/api/:path*", destination: `${base}/api/:path*` },
  //   ];
  // },
};

module.exports = nextConfig;
