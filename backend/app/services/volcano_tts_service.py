"""火山 TTS 官方 API 服务（付费用户专享）"""
import asyncio
import importlib.util
import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.utils.paths import AUDIO_DIR, PROJECT_ROOT
from app.constants.voices import (
    DEFAULT_PREMIUM_VOICE_ID,
    PREVIEW_TEXT,
    get_voice_by_id,
    is_premium_voice,
)

logger = logging.getLogger(__name__)

# TTS 音频存储路径
VOLCANO_TTS_AUDIO_DIR = AUDIO_DIR / "volcano_tts"
VOLCANO_TTS_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
VOLCANO_PREVIEW_AUDIO_DIR = AUDIO_DIR / "preview_volcano"
VOLCANO_PREVIEW_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

logger.info(f"[火山TTS] 音频目录: {VOLCANO_TTS_AUDIO_DIR}")


@lru_cache(maxsize=1)
def _load_binary_module():
    """
    动态加载官方 demo 实现。
    源文件：PROJECT_ROOT/apis/tts/binary.py
    """
    binary_path = PROJECT_ROOT / "apis" / "tts" / "binary.py"
    if not binary_path.exists():
        raise RuntimeError(f"缺少官方 demo 文件: {binary_path}")

    spec = importlib.util.spec_from_file_location("volcano_tts_binary_demo", binary_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载官方 demo 文件: {binary_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ========== TTS 生成逻辑 ==========


def get_cluster(voice: str) -> str:
    """根据音色类型返回集群名称"""
    if voice.startswith("S_"):
        return "volcano_icl"
    return "volcano_tts"


def is_volcano_tts_available() -> bool:
    """检查线上 TTS 配置是否可用。"""
    settings = get_settings()
    return bool(settings.volcano_tts_appid and settings.volcano_tts_access_token)


async def generate_tts_audio_volcano(
    text: str,
    output_path: str,
    voice_id: Optional[str] = None,
    rate: str = "+0%",
    max_retries: int = 3,
) -> str:
    """
    使用火山 TTS 官方 API 生成语音

    Args:
        text: 要转换的文本
        output_path: 输出文件路径
        voice_id: 音色ID（可选，默认使用配置中的音色）
        rate: 语速调整（暂不支持）
        max_retries: 最大重试次数

    Returns:
        生成的音频文件路径

    Raises:
        RuntimeError: TTS 生成失败
    """
    settings = get_settings()
    _ = rate  # 保留接口兼容；火山 TTS 当前不使用 rate 参数

    # 验证配置
    if not is_volcano_tts_available():
        raise RuntimeError(
            "火山 TTS API 配置不完整，请检查 .env 文件中的 "
            "VOLCANO_TTS_APPID 和 VOLCANO_TTS_ACCESS_TOKEN"
        )

    # 使用用户指定音色（付费音色）或默认付费音色
    voice_type = (voice_id or settings.volcano_tts_voice_type or DEFAULT_PREMIUM_VOICE_ID).strip()
    if not is_premium_voice(voice_type):
        logger.warning(f"[火山TTS] 音色 {voice_type} 不是付费音色，回退到默认: {DEFAULT_PREMIUM_VOICE_ID}")
        voice_type = DEFAULT_PREMIUM_VOICE_ID
    cluster = get_cluster(voice_type)

    # 确保输出目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"[火山TTS] 开始生成语音，音色: {voice_type}, 文本长度: {len(text)}"
    )

    last_error = None
    for attempt in range(max_retries):
        try:
            # 如果是重试，添加延迟
            if attempt > 0:
                delay = 2**attempt
                logger.info(f"[火山TTS] 等待 {delay}s 后重试...")
                await asyncio.sleep(delay)

            logger.info(
                f"[火山TTS] 连接中: {settings.volcano_tts_endpoint}"
            )
            binary = _load_binary_module()
            synthesize_to_file = getattr(binary, "synthesize_audio_to_file", None)
            if synthesize_to_file is None:
                raise RuntimeError("官方 demo binary.py 缺少 synthesize_audio_to_file 接口")

            result = await synthesize_to_file(
                appid=settings.volcano_tts_appid,
                access_token=settings.volcano_tts_access_token,
                voice_type=voice_type,
                text=text,
                output_path=output_path,
                cluster=cluster,
                encoding=settings.volcano_tts_encoding,
                endpoint=settings.volcano_tts_endpoint,
                proxy=None,
                open_timeout=30.0,
                recv_timeout=30.0,
            )

            output_file = Path(output_path)
            if not output_file.exists() or output_file.stat().st_size == 0:
                raise RuntimeError("未接收到音频数据（文件为空）")

            file_size_kb = output_file.stat().st_size / 1024
            logger.info(
                f"[火山TTS] ✅ 音频生成成功: {output_path} ({file_size_kb:.1f}KB, chunks={result.get('chunk_count', 0)}, logid={result.get('logid', 'N/A')})"
            )
            return output_path

        except Exception as e:
            last_error = e
            logger.warning(
                f"[火山TTS] ⚠️ 生成失败 (尝试 {attempt + 1}/{max_retries}): {e}"
            )

            if attempt == max_retries - 1:
                logger.error(
                    f"[火山TTS] ❌ 所有重试均失败: {e}", exc_info=True
                )

    # 所有重试都失败
    raise RuntimeError(
        f"火山 TTS 生成失败（已重试 {max_retries} 次）: {str(last_error)}"
    )


def get_volcano_tts_audio_path(story_id: str, segment_index: int, voice_id: str) -> Path:
    """
    获取火山 TTS 音频文件路径

    Args:
        story_id: 故事 ID
        segment_index: 段落索引
        voice_id: 音色 ID

    Returns:
        音频文件路径
    """
    filename = f"{story_id}_{segment_index}_{voice_id}.mp3"
    return VOLCANO_TTS_AUDIO_DIR / filename


async def generate_preview_audio_volcano(voice_id: str, force_regenerate: bool = False) -> str:
    """为付费音色生成预览音频。"""
    if not is_volcano_tts_available():
        raise RuntimeError("线上 TTS 服务不可用，请检查 VOLCANO_TTS_* 配置")

    voice_info = get_voice_by_id(voice_id)
    if not voice_info or not is_premium_voice(voice_id):
        raise ValueError(f"无效的付费音色 ID: {voice_id}")

    filename = f"{voice_id}.mp3"
    output_path = VOLCANO_PREVIEW_AUDIO_DIR / filename

    if not force_regenerate and output_path.exists() and output_path.stat().st_size > 0:
        file_size_kb = output_path.stat().st_size / 1024
        logger.info(f"[火山TTS] ✅ 使用缓存预览音频: {voice_id} ({file_size_kb:.1f}KB)")
        return f"data/audio/preview_volcano/{filename}"

    preview_text = PREVIEW_TEXT.format(voice_name=voice_info["name"])
    await generate_tts_audio_volcano(
        text=preview_text,
        output_path=str(output_path),
        voice_id=voice_id,
        max_retries=3,
    )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"预览音频生成失败: {voice_id}")

    return f"data/audio/preview_volcano/{filename}"
