"use client";

import { motion } from "framer-motion";
import { useEffect } from "react";
import { resolveImageUrl } from "@/utils/media";

interface ImageDisplayProps {
  imageUrl?: string | null;
}

export default function ImageDisplay({ imageUrl }: ImageDisplayProps) {
  const resolvedImageUrl = resolveImageUrl(imageUrl);

  useEffect(() => {
    if (resolvedImageUrl) {
      console.log("[前端] 图片 URL:", resolvedImageUrl.substring(0, 100));
    } else {
      console.warn("[前端] ⚠️ 图片 URL 为空");
    }
  }, [resolvedImageUrl]);

  return (
    <div className="w-full h-full min-h-[240px] flex items-center justify-center bg-gradient-to-br from-primary/10 to-secondary/10 rounded-story-md overflow-hidden">
      {resolvedImageUrl ? (
        <motion.img
          key={resolvedImageUrl}
          src={resolvedImageUrl}
          alt="故事插画"
          className="w-full h-full object-cover"
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          onError={(e) => {
            console.error("[前端] ❌ 图片加载失败:", resolvedImageUrl, e);
          }}
          onLoad={() => {
            console.log("[前端] ✅ 图片加载成功:", resolvedImageUrl.substring(0, 50));
          }}
        />
      ) : (
        <span className="text-text-ui/60">插画加载中…</span>
      )}
    </div>
  );
}
