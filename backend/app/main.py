import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.routers import story, video, auth
from app.utils.store import load_stories_from_disk

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时：加载故事数据
    logger.info("========== 应用启动 ==========")
    load_stories_from_disk()
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（压缩后的图片）
images_dir = Path("data/images")
images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=str(images_dir)), name="images")

app.include_router(auth.router)
app.include_router(story.router)
app.include_router(video.router)


@app.get("/")
def root():
    return {"message": "有声互动故事书 API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
