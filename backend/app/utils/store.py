"""故事状态存储：内存+文件持久化（后端重启不丢失）"""
import json
import logging
from typing import Optional, List
import uuid
from app.models.story import StoryState
from app.utils.paths import STORIES_DIR
from app.utils.url_utils import normalize_image_url

logger = logging.getLogger(__name__)

# 内存缓存
_stories: dict[str, StoryState] = {}
_story_order: List[str] = []  # 创建顺序，用于画廊（新在前）

# 文件存储目录
INDEX_FILE = STORIES_DIR / "_index.json"


def _save_story_to_file(state: StoryState) -> None:
    """将故事保存到文件"""
    try:
        story_file = STORIES_DIR / f"{state.id}.json"
        # 使用 model_dump() 转为字典，再序列化为 JSON
        data = state.model_dump()
        segments = data.get("segments") or []
        for seg in segments:
            seg["image_url"] = normalize_image_url(seg.get("image_url"))
        story_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"[存储] 故事已保存到文件: {story_file}")
    except Exception as e:
        logger.error(f"[存储] ❌ 保存故事文件失败: {e}", exc_info=True)


def _save_index() -> None:
    """保存故事索引（顺序）"""
    try:
        INDEX_FILE.write_text(json.dumps(_story_order, ensure_ascii=False), encoding="utf-8")
        logger.debug(f"[存储] 索引已保存，共 {len(_story_order)} 个故事")
    except Exception as e:
        logger.error(f"[存储] ❌ 保存索引失败: {e}", exc_info=True)


def load_stories_from_disk() -> None:
    """启动时从磁盘加载所有故事到内存"""
    logger.info("[存储] 开始从磁盘加载故事...")
    
    # 加载索引
    if INDEX_FILE.exists():
        try:
            _story_order.clear()
            order_data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            _story_order.extend(order_data)
            logger.info(f"[存储] ✅ 索引加载完成，共 {len(_story_order)} 个故事")
        except Exception as e:
            logger.error(f"[存储] ❌ 加载索引失败: {e}", exc_info=True)
    
    # 加载所有故事文件
    loaded_count = 0
    for story_file in STORIES_DIR.glob("*.json"):
        if story_file.name == "_index.json":
            continue
        
        try:
            data = json.loads(story_file.read_text(encoding="utf-8"))
            story_id = data.get("id")
            if story_id:
                # 启动时修复历史数据中的图片 URL（仅内存修复，保存时持久化）
                segments = data.get("segments") or []
                normalized = False
                for seg in segments:
                    old = seg.get("image_url")
                    new = normalize_image_url(old)
                    if old != new:
                        seg["image_url"] = new
                        normalized = True
                _stories[story_id] = StoryState(**data)
                loaded_count += 1
                if normalized:
                    _save_story_to_file(_stories[story_id])
                logger.debug(f"[存储] 加载故事: {story_id} - {data.get('title', 'untitled')}")
        except Exception as e:
            logger.error(f"[存储] ❌ 加载故事文件失败 {story_file}: {e}", exc_info=True)
    
    logger.info(f"[存储] ✅ 故事加载完成，共 {loaded_count} 个故事")


def save_story(state: StoryState) -> StoryState:
    """保存故事到内存和文件"""
    for seg in state.segments:
        seg.image_url = normalize_image_url(seg.image_url)
    _stories[state.id] = state
    if state.id not in _story_order:
        _story_order.append(state.id)
        _save_index()
    _save_story_to_file(state)
    return state


def get_story(story_id: str) -> Optional[StoryState]:
    """获取故事（先从内存，如未找到则尝试从文件加载）"""
    # 先从内存获取
    if story_id in _stories:
        return _stories[story_id]
    
    # 尝试从文件加载
    story_file = STORIES_DIR / f"{story_id}.json"
    if story_file.exists():
        try:
            data = json.loads(story_file.read_text(encoding="utf-8"))
            story = StoryState(**data)
            _stories[story_id] = story  # 加载到内存
            if story_id not in _story_order:
                _story_order.append(story_id)
            logger.info(f"[存储] 从文件加载故事: {story_id}")
            return story
        except Exception as e:
            logger.error(f"[存储] ❌ 从文件加载故事失败 {story_id}: {e}", exc_info=True)
    
    return None


def update_story(story_id: str, **kwargs) -> Optional[StoryState]:
    """更新故事并保存到文件"""
    s = _stories.get(story_id)
    if not s:
        return None
    for k, v in kwargs.items():
        if hasattr(s, k):
            setattr(s, k, v)
    for seg in s.segments:
        seg.image_url = normalize_image_url(seg.image_url)
    _save_story_to_file(s)
    return s


def new_story_id() -> str:
    return str(uuid.uuid4())[:8]


def list_stories() -> List[dict]:
    """返回所有故事摘要（用于画廊），按创建时间倒序。"""
    result = []
    for story_id in reversed(_story_order):
        state = _stories.get(story_id)
        if not state:
            # 尝试从文件加载
            state = get_story(story_id)
        if not state:
            continue
        cover_url = None
        if state.segments and state.segments[0].image_url:
            cover_url = normalize_image_url(state.segments[0].image_url)
        result.append({
            "story_id": state.id,
            "title": state.title,
            "theme": state.theme,
            "cover_url": cover_url,
            "total_segments": len(state.segments),
        })
    return result
