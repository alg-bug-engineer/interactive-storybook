import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "有声互动故事书",
  description: "听故事、看画面、一起玩——AI 为你讲童话",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen antialiased bg-bg-main font-story">
        {children}
      </body>
    </html>
  );
}
