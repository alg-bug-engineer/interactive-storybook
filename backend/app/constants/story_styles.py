"""故事风格配置"""
from typing import Dict, TypedDict


class StoryStyle(TypedDict):
    """故事风格定义"""
    id: str
    name: str
    description: str
    suitable_for: str
    prompt: str  # 用于图片生成的风格prompt


# 6种故事风格配置
STORY_STYLES: Dict[str, StoryStyle] = {
    "q_cute": {
        "id": "q_cute",
        "name": "软萌 Q 版卡通风",
        "description": "角色圆滚滚、大眼睛、线条圆润，色彩鲜艳柔和",
        "suitable_for": "小动物主角、低幼童话、日常温馨小故事",
        "prompt": "soft cute Q-version cartoon style, chibi characters with big round eyes, smooth rounded lines, bright and soft colors, kawaii style, adorable and gentle, children's book illustration, high quality, masterpiece"
    },
    "watercolor_healing": {
        "id": "watercolor_healing",
        "name": "治愈水彩手绘风",
        "description": "淡彩晕染、笔触温柔、画面干净温暖",
        "suitable_for": "亲情、友情、成长类温柔小故事",
        "prompt": "healing watercolor hand-painted style, soft color washes, gentle brushstrokes, clean and warm atmosphere, soft pastel colors, dreamy and soothing, children's book illustration, high quality, masterpiece"
    },
    "classic_fairy_tale": {
        "id": "classic_fairy_tale",
        "name": "经典童话绘本风",
        "description": "复古绘本质感、线条柔和、像小时候的纸质故事书",
        "suitable_for": "公主、森林、魔法、王子骑士类传统童话",
        "prompt": "classic fairy tale picture book style, vintage picture book texture, soft lines, nostalgic paper storybook feel, traditional children's book illustration, warm and cozy, rich colors, detailed background, high quality, masterpiece"
    },
    "chinese_ink_cute": {
        "id": "chinese_ink_cute",
        "name": "国风童趣水墨风",
        "description": "淡彩水墨 + 可爱化处理，不严肃、很萌",
        "suitable_for": "传统寓言、神话、中式小动物（熊猫、兔子、鲤鱼）故事",
        "prompt": "Chinese ink painting style with cute treatment, soft ink wash colors, adorable and playful, not serious, very cute, traditional Chinese art style with modern children's book charm, gentle colors, high quality, masterpiece"
    },
    "minimal_simple": {
        "id": "minimal_simple",
        "name": "极简低幼简笔风",
        "description": "大色块、简单线条、辨识度极高",
        "suitable_for": "启蒙认知、短小故事、低龄宝宝",
        "prompt": "minimalist simple line drawing style for toddlers, large color blocks, simple clean lines, highly recognizable, bold and clear shapes, educational children's book style, bright colors, high quality, masterpiece"
    },
    "clay_doll": {
        "id": "clay_doll",
        "name": "黏土/玩偶质感风",
        "description": "像手工黏土做的，立体软萌、超有亲和力",
        "suitable_for": "小动物主角、治愈系小童话",
        "prompt": "clay and doll texture style, handmade clay appearance, three-dimensional soft and cute, super friendly and approachable, stop-motion animation feel, warm and cozy, children's book illustration, high quality, masterpiece"
    }
}

# 默认风格（保持向后兼容）
DEFAULT_STYLE_ID = "q_cute"

# 获取风格prompt
def get_style_prompt(style_id: str) -> str:
    """根据风格ID获取对应的prompt"""
    style = STORY_STYLES.get(style_id)
    if not style:
        # 如果风格不存在，使用默认风格
        style = STORY_STYLES[DEFAULT_STYLE_ID]
    return style["prompt"]

# 获取风格信息
def get_style_info(style_id: str) -> StoryStyle | None:
    """根据风格ID获取风格信息"""
    return STORY_STYLES.get(style_id)

# 获取所有风格列表
def get_all_styles() -> list[StoryStyle]:
    """获取所有可用风格列表"""
    return list(STORY_STYLES.values())
