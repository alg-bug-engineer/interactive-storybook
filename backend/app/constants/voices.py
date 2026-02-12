"""音色常量定义（按用户等级区分）"""
from typing import Dict, List, Optional

# 免费用户（edge-tts）
FREE_AVAILABLE_VOICES = [
    {
        "id": "zh-CN-XiaoxiaoNeural",
        "name": "晓晓",
        "gender": "female",
        "description": "温柔、亲切",
        "tags": ["默认", "温柔", "亲切", "儿童"],
        "recommended_for": ["睡前故事", "儿童故事"],
        "is_default": True,
        "is_recommended": True,
        "provider": "edge",
        "tier": "free",
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
        "provider": "edge",
        "tier": "free",
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
        "provider": "edge",
        "tier": "free",
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
        "provider": "edge",
        "tier": "free",
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
        "provider": "edge",
        "tier": "free",
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
        "provider": "edge",
        "tier": "free",
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
        "provider": "edge",
        "tier": "free",
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
        "provider": "edge",
        "tier": "free",
    },
]

# 付费用户（火山线上 TTS）
PREMIUM_AVAILABLE_VOICES = [
    {
        "id": "zh_female_wanqudashu_moon_bigtts",
        "name": "湾区大叔",
        "gender": "female",
        "description": "趣味方言",
        "tags": ["趣味方言"],
        "recommended_for": ["中文"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_female_daimengchuanmei_moon_bigtts",
        "name": "呆萌川妹",
        "gender": "female",
        "description": "趣味方言",
        "tags": ["趣味方言"],
        "recommended_for": ["中文"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_male_guozhoudege_moon_bigtts",
        "name": "广州德哥",
        "gender": "male",
        "description": "趣味方言",
        "tags": ["趣味方言"],
        "recommended_for": ["中文"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_male_beijingxiaoye_moon_bigtts",
        "name": "北京小爷",
        "gender": "male",
        "description": "趣味方言",
        "tags": ["趣味方言"],
        "recommended_for": ["中文"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_male_shaonianzixin_moon_bigtts",
        "name": "少年梓辛/Brayan",
        "gender": "male",
        "description": "通用场景",
        "tags": ["通用场景"],
        "recommended_for": ["中/英"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_female_meilinvyou_moon_bigtts",
        "name": "魅力女友",
        "gender": "female",
        "description": "角色扮演",
        "tags": ["角色扮演"],
        "recommended_for": ["中文"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_male_shenyeboke_moon_bigtts",
        "name": "深夜播客",
        "gender": "male",
        "description": "角色扮演",
        "tags": ["角色扮演"],
        "recommended_for": ["中文"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_female_sajiaonvyou_moon_bigtts",
        "name": "柔美女友",
        "gender": "female",
        "description": "角色扮演",
        "tags": ["角色扮演"],
        "recommended_for": ["中文"],
        "is_default": True,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_female_yuanqinvyou_moon_bigtts",
        "name": "撒娇学妹",
        "gender": "female",
        "description": "角色扮演",
        "tags": ["角色扮演"],
        "recommended_for": ["中文"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
    {
        "id": "zh_male_haoyuxiaoge_moon_bigtts",
        "name": "浩宇小哥",
        "gender": "male",
        "description": "趣味方言",
        "tags": ["趣味方言"],
        "recommended_for": ["中文"],
        "is_default": False,
        "is_recommended": True,
        "provider": "volcano",
        "tier": "premium",
    },
]

DEFAULT_FREE_VOICE_ID = "zh-CN-XiaoxiaoNeural"
DEFAULT_PREMIUM_VOICE_ID = "zh_female_sajiaonvyou_moon_bigtts"

# 向后兼容（旧代码默认 free）
AVAILABLE_VOICES = FREE_AVAILABLE_VOICES
DEFAULT_VOICE_ID = DEFAULT_FREE_VOICE_ID

# 试听示例文案
PREVIEW_TEXT = (
    "你好，我是{voice_name}。在一个遥远的森林里，"
    "住着一只聪明的小狐狸，它最喜欢在月光下听妈妈讲故事。"
)

FREE_VOICE_ID_MAP = {v["id"]: v for v in FREE_AVAILABLE_VOICES}
PREMIUM_VOICE_ID_MAP = {v["id"]: v for v in PREMIUM_AVAILABLE_VOICES}
ALL_VOICE_ID_MAP = {**FREE_VOICE_ID_MAP, **PREMIUM_VOICE_ID_MAP}


def _is_premium_user(user: Optional[dict]) -> bool:
    return bool(user and user.get("is_paid"))


def get_available_voices(user: Optional[dict] = None) -> List[Dict]:
    """按用户等级返回可用音色。"""
    return PREMIUM_AVAILABLE_VOICES if _is_premium_user(user) else FREE_AVAILABLE_VOICES


def get_voice_by_id(voice_id: str) -> Optional[Dict]:
    """根据 ID 获取音色信息（跨全部音色）。"""
    return ALL_VOICE_ID_MAP.get(voice_id)


def get_default_voice_id(user: Optional[dict] = None) -> str:
    return DEFAULT_PREMIUM_VOICE_ID if _is_premium_user(user) else DEFAULT_FREE_VOICE_ID


def get_default_voice(user: Optional[dict] = None) -> Dict:
    """获取默认音色。"""
    return get_voice_by_id(get_default_voice_id(user))


def get_recommended_voices(user: Optional[dict] = None) -> List[Dict]:
    """按用户等级返回推荐音色。"""
    return [v for v in get_available_voices(user) if v.get("is_recommended")]


def is_free_voice(voice_id: str) -> bool:
    return voice_id in FREE_VOICE_ID_MAP


def is_premium_voice(voice_id: str) -> bool:
    return voice_id in PREMIUM_VOICE_ID_MAP


def is_valid_voice(voice_id: str, user: Optional[dict] = None) -> bool:
    """
    验证音色是否有效。
    - 传 user：按该用户等级验证
    - 不传 user：在全量音色中验证（向后兼容）
    """
    if not voice_id:
        return False
    if user is None:
        return voice_id in ALL_VOICE_ID_MAP
    if _is_premium_user(user):
        return is_premium_voice(voice_id)
    return is_free_voice(voice_id)


def normalize_voice_for_user(voice_id: Optional[str], user: Optional[dict] = None) -> str:
    """将传入音色归一化为当前用户等级可用的音色。"""
    candidate = (voice_id or "").strip()
    if _is_premium_user(user):
        return candidate if is_premium_voice(candidate) else DEFAULT_PREMIUM_VOICE_ID
    return candidate if is_free_voice(candidate) else DEFAULT_FREE_VOICE_ID
