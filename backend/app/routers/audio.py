"""音频文件服务：提供 TTS 音频和预览音频的访问"""
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audio", tags=["audio"])

# 音频文件根目录
AUDIO_BASE_DIR = Path("backend/data/audio")


@router.get("/data/audio/preview/{filename}")
async def get_preview_audio(filename: str):
    """
    获取预览音频文件
    
    示例: /api/audio/data/audio/preview/zh-CN-XiaoxiaoNeural.mp3
    """
    # 安全检查：防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    
    file_path = AUDIO_BASE_DIR / "preview" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")
    
    return FileResponse(
        path=str(file_path),
        media_type="audio/mpeg",
        filename=filename,
    )


@router.get("/data/audio/tts/{filename}")
async def get_tts_audio(filename: str):
    """
    获取 edge-tts 音频文件

    示例: /api/audio/data/audio/tts/story_123_0_zh-CN-XiaoxiaoNeural.mp3
    """
    # 安全检查：防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    file_path = AUDIO_BASE_DIR / "tts" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")

    return FileResponse(
        path=str(file_path),
        media_type="audio/mpeg",
        filename=filename,
    )


@router.get("/data/audio/volcano_tts/{filename}")
async def get_volcano_tts_audio(filename: str):
    """
    获取火山 TTS 音频文件（付费用户）

    示例: /api/audio/data/audio/volcano_tts/story_123_0_BV700_V2.mp3
    """
    # 安全检查：防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    file_path = AUDIO_BASE_DIR / "volcano_tts" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")

    return FileResponse(
        path=str(file_path),
        media_type="audio/mpeg",
        filename=filename,
    )
