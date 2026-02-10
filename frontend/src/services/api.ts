// 开发环境直接调用后端，生产环境可通过环境变量配置
// 注意：必须使用完整 URL，不能使用相对路径，否则 Next.js 会将其当作页面路由
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

// 确保 API 基础 URL 是完整的
if (!API.startsWith('http://') && !API.startsWith('https://')) {
  console.warn('API base URL should be a full URL, defaulting to http://localhost:8100');
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
  const res = await fetch(`${API}/api/auth/register`, {
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
  const res = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchMe(token: string): Promise<AuthUser> {
  const res = await fetch(`${API}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function logoutApi(token: string): Promise<void> {
  await fetch(`${API}/api/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function upgradeToPaid(token: string): Promise<AuthUser> {
  const res = await fetch(`${API}/api/auth/upgrade`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.user;
}

/** 开始故事（需登录，传入 token）。theme 为空或省略则随机一个儿童故事。 */
export async function startStory(
  theme?: string | null,
  token?: string | null
): Promise<StoryStartResponse> {
  const res = await fetch(`${API}/api/story/start`, {
    method: "POST",
    headers: authHeaders(token ?? null),
    body: JSON.stringify(theme ? { theme } : {}),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
  const res = await fetch(`${API}/api/story/list`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.stories ?? [];
}

export async function getStory(storyId: string): Promise<StoryStateResponse> {
  const res = await fetch(`${API}/api/story/${storyId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function nextSegment(storyId: string): Promise<NextSegmentResponse> {
  const res = await fetch(`${API}/api/story/${storyId}/next`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitInteraction(
  storyId: string,
  segmentIndex: number,
  interactionType: string,
  userInput: string
): Promise<InteractResponse> {
  const res = await fetch(`${API}/api/story/interact`, {
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
  const res = await fetch(`${API}/api/story/${storyId}/segment/${segmentIndex}/image`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 后台预生成指定段落插画，当前页无互动时调用以优化翻页加载 */
export async function preloadSegmentImage(
  storyId: string,
  segmentIndex: number
): Promise<{ ok: boolean; preloading: boolean }> {
  const res = await fetch(`${API}/api/story/${storyId}/preload-segment/${segmentIndex}`, {
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
  const res = await fetch(`${API}/api/video/generate`, {
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
  const res = await fetch(`${API}/api/video/status/${storyId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getVideoDownloadUrl(storyId: string): string {
  return `${API}/api/video/download/${storyId}`;
}

export async function getVideoClips(storyId: string): Promise<{
  story_id: string;
  video_clips: Record<string, string>;
  total_clips: number;
}> {
  const res = await fetch(`${API}/api/video/clips/${storyId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
