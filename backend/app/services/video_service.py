"""
视频生成服务：基于即梦 API 首尾帧视频生成功能
异步生成视频片段，最后合成完整的带音频故事视频

生成逻辑：
- 顺序提交每个片段生成请求，保存任务 id，最多同时 5 个在途任务
- 提交与轮询分离：有槽位就继续提交，轮询到完成则释放槽位并按顺序收集结果
- 最终按 segment_index 顺序拼接视频
"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import httpx
from app.config import get_settings
from app.models.story import StorySegment, Character

logger = logging.getLogger(__name__)

# 最大同时进行的视频生成任务数
MAX_CONCURRENT_VIDEO_TASKS = 5
# 轮询间隔（秒）
POLL_INTERVAL_SECONDS = 5

# 视频生成状态存储（实际项目中应该用数据库）
_video_tasks: Dict[str, Dict] = {}


async def _url_to_local_path(image_url: str) -> Optional[str]:
    """
    将图片URL转换为本地文件路径
    
    Args:
        image_url: 图片URL（可能是 http://localhost:8100/images/xxx.png）
    
    Returns:
        本地文件路径，如果找不到返回 None
    """
    try:
        # 如果已经是本地路径，直接返回
        if os.path.exists(image_url):
            logger.debug(f"[视频服务] 图片已是本地路径: {image_url}")
            return image_url
        
        # 如果是本地服务的URL，提取文件名并查找本地文件
        if "localhost" in image_url or "127.0.0.1" in image_url:
            # 从URL提取文件名，例如: /images/xxx.png -> xxx.png
            filename = os.path.basename(image_url.split("?")[0])
            
            # 在 backend/data/images 目录查找
            settings = get_settings()
            possible_paths = [
                Path("backend/data/images") / filename,
                Path("data/images") / filename,
                Path("../data/images") / filename,
            ]
            
            for path in possible_paths:
                if path.exists():
                    logger.info(f"[视频服务] 找到本地图片文件: {path}")
                    return str(path.absolute())
            
            logger.error(f"[视频服务] 无法找到本地文件: {filename}")
            logger.error(f"[视频服务] 已尝试路径: {[str(p) for p in possible_paths]}")
        else:
            # 网络URL，下载到临时文件
            logger.info(f"[视频服务] 下载网络图片: {image_url[:80]}...")
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                temp_file.write(resp.content)
                temp_file.close()
                logger.info(f"[视频服务] 图片已下载到: {temp_file.name}")
                return temp_file.name
    
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

# 即梦视频模型配置
# - DEFAULT_VIDEO_MODEL：原先使用的 jimeng-video-3.5-pro，只支持 5/10 秒
# - LONG_VIDEO_MODEL：最新的 4.0 系列模型，支持 15 秒
DEFAULT_VIDEO_MODEL = "jimeng-video-3.5-pro"
LONG_VIDEO_MODEL = "jimeng-video-4.0-pro"
LONG_VIDEO_MAX_DURATION = 15


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
    duration_int = int(duration)
    # 统一限制到 5/10/15 秒，超出范围回退到 5 秒
    if duration_int not in [5, 10, LONG_VIDEO_MAX_DURATION]:
        duration_int = 5

    # 根据时长选择模型：
    # - 5/10 秒：使用旧模型（3.5-pro）
    # - 15 秒：使用新模型（4.0-pro，支持 15 秒）
    if duration_int > 10:
        model = LONG_VIDEO_MODEL
    else:
        model = DEFAULT_VIDEO_MODEL

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
    data = {
        "model": model,
        "prompt": prompt or "smooth transition, cinematic camera movement",
        "duration": str(duration_int),
    }
    try:
        logger.info(f"[视频服务] 片段 {segment_index} 发送POST到 {url}")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
        raw_text = resp.text or ""
        logger.info(f"[视频服务] 片段 {segment_index} 响应状态: {resp.status_code}, 内容长度: {len(raw_text)}")
        
        if resp.status_code != 200:
            logger.error(f"[视频服务] 片段 {segment_index} HTTP错误: {resp.status_code}, 响应: {raw_text[:500]}")
            raise ValueError(f"即梦视频 API 返回 {resp.status_code}: {raw_text[:500]}")

        result = resp.json() if raw_text.strip() else {}
        code = result.get("code")
        msg = result.get("message")
        if code and code != 0:
            logger.error(f"[视频服务] 片段 {segment_index} API错误码: {code}, 消息: {msg}, 完整响应: {result}")
            raise ValueError(f"即梦视频API错误 (code={code}): {msg}")

        # 解析：可能是同步返回 video_url，或异步返回 task_id
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
        async with httpx.AsyncClient(timeout=30) as client:
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
        duration: 视频时长（秒），支持 5 / 10 / 15 秒（15 秒需 4.0 系列模型）
        prompt: 可选的运动提示词
    
    Returns:
        视频 URL
    """
    settings = get_settings()
    url = f"{settings.jimeng_api_base_url.rstrip('/')}/v1/videos/generations"
    headers = {
        "Authorization": f"Bearer {settings.jimeng_session_id}",
    }
    
    # 确保 duration 是 5 / 10 / 15 秒
    duration_int = int(duration)
    if duration_int not in [5, 10, LONG_VIDEO_MAX_DURATION]:
        logger.warning(f"[视频服务] duration={duration_int} 不在支持范围，调整为 5 秒")
        duration_int = 5

    # 选择模型：>10 秒使用 4.0 模型，其余使用 3.5 模型
    if duration_int > 10:
        model = LONG_VIDEO_MODEL
    else:
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
        async with httpx.AsyncClient(timeout=600) as client:
            logger.info("[视频服务] 发送POST请求（multipart/form-data）...")
            resp = await client.post(url, headers=headers, data=data, files=files)
            logger.info(f"[视频服务] ========== 收到响应 ==========")
            logger.info(f"[视频服务] 响应状态码: {resp.status_code}")
            logger.info(f"[视频服务] 响应头: {dict(resp.headers)}")
            
            # 获取原始响应文本
            raw_text = resp.text or ""
            logger.info(f"[视频服务] 原始响应 (前1000字符): {raw_text[:1000]}")
            
            if resp.status_code != 200:
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
        async with httpx.AsyncClient(timeout=300) as client:
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
        视频时长（5 / 10 / 15 秒）
    """
    # 规则：
    # - 预估音频 <= 5 秒：使用 5 秒视频
    # - 5 秒 < 预估音频 <= 10 秒：使用 10 秒视频
    # - 预估音频 > 10 秒：使用 15 秒视频（需要 4.0 模型）
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
    - 如果音频时长 > 视频时长：视频循环播放，最后一段慢放到剩余时长
    
    Args:
        video_clip: VideoFileClip 对象
        audio_duration: 音频时长（秒）
    
    Returns:
        调整后的视频片段
    """
    from moviepy.editor import VideoFileClip, concatenate_videoclips
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
    else:
        # 音频更长：视频循环播放
        loops = int(audio_duration / video_duration)
        remainder = audio_duration % video_duration
        
        clips = []
        # 添加完整循环的视频
        for _ in range(loops):
            clips.append(video_clip)
        
        # 如果有余数，添加最后一段
        if remainder > 0.1:  # 避免过短的片段
            if remainder < video_duration:
                # 余数小于视频时长，需要慢放
                speed_factor = video_duration / remainder
                speed_factor = max(0.3, min(speed_factor, 2.0))
                last_clip = video_clip.fx(speedx, speed_factor).subclip(0, remainder)
            else:
                # 余数大于视频时长（理论上不会发生，但保险起见）
                last_clip = video_clip.subclip(0, remainder)
            clips.append(last_clip)
        
        logger.debug(f"[视频服务] 视频循环: {video_duration}s 视频循环 {loops} 次 + {remainder:.2f}s")
        return concatenate_videoclips(clips, method="compose")


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
) -> Dict:
    """
    生成完整的故事视频。
    顺序提交每个片段生成请求，最多 5 个在途任务；轮询完成后按 segment 顺序拼接。
    """
    logger.info(f"[视频服务] 开始生成故事视频: {story_id}, 段落数: {len(segments)}, 标题: {title}")

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

        # 待生成列表：(segment_index, start_url, end_url, prompt, duration)
        # duration 根据预估音频时长选择
        specs: List[Tuple[int, str, str, str, int]] = []
        for i in range(len(segments) - 1):
            a, b = segments[i], segments[i + 1]
            if not a.image_url or not b.image_url:
                logger.warning(f"[视频服务] ⚠️ 段落 {i} 或 {i+1} 缺少图片，跳过")
                continue
            motion_prompt = f"{a.emotion} mood, {b.emotion} transition, smooth cinematic movement"
            
            # 根据文本预估音频时长，选择合适的视频时长
            estimated_duration = 5  # 默认 5 秒
            if enable_audio and a.text:
                estimated_audio = _estimate_audio_duration(a.text)
                estimated_duration = _choose_video_duration(estimated_audio)
                logger.debug(f"[视频服务] 段落 {i} 预估音频时长: {estimated_audio:.2f}s, 选择视频时长: {estimated_duration}s")
            
            specs.append((i, a.image_url, b.image_url, motion_prompt, estimated_duration))

        total = len(specs)
        if total == 0:
            task_info["status"] = VideoGenerationStatus.FAILED
            task_info["error"] = "没有可生成片段的段落（缺少图片）"
            return task_info

        task_info["total_clips"] = total
        logger.info(f"[视频服务] 步骤 1: 提交并轮询共 {total} 个片段，最多 {MAX_CONCURRENT_VIDEO_TASKS} 个并发")

        # 按 segment_index 收集结果；pending: task_id -> segment_index
        results: Dict[int, str] = {}
        pending: Dict[str, int] = {}
        next_spec_index = 0

        def update_progress():
            done = len(results)
            task_info["generated_clips"] = done
            task_info["progress"] = int(done / total * 70) if total else 0

        while next_spec_index < total or pending:
            # 提交：有槽位就继续按顺序提交
            while len(pending) < MAX_CONCURRENT_VIDEO_TASKS and next_spec_index < total:
                seg_i, start_url, end_url, prompt, duration = specs[next_spec_index]
                next_spec_index += 1
                
                # 提交（带一次重试）
                submitted = False
                for attempt in range(2):  # 最多尝试2次
                    try:
                        r = await submit_video_clip_request(
                            segment_index=seg_i,
                            start_image_url=start_url,
                            end_image_url=end_url,
                            duration=duration,  # 使用预估的时长
                            prompt=prompt,
                        )
                        if r["type"] == "url":
                            results[seg_i] = r["video_url"]
                            update_progress()
                            logger.info(f"[视频服务] 片段 {seg_i} 同步返回 URL")
                        else:
                            pending[r["task_id"]] = r["segment_index"]
                            logger.info(f"[视频服务] 片段 {seg_i} 已提交，task_id={r['task_id'][:16]}..., 当前在途: {len(pending)}/{MAX_CONCURRENT_VIDEO_TASKS}")
                        submitted = True
                        break
                    except Exception as e:
                        if attempt == 0:
                            logger.warning(f"[视频服务] 片段 {seg_i} 提交失败（第1次），将重试: {e}")
                            await asyncio.sleep(2)  # 等待2秒后重试
                        else:
                            logger.error(f"[视频服务] ❌ 片段 {seg_i} 提交失败（已重试），跳过: {e}")
                
                if not submitted:
                    logger.error(f"[视频服务] 片段 {seg_i} 两次提交均失败，跳过该片段")

            if not pending:
                break

            # 并发轮询所有在途任务（使用 asyncio.gather）
            logger.debug(f"[视频服务] 开始并发轮询 {len(pending)} 个在途任务")
            pending_list = list(pending.items())
            poll_tasks = [poll_video_task(task_id) for task_id, _ in pending_list]
            poll_results = await asyncio.gather(*poll_tasks, return_exceptions=True)
            
            # 处理轮询结果
            for (task_id, seg_i), poll_result in zip(pending_list, poll_results):
                if isinstance(poll_result, Exception):
                    logger.warning(f"[视频服务] 片段 {seg_i} 轮询异常: {poll_result}")
                    continue
                
                if poll_result["status"] == "success" and poll_result.get("video_url"):
                    results[seg_i] = poll_result["video_url"]
                    del pending[task_id]
                    update_progress()
                    logger.info(f"[视频服务] ✅ 片段 {seg_i} 轮询完成，剩余在途: {len(pending)}/{MAX_CONCURRENT_VIDEO_TASKS}")
                elif poll_result["status"] == "failed":
                    del pending[task_id]
                    logger.warning(f"[视频服务] ❌ 片段 {seg_i} 生成失败")

            # 如果还有在途任务，等待后继续轮询
            if pending:
                logger.debug(f"[视频服务] 等待 {POLL_INTERVAL_SECONDS} 秒后继续轮询 {len(pending)} 个任务")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        if not results:
            task_info["status"] = VideoGenerationStatus.FAILED
            task_info["error"] = "没有成功生成任何视频片段"
            return task_info

        # 按 segment_index 顺序拼接（顺序必须正确）
        ordered_indices = sorted(results.keys())
        video_clips = []
        audio_clips = []
        for k, seg_i in enumerate(ordered_indices):
            video_url = results[seg_i]
            clip_path = temp_dir / f"clip_{k:03d}.mp4"
            await download_file(video_url, str(clip_path))
            video_clips.append(str(clip_path))
            if enable_audio and seg_i < len(segments) and segments[seg_i].text:
                audio_path = temp_dir / f"audio_{k:03d}.mp3"
                # 使用默认音色生成音频
                audio_file = await generate_tts_audio(
                    text=segments[seg_i].text,
                    output_path=str(audio_path),
                    voice_id="zh-CN-XiaoxiaoNeural",  # 默认中文女声
                )
                if audio_file:
                    logger.info(f"[视频服务] 片段 {k} 音频生成成功: {audio_file}")
                else:
                    logger.warning(f"[视频服务] ⚠️ 片段 {k} 音频生成失败，将跳过音频")
                audio_clips.append(audio_file)
            else:
                audio_clips.append("")

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
    # 检查是否可以生成视频（需要当前和下一段都有图片）
    if segment_index >= len(segments) - 1:
        return None
    
    current_seg = segments[segment_index]
    next_seg = segments[segment_index + 1]
    
    if not current_seg.image_url or not next_seg.image_url:
        logger.info(f"[视频服务] 段落 {segment_index} 和 {segment_index+1} 还未完成图片生成，暂不生成视频")
        return None
    
    logger.info(f"[视频服务] 异步生成段落 {segment_index} -> {segment_index+1} 的视频片段")
    
    try:
        motion_prompt = f"{current_seg.emotion} mood transition, smooth cinematic camera movement"
        # 浏览时的过渡片段仍然保持 5 秒，使用默认模型即可
        video_url = await generate_video_clip(
            start_image_url=current_seg.image_url,
            end_image_url=next_seg.image_url,
            duration=5,
            prompt=motion_prompt,
        )
        
        logger.info(f"[视频服务] ✅ 异步视频片段生成完成: 段落 {segment_index} -> {segment_index+1}")
        return video_url
        
    except Exception as e:
        logger.error(f"[视频服务] ❌ 异步视频片段生成失败: {e}")
        return None
