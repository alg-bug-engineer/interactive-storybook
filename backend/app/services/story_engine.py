"""故事引擎：编排 LLM 生成大纲、即梦生成首图、互动续写与配图"""
import asyncio
import logging
from typing import List
from app.models.story import StoryState, StoryOutline, StorySegment, InteractRequest, ContinueResponse, Character
from app.services.llm_service import generate_story_outline, continue_story_with_interaction
from app.services.jimeng_service import generate_story_illustration
from app.utils.store import save_story, get_story, update_story, new_story_id

logger = logging.getLogger(__name__)


async def start_new_story(
    user_theme: str | None = None,
    total_pages: int | None = None,
    no_interaction: bool = False,
    style_id: str = "q_cute",
) -> StoryState:
    """生成新故事：大纲 + 第一段配图。user_theme 为空则随机主题。
    total_pages 指定则生成固定页数；no_interaction 为 True 时不设互动节点，且后台依次生成全部插画（不等待用户翻页）。"""
    outline: StoryOutline = await generate_story_outline(
        user_theme=user_theme,
        total_pages=total_pages,
        no_interaction=no_interaction,
    )
    story_id = new_story_id()
    segments = list(outline.segments)
    if not segments:
        raise ValueError("故事大纲没有段落")
    if no_interaction:
        for i, seg in enumerate(segments):
            if seg.interaction_point is not None:
                segments[i] = StorySegment(
                    id=seg.id,
                    text=seg.text,
                    scene_description=seg.scene_description,
                    emotion=seg.emotion,
                    interaction_point=None,
                    image_url=seg.image_url,
                )

    # 为第一段生成图片
    first = segments[0]
    first.image_url = await generate_story_illustration(first, outline.characters, style_id=style_id)
    segments[0] = first

    state = StoryState(
        id=story_id,
        title=outline.title,
        theme=outline.theme,
        characters=outline.characters,
        setting=outline.setting,
        segments=segments,
        current_index=0,
        status="narrating",
        style_id=style_id,
    )
    save_story(state)

    if len(segments) > 1:
        if no_interaction:
            # 无互动模式：后台依次生成剩余全部插画，不等待用户翻页
            asyncio.create_task(
                _generate_images_async(story_id, 1, len(segments) - 1, outline.characters, style_id=style_id)
            )
        else:
            asyncio.create_task(_pregenerate_image(story_id, 1, style_id=style_id))

    return state


async def _pregenerate_image(story_id: str, segment_index: int, style_id: str | None = None) -> None:
    """后台预生成某段图片并写回 state。"""
    state = get_story(story_id)
    if not state or segment_index >= len(state.segments):
        return
    seg = state.segments[segment_index]
    if seg.image_url:
        return
    # 如果没有传入style_id，使用故事状态中保存的风格
    if style_id is None:
        style_id = getattr(state, 'style_id', 'q_cute')
    try:
        url = await generate_story_illustration(seg, state.characters, style_id=style_id)
        seg.image_url = url
        state.segments[segment_index] = seg
        update_story(story_id, segments=state.segments)
        logger.info(f"[故事引擎] ✅ 预生成段落 {segment_index} 图片完成")
    except Exception as e:
        logger.warning(f"[故事引擎] 预生成段落 {segment_index} 图片失败: {e}")


async def preload_segment_image(story_id: str, segment_index: int) -> None:
    """供 API 调用的预生成接口，后台生成指定段落插画。"""
    await _pregenerate_image(story_id, segment_index)


def get_current_segment(state: StoryState) -> tuple[StorySegment | None, bool]:
    """返回当前段落及是否有互动节点。"""
    if state.current_index >= len(state.segments):
        return None, False
    seg = state.segments[state.current_index]
    has_interaction = seg.interaction_point is not None
    return seg, has_interaction


async def go_next_segment(story_id: str) -> StoryState | None:
    """进入下一段；若下一段无图则同步生成。"""
    state = get_story(story_id)
    if not state:
        return None
    idx = state.current_index + 1
    if idx >= len(state.segments):
        state.status = "completed"
        update_story(story_id, current_index=idx, status="completed")
        return get_story(story_id)
    next_seg = state.segments[idx]
    if not next_seg.image_url:
        style_id = getattr(state, 'style_id', 'q_cute')
        next_seg.image_url = await generate_story_illustration(next_seg, state.characters, style_id=style_id)
        state.segments[idx] = next_seg
    state.current_index = idx
    
    # 如果是最后一段且没有互动节点，故事完结
    is_last_segment = (idx == len(state.segments) - 1)
    if is_last_segment and not next_seg.interaction_point:
        state.status = "completed"
        logger.info(f"[故事引擎] 翻到最后一段（无互动），故事完结")
    else:
        state.status = "waiting_interaction" if next_seg.interaction_point else "narrating"
    
    update_story(story_id, current_index=idx, status=state.status, segments=state.segments)
    return get_story(story_id)


async def handle_interaction(req: InteractRequest) -> ContinueResponse:
    """处理用户互动：续写 + 为新段落生成图片。"""
    logger.info(f"[故事引擎] 处理互动请求: story_id={req.story_id}, segment_index={req.segment_index}, type={req.interaction_type}, input={req.user_input[:50]}...")
    
    state = get_story(req.story_id)
    if not state or req.segment_index >= len(state.segments):
        logger.error(f"[故事引擎] ❌ 故事或段落不存在: story_id={req.story_id}, segment_index={req.segment_index}, total_segments={len(state.segments) if state else 0}")
        raise ValueError("故事或段落不存在")
    
    seg = state.segments[req.segment_index]
    ip = seg.interaction_point
    if not ip:
        logger.error(f"[故事引擎] ❌ 段落没有互动节点: segment_index={req.segment_index}")
        raise ValueError("该段落没有互动节点")
    
    ip.user_input = req.user_input
    seg.interaction_point = ip
    state.segments[req.segment_index] = seg

    # 构建上下文（最近几段文本）
    start = max(0, req.segment_index - 2)
    context_parts = [state.segments[i].text for i in range(start, req.segment_index + 1)]
    story_context = "\n\n".join(context_parts)
    logger.debug(f"[故事引擎] 故事上下文长度: {len(story_context)} 字符")

    # 计算故事进度：已有段落数、已使用交互次数
    current_segment_count = len(state.segments)
    total_interactions_used = sum(1 for s in state.segments if s.interaction_point is not None)
    logger.info(f"[故事引擎] 故事进度: 已有 {current_segment_count} 段，已使用 {total_interactions_used} 次交互")

    logger.info(f"[故事引擎] 调用 LLM 续写故事...")
    continuation = await continue_story_with_interaction(
        story_context=story_context,
        interaction_type=req.interaction_type,
        interaction_prompt=ip.prompt,
        user_input=req.user_input,
        current_segment_count=current_segment_count,
        total_interactions_used=total_interactions_used,
    )
    logger.info(f"[故事引擎] ✅ LLM 续写完成，生成 {len(continuation.segments)} 个新段落")

    # 把续写段落追加到 segments，图片异步生成
    new_segments = continuation.segments
    logger.info(f"[故事引擎] 开始为新段落生成图片，共 {len(new_segments)} 段")
    
    # 先设置段落 ID，图片 URL 初始为 None（异步生成）
    for i, new_seg in enumerate(new_segments):
        new_seg.id = f"{req.story_id}-cont-{i}"
        new_seg.image_url = None  # 初始为空，后台异步生成
    
    state.segments.extend(new_segments)
    
    # 篇幅控制：如果超过8页，截断并确保最后一段是结局（无互动）
    MAX_SEGMENTS = 8
    if len(state.segments) > MAX_SEGMENTS:
        logger.warning(f"[故事引擎] 续写后段落数 {len(state.segments)} 超过 {MAX_SEGMENTS}，截断为 {MAX_SEGMENTS} 页")
        state.segments = state.segments[:MAX_SEGMENTS]
        # 确保最后一段没有互动节点（结局）
        if state.segments[-1].interaction_point:
            last = state.segments[-1]
            state.segments[-1] = StorySegment(
                id=last.id,
                text=last.text + " 故事到这里就结束啦，小朋友们晚安！",
                scene_description=last.scene_description,
                emotion="warm",
                interaction_point=None,
                image_url=last.image_url,
            )
            logger.info("[故事引擎] 最后一段有互动节点，已移除并添加结束语")
    
    # 状态：续写后继续叙述，由 go_next_segment 在翻到最后一页时设为 completed
    state.status = "narrating"
    state.current_index = req.segment_index + 1  # 下一段是续写的第一段
    update_story(req.story_id, segments=state.segments, current_index=state.current_index, status=state.status)
    
    # 异步生成图片（不阻塞响应）
    style_id = getattr(state, 'style_id', 'q_cute')
    asyncio.create_task(_generate_images_async(req.story_id, req.segment_index + 1, len(new_segments), state.characters, style_id=style_id))
    
    logger.info(f"[故事引擎] ✅ 互动处理完成，当前段落索引: {state.current_index}, 总段落数: {len(state.segments)}，图片后台生成中...")
    return continuation


async def _generate_images_async(
    story_id: str,
    start_index: int,
    count: int,
    characters: List[Character],
    style_id: str | None = None,
) -> None:
    """后台异步生成图片，更新到 story state。"""
    logger.info(f"[故事引擎] 后台开始生成图片: story_id={story_id}, start_index={start_index}, count={count}")
    
    state = get_story(story_id)
    if not state:
        logger.error(f"[故事引擎] ❌ 故事不存在，无法生成图片: {story_id}")
        return
    
    # 如果没有传入style_id，使用故事状态中保存的风格
    if style_id is None:
        style_id = getattr(state, 'style_id', 'q_cute')
    
    for i in range(count):
        segment_index = start_index + i
        if segment_index >= len(state.segments):
            logger.warning(f"[故事引擎] ⚠️ 段落索引超出范围: {segment_index} >= {len(state.segments)}")
            break
        
        seg = state.segments[segment_index]
        if seg.image_url:  # 已有图片，跳过
            logger.info(f"[故事引擎] 段落 {segment_index} 已有图片，跳过")
            continue
        
        logger.info(f"[故事引擎] 后台生成第 {i+1}/{count} 段图片 (索引 {segment_index})...")
        try:
            # 重试机制：最多重试 2 次
            max_retries = 2
            for retry in range(max_retries + 1):
                try:
                    image_url = await generate_story_illustration(seg, characters, style_id=style_id)
                    seg.image_url = image_url
                    state.segments[segment_index] = seg
                    update_story(story_id, segments=state.segments)
                    logger.info(f"[故事引擎] ✅ 段落 {segment_index} 图片生成成功: {image_url[:80]}...")
                    break
                except Exception as e:
                    if retry < max_retries:
                        wait_time = (retry + 1) * 5  # 5秒、10秒
                        logger.warning(f"[故事引擎] ⚠️ 段落 {segment_index} 图片生成失败，{wait_time}秒后重试 ({retry+1}/{max_retries}): {e}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"[故事引擎] ❌ 段落 {segment_index} 图片生成最终失败: {type(e).__name__}: {e}", exc_info=True)
                        # 生成失败，保持 image_url 为 None，前端会显示"加载中"
        except Exception as e:
            logger.error(f"[故事引擎] ❌ 段落 {segment_index} 图片生成异常: {type(e).__name__}: {e}", exc_info=True)
    
    logger.info(f"[故事引擎] ✅ 后台图片生成任务完成: story_id={story_id}")
