"""视频生成相关 API"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.routers.auth import get_current_user_optional
from app.services.video_service import (
    generate_story_video,
    get_video_generation_status,
    VideoGenerationStatus,
)
from app.utils.store import get_story

router = APIRouter(prefix="/api/video", tags=["video"])
logger = logging.getLogger(__name__)


class GenerateVideoRequest(BaseModel):
    story_id: str
    enable_audio: bool = True  # 默认开启音频（使用 TTS 缓存）


class VideoStatusResponse(BaseModel):
    story_id: str
    status: str
    progress: int
    total_clips: int
    generated_clips: int
    video_url: str | None
    error: str | None


@router.post("/generate")
async def generate_video(
    req: GenerateVideoRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_optional),
):
    """
    生成故事视频（异步任务）
    
    - **story_id**: 故事 ID
    - **enable_audio**: 是否启用音频（需要 TTS 支持）
    """
    logger.info(f"[视频 API] 收到生成视频请求: story_id={req.story_id}, enable_audio={req.enable_audio}")
    
    # 检查故事是否存在
    state = get_story(req.story_id)
    if not state:
        logger.error(f"[视频 API] ❌ 故事不存在: {req.story_id}")
        raise HTTPException(status_code=404, detail="故事不存在")
    
    # 检查是否有足够的段落
    if len(state.segments) < 2:
        logger.error(f"[视频 API] ❌ 故事段落不足: {len(state.segments)}")
        raise HTTPException(status_code=400, detail="故事段落不足，至少需要 2 个段落")
    
    # 检查所有段落是否都有图片
    missing_images = [i for i, seg in enumerate(state.segments) if not seg.image_url]
    if missing_images:
        logger.warning(f"[视频 API] ⚠️ 部分段落缺少图片: {missing_images}")
        # 继续处理，跳过没有图片的段落
    
    # 启动后台任务
    background_tasks.add_task(
        generate_story_video,
        story_id=req.story_id,
        segments=state.segments,
        title=state.title,
        enable_audio=req.enable_audio,
        user=current_user,
        prebuilt_clips=dict(state.video_clips or {}),
    )
    
    logger.info(f"[视频 API] ✅ 视频生成任务已启动: {req.story_id}")
    
    return {
        "message": "视频生成任务已启动",
        "story_id": req.story_id,
        "status": VideoGenerationStatus.GENERATING_CLIPS,
    }


@router.get("/status/{story_id}")
async def get_video_status(story_id: str) -> VideoStatusResponse:
    """
    查询视频生成状态
    
    - **story_id**: 故事 ID
    """
    logger.info(f"[视频 API] 查询视频生成状态: story_id={story_id}（故事ID，非即梦task_id）")
    
    status = get_video_generation_status(story_id)
    if not status:
        logger.info(f"[视频 API] 未找到视频生成任务: {story_id}")
        return VideoStatusResponse(
            story_id=story_id,
            status=VideoGenerationStatus.IDLE,
            progress=0,
            total_clips=0,
            generated_clips=0,
            video_url=None,
            error=None,
        )
    
    return VideoStatusResponse(
        story_id=status["story_id"],
        status=status["status"],
        progress=status["progress"],
        total_clips=status["total_clips"],
        generated_clips=status["generated_clips"],
        video_url=status["video_url"],
        error=status.get("error"),
    )


@router.get("/download/{story_id}")
async def download_video(story_id: str):
    """
    下载生成的视频
    
    - **story_id**: 故事 ID
    """
    logger.info(f"[视频 API] 下载视频请求: {story_id}")
    
    status = get_video_generation_status(story_id)
    if not status or status["status"] != VideoGenerationStatus.COMPLETED:
        logger.error(f"[视频 API] ❌ 视频未生成或生成中: {story_id}")
        raise HTTPException(status_code=404, detail="视频未生成或生成中")
    
    video_path = status["video_url"]
    if not video_path:
        logger.error(f"[视频 API] ❌ 视频文件路径为空: {story_id}")
        raise HTTPException(status_code=404, detail="视频文件不存在")
    
    logger.info(f"[视频 API] ✅ 返回视频文件: {video_path}")
    
    # 获取故事标题作为文件名
    state = get_story(story_id)
    filename = f"{state.title if state else story_id}_故事视频.mp4"
    
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=filename,
    )


@router.get("/clips/{story_id}")
async def get_video_clips(story_id: str):
    """
    获取故事的所有视频片段
    
    - **story_id**: 故事 ID
    """
    logger.info(f"[视频 API] 查询视频片段: {story_id}")
    
    state = get_story(story_id)
    if not state:
        logger.error(f"[视频 API] ❌ 故事不存在: {story_id}")
        raise HTTPException(status_code=404, detail="故事不存在")
    
    return {
        "story_id": story_id,
        "video_clips": state.video_clips,
        "total_clips": len(state.video_clips),
    }
