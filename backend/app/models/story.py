"""故事与互动数据模型"""
from typing import Optional, List
from pydantic import BaseModel, Field


class Character(BaseModel):
    name: str
    species: str
    trait: str
    appearance: str  # 英文，用于即梦画图


class Setting(BaseModel):
    location: str
    time: str
    weather: str
    visual_description: str = ""  # 英文，用于即梦画图


class InteractionPoint(BaseModel):
    type: str  # guess | choice | name | describe
    prompt: str
    hints: Optional[List[str]] = None
    user_input: Optional[str] = None


class StorySegment(BaseModel):
    id: Optional[str] = None
    text: str
    scene_description: str  # 英文，用于即梦
    emotion: str = "warm"  # happy | excited | mysterious | warm | tense
    interaction_point: Optional[InteractionPoint] = None
    image_url: Optional[str] = None


class StoryOutline(BaseModel):
    title: str
    theme: str
    characters: List[Character]
    setting: Setting
    segments: List[StorySegment]


class StoryState(BaseModel):
    """运行时故事状态（内存存储）"""
    id: str
    title: str
    theme: str
    characters: List[Character]
    setting: Setting
    segments: List[StorySegment]
    current_index: int = 0
    status: str = "narrating"  # generating | narrating | waiting_interaction | completed
    video_clips: dict[str, str] = Field(default_factory=dict)  # {segment_index: video_url}
    style_id: str = "q_cute"  # 故事风格ID，默认为软萌Q版卡通风
    max_total_pages: int = 7  # 用户设定的最大总页数（包括互动续写的页数），默认7页


class InteractRequest(BaseModel):
    story_id: str
    segment_index: int
    interaction_type: str
    user_input: str


class ContinueResponse(BaseModel):
    feedback: str
    segments: List[StorySegment]
