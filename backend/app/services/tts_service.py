"""TTS 服务：基于 edge-tts 的语音合成"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    logging.warning("edge-tts 未安装，TTS 功能将不可用。请运行: pip install edge-tts")

from app.constants.voices import (
    DEFAULT_VOICE_ID,
    AVAILABLE_VOICES,
    get_voice_by_id,
    is_valid_voice,
    PREVIEW_TEXT,
)

logger = logging.getLogger(__name__)

# TTS 音频存储路径
TTS_AUDIO_DIR = Path("backend/data/audio/tts")
TTS_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# 预览音频存储路径
PREVIEW_AUDIO_DIR = Path("backend/data/audio/preview")
PREVIEW_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


async def generate_tts_audio(
    text: str,
    output_path: str,
    voice_id: str = DEFAULT_VOICE_ID,
    rate: str = "+0%",
    volume: str = "+0%",
    max_retries: int = 3,
) -> str:
    """
    生成 TTS 语音文件（带重试机制）
    
    Args:
        text: 要转换的文本
        output_path: 输出文件路径
        voice_id: 音色 ID（如 zh-CN-XiaoxiaoNeural）
        rate: 语速调整（如 +10% 或 -10%）
        volume: 音量调整（如 +10% 或 -10%）
        max_retries: 最大重试次数
    
    Returns:
        生成的音频文件路径
    
    Raises:
        RuntimeError: TTS 生成失败
    """
    if not HAS_EDGE_TTS:
        raise RuntimeError("edge-tts 未安装，无法生成语音")
    
    # 验证音色
    if not is_valid_voice(voice_id):
        logger.warning(f"音色 {voice_id} 无效，使用默认音色 {DEFAULT_VOICE_ID}")
        voice_id = DEFAULT_VOICE_ID
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    last_error = None
    for attempt in range(max_retries):
        try:
            logger.info(f"[TTS] 开始生成语音 (尝试 {attempt + 1}/{max_retries}): voice={voice_id}, text_len={len(text)}")
            
            # 如果是重试，添加延迟避免频率限制
            if attempt > 0:
                delay = 2 ** attempt  # 指数退避：2s, 4s, 8s
                logger.info(f"[TTS] 等待 {delay}s 后重试...")
                await asyncio.sleep(delay)
            
            # 使用 edge-tts 生成语音
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, volume=volume)
            await communicate.save(output_path)
            
            # 验证文件是否生成成功
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise RuntimeError(f"TTS 文件生成失败: {output_path}")
            
            logger.info(f"[TTS] ✅ 语音生成成功: {output_path} ({os.path.getsize(output_path)} bytes)")
            return output_path
            
        except Exception as e:
            last_error = e
            logger.warning(f"[TTS] ⚠️ 生成失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            
            # 如果是最后一次尝试，记录完整错误
            if attempt == max_retries - 1:
                logger.error(f"[TTS] ❌ 所有重试均失败: {e}", exc_info=True)
    
    # 所有重试都失败
    raise RuntimeError(f"TTS 生成失败（已重试 {max_retries} 次）: {str(last_error)}")


async def generate_preview_audio(voice_id: str, force_regenerate: bool = False) -> str:
    """
    为指定音色生成预览音频
    
    Args:
        voice_id: 音色 ID
        force_regenerate: 是否强制重新生成（默认 False，使用缓存）
    
    Returns:
        预览音频文件路径（相对路径）
    """
    if not HAS_EDGE_TTS:
        raise RuntimeError("edge-tts 未安装，无法生成预览音频")
    
    # 验证音色
    voice_info = get_voice_by_id(voice_id)
    if not voice_info:
        raise ValueError(f"无效的音色 ID: {voice_id}")
    
    # 生成预览文件名
    filename = f"{voice_id}.mp3"
    output_path = PREVIEW_AUDIO_DIR / filename
    
    # 如果预览文件已存在且不强制重新生成，直接返回
    if not force_regenerate and output_path.exists() and output_path.stat().st_size > 0:
        logger.info(f"[TTS] 预览音频已存在: {output_path}")
        return f"data/audio/preview/{filename}"
    
    # 生成预览文案
    preview_text = PREVIEW_TEXT.format(voice_name=voice_info["name"])
    
    # 生成语音（带重试机制）
    await generate_tts_audio(preview_text, str(output_path), voice_id, max_retries=3)
    
    return f"data/audio/preview/{filename}"


async def pregenerate_all_previews():
    """
    预生成所有推荐音色的预览音频（后台任务）
    
    注意：为避免触发 Microsoft 限流，采用串行生成 + 延迟策略
    """
    if not HAS_EDGE_TTS:
        logger.warning("[TTS] edge-tts 未安装，跳过预览音频预生成")
        return
    
    logger.info("[TTS] 开始预生成所有推荐音色的预览音频...")
    
    success_count = 0
    failed_voices = []
    
    for voice in AVAILABLE_VOICES:
        if not voice.get("is_recommended"):
            continue
        
        try:
            # 串行生成，避免并发请求触发限流
            await generate_preview_audio(voice["id"])
            success_count += 1
            logger.info(f"[TTS] ✅ {voice['name']} ({voice['id']}) 预览生成成功")
            
            # 每次生成后延迟 1 秒，避免频率限制
            await asyncio.sleep(1)
            
        except Exception as e:
            failed_voices.append(voice["name"])
            logger.warning(f"[TTS] ⚠️ {voice['name']} ({voice['id']}) 预览生成失败: {e}")
    
    total = sum(1 for v in AVAILABLE_VOICES if v.get("is_recommended"))
    
    if success_count > 0:
        logger.info(f"[TTS] ✅ 预生成完成: {success_count}/{total} 个音色成功")
    else:
        logger.warning(f"[TTS] ⚠️ 预生成失败: 所有音色均失败，可能是网络问题或 edge-tts 服务不可用")
        logger.warning(f"[TTS] 💡 不用担心，音色试听时会按需生成")


def speed_to_rate(speed: float) -> str:
    """
    将播放倍速转换为 edge-tts 的 rate 参数
    
    Args:
        speed: 播放倍速（如 0.75, 1.0, 1.5, 2.0）
    
    Returns:
        rate 字符串（如 "-25%", "+0%", "+50%", "+100%"）
    """
    # edge-tts 的 rate 参数范围：-50% 到 +100%
    # speed 0.5 -> -50%, 1.0 -> +0%, 1.5 -> +50%, 2.0 -> +100%
    percentage = int((speed - 1.0) * 100)
    
    # 限制范围
    percentage = max(-50, min(100, percentage))
    
    return f"{percentage:+d}%"


def get_tts_audio_path(story_id: str, segment_index: int, voice_id: str) -> Path:
    """
    获取 TTS 音频文件路径
    
    Args:
        story_id: 故事 ID
        segment_index: 段落索引
        voice_id: 音色 ID
    
    Returns:
        音频文件路径
    """
    filename = f"{story_id}_{segment_index}_{voice_id}.mp3"
    return TTS_AUDIO_DIR / filename


async def get_or_generate_segment_audio(
    story_id: str,
    segment_index: int,
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    speed: float = 1.0,
) -> str:
    """
    获取或生成段落音频（带缓存）
    
    Args:
        story_id: 故事 ID
        segment_index: 段落索引
        text: 段落文本
        voice_id: 音色 ID
        speed: 播放倍速
    
    Returns:
        音频文件相对路径
    """
    # 获取缓存路径
    audio_path = get_tts_audio_path(story_id, segment_index, voice_id)
    
    # 如果缓存存在且有效，直接返回
    if audio_path.exists() and audio_path.stat().st_size > 0:
        logger.info(f"[TTS] 使用缓存音频: {audio_path}")
        return f"data/audio/tts/{audio_path.name}"
    
    # 生成新音频
    rate = speed_to_rate(speed)
    await generate_tts_audio(text, str(audio_path), voice_id, rate=rate)
    
    return f"data/audio/tts/{audio_path.name}"
