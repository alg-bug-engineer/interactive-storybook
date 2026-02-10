# 音画同步解决方案

## 问题背景

### 当前限制
1. **视频片段时长**：即梦 API 只支持 5 秒或 10 秒的固定时长
2. **音频时长**：动态变化，取决于文本长度和语速（edge-tts 无时长限制）
3. **音画不匹配**：一个段落的音频可能是 3 秒、8 秒、15 秒或 20 秒，但视频只能是 5 或 10 秒

### 核心挑战
- **音频 < 5 秒**：视频会继续播放，出现静音
- **音频 5-10 秒**：可以使用 10 秒视频，但可能仍有不匹配
- **音频 > 10 秒**：视频会被截断，音频不完整

## 解决方案

### 策略：视频适配音频（优先保证音频完整性）

#### 1. 音频时长 ≤ 5 秒
**方案：视频慢放 + 循环**
- 如果音频 3 秒，视频 5 秒 → 视频慢放到 3 秒（速度 0.6x）
- 如果音频 4 秒，视频 5 秒 → 视频慢放到 4 秒（速度 0.8x）
- 如果音频正好 5 秒 → 使用 5 秒视频，无需调整

**实现**：
```python
if audio_duration <= 5:
    # 使用 5 秒视频，慢放到音频时长
    speed_factor = video_duration / audio_duration  # 例如 5/3 = 1.67
    video_clip = video_clip.fx(vfx.speedx, speed_factor)
```

#### 2. 音频时长 5-10 秒
**方案：使用 10 秒视频 + 慢放（如需要）**
- 如果音频 8 秒，视频 10 秒 → 视频慢放到 8 秒（速度 0.8x）
- 如果音频正好 10 秒 → 使用 10 秒视频，无需调整

**实现**：
```python
if 5 < audio_duration <= 10:
    # 使用 10 秒视频，慢放到音频时长
    speed_factor = 10 / audio_duration
    video_clip = video_clip.fx(vfx.speedx, speed_factor)
```

#### 3. 音频时长 > 10 秒
**方案：视频循环播放 + 最后一段慢放**

**子方案 A：视频循环（推荐）**
- 如果音频 15 秒，视频 10 秒 → 视频循环 1.5 次
- 如果音频 20 秒，视频 10 秒 → 视频循环 2 次
- 最后一段视频慢放到剩余时长

**实现**：
```python
if audio_duration > 10:
    # 计算需要循环几次
    loops_needed = int(audio_duration / 10)  # 例如 15/10 = 1
    remainder = audio_duration % 10  # 例如 15%10 = 5
    
    # 循环视频
    video_clips = [video_clip] * loops_needed
    
    # 如果有余数，添加最后一段慢放视频
    if remainder > 0:
        last_clip = video_clip.subclip(0, remainder)
        video_clips.append(last_clip)
    
    final_video = concatenate_videoclips(video_clips)
```

**子方案 B：音频倍速（备选）**
- 如果音频 20 秒，视频 10 秒 → 音频倍速到 10 秒（速度 2.0x）
- 优点：视频无需处理
- 缺点：语速过快可能影响体验

**子方案 C：音频分段（复杂）**
- 将长音频分成多段，每段对应一个视频片段
- 需要多个视频片段（但即梦 API 限制，只能生成 5/10 秒）

## 实现细节

### 1. 视频生成时选择合适时长

在生成视频片段时，根据预估音频时长选择：
- 预估音频 ≤ 5 秒 → 生成 5 秒视频
- 预估音频 5-10 秒 → 生成 10 秒视频
- 预估音频 > 10 秒 → 生成 10 秒视频（后续循环）

**预估音频时长**：
```python
# 根据文本长度估算（粗略）
# 中文：约 3-4 字/秒（正常语速）
# 英文：约 2-3 词/秒
estimated_duration = len(text) / 3.5  # 中文估算
```

### 2. 音频生成后精确匹配

实际音频生成后，获取真实时长，然后调整视频：
```python
from moviepy import AudioFileClip

audio_clip = AudioFileClip(audio_path)
actual_audio_duration = audio_clip.duration

# 根据实际时长调整视频
adjusted_video = adjust_video_to_audio(video_clip, actual_audio_duration)
```

### 3. 视频调整函数

```python
def adjust_video_to_audio(video_clip, audio_duration):
    """调整视频时长以匹配音频"""
    video_duration = video_clip.duration
    
    if audio_duration <= video_duration:
        # 音频更短：视频慢放
        speed_factor = video_duration / audio_duration
        return video_clip.fx(vfx.speedx, speed_factor).subclip(0, audio_duration)
    else:
        # 音频更长：视频循环
        loops = int(audio_duration / video_duration)
        remainder = audio_duration % video_duration
        
        clips = [video_clip] * loops
        if remainder > 0:
            last_clip = video_clip.subclip(0, remainder)
            clips.append(last_clip)
        
        return concatenate_videoclips(clips)
```

## 代码实现

### 改进的 `merge_videos_with_audio` 函数

```python
async def merge_videos_with_audio(
    video_clips: List[str],
    audio_clips: List[str],
    output_path: str,
    sync_strategy: str = "video_adapts_audio",  # "video_adapts_audio" | "audio_adapts_video"
) -> str:
    """
    合并视频片段并添加音频，支持音画同步
    
    Args:
        video_clips: 视频片段文件路径列表
        audio_clips: 音频片段文件路径列表
        output_path: 输出文件路径
        sync_strategy: 同步策略
            - "video_adapts_audio": 视频适配音频（推荐）
            - "audio_adapts_video": 音频适配视频
    """
    from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
    from moviepy.video.fx import speedx
    
    # 加载视频和音频
    video_objects = []
    audio_objects = []
    current_time = 0
    
    for i, (video_path, audio_path) in enumerate(zip(video_clips, audio_clips)):
        video_clip = VideoFileClip(video_path)
        
        if audio_path and os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            audio_duration = audio_clip.duration
            video_duration = video_clip.duration
            
            # 根据策略调整
            if sync_strategy == "video_adapts_audio":
                # 视频适配音频
                adjusted_video = adjust_video_to_audio(video_clip, audio_duration)
            else:
                # 音频适配视频（倍速或截断）
                adjusted_video = video_clip
                if audio_duration > video_duration:
                    # 音频倍速
                    speed_factor = audio_duration / video_duration
                    audio_clip = audio_clip.fx(speedx, speed_factor)
                elif audio_duration < video_duration:
                    # 音频添加静音
                    from moviepy import AudioClip
                    silence = AudioClip(lambda t: [0, 0], duration=video_duration - audio_duration)
                    audio_clip = CompositeAudioClip([audio_clip, silence.set_start(audio_duration)])
            
            adjusted_video = adjusted_video.set_start(current_time)
            audio_clip = audio_clip.set_start(current_time)
            
            video_objects.append(adjusted_video)
            audio_objects.append(audio_clip)
            current_time += adjusted_video.duration
        else:
            # 无音频，直接添加视频
            video_clip = video_clip.set_start(current_time)
            video_objects.append(video_clip)
            current_time += video_clip.duration
    
    # 合并视频和音频
    final_video = concatenate_videoclips(video_objects, method="compose")
    if audio_objects:
        final_audio = CompositeAudioClip(audio_objects)
        final_video = final_video.set_audio(final_audio)
    
    # 导出
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=24)
    
    # 释放资源
    final_video.close()
    for v in video_objects:
        v.close()
    for a in audio_objects:
        a.close()
    
    return output_path
```

## 关于"即梦 API 15 秒限制"的说明

根据代码分析，即梦 API 的实际情况是：
- **视频生成**：支持 5 秒或 10 秒（不是 15 秒）
- **音频生成**：edge-tts 无时长限制，可以生成任意时长的音频

如果即梦 API 确实支持 15 秒视频，可以：
1. 在 `submit_video_clip_request` 中添加 15 秒选项
2. 在 `adjust_video_to_audio` 中处理 15 秒的情况

## 推荐方案

**最佳实践：视频适配音频 + 智能时长选择**

1. **生成阶段**：
   - 根据文本长度预估音频时长
   - 选择 5 秒或 10 秒视频（如果支持 15 秒，也考虑）

2. **合成阶段**：
   - 获取实际音频时长
   - 视频慢放或循环以匹配音频
   - 优先保证音频完整性

3. **用户体验**：
   - 音频完整播放
   - 视频流畅过渡
   - 音画同步自然

## 注意事项

1. **视频慢放限制**：moviepy 的 `speedx` 可以慢放到 0.1x，但过慢可能影响观感
2. **视频循环**：循环时注意过渡自然，避免突兀
3. **音频倍速**：倍速过快（>1.5x）可能影响理解
4. **性能考虑**：视频处理需要时间，考虑异步处理
