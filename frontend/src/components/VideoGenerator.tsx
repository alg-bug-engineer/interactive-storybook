"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  generateVideo,
  getVideoStatus,
  getVideoDownloadUrl,
  type VideoStatusResponse,
} from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

interface VideoGeneratorProps {
  storyId: string;
  storyTitle: string;
  isStoryCompleted: boolean;
  totalSegments: number;
}

const STATUS_TEXT: Record<string, string> = {
  idle: "准备生成",
  generating_clips: "正在生成视频片段...",
  merging: "正在合并视频...",
  adding_audio: "正在添加音频...",
  completed: "视频已生成！",
  failed: "生成失败",
};
const STATUS_POLL_INTERVAL_MS = 5000;

export default function VideoGenerator({
  storyId,
  storyTitle,
  isStoryCompleted,
  totalSegments,
}: VideoGeneratorProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState<VideoStatusResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [showModal, setShowModal] = useState(false);

  const { user, token } = useAuthStore();

  // 轮询检查视频生成状态
  const pollVideoStatus = useCallback(async () => {
    try {
      const statusData = await getVideoStatus(storyId);
      setStatus(statusData);

      // 如果完成或失败，停止轮询
      if (statusData.status === "completed" || statusData.status === "failed") {
        setIsGenerating(false);
        if (statusData.error) {
          setError(statusData.error);
        }
      }
    } catch (e) {
      console.error("[视频生成] 查询状态失败:", e);
    }
  }, [storyId]);

  // 点击「一键转视频」：检查登录状态
  const onVideoButtonClick = () => {
    if (!user || !token) {
      alert("请先登录后再使用视频生成功能");
      return;
    }
    handleGenerateVideo();
  };

  // 开始生成视频
  const handleGenerateVideo = async () => {
    if (!isStoryCompleted) {
      setError("请先完成整个故事再生成视频");
      return;
    }

    if (totalSegments < 2) {
      setError("故事段落不足，至少需要 2 个段落才能生成视频");
      return;
    }

    setError("");
    setIsGenerating(true);
    setShowModal(true);

    try {
      await generateVideo(storyId, true);
      console.log("[视频生成] 任务已启动，开始轮询状态...");
      await pollVideoStatus();
    } catch (e) {
      setIsGenerating(false);
      setError(e instanceof Error ? e.message : "生成视频失败");
      console.error("[视频生成] 启动失败:", e);
    }
  };

  // 初始查询状态（检查是否有正在进行的任务）
  useEffect(() => {
    const checkInitialStatus = async () => {
      try {
        const statusData = await getVideoStatus(storyId);
        if (
          statusData.status !== "idle" &&
          statusData.status !== "completed" &&
          statusData.status !== "failed"
        ) {
          setStatus(statusData);
          setIsGenerating(true);
          setShowModal(true);
        } else if (statusData.status === "completed") {
          setStatus(statusData);
        }
      } catch (e) {
        console.error("[视频生成] 初始状态查询失败:", e);
      }
    };

    checkInitialStatus();
  }, [storyId]);

  // 自动轮询（当正在生成时）
  useEffect(() => {
    if (!isGenerating) return;

    const interval = setInterval(pollVideoStatus, STATUS_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [isGenerating, pollVideoStatus]);

  const handleDownload = () => {
    const downloadUrl = getVideoDownloadUrl(storyId);
    window.open(downloadUrl, "_blank");
  };

  const statusColor =
    status?.status === "completed"
      ? "text-green-600"
      : status?.status === "failed"
      ? "text-red-600"
      : "text-blue-600";

  return (
    <>
      <div className="flex flex-col items-end">
        <button
          onClick={onVideoButtonClick}
          disabled={!isStoryCompleted || isGenerating}
          className="flex items-center gap-2 px-6 py-3 rounded-story-md bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          title={
            !isStoryCompleted
              ? "请先完成整个故事"
              : isGenerating
              ? "正在生成中..."
              : "一键转视频"
          }
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
          {isGenerating ? "生成中..." : "一键转视频"}
        </button>
      </div>

      {/* 状态模态框 */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={() => {
              if (!isGenerating) setShowModal(false);
            }}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-center">
                <h3 className="text-xl font-bold text-gray-800 mb-4">
                  {storyTitle} - 视频生成
                </h3>

                {/* 进度条 */}
                {status && (
                  <div className="mb-4">
                    <div className="flex justify-between text-sm text-gray-600 mb-2">
                      <span className={statusColor}>
                        {STATUS_TEXT[status.status] || status.status}
                      </span>
                      <span>{status.progress}%</span>
                    </div>
                    <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${status.progress}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                    <div className="text-sm text-gray-500 mt-2">
                      视频片段: {status.generated_clips} / {status.total_clips}
                    </div>
                  </div>
                )}

                {/* 加载动画 */}
                {isGenerating && (
                  <div className="flex justify-center my-6">
                    <div className="animate-spin rounded-full h-16 w-16 border-4 border-gray-200 border-t-purple-500" />
                  </div>
                )}

                {/* 完成状态 */}
                {status?.status === "completed" && (
                  <div className="my-6">
                    <div className="text-green-600 text-5xl mb-3">✓</div>
                    <p className="text-gray-600 mb-4">
                      视频生成成功！点击下载按钮保存视频。
                    </p>
                    <button
                      onClick={handleDownload}
                      className="px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-lg font-medium hover:shadow-lg transition-all"
                    >
                      下载视频
                    </button>
                  </div>
                )}

                {/* 错误信息 */}
                {(error || status?.error) && (
                  <div className="my-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-red-600 text-sm">
                      {error || status?.error}
                    </p>
                  </div>
                )}

                {/* 关闭按钮 */}
                {!isGenerating && (
                  <button
                    onClick={() => setShowModal(false)}
                    className="mt-4 px-6 py-2 text-gray-600 hover:text-gray-800 font-medium"
                  >
                    关闭
                  </button>
                )}

                {/* 提示信息 */}
                {isGenerating && (
                  <p className="text-sm text-gray-500 mt-4">
                    视频生成需要一些时间，请耐心等待...
                  </p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
