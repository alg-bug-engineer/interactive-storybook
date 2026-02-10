"""音色常量定义"""

# 可用音色列表（基于 edge-tts）
AVAILABLE_VOICES = [
    {
        "id": "zh-CN-XiaoxiaoNeural",
        "name": "晓晓",
        "gender": "female",
        "description": "温柔、亲切",
        "tags": ["默认", "温柔", "亲切", "儿童"],
        "recommended_for": ["睡前故事", "儿童故事"],
        "is_default": True,
        "is_recommended": True,
    },
    {
        "id": "zh-CN-XiaoyiNeural",
        "name": "晓伊",
        "gender": "female",
        "description": "活泼、明快",
        "tags": ["活泼", "明快"],
        "recommended_for": ["冒险故事", "互动故事"],
        "is_default": False,
        "is_recommended": True,
    },
    {
        "id": "zh-CN-YunjianNeural",
        "name": "云健",
        "gender": "male",
        "description": "沉稳、磁性",
        "tags": ["沉稳", "磁性", "男声"],
        "recommended_for": ["纪录片", "历史故事"],
        "is_default": False,
        "is_recommended": True,
    },
    {
        "id": "zh-CN-YunxiNeural",
        "name": "云希",
        "gender": "male",
        "description": "温和、自然",
        "tags": ["温和", "自然", "男声"],
        "recommended_for": ["通用故事"],
        "is_default": False,
        "is_recommended": False,
    },
    {
        "id": "zh-CN-YunxiaNeural",
        "name": "云霞",
        "gender": "female",
        "description": "柔和、舒缓",
        "tags": ["柔和", "舒缓"],
        "recommended_for": ["放松类故事"],
        "is_default": False,
        "is_recommended": False,
    },
    {
        "id": "zh-CN-YunyangNeural",
        "name": "云扬",
        "gender": "male",
        "description": "激昂、有力",
        "tags": ["激昂", "有力", "男声"],
        "recommended_for": ["励志故事", "体育故事"],
        "is_default": False,
        "is_recommended": False,
    },
    {
        "id": "zh-CN-liaoning-XiaobeiNeural",
        "name": "小北",
        "gender": "female",
        "description": "辽宁方言特色",
        "tags": ["方言", "辽宁", "特色"],
        "recommended_for": ["特色故事"],
        "is_default": False,
        "is_recommended": False,
    },
    {
        "id": "zh-CN-shaanxi-XiaoniNeural",
        "name": "小妮",
        "gender": "female",
        "description": "陕西方言特色",
        "tags": ["方言", "陕西", "特色"],
        "recommended_for": ["特色故事"],
        "is_default": False,
        "is_recommended": False,
    },
]

# 默认音色
DEFAULT_VOICE_ID = "zh-CN-XiaoxiaoNeural"

# 试听示例文案
PREVIEW_TEXT = "你好，我是{voice_name}。在一个遥远的森林里，住着一只聪明的小狐狸，它最喜欢在月光下听妈妈讲故事。"

# 音色 ID 映射（用于快速查找）
VOICE_ID_MAP = {v["id"]: v for v in AVAILABLE_VOICES}


def get_voice_by_id(voice_id: str) -> dict | None:
    """根据 ID 获取音色信息"""
    return VOICE_ID_MAP.get(voice_id)


def get_default_voice() -> dict:
    """获取默认音色"""
    return next(v for v in AVAILABLE_VOICES if v["is_default"])


def get_recommended_voices() -> list[dict]:
    """获取推荐音色列表"""
    return [v for v in AVAILABLE_VOICES if v["is_recommended"]]


def is_valid_voice(voice_id: str) -> bool:
    """验证音色 ID 是否有效"""
    return voice_id in VOICE_ID_MAP
