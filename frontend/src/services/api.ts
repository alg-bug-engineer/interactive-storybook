// API 基础 URL 配置
// - 开发环境: 直接访问 localhost:1001
// - 生产环境: 使用相对路径 /api，通过 Next.js rewrites 和 Nginx 代理到后端
const isBrowser = typeof window !== 'undefined';

// 在浏览器环境且未配置自定义 API URL 时，使用相对路径
// 这样请求会通过 Next.js rewrites -> Nginx -> 后端
const getApiUrl = () => {
  // 如果显式配置了 API URL，优先使用
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
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

async function readErrorMessage(res: Response): Promise<string> {
  const text = await res.text();
  if (!text) return `请求失败 (${res.status})`;
  try {
    const data = JSON.parse(text);
    return data?.detail || data?.message || text;
  } catch {
    return text;
  }
}

function normalizeRequestError(error: unknown): Error {
  if (error instanceof Error) {
    if (/Failed to fetch|NetworkError|fetch failed|ECONNREFUSED/i.test(error.message)) {
      return new Error(
        "无法连接后端服务（http://localhost:1001）。请先启动后端：cd backend && pip install -r requirements.txt && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 1001"
      );
    }
    return error;
  }
  return new Error("请求失败，请稍后重试");
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  try {
    const res = await fetch(url, init);
    if (!res.ok) throw new Error(await readErrorMessage(res));
    return (await res.json()) as T;
  } catch (error) {
    throw normalizeRequestError(error);
  }
}

async function requestVoid(url: string, init?: RequestInit): Promise<void> {
  try {
    const res = await fetch(url, init);
    if (!res.ok) throw new Error(await readErrorMessage(res));
  } catch (error) {
    throw normalizeRequestError(error);
  }
}

/** 带认证的请求头（用于需登录的接口） */
function authHeaders(token: string | null): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  if (token) (h as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  return h;
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
  return requestJson(`${getApiUrl()}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function login(
  email: string,
  password: string
): Promise<{ token: string; user: AuthUser }> {
  return requestJson(`${getApiUrl()}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchMe(token: string): Promise<AuthUser> {
  return requestJson(`${getApiUrl()}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function logoutApi(token: string): Promise<void> {
  await requestVoid(`${getApiUrl()}/api/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function upgradeToPaid(token: string): Promise<AuthUser> {
  const data = await requestJson<{ user: AuthUser }>(`${getApiUrl()}/api/auth/upgrade`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
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
  return requestJson(`${getApiUrl()}/api/story/start`, {
    method: "POST",
    headers: authHeaders(token ?? null),
    body: JSON.stringify(body),
  });
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
  const data = await requestJson<{ styles?: StoryStyle[] }>(`${getApiUrl()}/api/story/styles`);
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
  const data = await requestJson<{ stories?: StoryGalleryItem[] }>(`${getApiUrl()}/api/story/list`);
  return data.stories ?? [];
}

export async function getStory(storyId: string): Promise<StoryStateResponse> {
  return requestJson(`${getApiUrl()}/api/story/${storyId}`);
}

export async function nextSegment(
  storyId: string,
  token?: string | null
): Promise<NextSegmentResponse> {
  return requestJson(`${getApiUrl()}/api/story/${storyId}/next`, {
    method: "POST",
    headers: authHeaders(token ?? null),
  });
}

export async function getSegmentAudio(
  storyId: string,
  segmentIndex: number,
  voiceId?: string | null,
  speed?: number,
  token?: string | null
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
  return requestJson(`${getApiUrl()}/api/story/${storyId}/segment/${segmentIndex}/audio${qs ? `?${qs}` : ""}`, {
    headers: authHeaders(token ?? null),
  });
}

export async function submitInteraction(
  storyId: string,
  segmentIndex: number,
  interactionType: string,
  userInput: string,
  token?: string | null
): Promise<InteractResponse> {
  return requestJson(`${getApiUrl()}/api/story/interact`, {
    method: "POST",
    headers: authHeaders(token ?? null),
    body: JSON.stringify({
      story_id: storyId,
      segment_index: segmentIndex,
      interaction_type: interactionType,
      user_input: userInput,
    }),
  });
}

export async function checkSegmentImage(
  storyId: string,
  segmentIndex: number
): Promise<{ story_id: string; segment_index: number; image_url: string | null; has_image: boolean }> {
  return requestJson(`${getApiUrl()}/api/story/${storyId}/segment/${segmentIndex}/image`);
}

/** 后台预生成指定段落插画，当前页无互动时调用以优化翻页加载 */
export async function preloadSegmentImage(
  storyId: string,
  segmentIndex: number,
  token?: string | null
): Promise<{ ok: boolean; preloading: boolean }> {
  return requestJson(`${getApiUrl()}/api/story/${storyId}/preload-segment/${segmentIndex}`, {
    method: "POST",
    headers: authHeaders(token ?? null),
  });
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
  enableAudio: boolean = true
): Promise<{ message: string; story_id: string; status: string }> {
  return requestJson(`${getApiUrl()}/api/video/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      story_id: storyId,
      enable_audio: enableAudio,
    }),
  });
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
  return requestJson(`${getApiUrl()}/api/video/status/${storyId}`);
}

export function getVideoDownloadUrl(storyId: string): string {
  return `${getApiUrl()}/api/video/download/${storyId}`;
}

export async function getVideoClips(storyId: string): Promise<{
  story_id: string;
  video_clips: Record<string, string>;
  total_clips: number;
}> {
  return requestJson(`${getApiUrl()}/api/video/clips/${storyId}`);
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
  provider?: "edge" | "volcano";
  tier?: "free" | "premium";
}

export async function listVoices(token?: string | null): Promise<{
  voices: Voice[];
  default_voice_id: string;
  tts_available: boolean;
  tier?: "free" | "premium";
}> {
  return requestJson(`${getApiUrl()}/api/voices/list`, {
    headers: authHeaders(token ?? null),
  });
}

export async function getRecommendedVoices(token?: string | null): Promise<{
  voices: Voice[];
  default_voice_id: string;
}> {
  return requestJson(`${getApiUrl()}/api/voices/recommended`, {
    headers: authHeaders(token ?? null),
  });
}

export async function previewVoice(voiceId: string): Promise<{
  voice_id: string;
  audio_url: string;
  voice_info: Voice;
}> {
  return requestJson(`${getApiUrl()}/api/voices/preview/${voiceId}`);
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
  return requestJson(`${getApiUrl()}/api/voices/preferences`, {
    method: "POST",
    headers: authHeaders(token ?? null),
    body: JSON.stringify(preferences),
  });
}

export async function getVoicePreferences(
  token?: string | null
): Promise<{
  preferred_voice: string;
  playback_speed: number;
}> {
  return requestJson(`${getApiUrl()}/api/voices/preferences`, {
    headers: authHeaders(token ?? null),
  });
}

export function getAudioUrl(path: string): string {
  return `${getApiUrl()}/api/audio/${path}`;
}
