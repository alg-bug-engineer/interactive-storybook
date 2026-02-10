/**
 * 音频播放器组件
 * 
 * 功能：
 * - 播放/暂停
 * - 进度条拖拽
 * - 倍速控制
 * - 时长显示
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { useVoiceStore } from "@/stores/voiceStore";

interface AudioPlayerProps {
  audioUrl: string;
  onEnded?: () => void;
  autoPlay?: boolean;
  className?: string;
}

export default function AudioPlayer({
  audioUrl,
  onEnded,
  autoPlay = false,
  className = "",
}: AudioPlayerProps) {
  const { playbackSpeed, setPlaybackSpeed } = useVoiceStore();
  
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);

  // 初始化音频
  useEffect(() => {
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.onloadedmetadata = () => {
      setDuration(audio.duration);
      setIsLoading(false);
      if (autoPlay) {
        audio.play().catch((err) => console.error("自动播放失败:", err));
      }
    };

    audio.ontimeupdate = () => {
      setCurrentTime(audio.currentTime);
    };

    audio.onplay = () => setIsPlaying(true);
    audio.onpause = () => setIsPlaying(false);
    audio.onended = () => {
      setIsPlaying(false);
      if (onEnded) onEnded();
    };

    audio.onerror = () => {
      setIsLoading(false);
      console.error("音频加载失败");
    };

    // 设置播放速度
    audio.playbackRate = playbackSpeed;

    return () => {
      audio.pause();
      audio.src = "";
    };
  }, [audioUrl, autoPlay, onEnded, playbackSpeed]);

  // 更新播放速度
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch((err) => console.error("播放失败:", err));
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!audioRef.current) return;
    const newTime = parseFloat(e.target.value);
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const handleSpeedChange = async (speed: number) => {
    await setPlaybackSpeed(speed, true);
    setShowSpeedMenu(false);
  };

  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds)) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const speedOptions = [0.75, 1.0, 1.25, 1.5, 2.0];

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center p-4 ${className}`}>
        <div className="w-6 h-6 border-3 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <span className="ml-3 text-gray-600">加载音频中...</span>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 ${className}`}>
      {/* 播放控制区 */}
      <div className="flex items-center gap-4 mb-3">
        {/* 播放/暂停按钮 */}
        <button
          onClick={togglePlay}
          className="w-12 h-12 flex items-center justify-center bg-blue-500 hover:bg-blue-600 text-white rounded-full transition-colors text-2xl"
          aria-label={isPlaying ? "暂停" : "播放"}
        >
          {isPlaying ? "⏸" : "▶️"}
        </button>

        {/* 时间显示 */}
        <div className="flex-1">
          <div className="text-sm text-gray-600 mb-1">
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>
        </div>

        {/* 倍速控制 */}
        <div className="relative">
          <button
            onClick={() => setShowSpeedMenu(!showSpeedMenu)}
            className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded text-sm font-medium transition-colors"
          >
            {playbackSpeed}x
          </button>
          
          {showSpeedMenu && (
            <div className="absolute right-0 bottom-full mb-2 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10">
              {speedOptions.map((speed) => (
                <button
                  key={speed}
                  onClick={() => handleSpeedChange(speed)}
                  className={`
                    block w-full px-4 py-2 text-left text-sm hover:bg-gray-100 transition-colors
                    ${playbackSpeed === speed ? "bg-blue-50 text-blue-600 font-medium" : "text-gray-700"}
                  `}
                >
                  {speed}x {speed === 1.0 && "(标准)"}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 进度条 */}
      <div className="relative">
        <input
          type="range"
          min="0"
          max={duration || 0}
          value={currentTime}
          onChange={handleSeek}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-4
            [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:bg-blue-500
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:hover:bg-blue-600
            [&::-moz-range-thumb]:w-4
            [&::-moz-range-thumb]:h-4
            [&::-moz-range-thumb]:bg-blue-500
            [&::-moz-range-thumb]:rounded-full
            [&::-moz-range-thumb]:cursor-pointer
            [&::-moz-range-thumb]:hover:bg-blue-600
            [&::-moz-range-thumb]:border-0"
          style={{
            background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${
              (currentTime / duration) * 100
            }%, #e5e7eb ${(currentTime / duration) * 100}%, #e5e7eb 100%)`,
          }}
        />
      </div>

      {/* 进度百分比 */}
      <div className="mt-2 text-xs text-gray-500 text-right">
        {duration > 0 ? `${Math.round((currentTime / duration) * 100)}%` : "0%"}
      </div>
    </div>
  );
}
