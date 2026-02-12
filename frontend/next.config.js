/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  
  // API 代理配置：将前端 /api/* 请求转发到后端
  // 客户端请求相对路径 /api/* 会匹配这里的规则
  async rewrites() {
    // 服务端渲染时直接访问后端（内网可直连）
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:1001";
    
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
      {
        source: "/static/images/:path*",
        destination: `${apiBase}/static/images/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
