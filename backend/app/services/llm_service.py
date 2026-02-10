"""LLM 故事大纲生成与互动续写 - OpenAI 兼容 API"""
import json
import re
import logging
from openai import AsyncOpenAI
from app.config import get_settings
from app.models.story import (
    StoryOutline,
    StorySegment,
    InteractionPoint,
    Character,
    Setting,
    ContinueResponse,
)
from app.data.pools import pick_theme, pick_character, pick_setting

logger = logging.getLogger(__name__)

OUTLINE_SYSTEM = """你是一个专业的儿童故事创作家，专门为3-10岁小朋友创作温暖、有趣、富有教育意义的原创童话故事。

## 创作要求
1. 故事篇幅：**最少 5 页（段），最多 8 页（段）**，每段 80-150 字。
2. 语言风格：简单温馨，用词适合少儿理解，多用拟声词和形容词。
3. 角色设定：以可爱的动物或奇幻角色为主角。
4. **故事结构（必须严格遵守）**：
   - 起承转合，有悬念、有惊喜、有温暖的结局。
   - **最后一段必须是完整的故事结局**：问题已解决、冲突已化解、角色得到成长，传递积极向上的寓意。
   - **故事必须有始有终**，不能开放式结局或留下悬念让故事延续。
5. 教育意义：潜移默化传递正面价值观（勇气/友谊/善良/分享/好奇心/团结/诚实）。

## 互动设计（重要）
- 整篇故事**最少 1 个互动节点，最多 3 个互动节点**。有参与感不需要每一步都互动，在关键节点让小朋友参与即可。
- 只在部分段落的结尾设置 interaction_point（例如第 2 段、第 4 段等），其余段落的 interaction_point 一律为 null。
- **最后一段（结局段）不能有互动节点**，因为故事已经完结。
- 互动类型：猜一猜(guess)、选一选(choice)、起名字(name)、描述一下(describe)。以悬念或惊喜收尾，让故事自然停顿；无论孩子回答什么，都能自然衔接后续故事。

## 输出格式
只输出一个 JSON 对象，不要 markdown 代码块，不要其他文字。键名用英文。
{
  "title": "故事标题",
  "theme": "主题关键词",
  "characters": [{"name":"角色名","species":"种类","trait":"性格","appearance":"英文外观描述"}],
  "setting": {"location":"地点","time":"时间","weather":"天气","visual_description":"英文场景描述"},
  "segments": [
    {"text": "故事文本", "emotion": "warm", "scene_description": "英文场景描述", "interaction_point": null},
    {"text": "故事文本", "emotion": "warm", "scene_description": "英文场景描述", "interaction_point": {"type":"guess","prompt":"小朋友，你猜猜发生了什么？","hints":["提示A","提示B"]}}
  ]
}
"""


def _normalize_json(raw: str) -> str:
    """从模型输出中提取 JSON 并做清洗和修复。"""
    raw = raw.strip()
    
    # 去掉可能的 markdown 代码块
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
        raw = raw.strip()
    
    # 提取第一个完整的 JSON 对象（如果有多余文本）
    start = raw.find("{")
    if start >= 0:
        # 找到匹配的结束括号（考虑嵌套）
        brace_count = 0
        in_string = False
        escape_next = False
        end = start
        
        for i in range(start, len(raw)):
            char = raw[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
        
        if brace_count == 0:
            raw = raw[start:end]
    
    # 移除尾随逗号（在对象和数组的最后一个元素后）
    raw = re.sub(r',(\s*[}\]])', r'\1', raw)
    
    return raw


def _parse_json_with_retry(raw: str, max_retries: int = 3) -> dict:
    """解析 JSON，带重试和错误修复。"""
    last_error = None
    current_raw = raw
    
    for attempt in range(max_retries):
        try:
            # 尝试直接解析
            return json.loads(current_raw)
        except json.JSONDecodeError as e:
            last_error = e
            error_pos = e.pos if hasattr(e, 'pos') else None
            logger.warning(
                f"[LLM] JSON 解析失败 (尝试 {attempt + 1}/{max_retries}): "
                f"{e.msg} at pos {error_pos}, line {e.lineno}, col {e.colno}"
            )
            
            if attempt < max_retries - 1:
                # 尝试修复常见问题
                try:
                    # 方法1: 修复未转义的引号（在字符串值中）
                    if error_pos and error_pos < len(current_raw):
                        # 检查错误位置附近的上下文
                        context_start = max(0, error_pos - 50)
                        context_end = min(len(current_raw), error_pos + 50)
                        context = current_raw[context_start:context_end]
                        logger.debug(f"[LLM] 错误上下文: ...{context}...")
                        
                        # 如果错误位置是引号，且不在转义后，尝试转义
                        if current_raw[error_pos] == '"' and error_pos > 0:
                            if current_raw[error_pos - 1] != '\\':
                                # 检查是否在字符串值中（通过计算前面的引号数）
                                before = current_raw[:error_pos]
                                # 简单计算：统计未转义的引号
                                quote_count = 0
                                i = 0
                                while i < len(before):
                                    if before[i] == '\\':
                                        i += 2  # 跳过转义字符
                                        continue
                                    if before[i] == '"':
                                        quote_count += 1
                                    i += 1
                                
                                if quote_count % 2 == 1:  # 在字符串值中
                                    current_raw = current_raw[:error_pos] + '\\"' + current_raw[error_pos + 1:]
                                    logger.debug(f"[LLM] 尝试转义引号")
                                    continue
                    
                    # 方法2: 修复未转义的换行符和特殊字符
                    # 在字符串值中，换行符应该被转义
                    # 使用正则表达式找到字符串值并转义其中的特殊字符
                    def fix_string_content(match):
                        content = match.group(1)
                        # 转义特殊字符（但保留已转义的）
                        fixed = ""
                        i = 0
                        while i < len(content):
                            if content[i] == '\\' and i + 1 < len(content):
                                fixed += content[i:i+2]  # 保留已转义的字符
                                i += 2
                            elif content[i] in '\n\r\t':
                                fixed += '\\' + ('n' if content[i] == '\n' else 'r' if content[i] == '\r' else 't')
                                i += 1
                            else:
                                fixed += content[i]
                                i += 1
                        return f'"{fixed}"'
                    
                    # 匹配字符串值并修复
                    current_raw = re.sub(r'"([^"]*)"', fix_string_content, current_raw)
                    
                    # 方法3: 移除尾随逗号
                    current_raw = re.sub(r',(\s*[}\]])', r'\1', current_raw)
                    
                    # 方法4: 移除控制字符（但保留换行、回车、制表符）
                    current_raw = ''.join(
                        char for char in current_raw 
                        if ord(char) >= 32 or char in '\n\r\t' or (char == '\x00' and attempt == max_retries - 1)
                    )
                    
                except Exception as fix_error:
                    logger.warning(f"[LLM] JSON 修复过程出错: {fix_error}")
    
    # 所有尝试都失败，记录详细错误
    logger.error(f"[LLM] ❌ JSON 解析最终失败")
    logger.error(f"[LLM] 错误位置: pos {last_error.pos if hasattr(last_error, 'pos') else 'unknown'}, "
                 f"line {last_error.lineno}, col {last_error.colno}")
    logger.error(f"[LLM] 错误消息: {last_error.msg}")
    logger.error(f"[LLM] 原始内容 (前1000字符):\n{raw[:1000]}")
    logger.error(f"[LLM] 最后尝试的内容 (前1000字符):\n{current_raw[:1000]}")
    
    # 返回一个默认的空结构，避免完全崩溃
    return {
        "feedback": "太棒啦！你的想法真有趣！",
        "segments": [{
            "text": "故事继续发展着，充满了惊喜和温暖。",
            "emotion": "warm",
            "scene_description": "story continues with warmth",
            "interaction_point": None
        }]
    }


def _parse_outline(data: dict) -> StoryOutline:
    """将 LLM 返回的 dict 转为 StoryOutline。"""
    chars = [Character(**c) for c in data.get("characters", [])]
    setting_data = data.get("setting", {})
    if "visualDescription" in setting_data and "visual_description" not in setting_data:
        setting_data["visual_description"] = setting_data.pop("visualDescription", "")
    setting = Setting(**setting_data)
    segments = []
    for i, s in enumerate(data.get("segments", [])):
        ip = s.get("interaction_point") or s.get("interactionPoint")
        if ip:
            ip = InteractionPoint(
                type=ip.get("type", "guess"),
                prompt=ip.get("prompt", ""),
                hints=ip.get("hints"),
            )
        seg = StorySegment(
            id=str(i),
            text=s.get("text", ""),
            scene_description=s.get("scene_description", s.get("sceneDescription", "")),
            emotion=s.get("emotion", "warm"),
            interaction_point=ip,
        )
        segments.append(seg)
    
    # 强制保证至少 1 个、至多 3 个互动环节
    interaction_indices = [i for i, seg in enumerate(segments) if seg.interaction_point]
    if not interaction_indices and segments:
        idx = min(1, len(segments) - 1)
        seg = segments[idx]
        segments[idx] = StorySegment(
            id=seg.id,
            text=seg.text,
            scene_description=seg.scene_description,
            emotion=seg.emotion,
            interaction_point=InteractionPoint(
                type="guess",
                prompt="小朋友，你猜猜接下来会发生什么？",
                hints=["想一想故事里的角色会怎么做", "可以大胆猜一猜"],
            ),
        )
        logger.info(f"[LLM] 为保证互动，在第 {idx + 1} 段添加了互动节点")
    elif len(interaction_indices) > 3:
        for i in interaction_indices[3:]:
            seg = segments[i]
            segments[i] = StorySegment(
                id=seg.id,
                text=seg.text,
                scene_description=seg.scene_description,
                emotion=seg.emotion,
                interaction_point=None,
            )
        logger.info(f"[LLM] 互动节点超过 3 个，已保留前 3 个，移除第 {[x+1 for x in interaction_indices[3:]]} 段互动")
    
    # 篇幅限制：最少 5 页，最多 8 页
    if len(segments) > 8:
        segments = segments[:8]
        logger.info("[LLM] 段落超过 8 页，已截断为前 8 页")
    if len(segments) < 5:
        logger.warning(f"[LLM] 段落数为 {len(segments)}，建议 5-8 页")
    
    # 确保最后一段没有互动节点（因为是结局）
    if segments and segments[-1].interaction_point:
        last_seg = segments[-1]
        segments[-1] = StorySegment(
            id=last_seg.id,
            text=last_seg.text,
            scene_description=last_seg.scene_description,
            emotion=last_seg.emotion,
            interaction_point=None,
        )
        logger.info("[LLM] 最后一段有互动节点，已移除（结局不应有互动）")
    
    return StoryOutline(
        title=data.get("title", "奇妙冒险"),
        theme=data.get("theme", ""),
        characters=chars,
        setting=setting,
        segments=segments,
    )


async def generate_story_outline(
    user_theme: str | None = None,
    total_pages: int | None = None,
    no_interaction: bool = False,
) -> StoryOutline:
    """根据可选主题或随机选择主题/角色/场景，调用 LLM 生成故事大纲。
    total_pages 指定则生成恰好该页数；no_interaction 为 True 时所有段落的 interaction_point 均为 null。"""
    if user_theme and user_theme.strip():
        # 用户指定主题（如龟兔赛跑、小兔子找妈妈）
        theme_desc = user_theme.strip()
        character = pick_character()
        setting = pick_setting()
        user_content = f"""请根据以下故事主题创作一个完整的儿童故事，输出一个 JSON。
故事主题（必须围绕此主题展开）：{theme_desc}
主角：{character.name}，{character.species}，{character.trait}，外观（英文）：{character.appearance}
场景：{setting.location}，{setting.time}，{setting.weather}，视觉（英文）：{setting.visual_description}
"""
    else:
        # 随机故事
        theme = pick_theme()
        character = pick_character()
        setting = pick_setting()
        user_content = f"""请根据以下元素创作一个完整的儿童故事，输出一个 JSON。
主题：{theme['theme']}，{theme['keywords']}，情节种子：{theme['plot_seed']}
主角：{character.name}，{character.species}，{character.trait}，外观（英文）：{character.appearance}
场景：{setting.location}，{setting.time}，{setting.weather}，视觉（英文）：{setting.visual_description}
"""
    if total_pages is not None and total_pages >= 1:
        user_content += f"\n**篇幅要求（必须严格遵守）**：请生成恰好 {total_pages} 页（段），segments 数组长度必须为 {total_pages}。"
    if no_interaction:
        user_content += "\n**不要任何互动节点**：所有段落的 interaction_point 必须为 null，这是一个纯叙述故事。"
    settings = get_settings()
    client = AsyncOpenAI(
        base_url=settings.llm_api_base.rstrip("/"),
        api_key=settings.llm_api_key,
    )
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": OUTLINE_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.8,
    )
    raw = resp.choices[0].message.content or "{}"
    logger.debug(f"[LLM] 原始响应 (前200字符): {raw[:200]}...")
    
    raw = _normalize_json(raw)
    logger.debug(f"[LLM] 清洗后 (前200字符): {raw[:200]}...")
    
    data = _parse_json_with_retry(raw)
    logger.info(f"[LLM] ✅ JSON 解析成功")
    
    return _parse_outline(data)


CONTINUE_SYSTEM = """你正在为一个小朋友续写互动童话故事。请只输出一个 JSON 对象，不要 markdown 代码块，不要其他文字。

## 核心要求（必须严格遵守）
- **用户参与感**：孩子的回答（他/她起的名字、选的内容、猜的结果、描述的东西）必须在续写中明确出现并推动情节。例如：孩子起了名字「小星星」，续写里就要用「小星星」称呼角色；孩子选了「去山洞」，续写就要写他们去了山洞。让小朋友明显感到「我的选择/回答改变了故事」。
- **反馈**：先写一句热情鼓励的反馈，自然过渡到续写。
- **一致性**：续写风格、角色名、设定与上文完全一致。
- **故事进度控制（必须遵守）**：
  - 如果提示中说明"接近结尾"或"最后一次互动"，续写必须在 1-2 段内给出完整结局（问题解决、冲突化解、传递寓意）。
  - 如果是中期互动，续写 1-2 段即可，不要一次续写太多段落。
  - **故事必须有始有终**，不能开放式结局或无限延续。

## 输出格式
{
  "feedback": "对孩子回答的鼓励反馈，1-2句话，并自然衔接到续写（可提及孩子的回答）",
  "segments": [
    {
      "text": "续写的故事文本，80-150字，必须直接体现或引用孩子的回答",
      "emotion": "happy或excited或mysterious或warm或tense",
      "scene_description": "英文场景描述用于AI画图",
      "interaction_point": null 或 {"type":"guess或choice或name或describe","prompt":"问题","hints":["A","B"]}
    }
  ]
}

注意：如果已接近结尾，续写的最后一段 interaction_point 必须为 null（因为故事已完结）。
"""


def _parse_continue(data: dict) -> ContinueResponse:
    """解析续写响应，带容错处理。"""
    try:
        segs = []
        segments_data = data.get("segments", [])
        
        if not isinstance(segments_data, list):
            logger.warning(f"[LLM] segments 不是列表类型: {type(segments_data)}")
            segments_data = []
        
        for i, s in enumerate(segments_data):
            if not isinstance(s, dict):
                logger.warning(f"[LLM] 段落 {i} 不是字典类型: {type(s)}")
                continue
            
            ip = s.get("interaction_point") or s.get("interactionPoint")
            if ip and isinstance(ip, dict):
                ip = InteractionPoint(
                    type=ip.get("type", "guess"),
                    prompt=ip.get("prompt", ""),
                    hints=ip.get("hints"),
                )
            else:
                ip = None
            
            # 确保必要字段存在
            text = s.get("text", "")
            if not text:
                logger.warning(f"[LLM] 段落 {i} 文本为空，使用默认文本")
                text = "故事继续发展着..."
            
            segs.append(
                StorySegment(
                    text=text,
                    scene_description=s.get("scene_description", s.get("sceneDescription", "story scene")),
                    emotion=s.get("emotion", "warm"),
                    interaction_point=ip,
                )
            )
        
        # 如果没有段落，创建一个默认段落
        if not segs:
            logger.warning("[LLM] 没有有效段落，创建默认段落")
            segs.append(
                StorySegment(
                    text="故事继续发展着，充满了惊喜和温暖。",
                    scene_description="story continues with warmth",
                    emotion="warm",
                    interaction_point=None,
                )
            )
        
        feedback = data.get("feedback", "太棒啦！")
        if not feedback:
            feedback = "太棒啦！"
        
        return ContinueResponse(
            feedback=feedback,
            segments=segs,
        )
    except Exception as e:
        logger.error(f"[LLM] ❌ 解析续写响应失败: {type(e).__name__}: {e}", exc_info=True)
        # 返回默认响应，避免完全失败
        return ContinueResponse(
            feedback="太棒啦！你的想法真有趣！",
            segments=[
                StorySegment(
                    text="故事继续发展着，充满了惊喜和温暖。",
                    scene_description="story continues with warmth",
                    emotion="warm",
                    interaction_point=None,
                )
            ],
        )


async def continue_story_with_interaction(
    story_context: str,
    interaction_type: str,
    interaction_prompt: str,
    user_input: str,
    current_segment_count: int,
    total_interactions_used: int,
) -> ContinueResponse:
    """根据互动回答生成反馈与续写段落。
    
    Args:
        story_context: 当前故事上下文
        interaction_type: 互动类型
        interaction_prompt: 互动问题
        user_input: 用户回答
        current_segment_count: 当前已有段落数（续写前）
        total_interactions_used: 已使用的交互次数
    """
    # 计算剩余空间：最多8页，已有 current_segment_count 页
    remaining_segments = 8 - current_segment_count
    is_near_end = remaining_segments <= 3  # 剩余3页或更少就接近结尾
    is_last_interaction = total_interactions_used >= 2  # 已经2次或更多互动，不应再加互动
    
    progress_hint = ""
    if is_near_end or is_last_interaction:
        progress_hint = f"""
**故事进度提示（必须遵守）**：
- 当前故事已有 {current_segment_count} 页，最多只能再有 {remaining_segments} 页。
- 这是{'最后一次' if is_last_interaction else '接近尾声的'}互动，续写必须在 1-2 段内给出完整结局。
- 续写的最后一段必须是故事的完整结束（问题解决、角色成长、传递寓意），且不能有 interaction_point。
"""
    else:
        progress_hint = f"""
**故事进度提示**：当前故事已有 {current_segment_count} 页，最多8页。续写 1-2 段即可，不要一次续写太多。
"""
    
    user_content = f"""当前故事上下文：
{story_context}

互动类型：{interaction_type}
互动问题：{interaction_prompt}
孩子的回答：{user_input}
{progress_hint}
请先写一句热情鼓励的反馈（可提及孩子的回答），再续写1-2个段落。
**重要**：续写内容必须明确体现「孩子的回答」——例如孩子起的名字要在后文用来称呼角色，孩子的选择要成为后续情节（如选了去哪里、做了什么），让孩子明显感到自己的参与改变了故事。保持风格一致。只输出 JSON。"""
    settings = get_settings()
    client = AsyncOpenAI(
        base_url=settings.llm_api_base.rstrip("/"),
        api_key=settings.llm_api_key,
    )
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": CONTINUE_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.7,
    )
    raw = resp.choices[0].message.content or "{}"
    logger.debug(f"[LLM] 续写原始响应 (前200字符): {raw[:200]}...")
    
    raw = _normalize_json(raw)
    logger.debug(f"[LLM] 续写清洗后 (前200字符): {raw[:200]}...")
    
    data = _parse_json_with_retry(raw)
    logger.info(f"[LLM] ✅ 续写 JSON 解析成功")
    
    return _parse_continue(data)
