/**
 * 音色状态管理
 * 
 * 负责：
 * - 全局音色选择
 * - 播放倍速控制
 * - 本地缓存（LocalStorage）
 * - 与后端同步
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { Voice } from "@/services/api";
import {
  listVoices,
  getVoicePreferences,
  saveVoicePreferences,
} from "@/services/api";
import { getStoredToken } from "@/stores/authStore";

interface VoiceState {
  // 当前选中的音色 ID
  selectedVoiceId: string | null;
  
  // 播放倍速（0.5 - 2.0）
  playbackSpeed: number;
  
  // 可用音色列表
  voices: Voice[];
  
  // TTS 是否可用
  ttsAvailable: boolean;
  
  // 加载状态
  isLoading: boolean;
  
  // 操作方法
  setVoice: (voiceId: string, saveToBackend?: boolean) => Promise<void>;
  setPlaybackSpeed: (speed: number, saveToBackend?: boolean) => Promise<void>;
  loadVoices: (token?: string | null) => Promise<void>;
  loadPreferences: (token?: string | null) => Promise<void>;
  getSelectedVoice: () => Voice | null;
}

const DEFAULT_VOICE_ID = "zh-CN-XiaoxiaoNeural";
const DEFAULT_PLAYBACK_SPEED = 1.0;

export const useVoiceStore = create<VoiceState>()(
  persist(
    (set, get) => ({
      selectedVoiceId: DEFAULT_VOICE_ID,
      playbackSpeed: DEFAULT_PLAYBACK_SPEED,
      voices: [],
      ttsAvailable: true,
      isLoading: false,

      setVoice: async (voiceId: string, saveToBackend = true) => {
        set({ selectedVoiceId: voiceId });
        
        // 保存到后端（可选）
        if (saveToBackend) {
          try {
            const token = getStoredToken();
            await saveVoicePreferences({ preferred_voice: voiceId }, token);
          } catch (error) {
            console.warn("保存音色偏好到后端失败（可能未登录）:", error);
            // 不抛出错误，因为本地缓存已成功
          }
        }
      },

      setPlaybackSpeed: async (speed: number, saveToBackend = true) => {
        // 限制范围
        const clampedSpeed = Math.max(0.5, Math.min(2.0, speed));
        set({ playbackSpeed: clampedSpeed });
        
        // 保存到后端（可选）
        if (saveToBackend) {
          try {
            const token = getStoredToken();
            await saveVoicePreferences({ playback_speed: clampedSpeed }, token);
          } catch (error) {
            console.warn("保存播放倍速到后端失败（可能未登录）:", error);
          }
        }
      },

      loadVoices: async (token?: string | null) => {
        set({ isLoading: true });
        try {
          const tokenToUse = token ?? getStoredToken();
          const data = await listVoices(tokenToUse);
          const current = get().selectedVoiceId;
          const nextSelected =
            current && data.voices.find((v) => v.id === current)
              ? current
              : data.default_voice_id;

          set({
            voices: data.voices,
            ttsAvailable: data.tts_available,
            selectedVoiceId: nextSelected,
            isLoading: false,
          });
        } catch (error) {
          console.error("加载音色列表失败:", error);
          set({ isLoading: false, ttsAvailable: false });
        }
      },

      loadPreferences: async (token?: string | null) => {
        try {
          const prefs = await getVoicePreferences(token);
          
          // 只有后端返回的偏好才覆盖本地
          if (prefs.preferred_voice) {
            set({
              selectedVoiceId: prefs.preferred_voice,
              playbackSpeed: prefs.playback_speed || DEFAULT_PLAYBACK_SPEED,
            });
          }
        } catch (error) {
          console.warn("加载用户偏好失败（可能未登录）:", error);
          // 使用本地缓存，不做任何操作
        }
      },

      getSelectedVoice: () => {
        const { selectedVoiceId, voices } = get();
        if (!selectedVoiceId) return null;
        return voices.find((v) => v.id === selectedVoiceId) || null;
      },
    }),
    {
      name: "voice-preferences", // LocalStorage 键名
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // 只持久化这些字段
        selectedVoiceId: state.selectedVoiceId,
        playbackSpeed: state.playbackSpeed,
      }),
    }
  )
);
