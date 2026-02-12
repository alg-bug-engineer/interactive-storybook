import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.routers import story, video, auth, voices, audio
from app.utils.store import load_stories_from_disk
from app.utils.paths import IMAGES_DIR
from app.services.tts_service import pregenerate_all_previews
import asyncio

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

_PROXY_ENV_KEYS = [
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
]


def _disable_system_proxy_env() -> None:
    """清理代理环境变量，避免本地服务误走系统代理。"""
    removed = []
    for key in _PROXY_ENV_KEYS:
        value = os.environ.pop(key, None)
        if value:
            removed.append(key)
    if removed:
        logger.info(f"[启动] 已禁用系统代理环境变量: {', '.join(removed)}")


_disable_system_proxy_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时：加载故事数据
    logger.info("========== 应用启动 ==========")
    load_stories_from_disk()
    
    # 后台预生成音色预览（不阻塞启动）
    asyncio.create_task(pregenerate_all_previews())
    
    logger.info("========== 应用启动完成 ==========")
    yield
    # 关闭时：清理资源（如需要）
    logger.info("========== 应用关闭 ==========")


app = FastAPI(
    title="有声互动故事书 API",
    version="0.1.0",
    lifespan=lifespan,
)
settings = get_settings()
allowed_origins = []
for origin in settings.api_cors_origins.split(","):
    normalized = origin.strip().rstrip("/")
    if normalized:
        allowed_origins.append(normalized)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（压缩后的图片）
app.mount("/static/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

app.include_router(auth.router)
app.include_router(story.router)
app.include_router(video.router)
app.include_router(voices.router)
app.include_router(audio.router)


@app.get("/")
def root():
    return {"message": "有声互动故事书 API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
