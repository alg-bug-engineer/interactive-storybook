"""项目路径常量，避免因工作目录不同导致文件读写错位。"""
from pathlib import Path

# .../interactive-storybook/backend
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent

# 统一数据目录（始终落在 backend/data 下）
BACKEND_DATA_DIR = BACKEND_ROOT / "data"
IMAGES_DIR = BACKEND_DATA_DIR / "images"
STORIES_DIR = BACKEND_DATA_DIR / "stories"
AUDIO_DIR = BACKEND_DATA_DIR / "audio"
IMAGE_CACHE_DIR = BACKEND_DATA_DIR / "image_cache"

# 初始化目录
for _p in [BACKEND_DATA_DIR, IMAGES_DIR, STORIES_DIR, AUDIO_DIR, IMAGE_CACHE_DIR]:
    _p.mkdir(parents=True, exist_ok=True)
