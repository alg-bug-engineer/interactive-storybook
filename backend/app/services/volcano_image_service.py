"""火山即梦官方 API 服务（付费用户专享）"""
import time
import logging
import hashlib
from pathlib import Path
from typing import List
from volcengine.visual.VisualService import VisualService

from app.config import get_settings
from app.models.story import Character
from app.constants.story_styles import get_style_prompt, DEFAULT_STYLE_ID
from app.services.jimeng_service import (
    compress_and_save_image,
    EMOTION_MAP,
    NEGATIVE_PROMPT,
)

logger = logging.getLogger(__name__)

# 图片缓存目录
VOLCANO_IMAGE_CACHE_DIR = Path("data/images/volcano")
VOLCANO_IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _init_visual_service() -> VisualService:
    """初始化火山视觉服务"""
    settings = get_settings()

    if not settings.volcano_jimeng_ak or not settings.volcano_jimeng_sk:
        raise ValueError(
            "火山即梦 API 配置不完整，请检查 .env 文件中的 "
            "VOLCANO_JIMENG_AK 和 VOLCANO_JIMENG_SK"
        )

    visual_service = VisualService()
    visual_service.set_ak(settings.volcano_jimeng_ak)
    visual_service.set_sk(settings.volcano_jimeng_sk)

    logger.info("[火山即梦] ✅ 服务初始化成功")
    return visual_service


def _build_prompt_volcano(
    scene_description: str,
    characters: List[Character],
    emotion: str,
    style_id: str = DEFAULT_STYLE_ID,
) -> str:
    """构建火山即梦 prompt（与本地服务保持一致）"""
    char_desc = ", ".join(f"{c.name}({c.appearance})" for c in characters)

    if len(characters) >= 2:
        multi_char_emphasis = "multiple characters interacting together in the same scene, all characters visible and engaged"
        char_desc = f"{char_desc}, {multi_char_emphasis}"

    mood = EMOTION_MAP.get(emotion, EMOTION_MAP["warm"])
    style_prompt = get_style_prompt(style_id)
    return f"{style_prompt}, {scene_description}, featuring {char_desc}, {mood}"


async def generate_image_volcano(
    prompt: str,
    *,
    style_id: str = DEFAULT_STYLE_ID,
    width: int = 1024,
    height: int = 1024,
    compress: bool = True,
    max_retries: int = 20,
    poll_interval: float = 2.0,
) -> str:
    """
    调用火山即梦官方 API 生成图片

    Args:
        prompt: 图片生成提示词
        style_id: 故事风格ID
        width: 图片宽度（默认1024）
        height: 图片高度（默认1024）
        compress: 是否压缩图片（默认True）
        max_retries: 最大轮询次数（默认20）
        poll_interval: 轮询间隔（秒，默认2.0）

    Returns:
        图片URL或本地路径

    Raises:
        ValueError: API 调用失败或超时
    """
    settings = get_settings()
    start_time = time.time()

    logger.info(f"[火山即梦] 开始生成图片，风格: {style_id}")
    logger.debug(f"[火山即梦] Prompt (前100字): {prompt[:100]}...")

    try:
        # 初始化服务
        visual_service = _init_visual_service()

        # 第一步：提交任务
        submit_body = {
            "req_key": settings.volcano_jimeng_req_key,
            "prompt": prompt,
            "scale": 0.5,
            "width": width,
            "height": height,
            "force_single": True,
        }

        logger.info(f"[火山即梦] 提交任务中，参数: {submit_body}")
        submit_resp = visual_service.cv_sync2async_submit_task(submit_body)

        if submit_resp.get("code") != 10000:
            error_msg = f"任务提交失败: {submit_resp}"
            logger.error(f"[火山即梦] ❌ {error_msg}")
            raise ValueError(error_msg)

        task_id = submit_resp["data"]["task_id"]
        logger.info(f"[火山即梦] ✅ 任务提交成功，Task ID: {task_id}")

        # 第二步：轮询查询结果
        import json

        req_json_config = {
            "return_url": True,
            "logo_info": {"add_logo": False},
        }

        query_body = {
            "req_key": settings.volcano_jimeng_req_key,
            "task_id": task_id,
            "req_json": json.dumps(req_json_config),
        }

        logger.info(f"[火山即梦] 开始轮询结果，最多 {max_retries} 次")

        for i in range(max_retries):
            query_resp = visual_service.cv_sync2async_get_result(query_body)

            if query_resp.get("code") != 10000:
                error_msg = f"查询失败: {query_resp}"
                logger.error(f"[火山即梦] ❌ {error_msg}")
                raise ValueError(error_msg)

            status = query_resp["data"]["status"]

            if status == "done":
                elapsed = time.time() - start_time
                logger.info(f"[火山即梦] ✅ 生成完成，耗时: {elapsed:.2f}s")

                image_urls = query_resp["data"].get("image_urls", [])
                if not image_urls:
                    raise ValueError("API 未返回图片 URL")

                image_url = image_urls[0]
                logger.info(
                    f"[火山即梦] 获得图片 URL，长度: {len(image_url)}"
                )

                # 压缩图片
                if compress:
                    compressed_path = await compress_and_save_image(image_url)
                    logger.info(f"[火山即梦] ✅ 图片已压缩: {compressed_path}")
                    return compressed_path

                return image_url

            elif status in ["in_queue", "generating"]:
                logger.info(
                    f"[火山即梦] 任务处理中 ({status})... 第 {i + 1}/{max_retries} 次查询"
                )
                time.sleep(poll_interval)
            else:
                error_msg = f"任务状态异常: {status}"
                logger.error(f"[火山即梦] ❌ {error_msg}")
                raise ValueError(error_msg)

        # 超时
        error_msg = f"轮询超时（已重试 {max_retries} 次）"
        logger.error(f"[火山即梦] ❌ {error_msg}")
        raise ValueError(error_msg)

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            f"[火山即梦] ❌ 生成失败，耗时: {elapsed:.2f}s, 错误: {e}",
            exc_info=True,
        )
        raise


async def generate_story_illustration_volcano(
    scene_description: str,
    characters: List[Character],
    emotion: str,
    style_id: str = DEFAULT_STYLE_ID,
) -> str:
    """
    根据故事段落生成插画（火山即梦官方 API）

    Args:
        scene_description: 场景描述
        characters: 角色列表
        emotion: 情感类型
        style_id: 故事风格ID

    Returns:
        图片URL或本地路径
    """
    logger.info(
        f"[火山即梦] 为段落生成插画，风格ID: {style_id}, 情感: {emotion}"
    )

    prompt = _build_prompt_volcano(scene_description, characters, emotion, style_id)

    logger.info(f"[火山即梦] 完整 Prompt (前200字符): {prompt[:200]}...")
    logger.info(f"[火山即梦] 应用的风格prompt: {get_style_prompt(style_id)[:100]}...")

    # 16:9 分辨率
    return await generate_image_volcano(
        prompt=prompt,
        style_id=style_id,
        width=1024,
        height=576,  # 16:9 比例
        compress=True,
    )
