// API 基础 URL 配置
// - 开发环境: 直接访问 localhost:1001
// - 生产环境: 使用相对路径 /api，通过 Next.js rewrites 和 Nginx 代理到后端
const isBrowser = typeof window !== 'undefined';

// 在浏览器环境且未配置自定义 API URL 时，使用相对路径
// 这样请求会通过 Next.js rewrites -> Nginx -> 后端
export const getApiUrl = () => {
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  // 如果显式配置了 API URL，优先使用（但避免生产环境误配到 localhost）
  if (raw) {
    if (isBrowser) {
      try {
        const u = new URL(raw, window.location.href);
        const isLocalhost =
          u.hostname === "localhost" ||
          u.hostname === "127.0.0.1" ||
          u.hostname === "0.0.0.0";
        const isProdHost =
          window.location.hostname !== "localhost" &&
          window.location.hostname !== "127.0.0.1";
        if (isProdHost && isLocalhost) {
          // 生产域名下不应该请求用户本机的 localhost，回退为同源相对路径
          return "";
        }
      } catch {
        // ignore invalid URL and continue
      }
    }
    return raw;
  }
  
  // 浏览器端使用相对路径（通过代理）
  if (isBrowser) {
    // 在生产环境或未知环境，使用空字符串表示相对路径
    // Next.js rewrites 会处理 /api/* 请求
    return '';
  }
  
  // 服务端渲染时（开发环境）
  return 'http://localhost:1001';
};

/** 带认证的请求头（用于需登录的接口） */
function authHeaders(token: string | null): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  if (token) (h as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  return h;
}

function resolvePublicUrl(pathOrUrl: string): string {
  if (!pathOrUrl) return pathOrUrl;
  // 后端有时返回完整 URL，直接使用
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  // 其余情况视为相对路径（通常以 /api/... 开头）
  return `${getApiUrl()}${pathOrUrl}`;
}

// ========== 认证 API ==========

export interface AuthUser {
  email: string;
  is_paid: boolean;
  created_at?: string;
}

export async function register(
  email: string,
  password: string
): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch(`${getApiUrl()}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function login(
  email: string,
  password: string
): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch(`${getApiUrl()}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchMe(token: string): Promise<AuthUser> {
  const res = await fetch(`${getApiUrl()}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function logoutApi(token: string): Promise<void> {
  await fetch(`${getApiUrl()}/api/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function upgradeToPaid(token: string): Promise<AuthUser> {
  const res = await fetch(`${getApiUrl()}/api/auth/upgrade`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.user;
}

/** 开始故事（需登录，传入 token）。theme 为空或省略则随机；total_pages 指定则生成固定页数（3–4 页无互动，5 页及以上带互动）；style_id 指定故事风格。 */
export async function startStory(
  theme?: string | null,
  token?: string | null,
  totalPages?: number,
  styleId?: string | null
): Promise<StoryStartResponse> {
  const body: { theme?: string; total_pages?: number; style_id?: string } = {};
  if (theme) body.theme = theme;
  if (totalPages !== undefined && totalPages >= 3) body.total_pages = totalPages;
  if (styleId) body.style_id = styleId;
  const res = await fetch(`${getApiUrl()}/api/story/start`, {
    method: "POST",
    headers: authHeaders(token ?? null),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 故事风格定义 */
export interface StoryStyle {
  id: string;
  name: string;
  description: string;
  suitable_for: string;
  prompt: string;
}

/** 获取所有可用的故事风格列表 */
export async function listStoryStyles(): Promise<StoryStyle[]> {
  const res = await fetch(`${getApiUrl()}/api/story/styles`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.styles ?? [];
}

/** 画廊：获取所有故事摘要列表（按创建时间倒序） */
export interface StoryGalleryItem {
  story_id: string;
  title: string;
  theme: string;
  cover_url: string | null;
  total_segments: number;
}

export async function listStories(): Promise<StoryGalleryItem[]> {
  const res = await fetch(`${getApiUrl()}/api/story/list`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.stories ?? [];
}

export async function getStory(storyId: string): Promise<StoryStateResponse> {
  const res = await fetch(`${getApiUrl()}/api/story/${storyId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function nextSegment(storyId: string): Promise<NextSegmentResponse> {
  const res = await fetch(`${getApiUrl()}/api/story/${storyId}/next`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSegmentAudio(
  storyId: string,
  segmentIndex: number,
  voiceId?: string | null,
  speed?: number
): Promise<{
  story_id: string;
  segment_index: number;
  voice_id: string;
  speed: number;
  audio_path: string;
  audio_url: string; // 后端返回的相对 URL，如 /api/audio/data/audio/tts/xxx.mp3
}> {
  const params = new URLSearchParams();
  if (voiceId) params.set("voice_id", voiceId);
  if (typeof speed === "number") params.set("speed", String(speed));
  const qs = params.toString();
  const res = await fetch(
    `${getApiUrl()}/api/story/${storyId}/segment/${segmentIndex}/audio${qs ? `?${qs}` : ""}`
  );
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  if (data?.audio_url) data.audio_url = resolvePublicUrl(data.audio_url);
  return data;
}

export async function submitInteraction(
  storyId: string,
  segmentIndex: number,
  interactionType: string,
  userInput: string
): Promise<InteractResponse> {
  const res = await fetch(`${getApiUrl()}/api/story/interact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      story_id: storyId,
      segment_index: segmentIndex,
      interaction_type: interactionType,
      user_input: userInput,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function checkSegmentImage(
  storyId: string,
  segmentIndex: number
): Promise<{ story_id: string; segment_index: number; image_url: string | null; has_image: boolean }> {
  const res = await fetch(`${getApiUrl()}/api/story/${storyId}/segment/${segmentIndex}/image`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 后台预生成指定段落插画，当前页无互动时调用以优化翻页加载 */
export async function preloadSegmentImage(
  storyId: string,
  segmentIndex: number
): Promise<{ ok: boolean; preloading: boolean }> {
  const res = await fetch(`${getApiUrl()}/api/story/${storyId}/preload-segment/${segmentIndex}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface StoryStartResponse {
  story_id: string;
  title: string;
  theme: string;
  characters: { name: string; species: string; trait: string; appearance: string }[];
  setting: { location: string; time: string; weather: string; visual_description: string };
  total_segments: number;
  current_index: number;
  current_segment: StorySegmentResponse | null;
  has_interaction: boolean;
  status: string;
  style_id?: string;
  /** 完整段落列表（从画廊打开时带上，用于直接翻页无需请求） */
  segments?: StorySegmentResponse[];
}

export interface StorySegmentResponse {
  id?: string;
  text: string;
  scene_description: string;
  emotion: string;
  interaction_point?: { type: string; prompt: string; hints?: string[] } | null;
  image_url?: string | null;
}

export interface StoryStateResponse {
  story_id: string;
  title: string;
  theme: string;
  characters: { name: string; species: string; trait: string; appearance: string }[];
  setting: { location: string; time: string; weather: string; visual_description: string };
  segments?: StorySegmentResponse[];
  total_segments: number;
  current_index: number;
  current_segment: StorySegmentResponse | null;
  has_interaction: boolean;
  status: string;
  style_id?: string;
}

export interface NextSegmentResponse {
  story_id: string;
  current_index: number;
  current_segment: StorySegmentResponse | null;
  has_interaction: boolean;
  status: string;
}

export interface InteractResponse {
  feedback: string;
  new_segments: StorySegmentResponse[];
  current_index: number;
  current_segment: StorySegmentResponse | null;
  has_interaction: boolean;
  status: string;
}

// ========== 视频生成 API ==========

export async function generateVideo(
  storyId: string,
  enableAudio: boolean = false
): Promise<{ message: string; story_id: string; status: string }> {
  const res = await fetch(`${getApiUrl()}/api/video/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      story_id: storyId,
      enable_audio: enableAudio,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface VideoStatusResponse {
  story_id: string;
  status: string;
  progress: number;
  total_clips: number;
  generated_clips: number;
  video_url: string | null;
  error: string | null;
}

export async function getVideoStatus(storyId: string): Promise<VideoStatusResponse> {
  const res = await fetch(`${getApiUrl()}/api/video/status/${storyId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getVideoDownloadUrl(storyId: string): string {
  return `${getApiUrl()}/api/video/download/${storyId}`;
}

export async function getVideoClips(storyId: string): Promise<{
  story_id: string;
  video_clips: Record<string, string>;
  total_clips: number;
}> {
  const res = await fetch(`${getApiUrl()}/api/video/clips/${storyId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ========== 音色 API ==========

export interface Voice {
  id: string;
  name: string;
  gender: "male" | "female";
  description: string;
  tags: string[];
  recommended_for: string[];
  is_default: boolean;
  is_recommended: boolean;
}

export async function listVoices(): Promise<{
  voices: Voice[];
  default_voice_id: string;
  tts_available: boolean;
}> {
  const res = await fetch(`${getApiUrl()}/api/voices/list`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRecommendedVoices(): Promise<{
  voices: Voice[];
  default_voice_id: string;
}> {
  const res = await fetch(`${getApiUrl()}/api/voices/recommended`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function previewVoice(voiceId: string): Promise<{
  voice_id: string;
  audio_url: string;
  voice_info: Voice;
}> {
  const res = await fetch(`${getApiUrl()}/api/voices/preview/${voiceId}`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  if (data?.audio_url) data.audio_url = resolvePublicUrl(data.audio_url);
  return data;
}

export async function saveVoicePreferences(
  preferences: {
    preferred_voice?: string;
    playback_speed?: number;
  },
  token?: string | null
): Promise<{
  success: boolean;
  message: string;
  preferences: any;
}> {
  const res = await fetch(`${getApiUrl()}/api/voices/preferences`, {
    method: "POST",
    headers: authHeaders(token ?? null),
    body: JSON.stringify(preferences),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getVoicePreferences(
  token?: string | null
): Promise<{
  preferred_voice: string;
  playback_speed: number;
}> {
  const res = await fetch(`${getApiUrl()}/api/voices/preferences`, {
    headers: authHeaders(token ?? null),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getAudioUrl(path: string): string {
  return `${getApiUrl()}/api/audio/${path}`;
}
