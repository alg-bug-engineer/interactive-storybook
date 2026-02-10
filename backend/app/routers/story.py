"""故事 API：开始故事、获取当前段、下一页、互动、画廊列表、预加载"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.models.story import InteractRequest
from app.routers.auth import get_current_user
from app.constants.voices import DEFAULT_VOICE_ID, is_valid_voice
from app.services.story_engine import (
    start_new_story,
    get_story,
    get_current_segment,
    go_next_segment,
    handle_interaction,
    preload_segment_image,
)
from app.services.tts_service import HAS_EDGE_TTS, get_or_generate_segment_audio
from app.utils.store import list_stories
from app.constants.story_styles import DEFAULT_STYLE_ID, get_all_styles

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/story", tags=["story"])


class StartStoryRequest(BaseModel):
    """开始故事请求，主题与页数可选。"""
    theme: str | None = None  # 如 "龟兔赛跑"；空或省略则随机故事
    total_pages: int | None = None  # 指定则生成固定页数；3–4 页无互动，5 页及以上带互动
    style_id: str | None = None  # 故事风格ID，如 "q_cute"、"watercolor_healing" 等


@router.post("/start")
async def start(
    body: StartStoryRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    """开始一个新故事（需登录）。可传 theme 指定主题、total_pages 指定页数、style_id 指定风格。"""
    theme = None
    if body and body.theme and isinstance(body.theme, str):
        t = body.theme.strip()
        theme = t if t else None
    total_pages = getattr(body, "total_pages", None) if body else None
    if total_pages is not None and (total_pages < 3 or total_pages > 20):
        raise HTTPException(status_code=400, detail="页数至少 3 页、最多 20 页")
    style_id = getattr(body, "style_id", None) if body else None
    if style_id is None:
        style_id = DEFAULT_STYLE_ID
    no_interaction = total_pages is not None and 3 <= total_pages < 5
    try:
        state = await start_new_story(user_theme=theme, total_pages=total_pages, no_interaction=no_interaction, style_id=style_id)
        seg, has_interaction = get_current_segment(state)
        return {
            "story_id": state.id,
            "title": state.title,
            "theme": state.theme,
            "characters": [c.model_dump() for c in state.characters],
            "setting": state.setting.model_dump(),
            "total_segments": len(state.segments),
            "current_index": state.current_index,
            "current_segment": seg.model_dump() if seg else None,
            "has_interaction": has_interaction,
            "status": state.status,
            "style_id": getattr(state, "style_id", DEFAULT_STYLE_ID),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_stories_api():
    """获取所有故事摘要，用于主页画廊展示（按创建时间倒序）。"""
    return {"stories": list_stories()}


@router.get("/styles")
async def list_story_styles():
    """获取所有可用的故事风格列表。"""
    return {"styles": get_all_styles()}


@router.get("/{story_id}")
async def get_story_state(story_id: str):
    """获取故事状态与当前段。用于前端轮询检查图片是否生成完成。"""
    state = get_story(story_id)
    if not state:
        raise HTTPException(status_code=404, detail="故事不存在")
    seg, has_interaction = get_current_segment(state)
    return {
        "story_id": state.id,
        "title": state.title,
        "theme": state.theme,
        "characters": [c.model_dump() for c in state.characters],
        "setting": state.setting.model_dump(),
        "segments": [s.model_dump() for s in state.segments],
        "total_segments": len(state.segments),
        "current_index": state.current_index,
        "current_segment": seg.model_dump() if seg else None,
        "has_interaction": has_interaction,
        "status": state.status,
        "style_id": getattr(state, "style_id", DEFAULT_STYLE_ID),
    }


@router.post("/{story_id}/preload-segment/{segment_index}")
async def preload_segment(story_id: str, segment_index: int):
    """后台预生成指定段落的插画。当前页无互动时前端调用，用户翻页时可直接加载。"""
    state = get_story(story_id)
    if not state:
        raise HTTPException(status_code=404, detail="故事不存在")
    if segment_index < 0 or segment_index >= len(state.segments):
        raise HTTPException(status_code=400, detail="段落索引无效")
    if state.segments[segment_index].image_url:
        return {"ok": True, "preloading": False, "reason": "已有图片"}
    asyncio.create_task(preload_segment_image(story_id, segment_index))
    return {"ok": True, "preloading": True}


@router.get("/{story_id}/segment/{segment_index}/image")
async def get_segment_image(story_id: str, segment_index: int):
    """获取指定段落的图片 URL（用于轮询检查）。"""
    state = get_story(story_id)
    if not state:
        raise HTTPException(status_code=404, detail="故事不存在")
    if segment_index >= len(state.segments):
        raise HTTPException(status_code=404, detail="段落不存在")
    
    seg = state.segments[segment_index]
    return {
        "story_id": story_id,
        "segment_index": segment_index,
        "image_url": seg.image_url,
        "has_image": seg.image_url is not None,
    }


@router.get("/{story_id}/segment/{segment_index}/audio")
async def get_segment_audio(
    story_id: str,
    segment_index: int,
    voice_id: str | None = None,
    speed: float = 1.0,
):
    """获取或生成指定段落的 TTS 音频（edge-tts），用于前端朗读。"""
    if not HAS_EDGE_TTS:
        raise HTTPException(status_code=503, detail="TTS 服务不可用（edge-tts 未安装）")

    state = get_story(story_id)
    if not state:
        raise HTTPException(status_code=404, detail="故事不存在")
    if segment_index < 0 or segment_index >= len(state.segments):
        raise HTTPException(status_code=404, detail="段落不存在")

    seg = state.segments[segment_index]
    text = (seg.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="该段落没有可朗读的文本")

    # speed 限制范围，避免异常值
    try:
        speed = float(speed)
    except Exception:
        speed = 1.0
    speed = max(0.5, min(2.0, speed))

    # voice 校验；无效则回退默认
    vid = (voice_id or "").strip() or DEFAULT_VOICE_ID
    if not is_valid_voice(vid):
        vid = DEFAULT_VOICE_ID

    try:
        audio_path = await get_or_generate_segment_audio(
            story_id=story_id,
            segment_index=segment_index,
            text=text,
            voice_id=vid,
            speed=speed,
        )

        # 异步预生成「下一段」音频，减少用户翻页后的等待时间
        next_index = segment_index + 1
        if next_index < len(state.segments):
            next_seg = state.segments[next_index]
            next_text = (next_seg.text or "").strip()
            if next_text:
                asyncio.create_task(
                    get_or_generate_segment_audio(
                        story_id=story_id,
                        segment_index=next_index,
                        text=next_text,
                        voice_id=vid,
                        speed=speed,
                    )
                )

        return {
            "story_id": story_id,
            "segment_index": segment_index,
            "voice_id": vid,
            "speed": speed,
            "audio_path": audio_path,
            "audio_url": f"/api/audio/{audio_path}",
        }
    except Exception as e:
        logger.error(
            f"[API] 段落音频生成失败: story_id={story_id}, segment_index={segment_index}, voice={vid}, speed={speed}, error={e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="段落音频生成失败")


@router.post("/{story_id}/next")
async def next_segment(story_id: str):
    """进入下一段，返回更新后的当前段。"""
    state = await go_next_segment(story_id)
    if not state:
        raise HTTPException(status_code=404, detail="故事不存在或已结束")
    seg, has_interaction = get_current_segment(state)
    return {
        "story_id": state.id,
        "current_index": state.current_index,
        "current_segment": seg.model_dump() if seg else None,
        "has_interaction": has_interaction,
        "status": state.status,
    }


@router.post("/interact")
async def interact(req: InteractRequest):
    """提交互动回答，返回反馈与续写段落（含图片）。"""
    logger.info(f"[API] POST /interact - story_id={req.story_id}, segment_index={req.segment_index}")
    try:
        continuation = await handle_interaction(req)
        state = get_story(req.story_id)
        if not state:
            logger.error(f"[API] ❌ 故事不存在: {req.story_id}")
            raise HTTPException(status_code=404, detail="故事不存在")
        
        seg, has_interaction = get_current_segment(state)
        
        # 记录返回的数据
        response_data = {
            "feedback": continuation.feedback,
            "new_segments": [s.model_dump() for s in continuation.segments],
            "current_index": state.current_index,
            "current_segment": seg.model_dump() if seg else None,
            "has_interaction": has_interaction,
            "status": state.status,
        }
        
        # 检查图片 URL
        if seg and not seg.image_url:
            logger.warning(f"[API] ⚠️ 当前段落没有图片 URL: segment_index={state.current_index}")
        if continuation.segments:
            missing_images = [i for i, s in enumerate(continuation.segments) if not s.image_url]
            if missing_images:
                logger.warning(f"[API] ⚠️ 续写段落中缺少图片: 索引 {missing_images}")
        
        logger.info(f"[API] ✅ 互动处理成功，返回 {len(continuation.segments)} 个新段落")
        return response_data
        
    except ValueError as e:
        logger.error(f"[API] ❌ 参数错误: {e}")
        # JSON 解析错误通常是 ValueError，提供更友好的错误信息
        error_msg = str(e)
        if "JSON" in error_msg or "delimiter" in error_msg or "Expecting" in error_msg:
            error_msg = "LLM 返回格式错误，已使用默认内容继续故事"
            logger.warning(f"[API] ⚠️ JSON 解析错误，但已处理: {e}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"[API] ❌ 服务器错误: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
