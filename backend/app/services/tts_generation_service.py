"""统一 TTS 生成服务（集成 edge-tts 和官方 API）"""
import time
import logging
from pathlib import Path
from typing import Optional

from app.constants.voices import DEFAULT_VOICE_ID
from app.utils.service_tier import get_service_tier, get_user_identifier
from app.utils.logger_utils import log_service_call, log_cache_check, log_generation_result

# 导入两种服务实现
from app.services.tts_service import (
    generate_tts_audio as generate_tts_edge,
    get_tts_audio_path as get_edge_audio_path,
    TTS_AUDIO_DIR as EDGE_TTS_AUDIO_DIR,
)
from app.services.volcano_tts_service import (
    generate_tts_audio_volcano,
    get_volcano_tts_audio_path,
    VOLCANO_TTS_AUDIO_DIR,
)

logger = logging.getLogger(__name__)


def _get_tts_cache_path(
    story_id: str,
    segment_index: int,
    voice_id: str,
    tier: str,
) -> Path:
    """
    获取 TTS 音频缓存路径

    Args:
        story_id: 故事 ID
        segment_index: 段落索引
        voice_id: 音色 ID
        tier: 服务等级 ("free" 或 "premium")

    Returns:
        音频文件路径
    """
    if tier == "premium":
        return get_volcano_tts_audio_path(story_id, segment_index, voice_id)
    else:
        return get_edge_audio_path(story_id, segment_index, voice_id)


async def generate_segment_tts(
    story_id: str,
    segment_index: int,
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    speed: float = 1.0,
    user: Optional[dict] = None,
) -> str:
    """
    根据用户等级选择服务生成 TTS 音频（带缓存优化）

    Args:
        story_id: 故事 ID
        segment_index: 段落索引
        text: 段落文本
        voice_id: 音色 ID
        speed: 播放倍速（用于生成时的 rate 参数）
        user: 用户信息（None=未登录，is_paid=True=付费用户）

    Returns:
        音频文件相对路径

    Raises:
        RuntimeError: TTS 生成失败
    """
    start_time = time.time()
    tier = get_service_tier(user)
    user_email = get_user_identifier(user)

    # 记录服务调用
    log_service_call(
        logger,
        service_type="TTS生成",
        tier=tier,
        user_email=user_email,
        voice_id=voice_id,
        text_length=len(text),
    )

    # 获取缓存路径
    audio_path = _get_tts_cache_path(story_id, segment_index, voice_id, tier)

    # 检查缓存
    if audio_path.exists() and audio_path.stat().st_size > 0:
        cache_key = f"{story_id}_{segment_index}_{voice_id}"
        log_cache_check(logger, "音频", cache_hit=True, cache_key=cache_key)

        file_size_kb = audio_path.stat().st_size / 1024
        elapsed = time.time() - start_time
        logger.info(
            f"[TTS生成] ✅ 使用缓存，耗时: {elapsed:.2f}s, "
            f"路径: {audio_path.name}, 大小: {file_size_kb:.1f}KB"
        )

        # 返回相对路径
        if tier == "premium":
            return f"data/audio/volcano_tts/{audio_path.name}"
        else:
            return f"data/audio/tts/{audio_path.name}"

    cache_key = f"{story_id}_{segment_index}_{voice_id}"
    log_cache_check(logger, "音频", cache_hit=False, cache_key=cache_key)

    try:
        # 根据服务等级选择API
        if tier == "premium":
            logger.info("[TTS生成] 🚀 使用官方火山 TTS API（付费用户）")
            await generate_tts_audio_volcano(
                text=text,
                output_path=str(audio_path),
                voice_id=voice_id,
                rate="+0%",  # 火山 TTS 暂不支持倍速
                max_retries=3,
            )
            relative_path = f"data/audio/volcano_tts/{audio_path.name}"
        else:
            logger.info("[TTS生成] 🐌 使用 edge-tts 服务（免费用户）")
            await generate_tts_edge(
                text=text,
                output_path=str(audio_path),
                voice_id=voice_id,
                rate="+0%",  # 始终使用标准倍速生成，由播放器动态调整
                max_retries=3,
            )
            relative_path = f"data/audio/tts/{audio_path.name}"

        # 验证文件生成成功
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise RuntimeError(f"TTS 文件生成失败: {audio_path}")

        # 记录结果
        elapsed = time.time() - start_time
        file_size_kb = audio_path.stat().st_size / 1024
        log_generation_result(
            logger,
            service_type="TTS生成",
            success=True,
            elapsed=elapsed,
            output_path=str(audio_path),
        )
        logger.info(f"[TTS生成] 文件大小: {file_size_kb:.1f}KB")

        return relative_path

    except Exception as e:
        elapsed = time.time() - start_time
        log_generation_result(
            logger,
            service_type="TTS生成",
            success=False,
            elapsed=elapsed,
            error=str(e),
        )

        # 降级策略：如果官方 API 失败，尝试 edge-tts
        if tier == "premium":
            logger.warning(
                f"[TTS生成] ⚠️ 官方 API 失败，尝试降级到 edge-tts: {e}"
            )
            try:
                # 使用 edge-tts 路径
                fallback_path = get_edge_audio_path(story_id, segment_index, voice_id)
                await generate_tts_edge(
                    text=text,
                    output_path=str(fallback_path),
                    voice_id=voice_id,
                    rate="+0%",
                    max_retries=3,
                )
                logger.info("[TTS生成] ✅ 降级到 edge-tts 成功")
                return f"data/audio/tts/{fallback_path.name}"
            except Exception as fallback_error:
                logger.error(
                    f"[TTS生成] ❌ 降级失败: {fallback_error}", exc_info=True
                )
                raise

        raise
