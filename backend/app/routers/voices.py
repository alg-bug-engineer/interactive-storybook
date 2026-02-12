"""音色 API：音色列表、试听、用户偏好设置"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.constants.voices import (
    get_available_voices,
    get_default_voice_id,
    get_voice_by_id,
    get_recommended_voices,
    is_valid_voice,
    is_free_voice,
    is_premium_voice,
    normalize_voice_for_user,
)
from app.services.tts_service import generate_preview_audio, HAS_EDGE_TTS
from app.services.volcano_tts_service import (
    generate_preview_audio_volcano,
    is_volcano_tts_available,
)
from app.routers.auth import get_current_user_optional
from app.utils.service_tier import is_premium_user
from app.utils.user_store import get_user_by_email, update_user_preferences

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.get("/list")
async def list_voices(current_user: dict = Depends(get_current_user_optional)):
    """按当前用户等级返回可用音色列表。"""
    premium = is_premium_user(current_user)
    voices = get_available_voices(current_user)
    default_voice_id = get_default_voice_id(current_user)
    tts_available = is_volcano_tts_available() if premium else HAS_EDGE_TTS

    return {
        "voices": voices,
        "default_voice_id": default_voice_id,
        "tts_available": tts_available,
        "tier": "premium" if premium else "free",
    }


@router.get("/recommended")
async def get_recommended(current_user: dict = Depends(get_current_user_optional)):
    """按用户等级返回推荐音色列表（用于首页快速选择）。"""
    return {
        "voices": get_recommended_voices(current_user),
        "default_voice_id": get_default_voice_id(current_user),
    }


@router.get("/preview/{voice_id}")
async def preview_voice(voice_id: str, current_user: dict = Depends(get_current_user_optional)):
    """
    试听指定音色
    
    返回音频文件 URL 或直接返回音频文件
    """
    voice_info = get_voice_by_id(voice_id)
    if not voice_info:
        raise HTTPException(status_code=404, detail=f"音色不存在: {voice_id}")
    
    try:
        if is_premium_voice(voice_id):
            if not is_volcano_tts_available():
                raise HTTPException(status_code=503, detail="线上 TTS 配置不可用")
            audio_path = await generate_preview_audio_volcano(voice_id)
        else:
            if not HAS_EDGE_TTS:
                raise HTTPException(
                    status_code=503,
                    detail="TTS 服务不可用，请联系管理员安装 edge-tts",
                )
            if not is_free_voice(voice_id):
                raise HTTPException(status_code=400, detail="该音色不属于免费语音库")
            audio_path = await generate_preview_audio(voice_id)
        
        return {
            "voice_id": voice_id,
            "audio_url": f"/api/audio/{audio_path}",
            "voice_info": voice_info,
        }
        
    except HTTPException:
        raise
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
    
    normalized_preferred_voice = None
    if body.preferred_voice:
        if not is_valid_voice(body.preferred_voice, current_user):
            raise HTTPException(
                status_code=400,
                detail=f"该账号等级不可使用音色: {body.preferred_voice}",
            )
        normalized_preferred_voice = normalize_voice_for_user(body.preferred_voice, current_user)
    
    # 验证倍速
    if body.playback_speed is not None:
        if not (0.5 <= body.playback_speed <= 2.0):
            raise HTTPException(status_code=400, detail="播放倍速必须在 0.5-2.0 之间")
    
    try:
        email = current_user["email"]
        
        # 更新用户偏好
        preferences = {}
        if normalized_preferred_voice:
            preferences["preferred_voice"] = normalized_preferred_voice
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
    default_voice_id = get_default_voice_id(current_user)

    if not current_user:
        return {
            "preferred_voice": default_voice_id,
            "playback_speed": 1.0,
        }
    
    try:
        email = current_user["email"]
        user = get_user_by_email(email)
        
        if not user:
            return {
                "preferred_voice": default_voice_id,
                "playback_speed": 1.0,
            }
        preferred_voice = user.get("preferred_voice", default_voice_id)
        preferred_voice = normalize_voice_for_user(preferred_voice, current_user)

        return {
            "preferred_voice": preferred_voice,
            "playback_speed": user.get("playback_speed", 1.0),
        }
        
    except Exception as e:
        logger.error(f"[API] 获取用户偏好失败: {e}", exc_info=True)
        # 失败时返回默认值，不阻断用户使用
        return {
            "preferred_voice": default_voice_id,
            "playback_speed": 1.0,
        }
