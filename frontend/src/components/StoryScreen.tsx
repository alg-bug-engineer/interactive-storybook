"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  nextSegment,
  getSegmentAudio,
  submitInteraction,
  checkSegmentImage,
  preloadSegmentImage,
  type StoryStartResponse,
  type StorySegmentResponse,
  type NextSegmentResponse,
  type InteractResponse,
} from "@/services/api";
import ImageDisplay from "./ImageDisplay";
import TextDisplay from "./TextDisplay";
import InteractionPanel from "./InteractionPanel";
import VideoGenerator from "./VideoGenerator";
import AudioPlayer from "./AudioPlayer";
import { useVoiceStore } from "@/stores/voiceStore";

interface StoryScreenProps {
  initialData: StoryStartResponse;
  onBack: () => void;
}

const hasFullSegments = (data: StoryStartResponse) =>
  data.segments != null && data.segments.length === data.total_segments;

export default function StoryScreen({ initialData, onBack }: StoryScreenProps) {
  const [storyId, setStoryId] = useState(initialData.story_id);
  const [title, setTitle] = useState(initialData.title);
  const [currentSegment, setCurrentSegment] = useState<StorySegmentResponse | null>(
    initialData.current_segment
  );
  const [currentIndex, setCurrentIndex] = useState(initialData.current_index);
  const [totalSegments, setTotalSegments] = useState(initialData.total_segments);
  const [hasInteraction, setHasInteraction] = useState(initialData.has_interaction);
  const [status, setStatus] = useState(initialData.status);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [loadingNext, setLoadingNext] = useState(false);
  const [loadingInteract, setLoadingInteract] = useState(false);
  const [error, setError] = useState("");
  const [nextSegmentContent, setNextSegmentContent] = useState<StorySegmentResponse | null>(null);
  const [isFlipping, setIsFlipping] = useState(false);
  const [segmentAudioUrl, setSegmentAudioUrl] = useState<string | null>(null);
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [allSegments] = useState<StorySegmentResponse[] | null>(() =>
    hasFullSegments(initialData) ? initialData.segments! : null
  );
  const pendingNext = useRef<{ index: number; hasInteraction: boolean; status: string } | null>(null);
  const touchStartX = useRef<number>(0);

  const { selectedVoiceId, playbackSpeed, ttsAvailable } = useVoiceStore();

  const fetchSegmentAudio = useCallback(
    async (segmentIndex: number, text?: string | null) => {
      // 无文本或 TTS 不可用时不请求
      const t = (text || "").trim();
      if (!t || !ttsAvailable) {
        setSegmentAudioUrl(null);
        setAudioError(null);
        setAudioLoading(false);
        return;
      }

      setAudioLoading(true);
      setAudioError(null);
      try {
        const data = await getSegmentAudio(storyId, segmentIndex, selectedVoiceId, playbackSpeed);
        const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";
        setSegmentAudioUrl(`${API}${data.audio_url}`);
      } catch (e) {
        setSegmentAudioUrl(null);
        setAudioError(e instanceof Error ? e.message : "音频生成失败");
      } finally {
        setAudioLoading(false);
      }
    },
    [storyId, selectedVoiceId, playbackSpeed, ttsAvailable]
  );

  const pollSegmentImage = useCallback(
    async (segmentIndex: number, attempt: number = 0) => {
      const maxAttempts = 60;
      const pollInterval = 5000;
      if (attempt >= maxAttempts) return;
      try {
        const result = await checkSegmentImage(storyId, segmentIndex);
        if (result.has_image && result.image_url) {
          setCurrentSegment((prev) =>
            prev && prev.id === String(segmentIndex)
              ? { ...prev, image_url: result.image_url }
              : prev
          );
        } else {
          setTimeout(() => pollSegmentImage(segmentIndex, attempt + 1), pollInterval);
        }
      } catch (e) {
        if (attempt < maxAttempts - 1) {
          setTimeout(() => pollSegmentImage(segmentIndex, attempt + 1), pollInterval);
        }
      }
    },
    [storyId]
  );

  const goNext = useCallback(async () => {
    // 有完整段落时（画廊模式）允许翻页，否则在已完成时不允许
    if (loadingNext || (!allSegments && status === "completed")) return;
    const nextIdx = currentIndex + 1;
    if (nextIdx >= totalSegments) return;

    if (allSegments && nextIdx < allSegments.length) {
      const nextSeg = allSegments[nextIdx];
      setNextSegmentContent(nextSeg);
      pendingNext.current = {
        index: nextIdx,
        hasInteraction: !!nextSeg.interaction_point,
        status: nextIdx >= totalSegments - 1 ? "completed" : nextSeg.interaction_point ? "waiting_interaction" : "narrating",
      };
      setIsFlipping(true);
      if (nextSeg.text) fetchSegmentAudio(nextIdx, nextSeg.text);
      return;
    }

    setLoadingNext(true);
    setError("");
    try {
      const data: NextSegmentResponse = await nextSegment(storyId);
      setNextSegmentContent(data.current_segment);
      pendingNext.current = {
        index: data.current_index,
        hasInteraction: data.has_interaction,
        status: data.status,
      };
      setIsFlipping(true);
      if (data.current_segment?.text) fetchSegmentAudio(data.current_index, data.current_segment.text);
      if (data.current_segment && !data.current_segment.image_url) {
        pollSegmentImage(data.current_index, 0);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载下一段失败");
      setLoadingNext(false);
    }
  }, [storyId, status, loadingNext, currentIndex, totalSegments, allSegments, pollSegmentImage, fetchSegmentAudio]);

  /** 上一页：仅在已有完整段落列表时可用（如从画廊打开），支持左右翻页浏览 */
  const goPrev = useCallback(() => {
    if (currentIndex <= 0 || !allSegments || isFlipping) return;
    const prevIdx = currentIndex - 1;
    const prevSeg = allSegments[prevIdx];
    setCurrentIndex(prevIdx);
    setCurrentSegment(prevSeg);
    setHasInteraction(!!prevSeg?.interaction_point);
    setStatus(
      prevIdx >= totalSegments - 1 ? "completed" : prevSeg?.interaction_point ? "waiting_interaction" : "narrating"
    );
    if (prevSeg?.text) fetchSegmentAudio(prevIdx, prevSeg.text);
  }, [currentIndex, allSegments, isFlipping, totalSegments, fetchSegmentAudio]);

  const handleInteract = useCallback(
    async (userInput: string) => {
      if (!currentSegment?.interaction_point || loadingInteract) return;
      setLoadingInteract(true);
      setError("");
      try {
        const data: InteractResponse = await submitInteraction(
          storyId,
          currentIndex,
          currentSegment.interaction_point.type,
          userInput
        );
        setFeedback(data.feedback);
        setTotalSegments((prev) => prev + (data.new_segments?.length ?? 0));
        setCurrentIndex(data.current_index);
        setCurrentSegment(data.current_segment);
        setHasInteraction(data.has_interaction);
        setStatus(data.status);
        // 互动反馈先不强制走 TTS（文本可能很短且变化快）；主要段落朗读会使用选定音色
        if (!data.current_segment?.image_url) {
          pollSegmentImage(data.current_index, 0);
        }
        setTimeout(() => {
          setFeedback(null);
          if (data.current_segment?.text) {
            fetchSegmentAudio(data.current_index, data.current_segment.text);
          }
        }, 500);
      } catch (e) {
        setError(e instanceof Error ? e.message : "提交失败");
      } finally {
        setLoadingInteract(false);
      }
    },
    [storyId, currentIndex, currentSegment, loadingInteract, pollSegmentImage, fetchSegmentAudio]
  );

  useEffect(() => {
    if (initialData.current_segment?.text && !hasInteraction) {
      fetchSegmentAudio(initialData.current_index, initialData.current_segment.text);
    }
    return () => {};
  }, []);

  // 关键：当用户切换音色/倍速时，让“当前页”的朗读也立刻生效（重新拉取对应音频）
  useEffect(() => {
    if (!currentSegment?.text || showInteraction) return;
    fetchSegmentAudio(currentIndex, currentSegment.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedVoiceId, playbackSpeed]);

  // 当前页无互动且非本地模式时，后台预生成下一页插画，翻页时直接加载
  useEffect(() => {
    if (allSegments || hasInteraction || status === "completed" || loadingNext) return;
    const nextIdx = currentIndex + 1;
    if (nextIdx >= totalSegments) return;
    preloadSegmentImage(storyId, nextIdx).catch(() => {});
  }, [storyId, currentIndex, totalSegments, hasInteraction, status, allSegments, loadingNext]);

  // 画廊浏览模式（有完整段落）不支持交互，避免改变已完成的故事内容
  const showInteraction = !!(
    hasInteraction &&
    currentSegment?.interaction_point &&
    !feedback &&
    !allSegments  // 只有新生成的故事才支持交互
  );

  const handleBookTap = () => {
    if (showInteraction || status === "completed" || loadingNext || loadingInteract) return;
    goNext();
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    const endX = e.changedTouches[0].clientX;
    const delta = touchStartX.current - endX;
    if (delta > 60 && !showInteraction && status !== "completed" && !loadingNext) {
      goNext();
    } else if (delta < -60 && !showInteraction && !loadingNext && allSegments && currentIndex > 0) {
      goPrev();
    }
  };

  return (
    <main className="min-h-screen flex flex-col bg-[#f5ebe0]">
      <header className="flex items-center justify-between px-4 py-3 border-b border-amber-900/20 bg-amber-50/80">
        <button onClick={onBack} className="text-amber-900 font-medium">
          ← 返回
        </button>
        <h1 className="text-lg font-bold text-amber-900 truncate max-w-[40%]">
          {title}
        </h1>
        <VideoGenerator
          storyId={storyId}
          storyTitle={title}
          isStoryCompleted={status === "completed"}
          totalSegments={totalSegments}
        />
      </header>

      {/* 书籍主体：左图右文，点击/左滑翻页 */}
      <section
        className="flex-1 flex min-h-0 p-3 md:p-6"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <div className="flex-1 flex max-w-5xl mx-auto w-full rounded-2xl overflow-hidden shadow-2xl border border-amber-200 bg-amber-50/90 min-h-[320px]">
          {/* 左页：插画 */}
          <div className="w-1/2 min-w-0 flex flex-col border-r-2 border-amber-200/80 rounded-l-2xl overflow-hidden bg-gradient-to-br from-amber-100/50 to-orange-100/30">
            <div className="flex-1 min-h-[200px] flex items-center justify-center p-2">
              <ImageDisplay imageUrl={currentSegment?.image_url} />
            </div>
          </div>

          {/* 右页：故事文字（带翻页效果） */}
          <div className="w-1/2 min-w-0 flex flex-col relative rounded-r-2xl overflow-hidden bg-[#fefcf8]">
            <div
              className="flex-1 flex flex-col p-4 cursor-pointer select-none min-h-0"
              style={{ perspective: "1200px" }}
              onClick={handleBookTap}
            >
              <div className="flex-1 min-h-0 overflow-hidden relative" style={{ transformStyle: "preserve-3d" }}>
                <motion.div
                  className="absolute inset-0 flex flex-col"
                  animate={{ rotateY: isFlipping ? -180 : 0 }}
                  transition={{
                    duration: isFlipping ? 0.55 : 0,
                    ease: [0.33, 0.66, 0.33, 1],
                  }}
                  style={{ transformStyle: "preserve-3d" }}
                  onAnimationComplete={() => {
                    if (!isFlipping || !nextSegmentContent) return;
                    const pending = pendingNext.current;
                    setCurrentSegment(nextSegmentContent);
                    setNextSegmentContent(null);
                    if (pending) {
                      setCurrentIndex(pending.index);
                      setHasInteraction(pending.hasInteraction);
                      setStatus(pending.status);
                      pendingNext.current = null;
                    }
                    setLoadingNext(false);
                    setIsFlipping(false);
                  }}
                >
                  {/* 正面：当前段文字 */}
                  <div
                    className="absolute inset-0 p-4 flex flex-col bg-[#fefcf8] overflow-y-auto"
                    style={{ backfaceVisibility: "hidden" }}
                  >
                    <AnimatePresence mode="wait">
                      {feedback ? (
                        <motion.p
                          key="fb"
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="text-amber-800 font-medium"
                        >
                          ✨ {feedback}
                        </motion.p>
                      ) : (
                        <TextDisplay key="text" text={currentSegment?.text ?? ""} />
                      )}
                    </AnimatePresence>
                    {!showInteraction && status !== "completed" && !loadingNext && (
                      <p className="mt-auto pt-2 text-amber-700/70 text-sm">
                        {allSegments && currentIndex > 0 ? "← 左滑上一页 · 右滑下一页 →" : "点击或左滑下一页 →"}
                      </p>
                    )}
                  </div>
                  {/* 背面：下一页内容（翻页时显示） */}
                  <div
                    className="absolute inset-0 p-4 flex flex-col bg-[#fefcf8] overflow-y-auto"
                    style={{
                      backfaceVisibility: "hidden",
                      transform: "rotateY(180deg)",
                    }}
                  >
                    {nextSegmentContent ? (
                      <TextDisplay text={nextSegmentContent.text} />
                    ) : (
                      <span className="text-amber-700/60">加载中…</span>
                    )}
                  </div>
                </motion.div>
              </div>
            </div>

            {/* 页码与互动区（不参与翻页） */}
            <div className="border-t border-amber-200/80 p-3 bg-amber-50/50 rounded-br-2xl">
              {error && <p className="text-red-600 text-sm mb-2">{error}</p>}
              <InteractionPanel
                visible={showInteraction}
                interactionPoint={currentSegment?.interaction_point}
                onSubmit={handleInteract}
                loading={loadingInteract}
              />

              {/* 朗读音频（edge-tts，按所选音色生成） */}
              {!showInteraction && (
                <div className="mt-3">
                  {audioError && (
                    <p className="text-amber-700/80 text-xs mb-2">
                      朗读音频生成失败：{audioError}
                    </p>
                  )}
                  {audioLoading && (
                    <p className="text-amber-700/70 text-sm">正在生成朗读音频…</p>
                  )}
                  {segmentAudioUrl && !audioLoading && (
                    <AudioPlayer audioUrl={segmentAudioUrl} autoPlay className="bg-amber-50/80" />
                  )}
                </div>
              )}
              {/* 翻页按钮：有完整段落时（画廊打开）总是显示，否则仅在未完成且无互动时显示 */}
              {!showInteraction && (allSegments || status !== "completed") && (
                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      goPrev();
                    }}
                    disabled={!allSegments || currentIndex <= 0 || isFlipping}
                    className="p-2 rounded-xl text-amber-700 hover:bg-amber-200/60 disabled:opacity-40 disabled:pointer-events-none"
                    title="上一页"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    </svg>
                  </button>
                  <span className="text-amber-800/70 text-sm flex-shrink-0">
                    {currentIndex + 1} / {totalSegments}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      goNext();
                    }}
                    disabled={!allSegments ? (loadingNext || audioLoading) : (currentIndex >= totalSegments - 1 || isFlipping)}
                    className="p-2 rounded-xl bg-amber-600 text-white font-medium shadow hover:bg-amber-700 disabled:opacity-50"
                    title="下一页"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              )}
              {/* "故事讲完"提示：仅在没有完整段落且已完成时显示 */}
              {status === "completed" && !allSegments && (
                <p className="text-center text-amber-800 font-medium py-1">
                  🎉 故事讲完啦！晚安，做个好梦哦～
                </p>
              )}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
