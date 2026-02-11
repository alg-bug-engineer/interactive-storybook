"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  startStory,
  getStory,
  listStories,
  fetchMe,
  logoutApi,
  type StoryStartResponse,
  type StoryStateResponse,
  type StoryGalleryItem,
} from "@/services/api";
import StoryScreen from "@/components/StoryScreen";
import AuthModal from "@/components/AuthModal";
import VoiceSelector from "@/components/VoiceSelector";
import StyleSelector from "@/components/StyleSelector";
import { useAuthStore } from "@/stores/authStore";
import { useVoiceStore } from "@/stores/voiceStore";

const GALLERY_VISIBLE_INITIAL = 6;

function stateToStartResponse(state: StoryStateResponse): StoryStartResponse {
  return {
    story_id: state.story_id,
    title: state.title,
    theme: state.theme,
    characters: state.characters,
    setting: state.setting,
    total_segments: state.total_segments,
    current_index: state.current_index,
    current_segment: state.current_segment,
    has_interaction: state.has_interaction,
    status: state.status,
    segments: state.segments,
    style_id: state.style_id,
  };
}

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [story, setStory] = useState<StoryStartResponse | null>(null);
  const [themeInput, setThemeInput] = useState("");
  const [pageCountInput, setPageCountInput] = useState("");
  const [gallery, setGallery] = useState<StoryGalleryItem[]>([]);
  const [galleryExpanded, setGalleryExpanded] = useState(false);
  const [loadingGallery, setLoadingGallery] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState<"login" | "register">("login");
  const [voiceSelectorOpen, setVoiceSelectorOpen] = useState(false);
  const [selectedStyleId, setSelectedStyleId] = useState<string | null>(null);

  const { token, user, setAuth, logout, loadFromStorage, setUser } = useAuthStore();
  const { loadVoices, loadPreferences, getSelectedVoice } = useVoiceStore();

  useEffect(() => {
    loadFromStorage();
    // 加载音色列表
    loadVoices();
  }, [loadFromStorage, loadVoices]);

  useEffect(() => {
    if (token && !user) {
      fetchMe(token)
        .then(setUser)
        .catch(() => logout());
    }
  }, [token, user, setUser, logout]);

  // 登录后加载用户音色偏好
  useEffect(() => {
    if (token) {
      loadPreferences(token);
    }
  }, [token, loadPreferences]);

  const loadGallery = useCallback(async () => {
    setLoadingGallery(true);
    try {
      const list = await listStories();
      setGallery(list);
    } catch {
      setGallery([]);
    } finally {
      setLoadingGallery(false);
    }
  }, []);

  useEffect(() => {
    loadGallery();
  }, [loadGallery]);

  async function handleStartWithTheme(theme: string | null) {
    if (!user || !token) {
      setAuthModalOpen(true);
      return;
    }
    const totalPages = pageCountInput.trim() ? parseInt(pageCountInput.trim(), 10) : undefined;
    if (totalPages !== undefined) {
      if (Number.isNaN(totalPages) || totalPages < 1) {
        setError("请输入有效的页数（留空则随机）");
        return;
      }
      if (totalPages < 3) {
        alert("故事太短了，至少需要 3 页哦～");
        return;
      }
      if (totalPages > 7) {
        alert("故事最长 7 页哦～请输入 3-7 之间的数字");
        return;
      }
    }
    setLoading(true);
    setError("");
    try {
      const data = await startStory(theme, token, totalPages, selectedStyleId);
      setStory(data);
      await loadGallery();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "生成故事失败，请稍后再试";
      if (msg.includes("登录") || msg.includes("401")) {
        logout();
        setAuthModalOpen(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  function handleSubmitTheme() {
    const t = themeInput.trim();
    handleStartWithTheme(t || null);
  }

  function handleRandomStory() {
    setThemeInput("");
    handleStartWithTheme(null);
  }

  async function handleLogout() {
    if (token) await logoutApi(token).catch(() => {});
    logout();
  }

  async function handleOpenFromGallery(storyId: string) {
    setError("");
    try {
      const state = await getStory(storyId);
      // 画廊打开时默认从第一页开始，便于浏览历史内容
      const firstSegment = state.segments?.[0] ?? null;
      setStory(
        stateToStartResponse({
          ...state,
          current_index: 0,
          current_segment: firstSegment,
        })
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载故事失败");
    }
  }

  if (story) {
    return (
      <StoryScreen
        initialData={story}
        onBack={() => setStory(null)}
      />
    );
  }

  const visibleGallery = galleryExpanded ? gallery : gallery.slice(0, GALLERY_VISIBLE_INITIAL);
  const hasMoreGallery = gallery.length > GALLERY_VISIBLE_INITIAL;

  const selectedVoice = getSelectedVoice();

  return (
    <main 
      className="min-h-screen flex flex-col items-center p-6 pb-12"
      style={{
        background: 'linear-gradient(135deg, #8b7355 0%, #a0826d 50%, #8b7355 100%)',
      }}
    >
      {/* 顶部：登录/注册 或 用户信息 */}
      <header className="absolute top-0 right-0 p-4 flex items-center gap-3">
        {/* 音色选择按钮 */}
        <button
          type="button"
          onClick={() => setVoiceSelectorOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white border-2 border-primary/30 rounded-lg hover:border-primary/50 transition-colors text-sm"
          title="选择朗读音色"
        >
          <span>🎙️</span>
          <span className="hidden sm:inline text-text-ui">
            {selectedVoice ? selectedVoice.name : "音色"}
          </span>
        </button>

        {user ? (
          <>
            <span className="text-text-ui text-sm truncate max-w-[120px]" title={user.email}>
              {user.email}
            </span>
            {user.is_paid && (
              <span className="text-xs bg-amber-200 text-amber-900 px-2 py-0.5 rounded">付费用户</span>
            )}
            <button
              type="button"
              onClick={handleLogout}
              className="text-sm text-primary hover:underline"
            >
              退出
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => { setAuthModalTab("login"); setAuthModalOpen(true); }}
              className="text-sm text-primary font-medium hover:underline"
            >
              登录
            </button>
            <button
              type="button"
              onClick={() => { setAuthModalTab("register"); setAuthModalOpen(true); }}
              className="text-sm text-secondary font-medium hover:underline"
            >
              注册
            </button>
          </>
        )}
      </header>

      <AuthModal
        open={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        defaultTab={authModalTab}
      />

      {/* 音色选择器模态框 */}
      <AnimatePresence>
        {voiceSelectorOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={() => setVoiceSelectorOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <VoiceSelector onClose={() => setVoiceSelectorOpen(false)} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center max-w-lg w-full relative"
        style={{
          background: 'linear-gradient(135deg, #f8f3ed 0%, #fffef9 50%, #f5ebe0 100%)',
          padding: '3rem 2.5rem',
          borderRadius: '1rem',
          boxShadow: '0 20px 60px rgba(0,0,0,0.4), inset 0 0 0 1px rgba(255,255,255,0.5), inset 0 0 30px rgba(139,69,19,0.1)',
          border: '3px solid #8b7355',
        }}
      >
        {/* 书籍装饰纹理 */}
        <div 
          className="absolute inset-0 opacity-[0.02] pointer-events-none rounded-lg"
          style={{
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(139,69,19,0.3) 2px, rgba(139,69,19,0.3) 4px)',
          }}
        />
        
        {/* 书脊装饰 */}
        <div 
          className="absolute top-0 left-3 bottom-0 w-1 opacity-30"
          style={{
            background: 'linear-gradient(to bottom, #8b7355, #a0826d, #8b7355)',
          }}
        />
        <div 
          className="absolute top-0 right-3 bottom-0 w-1 opacity-30"
          style={{
            background: 'linear-gradient(to bottom, #8b7355, #a0826d, #8b7355)',
          }}
        />
        
        <h1 
          className="text-4xl font-bold mb-2 relative z-10"
          style={{
            color: '#6b4423',
            textShadow: '2px 2px 4px rgba(139,69,19,0.2)',
          }}
        >
          🌟 有声互动故事书
        </h1>
        <p 
          className="mb-6 relative z-10 text-lg"
          style={{ color: '#8b6f47' }}
        >
          听故事、看画面、一起玩——每次都是新故事
        </p>

        {/* 风格选择器 */}
        <div className="relative z-10">
          <StyleSelector
            selectedStyleId={selectedStyleId}
            onSelectStyle={setSelectedStyleId}
          />
        </div>

        {/* 主题输入框 + 页码(可选) + 向右箭头确认 */}
        <div className="flex items-center gap-2 mb-3 relative z-10">
          <input
            type="text"
            value={themeInput}
            onChange={(e) => setThemeInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmitTheme()}
            placeholder="输入故事主题，如：龟兔赛跑、小兔子找妈妈"
            className="flex-1 min-w-0 px-4 py-3 rounded-story-md border-2 bg-white/90 placeholder:text-text-ui/60 focus:outline-none"
            style={{
              borderColor: '#a0826d',
              boxShadow: 'inset 2px 2px 5px rgba(139,69,19,0.1)',
            }}
            disabled={loading}
          />
          <input
            type="number"
            min={3}
            max={7}
            value={pageCountInput}
            onChange={(e) => setPageCountInput(e.target.value.replace(/[^0-9]/g, ""))}
            onKeyDown={(e) => e.key === "Enter" && handleSubmitTheme()}
            placeholder="页数"
            title="留空则随机页数（3-7页）；填 5-7 为固定页数且带互动；填 3-4 为固定页数无互动"
            className="w-14 px-2 py-3 rounded-story-md border-2 bg-white/90 placeholder:text-text-ui/60 focus:outline-none text-center [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            style={{
              borderColor: '#a0826d',
              boxShadow: 'inset 2px 2px 5px rgba(139,69,19,0.1)',
            }}
            disabled={loading}
          />
          <button
            onClick={handleSubmitTheme}
            disabled={loading}
            className="flex-shrink-0 w-12 h-12 rounded-story-md text-white flex items-center justify-center hover:opacity-90 disabled:opacity-60 transition"
            style={{
              background: 'linear-gradient(135deg, #8b7355 0%, #a0826d 100%)',
              boxShadow: '0 4px 12px rgba(139,69,19,0.3)',
            }}
            title="根据主题生成故事"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
        </div>

        {/* 随机一个故事 */}
        <button
          onClick={handleRandomStory}
          disabled={loading}
          className="w-full py-3 rounded-story-md border-2 font-medium hover:opacity-90 disabled:opacity-60 transition mb-8 relative z-10"
          style={{
            borderColor: '#a0826d',
            color: '#6b4423',
            background: 'linear-gradient(to bottom, rgba(255,255,255,0.5), rgba(248,243,237,0.8))',
            boxShadow: '0 4px 12px rgba(139,69,19,0.2), inset 0 1px 2px rgba(255,255,255,0.8)',
          }}
        >
          {loading ? "正在生成故事和插画…" : "🎲 随机一个故事"}
        </button>

        {error && (
          <p className="mb-4 text-red-600 text-sm relative z-10 font-medium">{error}</p>
        )}
      </motion.div>

      {/* 画廊：生成的故事书列表 - 书架效果 */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="w-full max-w-4xl mt-8 p-6 rounded-xl"
        style={{
          background: 'linear-gradient(to bottom, #6b5444 0%, #8b7355 50%, #6b5444 100%)',
          boxShadow: '0 10px 40px rgba(0,0,0,0.5), inset 0 0 20px rgba(0,0,0,0.2)',
        }}
      >
        <h2 
          className="text-lg font-bold mb-3"
          style={{
            color: '#f5ebe0',
            textShadow: '2px 2px 4px rgba(0,0,0,0.3)',
          }}
        >
          📚 我的故事画廊
        </h2>
        {loadingGallery ? (
          <p className="text-sm" style={{ color: '#f5ebe0' }}>加载中…</p>
        ) : gallery.length === 0 ? (
          <p className="text-sm" style={{ color: '#f5ebe0' }}>还没有故事，去上面创建一个吧～</p>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {visibleGallery.map((item) => (
                <button
                  key={item.story_id}
                  onClick={() => handleOpenFromGallery(item.story_id)}
                  className="rounded-story-md overflow-hidden border-2 bg-white shadow hover:shadow-lg transition text-left transform hover:scale-105"
                  style={{
                    borderColor: '#a0826d',
                    boxShadow: '0 8px 20px rgba(0,0,0,0.4)',
                    background: 'linear-gradient(135deg, #fffef9 0%, #f8f3ed 100%)',
                  }}
                >
                  <div className="aspect-[4/3] bg-bg-main flex items-center justify-center">
                    {item.cover_url ? (
                      <img
                        src={item.cover_url}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="text-text-ui/60 text-sm">暂无封面</span>
                    )}
                  </div>
                  <div className="p-2">
                    <p className="font-medium text-text-story truncate text-sm" title={item.title}>
                      {item.title}
                    </p>
                    {item.theme && (
                      <p className="text-text-ui text-xs truncate" title={item.theme}>
                        {item.theme}
                      </p>
                    )}
                  </div>
                </button>
              ))}
            </div>
            {hasMoreGallery && (
              <button
                onClick={() => setGalleryExpanded((e) => !e)}
                className="mt-3 font-medium text-sm hover:underline"
                style={{ color: '#f5ebe0' }}
              >
                {galleryExpanded ? "收起" : `展开更多（共 ${gallery.length} 个）`}
              </button>
            )}
          </>
        )}
      </motion.section>
    </main>
  );
}
