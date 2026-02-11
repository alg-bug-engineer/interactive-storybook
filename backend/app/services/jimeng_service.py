"""
即梦 API 集成 - 方案 B：开源 jimeng-api 本地服务
接口: POST {base_url}/v1/images/generations
认证: Authorization: Bearer {session_id}
"""
import logging
import io
import base64
import hashlib
from pathlib import Path
from typing import List
import httpx
from PIL import Image
from app.config import get_settings
from app.models.story import Character, StorySegment
from app.constants.story_styles import get_style_prompt, DEFAULT_STYLE_ID

logger = logging.getLogger(__name__)

NEGATIVE_PROMPT = (
    "scary, horror, violent, blood, dark, ugly, deformed, nsfw, "
    "realistic photo, text, watermark, signature, blurry, "
    "low quality, bad anatomy, extra limbs"
)

EMOTION_MAP = {
    "happy": "warm golden sunlight, cheerful bright colors, blue sky",
    "excited": "vibrant saturated colors, dynamic angle, sparkles",
    "mysterious": "soft purple and blue fog, moonlight, glowing details",
    "warm": "sunset orange glow, cozy atmosphere, soft bokeh",
    "tense": "dramatic shadows, stormy clouds, contrast lighting",
}

# 默认风格（向后兼容，已迁移到story_styles.py）
DEFAULT_STYLE = "whimsical children's book watercolor illustration, Pixar style, cute rounded characters, storybook illustration, rich colors, detailed background, high quality, masterpiece"

# 压缩图片配置
COMPRESSED_IMAGES_DIR = Path("data/images")
COMPRESSED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
COMPRESSION_QUALITY = 85  # JPEG 压缩质量（1-100）
MAX_IMAGE_WIDTH = 1280  # 最大宽度，保持16:9比例


def _build_prompt(
    scene_description: str,
    characters: List[Character],
    emotion: str,
    style_id: str = DEFAULT_STYLE_ID,
) -> str:
    # 构建角色描述
    char_desc = ", ".join(f"{c.name}({c.appearance})" for c in characters)
    
    # 多角色场景优化：当有2个或更多角色时，明确强调多角色互动
    if len(characters) >= 2:
        multi_char_emphasis = "multiple characters interacting together in the same scene, all characters visible and engaged"
        char_desc = f"{char_desc}, {multi_char_emphasis}"
    
    mood = EMOTION_MAP.get(emotion, EMOTION_MAP["warm"])
    style_prompt = get_style_prompt(style_id)
    return f"{style_prompt}, {scene_description}, featuring {char_desc}, {mood}"


async def compress_and_save_image(image_url: str) -> str:
    """
    下载图片，压缩并保存为JPEG格式，返回本地路径
    
    Args:
        image_url: 原始图片URL或base64数据
    
    Returns:
        压缩后的本地图片路径（相对路径）
    """
    try:
        # 生成唯一文件名（基于URL hash）
        url_hash = hashlib.md5(image_url.encode()).hexdigest()[:16]
        output_path = COMPRESSED_IMAGES_DIR / f"{url_hash}.jpg"
        
        # 如果已经压缩过，直接返回
        if output_path.exists():
            logger.debug(f"[图片压缩] 图片已存在，跳过: {output_path}")
            return str(output_path)
        
        # 处理base64图片
        if image_url.startswith("data:image"):
            logger.info("[图片压缩] 处理base64图片")
            # 提取base64数据
            base64_data = image_url.split(",")[1] if "," in image_url else image_url
            image_data = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_data))
        # 处理URL图片
        else:
            logger.info(f"[图片压缩] 下载图片: {image_url[:80]}...")
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                image = Image.open(io.BytesIO(resp.content))
        
        # 转换为RGB（处理RGBA等格式）
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 等比例缩放（保持16:9）
        original_width, original_height = image.size
        if original_width > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / original_width
            new_height = int(original_height * ratio)
            image = image.resize((MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)
            logger.info(f"[图片压缩] 缩放: {original_width}x{original_height} -> {MAX_IMAGE_WIDTH}x{new_height}")
        
        # 保存为JPEG，压缩质量85
        image.save(output_path, 'JPEG', quality=COMPRESSION_QUALITY, optimize=True)
        file_size = output_path.stat().st_size / 1024  # KB
        logger.info(f"[图片压缩] ✅ 压缩完成: {output_path}, 大小: {file_size:.1f}KB")
        
        return str(output_path)
        
    except Exception as e:
        logger.error(f"[图片压缩] ❌ 压缩失败: {type(e).__name__}: {e}", exc_info=True)
        # 压缩失败时返回原始URL
        return image_url


async def generate_image(
    prompt: str,
    *,
    ratio: str = "16:9",
    resolution: str = "1k",
    negative_prompt: str = NEGATIVE_PROMPT,
    compress: bool = True,
) -> str:
    """调用即梦 API 生成一张图，可选压缩，返回图片 URL 或本地路径。"""
    settings = get_settings()
    url = f"{settings.jimeng_api_base_url.rstrip('/')}/v1/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.jimeng_session_id}",
    }
    payload = {
        "model": settings.jimeng_model,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "ratio": ratio,
        "resolution": resolution,
    }
    
    logger.info(f"[即梦API] 开始生成图片，URL: {url}, Model: {settings.jimeng_model}, 分辨率: {resolution}")
    logger.debug(f"[即梦API] Prompt (前100字): {prompt[:100]}...")
    
    try:
        # 增加超时时间到 300 秒（5分钟），即梦生成可能需要较长时间
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(url, headers=headers, json=payload)
            logger.info(f"[即梦API] 响应状态码: {resp.status_code}")
            
            if resp.status_code != 200:
                error_text = resp.text[:500]
                logger.error(f"[即梦API] 请求失败: {resp.status_code}, 响应: {error_text}")
                raise ValueError(f"即梦 API 返回错误 {resp.status_code}: {error_text}")
            
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[即梦API] 响应数据: {str(data)[:200]}...")
            
        urls = data.get("data") or []
        if not urls:
            logger.error(f"[即梦API] 响应中没有图片数据，完整响应: {data}")
            raise ValueError("即梦 API 未返回图片数据")
        
        image_url = urls[0].get("url") or urls[0].get("b64_json")
        if not image_url:
            logger.error(f"[即梦API] 图片 URL 为空，响应: {urls[0]}")
            raise ValueError("即梦 API 返回的图片 URL 为空")
        
        logger.info(f"[即梦API] ✅ 图片生成成功，原始URL长度: {len(image_url)}")
        
        # 压缩图片（如果启用）
        if compress:
            compressed_path = await compress_and_save_image(image_url)
            # 转换为可访问的URL路径
            if compressed_path.startswith("data/images/"):
                # 返回静态文件URL
                filename = Path(compressed_path).name
                settings = get_settings()
                # 假设后端运行在 localhost:8100
                api_base = f"http://localhost:{settings.backend_port}"
                return f"{api_base}/static/images/{filename}"
            return compressed_path
        
        return image_url
        
    except httpx.TimeoutException as e:
        logger.error(f"[即梦API] ⏱️ 请求超时: {e}")
        raise ValueError(f"即梦 API 请求超时: {e}")
    except httpx.RequestError as e:
        logger.error(f"[即梦API] ❌ 网络错误: {e}")
        raise ValueError(f"即梦 API 网络错误: {e}")
    except Exception as e:
        logger.error(f"[即梦API] ❌ 未知错误: {type(e).__name__}: {e}", exc_info=True)
        raise


async def generate_story_illustration(
    segment: StorySegment,
    characters: List[Character],
    style_id: str = DEFAULT_STYLE_ID,
) -> str:
    """根据故事段落生成插画（自动压缩）。"""
    logger.info(f"[即梦API] 为段落生成插画，风格ID: {style_id}, 情感: {segment.emotion}, 场景描述: {segment.scene_description[:50]}...")
    prompt = _build_prompt(
        segment.scene_description,
        characters,
        segment.emotion,
        style_id=style_id,
    )
    logger.info(f"[即梦API] 完整 Prompt (前200字符): {prompt[:200]}...")
    logger.info(f"[即梦API] 应用的风格prompt: {get_style_prompt(style_id)[:100]}...")
    # 降低分辨率从2k到1k，并启用压缩
    return await generate_image(prompt=prompt, ratio="16:9", resolution="1k", compress=True)
