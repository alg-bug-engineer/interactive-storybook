"""统一图片生成服务（集成本地和官方 API）"""
import time
import logging
from typing import List, Optional

from app.models.story import Character
from app.constants.story_styles import DEFAULT_STYLE_ID
from app.utils.service_tier import get_service_tier, get_user_identifier
from app.utils.logger_utils import log_service_call, log_cache_check, log_generation_result
from app.utils.image_cache import get_cached_image, save_image_cache

# 导入两种服务实现
from app.services.jimeng_service import (
    _build_prompt as build_prompt_local,
    generate_image as generate_image_local,
)
from app.services.volcano_image_service import (
    generate_image_volcano,
    _build_prompt_volcano,
)

logger = logging.getLogger(__name__)


async def generate_story_image(
    scene_description: str,
    characters: List[Character],
    emotion: str,
    style_id: str = DEFAULT_STYLE_ID,
    user: Optional[dict] = None,
) -> str:
    """
    根据用户等级选择服务生成图片（带缓存优化）

    Args:
        scene_description: 场景描述
        characters: 角色列表
        emotion: 情感类型
        style_id: 故事风格ID
        user: 用户信息（None=未登录，is_paid=True=付费用户）

    Returns:
        图片URL或本地路径

    Raises:
        ValueError: 生成失败
    """
    start_time = time.time()
    tier = get_service_tier(user)
    user_email = get_user_identifier(user)

    # 构建 prompt（两种服务使用相同的 prompt 构建逻辑）
    prompt = build_prompt_local(scene_description, characters, emotion, style_id)

    # 记录服务调用
    log_service_call(
        logger,
        service_type="图片生成",
        tier=tier,
        user_email=user_email,
        style_id=style_id,
        emotion=emotion,
    )

    # 检查缓存
    cached_path = get_cached_image(prompt, style_id)
    if cached_path:
        log_cache_check(logger, "图片", cache_hit=True, cache_key=prompt[:16])
        elapsed = time.time() - start_time
        logger.info(
            f"[图片生成] ✅ 使用缓存，耗时: {elapsed:.2f}s, 路径: {cached_path}"
        )
        return cached_path

    log_cache_check(logger, "图片", cache_hit=False, cache_key=prompt[:16])

    try:
        # 根据服务等级选择API
        if tier == "premium":
            logger.info("[图片生成] 🚀 使用官方火山即梦 API（付费用户）")
            image_path = await generate_image_volcano(
                prompt=prompt,
                style_id=style_id,
                width=1024,
                height=1024,
                compress=True,
            )
        else:
            logger.info("[图片生成] 🐌 使用本地 jimeng-api 服务（免费用户）")
            image_path = await generate_image_local(
                prompt=prompt, ratio="1:1", resolution="1k", compress=True
            )

        # 保存缓存
        save_image_cache(prompt, style_id, image_path)

        # 记录结果
        elapsed = time.time() - start_time
        log_generation_result(
            logger,
            service_type="图片生成",
            success=True,
            elapsed=elapsed,
            output_path=image_path,
        )

        return image_path

    except Exception as e:
        elapsed = time.time() - start_time
        log_generation_result(
            logger,
            service_type="图片生成",
            success=False,
            elapsed=elapsed,
            error=str(e),
        )

        # 降级策略：如果官方 API 失败，尝试本地服务
        if tier == "premium":
            logger.warning(
                f"[图片生成] ⚠️ 官方 API 失败，尝试降级到本地服务: {e}"
            )
            try:
                image_path = await generate_image_local(
                    prompt=prompt, ratio="1:1", resolution="1k", compress=True
                )
                save_image_cache(prompt, style_id, image_path)
                logger.info("[图片生成] ✅ 降级到本地服务成功")
                return image_path
            except Exception as fallback_error:
                logger.error(
                    f"[图片生成] ❌ 降级失败: {fallback_error}", exc_info=True
                )
                raise

        raise
