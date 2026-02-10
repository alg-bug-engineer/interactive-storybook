"""音色 API：音色列表、试听、用户偏好设置"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.constants.voices import (
    AVAILABLE_VOICES,
    DEFAULT_VOICE_ID,
    get_voice_by_id,
    get_recommended_voices,
    is_valid_voice,
)
from app.services.tts_service import generate_preview_audio, HAS_EDGE_TTS
from app.routers.auth import get_current_user_optional
from app.utils.user_store import get_user_by_email, update_user_preferences

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.get("/list")
async def list_voices():
    """获取所有可用音色列表"""
    return {
        "voices": AVAILABLE_VOICES,
        "default_voice_id": DEFAULT_VOICE_ID,
        "tts_available": HAS_EDGE_TTS,
    }


@router.get("/recommended")
async def get_recommended():
    """获取推荐音色列表（用于首页快速选择）"""
    return {
        "voices": get_recommended_voices(),
        "default_voice_id": DEFAULT_VOICE_ID,
    }


@router.get("/preview/{voice_id}")
async def preview_voice(voice_id: str):
    """
    试听指定音色
    
    返回音频文件 URL 或直接返回音频文件
    """
    if not HAS_EDGE_TTS:
        raise HTTPException(
            status_code=503,
            detail="TTS 服务不可用，请联系管理员安装 edge-tts",
        )
    
    # 验证音色
    if not is_valid_voice(voice_id):
        raise HTTPException(status_code=404, detail=f"音色不存在: {voice_id}")
    
    try:
        # 生成或获取预览音频
        audio_path = await generate_preview_audio(voice_id)
        
        # 返回完整的音频 URL 路径
        # audio_path 格式: data/audio/preview/zh-CN-XiaoxiaoNeural.mp3
        return {
            "voice_id": voice_id,
            "audio_url": f"/api/audio/{audio_path}",  # /api/audio/data/audio/preview/xxx.mp3
            "voice_info": get_voice_by_id(voice_id),
        }
        
    except Exception as e:
        logger.error(f"[API] 音色预览失败: {voice_id}, error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"音色预览失败: {str(e)}")


class UserPreferencesRequest(BaseModel):
    """用户偏好设置请求"""
    preferred_voice: str | None = None
    playback_speed: float | None = None


@router.post("/preferences")
async def save_preferences(
    body: UserPreferencesRequest,
    current_user: dict = Depends(get_current_user_optional),
):
    """
    保存用户音色偏好（需登录）
    
    未登录时返回成功但不保存（前端使用 LocalStorage）
    """
    # 如果用户未登录，返回成功（前端用 LocalStorage）
    if not current_user:
        return {
            "success": True,
            "message": "未登录，偏好仅保存在本地",
            "preferences": body.model_dump(),
        }
    
    # 验证音色
    if body.preferred_voice and not is_valid_voice(body.preferred_voice):
        raise HTTPException(status_code=400, detail=f"无效的音色 ID: {body.preferred_voice}")
    
    # 验证倍速
    if body.playback_speed is not None:
        if not (0.5 <= body.playback_speed <= 2.0):
            raise HTTPException(status_code=400, detail="播放倍速必须在 0.5-2.0 之间")
    
    try:
        email = current_user["email"]
        
        # 更新用户偏好
        preferences = {}
        if body.preferred_voice:
            preferences["preferred_voice"] = body.preferred_voice
        if body.playback_speed is not None:
            preferences["playback_speed"] = body.playback_speed
        
        update_user_preferences(email, preferences)
        
        logger.info(f"[API] 用户偏好已保存: {email}, {preferences}")
        
        return {
            "success": True,
            "message": "偏好已保存",
            "preferences": preferences,
        }
        
    except Exception as e:
        logger.error(f"[API] 保存用户偏好失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/preferences")
async def get_preferences(current_user: dict = Depends(get_current_user_optional)):
    """
    获取用户音色偏好
    
    未登录时返回默认值
    """
    if not current_user:
        return {
            "preferred_voice": DEFAULT_VOICE_ID,
            "playback_speed": 1.0,
        }
    
    try:
        email = current_user["email"]
        user = get_user_by_email(email)
        
        if not user:
            return {
                "preferred_voice": DEFAULT_VOICE_ID,
                "playback_speed": 1.0,
            }
        
        return {
            "preferred_voice": user.get("preferred_voice", DEFAULT_VOICE_ID),
            "playback_speed": user.get("playback_speed", 1.0),
        }
        
    except Exception as e:
        logger.error(f"[API] 获取用户偏好失败: {e}", exc_info=True)
        # 失败时返回默认值，不阻断用户使用
        return {
            "preferred_voice": DEFAULT_VOICE_ID,
            "playback_speed": 1.0,
        }
