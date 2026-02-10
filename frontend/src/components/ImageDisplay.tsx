"use client";

import { motion } from "framer-motion";
import { useEffect } from "react";

interface ImageDisplayProps {
  imageUrl?: string | null;
}

export default function ImageDisplay({ imageUrl }: ImageDisplayProps) {
  useEffect(() => {
    if (imageUrl) {
      console.log("[前端] 图片 URL:", imageUrl.substring(0, 100));
    } else {
      console.warn("[前端] ⚠️ 图片 URL 为空");
    }
  }, [imageUrl]);

  return (
    <div className="w-full h-full min-h-[240px] flex items-center justify-center bg-gradient-to-br from-primary/10 to-secondary/10 rounded-story-md overflow-hidden">
      {imageUrl ? (
        <motion.img
          key={imageUrl}
          src={imageUrl}
          alt="故事插画"
          className="w-full h-full object-cover"
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          onError={(e) => {
            console.error("[前端] ❌ 图片加载失败:", imageUrl, e);
          }}
          onLoad={() => {
            console.log("[前端] ✅ 图片加载成功:", imageUrl.substring(0, 50));
          }}
        />
      ) : (
        <span className="text-text-ui/60">插画加载中…</span>
      )}
    </div>
  );
}
