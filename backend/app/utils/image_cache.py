"""图片缓存管理工具"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional
from app.utils.paths import IMAGE_CACHE_DIR, PROJECT_ROOT, BACKEND_ROOT

logger = logging.getLogger(__name__)

# 缓存映射文件
CACHE_DIR = IMAGE_CACHE_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_MAP_FILE = CACHE_DIR / "cache_map.json"


def _resolve_image_path(path_str: str) -> Path:
    """将缓存中的相对/绝对路径统一解析为绝对路径。"""
    p = Path(path_str)
    if p.is_absolute():
        return p

    # 兼容历史相对路径：
    # - data/images/xxx（通常相对 backend/）
    # - backend/data/images/xxx（通常相对项目根）
    candidates = [BACKEND_ROOT / p, PROJECT_ROOT / p]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_cache_key(prompt: str, style_id: str) -> str:
    """
    生成缓存键（基于 prompt + style_id）

    Args:
        prompt: 图片生成提示词
        style_id: 故事风格ID

    Returns:
        16位十六进制字符串

    Examples:
        >>> get_cache_key("a cute cat", "q_cute")
        'a1b2c3d4e5f6g7h8'
    """
    content = f"{prompt}|{style_id}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def _load_cache_map() -> dict:
    """加载缓存映射"""
    if not CACHE_MAP_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_MAP_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[图片缓存] 加载缓存映射失败: {e}")
        return {}


def _save_cache_map(cache_map: dict) -> None:
    """保存缓存映射"""
    try:
        CACHE_MAP_FILE.write_text(
            json.dumps(cache_map, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"[图片缓存] 保存缓存映射失败: {e}")


def get_cached_image(prompt: str, style_id: str) -> Optional[str]:
    """
    获取缓存的图片路径

    Args:
        prompt: 图片生成提示词
        style_id: 故事风格ID

    Returns:
        缓存的图片路径，如果没有缓存则返回 None

    Examples:
        >>> get_cached_image("a cute cat", "q_cute")
        'data/images/abc123.jpg'
    """
    cache_key = get_cache_key(prompt, style_id)
    cache_map = _load_cache_map()

    if cache_key in cache_map:
        image_path = cache_map[cache_key]
        resolved = _resolve_image_path(image_path)

        # 验证文件是否存在
        if resolved.exists():
            logger.info(f"[图片缓存] ✅ 命中，缓存键: {cache_key}")
            return str(resolved)
        else:
            # 文件已删除，清理缓存映射
            logger.warning(
                f"[图片缓存] ⚠️ 文件已删除，清理缓存: {image_path}"
            )
            del cache_map[cache_key]
            _save_cache_map(cache_map)

    logger.info(f"[图片缓存] ❌ 未命中，缓存键: {cache_key}")
    return None


def save_image_cache(prompt: str, style_id: str, image_path: str) -> None:
    """
    保存图片缓存映射

    Args:
        prompt: 图片生成提示词
        style_id: 故事风格ID
        image_path: 图片路径

    Examples:
        >>> save_image_cache("a cute cat", "q_cute", "data/images/abc123.jpg")
    """
    cache_key = get_cache_key(prompt, style_id)
    cache_map = _load_cache_map()

    cache_map[cache_key] = image_path
    _save_cache_map(cache_map)

    logger.info(
        f"[图片缓存] ✅ 已保存，缓存键: {cache_key}, 路径: {image_path}"
    )


def clear_cache() -> int:
    """
    清理所有缓存映射

    Returns:
        清理的缓存条目数量
    """
    cache_map = _load_cache_map()
    count = len(cache_map)

    if count > 0:
        _save_cache_map({})
        logger.info(f"[图片缓存] ✅ 已清理 {count} 条缓存")

    return count


def get_cache_stats() -> dict:
    """
    获取缓存统计信息

    Returns:
        缓存统计字典
    """
    cache_map = _load_cache_map()

    # 统计文件存在的条目
    valid_count = 0
    invalid_count = 0
    total_size = 0

    for image_path in cache_map.values():
        path = _resolve_image_path(image_path)
        if path.exists():
            valid_count += 1
            total_size += path.stat().st_size
        else:
            invalid_count += 1

    return {
        "total_entries": len(cache_map),
        "valid_entries": valid_count,
        "invalid_entries": invalid_count,
        "total_size_mb": total_size / (1024 * 1024),
    }
