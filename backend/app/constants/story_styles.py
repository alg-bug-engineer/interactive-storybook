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
        "prompt": "Q-version chibi kawaii style, super deformed characters with oversized heads and tiny bodies, extremely large sparkling round eyes, bubble-like rounded shapes, vibrant pastel gradient colors (pink, mint, lavender), glossy shiny finish, ultra cute and adorable, modern digital kawaii art, children's book illustration, high quality, masterpiece"
    },
    "watercolor_healing": {
        "id": "watercolor_healing",
        "name": "治愈水彩手绘风",
        "description": "淡彩晕染、笔触温柔、画面干净温暖",
        "suitable_for": "亲情、友情、成长类温柔小故事",
        "prompt": "delicate watercolor painting, soft flowing color washes with visible paper texture, gentle wet-on-wet technique, light transparent layers, subtle color bleeding, dreamy pastel palette (soft pink, sky blue, cream yellow), hand-painted brushstrokes, ethereal and peaceful atmosphere, children's picture book watercolor art, high quality, masterpiece"
    },
    "classic_fairy_tale": {
        "id": "classic_fairy_tale",
        "name": "经典童话绘本风",
        "description": "复古绘本质感、线条柔和、像小时候的纸质故事书",
        "suitable_for": "公主、森林、魔法、王子骑士类传统童话",
        "prompt": "vintage classic fairy tale illustration, traditional picture book style from 1960s-1980s, soft detailed linework with gentle shading, nostalgic warm color palette with aged paper texture, European children's book art, storybook illustration with ornate borders, detailed forest and castle backgrounds, romantic and magical atmosphere, high quality, masterpiece"
    },
    "chinese_ink_cute": {
        "id": "chinese_ink_cute",
        "name": "国风童趣水墨风",
        "description": "淡彩水墨 + 可爱化处理，不严肃、很萌",
        "suitable_for": "传统寓言、神话、中式小动物（熊猫、兔子、鲤鱼）故事",
        "prompt": "cute Chinese ink wash painting, traditional sumi-e style with playful twist, flowing black ink brushstrokes with light color accents, minimalist composition with negative space, adorable rounded animals in traditional Chinese art style, gentle ink gradients (from dark to light), rice paper texture, whimsical and cheerful, modern children's book with Chinese aesthetic, high quality, masterpiece"
    },
    "minimal_simple": {
        "id": "minimal_simple",
        "name": "极简黑白线稿风",
        "description": "黑白线条、简笔画风格、清晰易辨识",
        "suitable_for": "启蒙认知、涂色书、低龄宝宝",
        "prompt": "black and white line art, simple sketch style, monochrome line drawing, clean bold outlines without fill colors, minimalist coloring book illustration, pure line work on white background, geometric simplified shapes, high contrast black lines, very clear and recognizable forms, toddler coloring page style, no shading, no gradients, pure lineart only, high quality, masterpiece"
    },
    "clay_doll": {
        "id": "clay_doll",
        "name": "黏土/玩偶质感风",
        "description": "像手工黏土做的，立体软萌、超有亲和力",
        "suitable_for": "小动物主角、治愈系小童话",
        "prompt": "3D clay sculpture style, handmade plasticine texture with finger marks, soft matte polymer clay surface, cute rounded tactile forms, stop-motion animation aesthetic, visible molding details and seams, warm studio lighting with soft shadows, Claymation character design, friendly and huggable appearance, physically crafted look, children's craft illustration style, high quality, masterpiece"
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
