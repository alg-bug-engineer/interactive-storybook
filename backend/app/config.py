"""应用配置 - 从环境变量读取"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# 支持从项目根目录的 .env 加载（当在 backend/ 下启动时）
_root_env = Path(__file__).resolve().parent.parent.parent / ".env"
_env_file = _root_env if _root_env.exists() else ".env"


class Settings(BaseSettings):
    # 即梦 API (方案 B - 本地服务，免费用户使用)
    jimeng_api_base_url: str = "http://localhost:5100"
    jimeng_session_id: str = ""
    jimeng_model: str = "jimeng-4.5"

    # 后端
    backend_host: str = "0.0.0.0"
    backend_port: int = 8100
    api_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # LLM (OpenAI 兼容)
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # 视频生成
    enable_video_generation: bool = True
    video_output_dir: str = "/tmp/storybook_videos"

    # 用户数据（本地文件存储）
    data_dir: str = "data"
    auth_secret: str = "change-me-in-production"

    # 火山引擎官方 API（付费用户专享）
    # 火山即梦官方 API
    volcano_jimeng_ak: str = ""
    volcano_jimeng_sk: str = ""
    volcano_jimeng_req_key: str = "jimeng_t2i_v40"

    # 火山 TTS 官方 API
    volcano_tts_appid: str = ""
    volcano_tts_access_token: str = ""
    volcano_tts_cluster: str = "volcano_tts"
    volcano_tts_endpoint: str = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"
    volcano_tts_voice_type: str = "BV700_V2_streaming"
    volcano_tts_encoding: str = "mp3"

    class Config:
        env_file = _env_file
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
