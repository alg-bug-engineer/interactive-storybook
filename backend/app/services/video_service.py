"""
视频生成服务：基于即梦 API 首尾帧视频生成功能
异步生成视频片段，最后合成完整的带音频故事视频

生成逻辑：
- 并发提交每批片段生成请求，最多同时 5 个在途任务
- 并发轮询每批在途任务，完成后释放槽位并继续提交剩余任务
- 付费用户支持浏览期预生成，点击“转视频”时优先复用预生成片段
- 最终按 segment_index 顺序拼接视频
"""
import asyncio
import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlparse
import httpx
from app.config import get_settings
from app.models.story import StorySegment
from app.utils.paths import IMAGES_DIR
from app.utils.url_utils import normalize_image_url
from app.utils.store import get_story, update_story

logger = logging.getLogger(__name__)

# 最大同时进行的视频生成任务数
MAX_CONCURRENT_VIDEO_TASKS = 5
# 轮询间隔（秒）
POLL_INTERVAL_SECONDS = 5
# 视频统一画幅
TARGET_VIDEO_WIDTH = 1024
TARGET_VIDEO_HEIGHT = 1024
# 预生成目录名
PREGENERATED_DIRNAME = "pregenerated"
# 网络图片缓存目录（固定在项目内，避免系统临时目录）
REMOTE_IMAGE_CACHE_DIR = IMAGES_DIR / "remote_downloads"
REMOTE_IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 视频生成状态存储（实际项目中应该用数据库）
_video_tasks: Dict[str, Dict] = {}
_pregen_inflight: set[Tuple[str, int]] = set()


async def _url_to_local_path(image_url: str) -> Optional[str]:
    """
    将图片URL转换为本地文件路径
    
    Args:
        image_url: 图片URL（可能是 http://localhost:1001/images/xxx.png）
    
    Returns:
        本地文件路径，如果找不到返回 None
    """
    try:
        normalized_url = normalize_image_url(image_url) or image_url

        # 如果已经是本地路径，直接返回
        if os.path.exists(normalized_url):
            logger.debug(f"[视频服务] 图片已是本地路径: {normalized_url}")
            return normalized_url
        
        # 如果是本地服务的URL，提取文件名并查找本地文件
        if normalized_url.startswith("/static/images/"):
            filename = os.path.basename(normalized_url)
            candidate = IMAGES_DIR / filename
            if candidate.exists():
                logger.info(f"[视频服务] 命中本地图片: {candidate}")
                return str(candidate.resolve())
            logger.error(f"[视频服务] 本地图片不存在: {candidate}")
        elif "localhost" in normalized_url or "127.0.0.1" in normalized_url:
            # 从URL提取文件名，例如: /images/xxx.png -> xxx.png
            filename = os.path.basename(normalized_url.split("?")[0])
            
            # 在统一图片目录查找
            possible_paths = [IMAGES_DIR / filename]
            
            for path in possible_paths:
                if path.exists():
                    logger.info(f"[视频服务] 找到本地图片文件: {path}")
                    return str(path.resolve())
            
            logger.error(f"[视频服务] 无法找到本地文件: {filename}")
            logger.error(f"[视频服务] 已尝试路径: {[str(p) for p in possible_paths]}")
        else:
            # 网络URL，下载到项目内固定缓存目录
            logger.info(f"[视频服务] 下载网络图片: {normalized_url[:80]}...")
            parsed = urlparse(normalized_url)
            suffix = os.path.splitext(parsed.path)[1].lower() or ".png"
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                suffix = ".png"
            file_hash = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:24]
            cached_file = REMOTE_IMAGE_CACHE_DIR / f"{file_hash}{suffix}"
            tmp_file = REMOTE_IMAGE_CACHE_DIR / f"{file_hash}{suffix}.part"
            if cached_file.exists() and cached_file.stat().st_size > 0:
                logger.info(f"[视频服务] 命中网络图片缓存: {cached_file}")
                return str(cached_file.resolve())
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                resp = await client.get(normalized_url)
                resp.raise_for_status()
                tmp_file.write_bytes(resp.content)
                tmp_file.replace(cached_file)
                logger.info(f"[视频服务] 图片已下载到固定目录: {cached_file}")
                return str(cached_file.resolve())
    
    except Exception as e:
        logger.error(f"[视频服务] 获取图片文件失败: {e}", exc_info=True)
    
    return None


class VideoGenerationStatus:
    """视频生成状态"""
    IDLE = "idle"
    GENERATING_CLIPS = "generating_clips"
    MERGING = "merging"
    ADDING_AUDIO = "adding_audio"
    COMPLETED = "completed"
    FAILED = "failed"

# 即梦视频模型与时长规则
# - 3.5-pro: duration 支持 5/10/12（当前主模型）
# - 3.0: duration 支持 5/10（兜底）
DEFAULT_VIDEO_MODEL = "jimeng-video-3.5-pro"
FALLBACK_VIDEO_MODEL = "jimeng-video-3.0"
MODEL_35_ALLOWED_DURATIONS = (5, 10, 12)
MODEL_30_ALLOWED_DURATIONS = (5, 10)
LONG_VIDEO_MAX_DURATION = max(MODEL_35_ALLOWED_DURATIONS)

# 首尾帧提交请求超时策略：
# connect/write 维持合理上限，read 放宽以适配服务端排队高峰，避免“已入队但本地误判超时”。
VIDEO_SUBMIT_CONNECT_TIMEOUT_SECONDS = 20.0
VIDEO_SUBMIT_WRITE_TIMEOUT_SECONDS = 120.0
VIDEO_SUBMIT_READ_TIMEOUT_SECONDS = 420.0
VIDEO_SUBMIT_POOL_TIMEOUT_SECONDS = 60.0


class JimengVideoApiError(ValueError):
    """即梦视频 API 错误（保留 code/message 便于策略分支）。"""

    def __init__(self, code: Any, message: str, result: dict | None = None):
        self.code = code
        self.message = message or ""
        self.result = result or {}
        super().__init__(f"即梦视频API错误 (code={code}): {self.message}")


class VideoSubmitTimeoutUncertainError(RuntimeError):
    """提交阶段读超时：请求可能已被服务端接收，但客户端未拿到响应。"""


def _nearest_allowed_duration(target: int, allowed: Tuple[int, ...]) -> int:
    return min(allowed, key=lambda x: (abs(x - target), x))


def _build_model_duration_plan(requested_duration: int) -> List[Tuple[str, int]]:
    """
    生成模型-时长尝试计划：
    1) 3.5-pro + 5/10/12 最近值
    2) 3.0 + 5/10 最近值
    """
    d = max(1, int(requested_duration))
    model35_duration = _nearest_allowed_duration(d, MODEL_35_ALLOWED_DURATIONS)
    model30_duration = _nearest_allowed_duration(d, MODEL_30_ALLOWED_DURATIONS)

    plan: List[Tuple[str, int]] = [
        (DEFAULT_VIDEO_MODEL, model35_duration),
        (FALLBACK_VIDEO_MODEL, model30_duration),
    ]
    # 去重（保序）
    seen = set()
    deduped: List[Tuple[str, int]] = []
    for item in plan:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _is_duration_invalid_error(err: JimengVideoApiError) -> bool:
    msg = (err.message or "").lower()
    return "duration invalid" in msg or "body.duration" in msg


def _is_model_invalid_error(err: JimengVideoApiError) -> bool:
    msg = (err.message or "").lower()
    return "model" in msg and ("invalid" in msg or "not support" in msg or "unsupported" in msg)


def _parse_video_submit_result(segment_index: int, result: dict) -> Dict[str, Any]:
    inner = result.get("data") or result
    if isinstance(inner, list) and len(inner) > 0:
        inner = inner[0]

    video_url = None
    if isinstance(inner, dict):
        video_url = inner.get("video_url") or inner.get("url")
    if not video_url:
        video_url = result.get("video_url")

    task_id = None
    if isinstance(inner, dict):
        task_id = inner.get("task_id") or inner.get("id") or inner.get("taskId")
    if not task_id:
        task_id = result.get("task_id") or result.get("id")

    if video_url:
        logger.info(f"[视频服务] 片段 {segment_index} 同步返回video_url")
        return {"type": "url", "video_url": video_url, "segment_index": segment_index}
    if task_id:
        logger.info(f"[视频服务] 片段 {segment_index} 返回task_id: {task_id}")
        return {"type": "task", "task_id": str(task_id), "segment_index": segment_index}

    logger.error(f"[视频服务] 片段 {segment_index} 响应中无 task_id 也无 video_url: {result}")
    raise ValueError("即梦视频 API 未返回 task_id 或 video_url")


async def submit_video_clip_request(
    segment_index: int,
    start_image_url: str,
    end_image_url: str,
    duration: int = 5,
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    仅提交视频生成请求，不等待生成完成。
    返回 task_id（需轮询）或直接返回 video_url（同步完成）。
    
    Returns:
        {"type": "task", "task_id": str, "segment_index": int}
        或 {"type": "url", "video_url": str, "segment_index": int}
    """
    settings = get_settings()
    url = f"{settings.jimeng_api_base_url.rstrip('/')}/v1/videos/generations"
    headers = {"Authorization": f"Bearer {settings.jimeng_session_id}"}
    requested_duration = max(1, int(duration))
    submit_plan = _build_model_duration_plan(requested_duration)

    logger.info(f"[视频服务] 准备提交片段 {segment_index}：起始图={start_image_url[:80]}, 结束图={end_image_url[:80]}")
    
    start_image_path = await _url_to_local_path(start_image_url)
    end_image_path = await _url_to_local_path(end_image_url)
    if not start_image_path or not end_image_path:
        logger.error(f"[视频服务] 片段 {segment_index} 图片路径解析失败：start={start_image_path}, end={end_image_path}")
        raise ValueError("无法获取图片文件")

    logger.debug(f"[视频服务] 片段 {segment_index} 本地图片：start={start_image_path}, end={end_image_path}")

    files = {
        "image_file_1": ("first_frame.png", open(start_image_path, "rb"), "image/png"),
        "image_file_2": ("last_frame.png", open(end_image_path, "rb"), "image/png"),
    }
    base_data = {
        "prompt": prompt or "smooth transition, cinematic camera movement",
        # 明确模式，避免服务端分支差异导致参数解释不一致
        "functionMode": "first_last_frames",
    }

    last_api_error: JimengVideoApiError | None = None
    try:
        submit_timeout = httpx.Timeout(
            connect=VIDEO_SUBMIT_CONNECT_TIMEOUT_SECONDS,
            write=VIDEO_SUBMIT_WRITE_TIMEOUT_SECONDS,
            read=VIDEO_SUBMIT_READ_TIMEOUT_SECONDS,
            pool=VIDEO_SUBMIT_POOL_TIMEOUT_SECONDS,
        )
        # 按模型-时长组合尝试，优先 3.5-pro，再降级 3.0
        for model, duration_int in submit_plan:
            data = {
                **base_data,
                "model": model,
                "duration": str(duration_int),
            }
            logger.info(
                f"[视频服务] 片段 {segment_index} 发送POST到 {url} (model={model}, duration={duration_int})"
            )
            async with httpx.AsyncClient(timeout=submit_timeout, trust_env=False) as client:
                resp = await client.post(url, headers=headers, data=data, files=files)
            raw_text = resp.text or ""
            logger.info(
                f"[视频服务] 片段 {segment_index} 响应状态: {resp.status_code}, 内容长度: {len(raw_text)}"
            )

            if resp.status_code not in (200, 201, 202):
                logger.error(
                    f"[视频服务] 片段 {segment_index} HTTP错误: {resp.status_code}, 响应: {raw_text[:500]}"
                )
                raise ValueError(f"即梦视频 API 返回 {resp.status_code}: {raw_text[:500]}")

            result = resp.json() if raw_text.strip() else {}
            code = result.get("code")
            msg = result.get("message")
            if code and code != 0:
                api_error = JimengVideoApiError(code=code, message=msg or "", result=result)
                last_api_error = api_error
                logger.error(
                    f"[视频服务] 片段 {segment_index} API错误码: {code}, 消息: {msg}, 完整响应: {result}"
                )

                # duration / model 错误时切换到下一个组合继续尝试
                if _is_duration_invalid_error(api_error) or _is_model_invalid_error(api_error):
                    logger.warning(
                        f"[视频服务] 片段 {segment_index} 参数不兼容，切换下一个组合重试: model={model}, duration={duration_int}"
                    )
                    continue

                raise api_error

            return _parse_video_submit_result(segment_index, result)

        # 组合全部尝试后仍失败
        if last_api_error is not None:
            raise last_api_error
        raise ValueError("即梦视频 API 参数组合均不可用")
    except httpx.ReadTimeout as e:
        logger.error(
            f"[视频服务] 片段 {segment_index} 提交读超时（可能已被服务端接收）: {e}",
            exc_info=True,
        )
        raise VideoSubmitTimeoutUncertainError("提交响应超时，任务可能已在服务端排队")
    except httpx.TimeoutException as e:
        logger.error(f"[视频服务] 片段 {segment_index} 请求超时: {e}", exc_info=True)
        raise ValueError(f"请求超时: {e}")
    except httpx.RequestError as e:
        logger.error(f"[视频服务] 片段 {segment_index} 网络错误: {e}", exc_info=True)
        raise ValueError(f"网络错误: {e}")
    except Exception as e:
        logger.error(f"[视频服务] 片段 {segment_index} 提交失败，异常类型: {type(e).__name__}, 错误: {e}", exc_info=True)
        raise
    finally:
        try:
            files["image_file_1"][1].close()
            files["image_file_2"][1].close()
        except Exception:
            pass


async def poll_video_task(task_id: str) -> Dict[str, Any]:
    """
    根据任务 id 轮询视频生成结果。
    
    Returns:
        {"status": "pending"|"success"|"failed", "video_url": str|None}
    """
    settings = get_settings()
    base = settings.jimeng_api_base_url.rstrip("/")
    # 即梦常见轮询路径
    poll_url = f"{base}/v1/videos/generations/{task_id}"
    headers = {"Authorization": f"Bearer {settings.jimeng_session_id}"}
    try:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            resp = await client.get(poll_url, headers=headers)
        if resp.status_code != 200:
            return {"status": "pending", "video_url": None}
        data = resp.json() if resp.text else {}
        inner = data.get("data") or data
        if isinstance(inner, list) and len(inner) > 0:
            inner = inner[0]
        status_raw = None
        if isinstance(inner, dict):
            status_raw = inner.get("status") or inner.get("state")
            video_url = inner.get("video_url") or inner.get("url")
            if video_url and status_raw in ("success", "completed", "succeeded", "done"):
                return {"status": "success", "video_url": video_url}
            if status_raw in ("failed", "error"):
                return {"status": "failed", "video_url": None}
        if isinstance(inner, dict) and inner.get("video_url"):
            return {"status": "success", "video_url": inner["video_url"]}
        return {"status": "pending", "video_url": None}
    except Exception as e:
        logger.debug(f"[视频服务] 轮询任务 {task_id} 异常: {e}")
        return {"status": "pending", "video_url": None}


def _build_clip_spec(
    segment_index: int,
    start_image_url: str,
    end_image_url: str,
    segment_text: str,
    segment_emotion: str,
    enable_audio: bool,
) -> Tuple[int, str, str, str, int]:
    """构建统一的视频片段生成规格。"""
    motion_prompt = f"{segment_emotion} mood transition, smooth cinematic camera movement"
    duration = 5
    if enable_audio and segment_text:
        estimated_audio = _estimate_audio_duration(segment_text)
        duration = _choose_video_duration(estimated_audio)
    return (segment_index, start_image_url, end_image_url, motion_prompt, duration)


async def _submit_spec_with_retry(spec: Tuple[int, str, str, str, int], retries: int = 2):
    """并发提交时的单任务包装（带重试）。"""
    seg_i, start_url, end_url, prompt, duration = spec
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return await submit_video_clip_request(
                segment_index=seg_i,
                start_image_url=start_url,
                end_image_url=end_url,
                duration=duration,
                prompt=prompt,
            )
        except VideoSubmitTimeoutUncertainError as e:
            # 读超时时结果不确定，盲重试会造成重复提交；直接抛出由上层决定处理策略。
            logger.error(f"[视频服务] 片段 {seg_i} 提交状态不确定，停止自动重试: {e}")
            raise
        except Exception as e:
            last_error = e
            if attempt + 1 < retries:
                logger.warning(f"[视频服务] 片段 {seg_i} 提交失败（第 {attempt + 1}/{retries} 次），将重试: {e}")
                await asyncio.sleep(2)
    raise RuntimeError(f"片段 {seg_i} 提交失败（已重试 {retries} 次）: {last_error}")


async def _poll_until_success(task_id: str, max_rounds: int = 120) -> Dict[str, Any]:
    """轮询单个 task_id，直到成功/失败/超时。"""
    for _ in range(max_rounds):
        result = await poll_video_task(task_id)
        if result["status"] in {"success", "failed"}:
            return result
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    return {"status": "failed", "video_url": None, "error": "轮询超时"}


async def maybe_pregenerate_premium_clip(
    story_id: str,
    segment_index: int,
    segments: List[StorySegment],
    user: Optional[dict] = None,
) -> Optional[str]:
    """
    付费用户浏览时预生成片段：
    - 只处理 segment_index -> segment_index+1
    - 结果落盘到 storybook_videos/segments/{story_id}/pregenerated/
    - 已存在则直接复用
    """
    if not user or not user.get("is_paid"):
        return None
    if segment_index < 0 or segment_index >= len(segments) - 1:
        return None

    inflight_key = (story_id, segment_index)
    if inflight_key in _pregen_inflight:
        return None

    cached = _pregenerated_clip_path(story_id, segment_index)
    if cached.exists() and cached.stat().st_size > 0:
        logger.info(f"[视频服务] 预生成命中本地片段: {cached.name}")
        return str(cached)

    state = get_story(story_id)
    if state:
        existing = state.video_clips.get(str(segment_index))
        if existing and os.path.exists(existing):
            return existing

    current_seg = segments[segment_index]
    next_seg = segments[segment_index + 1]
    if not current_seg.image_url or not next_seg.image_url:
        return None

    _pregen_inflight.add(inflight_key)
    try:
        logger.info(f"[视频服务] 付费预生成开始: story={story_id}, segment={segment_index}")
        spec = _build_clip_spec(
            segment_index=segment_index,
            start_image_url=current_seg.image_url,
            end_image_url=next_seg.image_url,
            segment_text=current_seg.text or "",
            segment_emotion=current_seg.emotion or "warm",
            enable_audio=True,
        )

        result = await _submit_spec_with_retry(spec, retries=2)
        if result["type"] == "url":
            video_url = result["video_url"]
        else:
            poll_result = await _poll_until_success(result["task_id"])
            if poll_result["status"] != "success" or not poll_result.get("video_url"):
                raise RuntimeError(f"预生成失败: segment={segment_index}, task_id={result['task_id']}")
            video_url = poll_result["video_url"]

        cached.parent.mkdir(parents=True, exist_ok=True)
        await download_file(video_url, str(cached))

        state = get_story(story_id)
        if state:
            clips = dict(state.video_clips)
            clips[str(segment_index)] = str(cached)
            update_story(story_id, video_clips=clips)

        logger.info(f"[视频服务] ✅ 付费预生成完成: segment={segment_index}, path={cached}")
        return str(cached)
    finally:
        _pregen_inflight.discard(inflight_key)


async def generate_video_clip(
    start_image_url: str,
    end_image_url: str,
    duration: int = 5,
    prompt: Optional[str] = None,
) -> str:
    """
    使用即梦 API 生成首尾帧视频片段
    
    Args:
        start_image_url: 起始帧图片 URL（可以是本地路径或网络URL）
        end_image_url: 结束帧图片 URL（可以是本地路径或网络URL）
        duration: 视频时长（秒），支持 5 / 10 / 12 秒
        prompt: 可选的运动提示词
    
    Returns:
        视频 URL
    """
    settings = get_settings()
    url = f"{settings.jimeng_api_base_url.rstrip('/')}/v1/videos/generations"
    headers = {
        "Authorization": f"Bearer {settings.jimeng_session_id}",
    }
    
    requested_duration = int(duration)
    duration_int = _nearest_allowed_duration(requested_duration, MODEL_35_ALLOWED_DURATIONS)
    if duration_int != requested_duration:
        logger.warning(
            f"[视频服务] duration={requested_duration} 不在 3.5-pro 支持范围，调整为 {duration_int} 秒"
        )
    model = DEFAULT_VIDEO_MODEL
    
    # 将图片URL转换为本地文件路径
    start_image_path = await _url_to_local_path(start_image_url)
    end_image_path = await _url_to_local_path(end_image_url)
    
    if not start_image_path or not end_image_path:
        raise ValueError("无法获取图片文件，请检查图片URL是否有效")
    
    # 使用 multipart/form-data 上传本地图片文件
    files = {
        "image_file_1": ("first_frame.png", open(start_image_path, "rb"), "image/png"),
        "image_file_2": ("last_frame.png", open(end_image_path, "rb"), "image/png"),
    }
    
    data = {
        "model": model,  # 根据时长自动选择模型
        "prompt": prompt or "smooth transition, cinematic camera movement",
        "duration": str(duration_int),  # form-data 需要字符串
    }
    
    logger.info(f"[视频服务] ========== 开始生成视频片段 ==========")
    logger.info(f"[视频服务] 请求URL: {url}")
    logger.info(f"[视频服务] 模型: {data['model']}")
    logger.info(f"[视频服务] 时长: {duration_int}秒 (类型: {type(duration_int).__name__})")
    logger.info(f"[视频服务] 运动提示: {data['prompt']}")
    logger.info(f"[视频服务] 起始图文件: {start_image_path}")
    logger.info(f"[视频服务] 结束图文件: {end_image_path}")
    
    try:
        # 视频生成可能需要更长时间，设置 10 分钟超时
        async with httpx.AsyncClient(timeout=600, trust_env=False) as client:
            logger.info("[视频服务] 发送POST请求（multipart/form-data）...")
            resp = await client.post(url, headers=headers, data=data, files=files)
            logger.info(f"[视频服务] ========== 收到响应 ==========")
            logger.info(f"[视频服务] 响应状态码: {resp.status_code}")
            logger.info(f"[视频服务] 响应头: {dict(resp.headers)}")
            
            # 获取原始响应文本
            raw_text = resp.text or ""
            logger.info(f"[视频服务] 原始响应 (前1000字符): {raw_text[:1000]}")
            
            if resp.status_code not in (200, 201, 202):
                error_text = raw_text[:1000]
                logger.error(f"[视频服务] ❌ 请求失败: {resp.status_code}, 完整响应: {error_text}")
                raise ValueError(f"即梦视频 API 返回错误 {resp.status_code}: {error_text}")
            
            resp.raise_for_status()
            
            # 解析JSON
            data = None
            try:
                data = resp.json() if raw_text.strip() else {}
                logger.info(f"[视频服务] 解析后的JSON数据: {data}")
            except Exception as e:
                logger.error(f"[视频服务] ❌ JSON解析失败: {e}, 原始文本: {raw_text[:500]}")
                data = {}
            
            # 检查API错误码
            if isinstance(data, dict):
                error_code = data.get("code")
                error_msg = data.get("message")
                if error_code and error_code != 0:
                    logger.error(f"[视频服务] ❌ API返回错误码: {error_code}, 消息: {error_msg}")
                    logger.error(f"[视频服务] 完整响应数据: {data}")
                    raise ValueError(f"即梦视频API错误 (code={error_code}): {error_msg}")
            
            # 兼容多种 API 响应结构
            logger.info("[视频服务] 尝试提取视频URL...")
            video_url = None
            
            # 尝试多种可能的响应结构
            if isinstance(data.get("data"), dict):
                video_url = data["data"].get("video_url")
                logger.debug(f"[视频服务] 从 data.video_url 提取: {video_url}")
            
            if not video_url and isinstance(data.get("data"), list) and len(data["data"]) > 0:
                video_url = data["data"][0].get("url")
                logger.debug(f"[视频服务] 从 data[0].url 提取: {video_url}")
            
            if not video_url:
                video_url = data.get("video_url")
                logger.debug(f"[视频服务] 从 video_url 提取: {video_url}")
                
            if not video_url and isinstance(data.get("result"), dict):
                video_url = data["result"].get("video_url")
                logger.debug(f"[视频服务] 从 result.video_url 提取: {video_url}")
                
            if not video_url and isinstance(data.get("output"), dict):
                video_url = data["output"].get("video_url")
                logger.debug(f"[视频服务] 从 output.video_url 提取: {video_url}")
            
            if not video_url:
                logger.error(f"[视频服务] ❌ 响应中没有视频 URL")
                logger.error(f"[视频服务] 完整响应结构: {data}")
                logger.error(f"[视频服务] 可能的原因:")
                logger.error(f"[视频服务]   1. API返回了异步任务ID，需要轮询查询结果")
                logger.error(f"[视频服务]   2. duration参数值不在允许范围内")
                logger.error(f"[视频服务]   3. 图片URL格式不正确或无法访问")
                logger.error(f"[视频服务]   4. API响应结构发生变化")
                raise ValueError("即梦视频 API 未返回视频 URL（可能为异步任务，需轮询结果）")
        
        logger.info(f"[视频服务] ✅ 视频片段生成成功，URL: {video_url[:100]}...")
        return video_url
        
    except httpx.TimeoutException as e:
        logger.error(f"[视频服务] ⏱️ 请求超时: {e}")
        raise ValueError(f"即梦视频 API 请求超时: {e}")
    except httpx.RequestError as e:
        logger.error(f"[视频服务] ❌ 网络错误: {e}")
        raise ValueError(f"即梦视频 API 网络错误: {e}")
    except Exception as e:
        logger.error(f"[视频服务] ❌ 未知错误: {type(e).__name__}: {e}", exc_info=True)
        raise
    finally:
        # 关闭文件句柄
        try:
            files["image_file_1"][1].close()
            files["image_file_2"][1].close()
        except:
            pass


async def download_file(url: str, output_path: str) -> str:
    """下载文件到本地"""
    logger.info(f"[视频服务] 下载文件: {url[:80]}... -> {output_path}")
    
    try:
        async with httpx.AsyncClient(timeout=300, trust_env=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            
            with open(output_path, "wb") as f:
                f.write(resp.content)
            
            logger.info(f"[视频服务] ✅ 文件下载完成: {output_path}")
            return output_path
    except Exception as e:
        logger.error(f"[视频服务] ❌ 文件下载失败: {e}")
        raise


async def generate_tts_audio(text: str, output_path: str, voice_id: str = "zh-CN-XiaoxiaoNeural") -> str:
    """
    生成 TTS 语音，调用 TTS 服务
    
    Args:
        text: 要转换的文本
        output_path: 输出文件路径
        voice_id: 音色 ID（默认使用中文女声）
    
    Returns:
        生成的音频文件路径
    """
    logger.info(f"[视频服务] 生成 TTS 音频: {text[:50]}... -> {output_path}")
    
    try:
        # 导入 TTS 服务
        from app.services.tts_service import generate_tts_audio as tts_generate
        
        # 调用 TTS 服务生成音频
        audio_path = await tts_generate(
            text=text,
            output_path=output_path,
            voice_id=voice_id,
            rate="+0%",
            volume="+0%",
            max_retries=3,
        )
        
        logger.info(f"[视频服务] ✅ TTS 音频生成成功: {audio_path}")
        return audio_path
        
    except ImportError:
        logger.warning("[视频服务] ⚠️ TTS 服务不可用，跳过音频生成")
        return ""
    except Exception as e:
        logger.error(f"[视频服务] ❌ TTS 音频生成失败: {e}", exc_info=True)
        return ""


def _story_segments_dir(story_id: str) -> Path:
    """故事片段统一目录。"""
    settings = get_settings()
    return Path(settings.video_output_dir).resolve() / "segments" / story_id


def _pregenerated_clip_path(story_id: str, segment_index: int) -> Path:
    """付费预生成片段落盘路径。"""
    return _story_segments_dir(story_id) / PREGENERATED_DIRNAME / f"clip_{segment_index:03d}.mp4"


def _story_clip_path(story_dir: Path, segment_index: int) -> Path:
    """故事目录中的视频片段标准路径（按 segment_index 命名）。"""
    return story_dir / f"clip_{segment_index:03d}.mp4"


def _story_audio_path(story_dir: Path, segment_index: int) -> Path:
    """故事目录中的音频片段标准路径（按 segment_index 命名）。"""
    return story_dir / f"audio_{segment_index:03d}.mp3"


def _pick_existing_story_media_path(
    story_dir: Path,
    *,
    segment_index: int,
    ordered_index: int,
    media_type: str,
) -> Optional[str]:
    """
    兼容查找故事目录中的既有资源：
    - 新命名：按 segment_index（clip_005 / audio_005）
    - 旧命名：按顺序 index（clip_002 / audio_002）
    """
    if media_type == "clip":
        candidates = [
            _story_clip_path(story_dir, segment_index),
            story_dir / f"clip_{ordered_index:03d}.mp4",
        ]
    elif media_type == "audio":
        candidates = [
            _story_audio_path(story_dir, segment_index),
            story_dir / f"audio_{ordered_index:03d}.mp3",
        ]
    else:
        return None

    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return str(p.resolve())
    return None


def _materialize_audio_into_story_dir(
    source_audio_path: str,
    story_dir: Path,
    segment_index: int,
) -> str:
    """
    将外部缓存音频复制到当前故事片段目录，保证合并输入全部落在固定目录中。
    """
    target = _story_audio_path(story_dir, segment_index)
    source = Path(source_audio_path)
    if target.exists() and target.stat().st_size > 0:
        return str(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


def _normalize_video_clip_size(video_clip, target_width: int = TARGET_VIDEO_WIDTH, target_height: int = TARGET_VIDEO_HEIGHT):
    """
    将视频统一到固定画幅，保持原始比例并补黑边，避免输出出现 16:9 / 3:4 混杂。
    """
    scale = min(target_width / max(video_clip.w, 1), target_height / max(video_clip.h, 1))
    resized = video_clip.resize(scale)
    return resized.on_color(
        size=(target_width, target_height),
        color=(0, 0, 0),
        pos=("center", "center"),
    )


def _estimate_audio_duration(text: str, chars_per_second: float = 3.5) -> float:
    """
    根据文本长度估算音频时长
    
    Args:
        text: 文本内容
        chars_per_second: 每秒字符数（中文约 3-4 字/秒，英文约 2-3 词/秒）
    
    Returns:
        预估的音频时长（秒）
    """
    if not text:
        return 0.0
    # 简单估算：文本长度 / 每秒字符数
    estimated = len(text.strip()) / chars_per_second
    # 添加最小时长（避免过短）
    return max(estimated, 1.0)


def _choose_video_duration(estimated_audio_duration: float) -> int:
    """
    根据预估音频时长选择合适的视频时长
    
    Args:
        estimated_audio_duration: 预估的音频时长（秒）
    
    Returns:
        视频时长（5 / 10 / 12 秒）
    """
    # 规则：
    # - 预估音频 <= 5 秒：使用 5 秒视频
    # - 5 秒 < 预估音频 <= 10 秒：使用 10 秒视频
    # - 预估音频 > 10 秒：使用 12 秒视频（3.5-pro 上限）
    if estimated_audio_duration <= 5:
        return 5
    elif estimated_audio_duration <= 10:
        return 10
    else:
        return LONG_VIDEO_MAX_DURATION


def _adjust_video_to_audio(video_clip, audio_duration: float):
    """
    调整视频时长以匹配音频时长
    
    策略：
    - 如果音频时长 <= 视频时长：视频慢放到音频时长
    - 如果音频时长 > 视频时长：视频最后一帧定格到音频时长
    
    Args:
        video_clip: VideoFileClip 对象
        audio_duration: 音频时长（秒）
    
    Returns:
        调整后的视频片段
    """
    from moviepy.editor import ImageClip, concatenate_videoclips
    from moviepy.video.fx.loop import loop
    from moviepy.video.fx.speedx import speedx

    
    video_duration = video_clip.duration
    
    if audio_duration <= video_duration:
        # 音频更短：视频慢放到音频时长
        speed_factor = video_duration / audio_duration
        # 限制慢放速度，避免过慢（最快 0.3x）
        speed_factor = max(0.3, min(speed_factor, 2.0))
        adjusted = video_clip.fx(speedx, speed_factor).subclip(0, audio_duration)
        logger.debug(f"[视频服务] 视频慢放: {video_duration}s -> {audio_duration}s (速度: {speed_factor:.2f}x)")
        return adjusted
    # 音频更长：按需求改为“最后一帧定格”补齐，避免循环带来的突兀感
    freeze_duration = max(audio_duration - video_duration, 0)
    if freeze_duration <= 0.01:
        return video_clip

    try:
        fps = max(getattr(video_clip, "fps", 24) or 24, 1)
        # 避开末帧边界，减少 ffmpeg reader 在文件尾部读取失败的概率
        frame_time = max(video_duration - 2.0 / fps, 0)
        last_frame = video_clip.get_frame(frame_time)
        frozen_tail = ImageClip(last_frame).set_duration(freeze_duration)

        logger.debug(
            f"[视频服务] 视频尾帧定格补齐: video={video_duration:.2f}s, audio={audio_duration:.2f}s, freeze={freeze_duration:.2f}s"
        )
        return concatenate_videoclips([video_clip, frozen_tail], method="compose")
    except Exception as freeze_err:
        # 回退到循环补齐，确保流程可继续（避免因单帧读取失败导致整体失败）
        logger.warning(
            f"[视频服务] 尾帧定格失败，回退循环补齐: {freeze_err}",
            exc_info=True,
        )
        try:
            return video_clip.fx(loop, duration=audio_duration)
        except Exception:
            logger.warning("[视频服务] 循环补齐也失败，回退为原视频时长")
            return video_clip


async def merge_videos_with_audio(
    video_clips: List[str],
    audio_clips: List[str],
    output_path: str,
    sync_strategy: str = "video_adapts_audio",
) -> str:
    """
    合并视频片段并添加音频，支持音画同步
    
    Args:
        video_clips: 视频片段文件路径列表
        audio_clips: 音频片段文件路径列表
        output_path: 输出文件路径
        sync_strategy: 同步策略
            - "video_adapts_audio": 视频适配音频（推荐，保证音频完整性）
            - "audio_adapts_video": 音频适配视频（音频倍速或截断）
    
    Returns:
        合并后的视频文件路径
    """
    logger.info(f"[视频服务] 合并视频片段: {len(video_clips)} 个视频, {len(audio_clips)} 个音频")
    logger.info(f"[视频服务] 同步策略: {sync_strategy}")
    
    try:
        # 使用 moviepy 合并视频
        from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip
        from moviepy.video.fx import speedx
        
        # 加载视频和音频
        video_objects = []
        audio_objects = []
        current_time = 0
        
        for i, (video_path, audio_path) in enumerate(zip(video_clips, audio_clips)):
            logger.info(f"[视频服务] 处理片段 {i+1}/{len(video_clips)}: video={video_path}, audio={audio_path}")
            
            video_clip = VideoFileClip(video_path)
            video_clip = _normalize_video_clip_size(video_clip)
            video_duration = video_clip.duration
            
            if audio_path and os.path.exists(audio_path):
                try:
                    audio_clip = AudioFileClip(audio_path)
                    audio_duration = audio_clip.duration
                    
                    logger.info(f"[视频服务] 片段 {i+1}: 视频={video_duration:.2f}s, 音频={audio_duration:.2f}s")
                except Exception as e:
                    logger.error(f"[视频服务] ❌ 片段 {i+1} 音频加载失败: {audio_path}, 错误: {e}")
                    # 音频加载失败，跳过该音频
                    audio_path = None
                
                # 根据策略调整
                if sync_strategy == "video_adapts_audio":
                    # 视频适配音频（推荐）
                    adjusted_video = _adjust_video_to_audio(video_clip, audio_duration)
                    adjusted_audio = audio_clip
                else:
                    # 音频适配视频
                    adjusted_video = video_clip
                    if audio_duration > video_duration:
                        # 音频倍速（限制在合理范围）
                        speed_factor = audio_duration / video_duration
                        speed_factor = max(0.5, min(speed_factor, 2.0))  # 限制在 0.5x - 2.0x
                        adjusted_audio = audio_clip.fx(speedx, speed_factor)
                        logger.info(f"[视频服务] 音频倍速: {audio_duration:.2f}s -> {video_duration:.2f}s (速度: {speed_factor:.2f}x)")
                    elif audio_duration < video_duration:
                        # 音频添加静音（在末尾）
                        from moviepy import AudioClip
                        silence_duration = video_duration - audio_duration
                        silence = AudioClip(lambda t: [0, 0], duration=silence_duration)
                        adjusted_audio = CompositeAudioClip([
                            audio_clip,
                            silence.set_start(audio_duration)
                        ])
                        logger.info(f"[视频服务] 音频添加静音: {audio_duration:.2f}s + {silence_duration:.2f}s 静音")
                    else:
                        adjusted_audio = audio_clip
                
                # 设置时间轴位置
                adjusted_video = adjusted_video.set_start(current_time)
                adjusted_audio = adjusted_audio.set_start(current_time)
                
                video_objects.append(adjusted_video)
                audio_objects.append(adjusted_audio)
                current_time += adjusted_video.duration
                
            else:
                # 无音频，直接添加视频
                logger.info(f"[视频服务] 片段 {i+1}: 无音频，仅添加视频")
                video_clip = video_clip.set_start(current_time)
                video_objects.append(video_clip)
                current_time += video_clip.duration
        
        # 合并视频
        logger.info("[视频服务] 拼接视频片段...")
        final_video = concatenate_videoclips(video_objects, method="compose")
        
        # 添加音频
        if audio_objects:
            logger.info(f"[视频服务] 添加音频轨道: 共 {len(audio_objects)} 个音频片段")
            final_audio = CompositeAudioClip(audio_objects)
            final_video = final_video.set_audio(final_audio)
            logger.info("[视频服务] ✅ 音频已成功添加到视频")
        else:
            logger.warning("[视频服务] ⚠️ 没有可用的音频，将导出无声视频")
        
        # 导出最终视频
        logger.info(f"[视频服务] 导出最终视频: {output_path}")
        # 根据是否有音频决定是否指定音频编码
        write_kwargs = {
            "codec": "libx264",
            "fps": 24,
            "preset": "medium",
            "threads": 4,
        }
        if audio_objects:
            write_kwargs["audio_codec"] = "aac"
            logger.info("[视频服务] 导出带音频的视频（AAC 编码）")
        else:
            logger.info("[视频服务] 导出无声视频（无音频编码）")
        
        final_video.write_videofile(output_path, **write_kwargs)
        
        # 释放资源
        final_video.close()
        for v in video_objects:
            v.close()
        if audio_objects:
            for a in audio_objects:
                a.close()
        
        logger.info(f"[视频服务] ✅ 视频合并完成: {output_path}")
        return output_path
        
    except ImportError:
        logger.error("[视频服务] ❌ moviepy 未安装，请运行: pip install moviepy")
        raise ValueError("视频处理库未安装")
    except Exception as e:
        logger.error(f"[视频服务] ❌ 视频合并失败: {type(e).__name__}: {e}", exc_info=True)
        raise


async def generate_story_video(
    story_id: str,
    segments: List[StorySegment],
    title: str,
    enable_audio: bool = True,
    user: Optional[dict] = None,
    prebuilt_clips: Optional[Dict[str, str]] = None,
) -> Dict:
    """
    生成完整的故事视频。
    - 并发提交 + 并发轮询，最多 5 个在途任务
    - 提交前先检查并复用已有资源（图片/视频片段/音频）
    """
    logger.info(f"[视频服务] 开始生成故事视频: {story_id}, 段落数: {len(segments)}, 标题: {title}")
    logger.info(f"[视频服务] 音频开关: {'开启' if enable_audio else '关闭'}")

    task_info = {
        "story_id": story_id,
        "status": VideoGenerationStatus.GENERATING_CLIPS,
        "progress": 0,
        "total_clips": len(segments) - 1,
        "generated_clips": 0,
        "video_url": None,
        "error": None,
    }
    _video_tasks[story_id] = task_info

    try:
        settings = get_settings()
        # 片段与成片保存到 storybook_videos/segments/{story_id}/，不再使用系统临时目录
        base_dir = Path(settings.video_output_dir).resolve()
        segments_dir = base_dir / "segments" / story_id
        segments_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = segments_dir
        logger.info(f"[视频服务] 片段与成片目录: {temp_dir}")

        # 全量生成规格（提交前先检查图片资源是否可用）
        all_specs: List[Tuple[int, str, str, str, int]] = []
        for i in range(len(segments) - 1):
            a, b = segments[i], segments[i + 1]
            if not a.image_url or not b.image_url:
                logger.warning(f"[视频服务] ⚠️ 段落 {i} 或 {i+1} 缺少图片，跳过")
                continue
            start_local = await _url_to_local_path(a.image_url)
            end_local = await _url_to_local_path(b.image_url)
            if not start_local or not end_local:
                logger.warning(
                    f"[视频服务] ⚠️ 提交前资源检查未通过，段落 {i} 图片不可用，跳过提交: start={a.image_url}, end={b.image_url}"
                )
                continue
            logger.info(
                f"[视频服务] 提交前资源检查通过: segment={i}, start={Path(start_local).name}, end={Path(end_local).name}"
            )
            all_specs.append(
                _build_clip_spec(
                    segment_index=i,
                    start_image_url=a.image_url,
                    end_image_url=b.image_url,
                    segment_text=a.text or "",
                    segment_emotion=a.emotion or "warm",
                    enable_audio=enable_audio,
                )
            )

        total = len(all_specs)
        if total == 0:
            task_info["status"] = VideoGenerationStatus.FAILED
            task_info["error"] = "没有可生成片段的段落（缺少图片）"
            return task_info

        task_info["total_clips"] = total
        logger.info(f"[视频服务] 步骤 1: 提交并轮询共 {total} 个片段，最多 {MAX_CONCURRENT_VIDEO_TASKS} 个并发")

        # 提交前优先复用“当前故事目录/状态缓存”中的已有片段，避免重复提交
        results: Dict[int, str] = {}
        cache_store: Dict[str, str] = {}
        if prebuilt_clips:
            cache_store.update({str(k): v for k, v in prebuilt_clips.items() if v})
        state = get_story(story_id)
        if state and state.video_clips:
            cache_store.update({str(k): v for k, v in state.video_clips.items() if v})

        for ordered_i, (seg_i, _, _, _, _) in enumerate(all_specs):
            # 1) 当前故事目录中已存在片段（新命名/旧命名）优先复用
            local_existing = _pick_existing_story_media_path(
                temp_dir,
                segment_index=seg_i,
                ordered_index=ordered_i,
                media_type="clip",
            )
            if local_existing:
                results[seg_i] = local_existing
                logger.info(f"[视频服务] 命中当前目录视频片段: segment={seg_i}, path={local_existing}")
                continue

            # 2) 复用状态缓存或预生成缓存
            cached = cache_store.get(str(seg_i))
            if not cached:
                continue
            if os.path.exists(cached) or cached.startswith("http"):
                results[seg_i] = cached
                logger.info(f"[视频服务] 命中缓存视频片段: segment={seg_i}, ref={cached}")

        specs = [spec for spec in all_specs if spec[0] not in results]
        pending: Dict[str, int] = {}
        next_spec_index = 0

        def update_progress():
            done = len(results)
            task_info["generated_clips"] = done
            task_info["progress"] = int(done / total * 70) if total else 0

        update_progress()
        logger.info(f"[视频服务] 可复用已有片段: {len(results)}，待新生成: {len(specs)}")

        while next_spec_index < len(specs) or pending:
            # 提交：批量并发提交，不超过剩余槽位
            capacity = MAX_CONCURRENT_VIDEO_TASKS - len(pending)
            if capacity > 0 and next_spec_index < len(specs):
                batch = specs[next_spec_index : next_spec_index + capacity]
                next_spec_index += len(batch)
                logger.info(f"[视频服务] 并发提交 {len(batch)} 个片段，当前在途 {len(pending)}/{MAX_CONCURRENT_VIDEO_TASKS}")
                submit_tasks = [_submit_spec_with_retry(spec, retries=2) for spec in batch]
                submit_results = await asyncio.gather(*submit_tasks, return_exceptions=True)

                for spec, submit_result in zip(batch, submit_results):
                    seg_i = spec[0]
                    if isinstance(submit_result, Exception):
                        logger.error(f"[视频服务] ❌ 片段 {seg_i} 提交失败，跳过: {submit_result}")
                        continue
                    if submit_result["type"] == "url":
                        results[seg_i] = submit_result["video_url"]
                        logger.info(f"[视频服务] 片段 {seg_i} 同步返回 URL")
                    else:
                        pending[submit_result["task_id"]] = submit_result["segment_index"]
                        logger.info(
                            f"[视频服务] 片段 {seg_i} 已提交，task_id={submit_result['task_id'][:16]}..., 在途: {len(pending)}/{MAX_CONCURRENT_VIDEO_TASKS}"
                        )
                    update_progress()

            if not pending and next_spec_index >= len(specs):
                break
            if not pending:
                continue

            # 并发轮询所有在途任务
            pending_list = list(pending.items())
            polling_snapshot = ", ".join(
                [f"seg{seg_i}:task{task_id[:8]}" for task_id, seg_i in pending_list]
            )
            logger.info(f"[视频服务] 并发轮询 {len(pending_list)} 个在途任务: {polling_snapshot}")
            poll_tasks = [poll_video_task(task_id) for task_id, _ in pending_list]
            poll_results = await asyncio.gather(*poll_tasks, return_exceptions=True)

            for (task_id, seg_i), poll_result in zip(pending_list, poll_results):
                if isinstance(poll_result, Exception):
                    logger.warning(f"[视频服务] 片段 {seg_i} 轮询异常: {poll_result}")
                    continue

                if poll_result["status"] == "success" and poll_result.get("video_url"):
                    results[seg_i] = poll_result["video_url"]
                    pending.pop(task_id, None)
                    update_progress()
                    logger.info(f"[视频服务] ✅ 片段 {seg_i} 轮询完成，剩余在途: {len(pending)}/{MAX_CONCURRENT_VIDEO_TASKS}")
                elif poll_result["status"] == "failed":
                    pending.pop(task_id, None)
                    logger.warning(f"[视频服务] ❌ 片段 {seg_i} 生成失败")

            if pending:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        if not results:
            task_info["status"] = VideoGenerationStatus.FAILED
            task_info["error"] = "没有成功生成任何视频片段"
            return task_info

        # 按 segment_index 顺序拼接（顺序必须正确）
        ordered_indices = sorted(results.keys())
        video_clips: List[str] = []
        audio_clips = []
        clip_index_updates: Dict[str, str] = {}

        for k, seg_i in enumerate(ordered_indices):
            ref = results[seg_i]
            existing_story_clip = _pick_existing_story_media_path(
                temp_dir,
                segment_index=seg_i,
                ordered_index=k,
                media_type="clip",
            )
            if existing_story_clip:
                clip_local_path = existing_story_clip
                logger.info(f"[视频服务] 复用当前目录视频片段: segment={seg_i}, path={clip_local_path}")
            elif os.path.exists(ref):
                source_clip = Path(ref).resolve()
                target_clip = _story_clip_path(temp_dir, seg_i).resolve()
                if source_clip != target_clip:
                    target_clip.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_clip, target_clip)
                    logger.info(f"[视频服务] 复用外部视频片段并复制到当前目录: {source_clip} -> {target_clip}")
                clip_local_path = str(target_clip)
            else:
                clip_path = _story_clip_path(temp_dir, seg_i)
                await download_file(ref, str(clip_path))
                clip_local_path = str(clip_path)
            video_clips.append(clip_local_path)

            if os.path.exists(clip_local_path):
                clip_index_updates[str(seg_i)] = clip_local_path

            if enable_audio and seg_i < len(segments) and segments[seg_i].text:
                existing_story_audio = _pick_existing_story_media_path(
                    temp_dir,
                    segment_index=seg_i,
                    ordered_index=k,
                    media_type="audio",
                )
                if existing_story_audio:
                    logger.info(f"[视频服务] 复用当前目录音频片段: segment={seg_i}, path={existing_story_audio}")
                    audio_clips.append(existing_story_audio)
                    continue

                # 优先查找已缓存的音频文件
                cached_audio = None

                # 1. 检查 TTS 缓存目录（edge-tts）
                from app.services.tts_service import TTS_AUDIO_DIR, DEFAULT_VOICE_ID

                # 优先按 story_id + segment_index 通配扫描，避免仅查固定音色导致误判未命中
                wildcard_hits = sorted(TTS_AUDIO_DIR.glob(f"{story_id}_{seg_i}_*.mp3"))
                for cached_path in wildcard_hits:
                    if cached_path.exists() and cached_path.stat().st_size > 0:
                        cached_audio = str(cached_path)
                        logger.info(f"[视频服务] ✅ 使用已缓存的音频(通配命中): {cached_path.name}")
                        break

                # 向后兼容：若通配未命中，再尝试常用音色名
                if not cached_audio:
                    common_voices = [DEFAULT_VOICE_ID, "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunjianNeural"]
                    for voice in common_voices:
                        cached_path = TTS_AUDIO_DIR / f"{story_id}_{seg_i}_{voice}.mp3"
                        if cached_path.exists() and cached_path.stat().st_size > 0:
                            cached_audio = str(cached_path)
                            logger.info(f"[视频服务] ✅ 使用已缓存的音频: {cached_path.name}")
                            break

                # 2. 如果没有缓存，则生成新音频
                if not cached_audio:
                    audio_path = _story_audio_path(temp_dir, seg_i)
                    logger.info(f"[视频服务] 未找到缓存音频，为段落 {seg_i}（序号 {k}）生成新音频")
                    try:
                        audio_file = await generate_tts_audio(
                            text=segments[seg_i].text,
                            output_path=str(audio_path),
                            voice_id=DEFAULT_VOICE_ID,
                        )
                        if audio_file:
                            logger.info(f"[视频服务] 片段 {k} 音频生成成功: {audio_file}")
                            audio_clips.append(audio_file)
                        else:
                            logger.warning(f"[视频服务] ⚠️ 片段 {k} 音频生成失败，将跳过音频")
                            audio_clips.append("")
                    except Exception as e:
                        logger.error(f"[视频服务] ❌ 片段 {k} 音频生成异常: {e}")
                        audio_clips.append("")
                else:
                    # 使用缓存的音频，但仍落盘到当前故事目录，避免依赖外部缓存目录
                    local_audio_path = _materialize_audio_into_story_dir(
                        source_audio_path=cached_audio,
                        story_dir=temp_dir,
                        segment_index=seg_i,
                    )
                    logger.info(
                        f"[视频服务] 使用缓存音频并落盘到故事目录: source={cached_audio}, local={local_audio_path}"
                    )
                    audio_clips.append(local_audio_path)
            else:
                audio_clips.append("")

        if clip_index_updates:
            state = get_story(story_id)
            if state:
                clips = dict(state.video_clips)
                clips.update(clip_index_updates)
                update_story(story_id, video_clips=clips)

        # 统计音频生成情况
        valid_audio_count = sum(1 for a in audio_clips if a and os.path.exists(a))
        logger.info(f"[视频服务] ✅ 成功生成 {len(video_clips)} 个视频片段，{valid_audio_count}/{len(audio_clips)} 个音频片段，按顺序拼接")

        task_info["status"] = VideoGenerationStatus.MERGING
        task_info["progress"] = 75
        output_path = temp_dir / f"story_{story_id}_final.mp4"
        if enable_audio and any(audio_clips):
            task_info["status"] = VideoGenerationStatus.ADDING_AUDIO
            task_info["progress"] = 85

        final_video_path = await merge_videos_with_audio(
            video_clips=video_clips,
            audio_clips=audio_clips,
            output_path=str(output_path),
            sync_strategy="video_adapts_audio",  # 使用视频适配音频策略
        )

        logger.info(f"[视频服务] ✅ 故事视频生成完成: {final_video_path}")
        task_info["status"] = VideoGenerationStatus.COMPLETED
        task_info["progress"] = 100
        task_info["video_url"] = final_video_path
        return task_info

    except Exception as e:
        logger.error(f"[视频服务] ❌ 故事视频生成失败: {type(e).__name__}: {e}", exc_info=True)
        task_info["status"] = VideoGenerationStatus.FAILED
        task_info["error"] = str(e)
        return task_info


def get_video_generation_status(story_id: str) -> Optional[Dict]:
    """获取视频生成状态"""
    return _video_tasks.get(story_id)


async def generate_video_clip_between_segments(
    story_id: str,
    segment_index: int,
    segments: List[StorySegment],
    user: Optional[dict] = None,
) -> Optional[str]:
    """
    在用户浏览故事时，异步生成当前段落到下一段落的视频片段
    
    Args:
        story_id: 故事 ID
        segment_index: 当前段落索引
        segments: 所有段落列表
    
    Returns:
        视频 URL 或 None
    """
    try:
        return await maybe_pregenerate_premium_clip(
            story_id=story_id,
            segment_index=segment_index,
            segments=segments,
            user=user,
        )
    except Exception as e:
        logger.error(f"[视频服务] ❌ 异步视频片段生成失败: {e}")
        return None
