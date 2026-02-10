/**
 * 音色选择组件
 * 
 * 功能：
 * - 展示可用音色卡片
 * - 试听音色
 * - 选择音色并保存
 */

"use client";

import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { useVoiceStore } from "@/stores/voiceStore";
import { previewVoice, type Voice } from "@/services/api";

interface VoiceSelectorProps {
  onClose?: () => void;
  showTitle?: boolean;
}

export default function VoiceSelector({ onClose, showTitle = true }: VoiceSelectorProps) {
  const {
    voices,
    selectedVoiceId,
    setVoice,
    loadVoices,
    ttsAvailable,
    isLoading,
  } = useVoiceStore();

  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    // 加载音色列表
    loadVoices();
  }, [loadVoices]);

  // 清理音频
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const handlePreview = async (voiceId: string) => {
    try {
      setPreviewError(null);

      // 如果正在播放同一个音色，停止
      if (playingVoiceId === voiceId && audioRef.current) {
        audioRef.current.pause();
        setPlayingVoiceId(null);
        return;
      }

      // 停止当前播放
      if (audioRef.current) {
        audioRef.current.pause();
      }

      setPlayingVoiceId(voiceId);

      // 获取预览音频
      const data = await previewVoice(voiceId);
      
      // 构造完整的音频 URL（后端返回的是相对路径，需要加上 API base URL）
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";
      const audioUrl = `${API}${data.audio_url}`;

      // 播放音频
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onended = () => {
        setPlayingVoiceId(null);
      };

      audio.onerror = () => {
        setPreviewError("试听失败，请重试");
        setPlayingVoiceId(null);
      };

      await audio.play();
    } catch (error) {
      console.error("试听音色失败:", error);
      setPreviewError("试听失败，请重试");
      setPlayingVoiceId(null);
    }
  };

  const handleSelectVoice = async (voiceId: string) => {
    await setVoice(voiceId, true);
  };

  if (!ttsAvailable) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-500 mb-4">TTS 服务暂时不可用</p>
        <p className="text-gray-600 text-sm">请联系管理员检查 edge-tts 是否已安装</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-8 text-center">
        <div className="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="mt-4 text-gray-600">加载音色中...</p>
      </div>
    );
  }

  // 分组：推荐音色 vs 更多音色
  const recommendedVoices = voices.filter((v) => v.is_recommended);
  const otherVoices = voices.filter((v) => !v.is_recommended);

  return (
    <div className="w-full max-w-4xl mx-auto p-6">
      {showTitle && (
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold">🎙️ 选择朗读音色</h2>
          {onClose && (
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 text-2xl"
              aria-label="关闭"
            >
              ×
            </button>
          )}
        </div>
      )}

      {previewError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-600 text-sm">
          {previewError}
        </div>
      )}

      {/* 推荐音色 */}
      {recommendedVoices.length > 0 && (
        <section className="mb-8">
          <h3 className="text-lg font-semibold mb-4 text-gray-700">默认推荐</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {recommendedVoices.map((voice) => (
              <VoiceCard
                key={voice.id}
                voice={voice}
                isSelected={selectedVoiceId === voice.id}
                isPlaying={playingVoiceId === voice.id}
                onPreview={() => handlePreview(voice.id)}
                onSelect={() => handleSelectVoice(voice.id)}
              />
            ))}
          </div>
        </section>
      )}

      {/* 更多音色 */}
      {otherVoices.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold mb-4 text-gray-700">更多音色</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {otherVoices.map((voice) => (
              <VoiceCard
                key={voice.id}
                voice={voice}
                isSelected={selectedVoiceId === voice.id}
                isPlaying={playingVoiceId === voice.id}
                onPreview={() => handlePreview(voice.id)}
                onSelect={() => handleSelectVoice(voice.id)}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

interface VoiceCardProps {
  voice: Voice;
  isSelected: boolean;
  isPlaying: boolean;
  onPreview: () => void;
  onSelect: () => void;
}

function VoiceCard({ voice, isSelected, isPlaying, onPreview, onSelect }: VoiceCardProps) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onSelect}
      className={`
        relative p-4 rounded-lg border-2 cursor-pointer transition-all
        ${
          isSelected
            ? "border-blue-500 bg-blue-50 shadow-lg"
            : "border-gray-200 bg-white hover:border-blue-300 hover:shadow-md"
        }
      `}
    >
      {/* 选中标记 */}
      {isSelected && (
        <div className="absolute top-2 right-2 bg-blue-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm">
          ✓
        </div>
      )}

      {/* 音色信息 */}
      <div className="mb-3">
        <h4 className="font-bold text-lg mb-1">{voice.name}</h4>
        <p className="text-sm text-gray-600">{voice.description}</p>
      </div>

      {/* 标签 */}
      <div className="flex flex-wrap gap-1 mb-3">
        {voice.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded"
          >
            {tag}
          </span>
        ))}
      </div>

      {/* 推荐场景 */}
      {voice.recommended_for.length > 0 && (
        <p className="text-xs text-gray-500 mb-3">
          适合：{voice.recommended_for.slice(0, 2).join("、")}
        </p>
      )}

      {/* 试听按钮 */}
      <button
        onClick={(e) => {
          e.stopPropagation(); // 防止触发卡片的点击事件
          onPreview();
        }}
        className={`
          w-full py-2 px-4 rounded text-sm font-medium transition-colors
          ${
            isPlaying
              ? "bg-red-500 hover:bg-red-600 text-white"
              : "bg-gray-100 hover:bg-gray-200 text-gray-700"
          }
        `}
      >
        {isPlaying ? "⏹ 停止" : "▶️ 试听"}
      </button>

      {/* 使用中标记 */}
      {isSelected && (
        <div className="mt-2 text-center text-xs text-blue-600 font-medium">
          当前使用中
        </div>
      )}
    </motion.div>
  );
}
