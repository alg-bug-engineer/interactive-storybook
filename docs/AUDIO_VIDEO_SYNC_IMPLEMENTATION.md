# 音画同步功能实现总结

## 实现日期
2026-02-10

## 问题背景

### 核心挑战
1. **视频时长限制**：即梦 API 只支持 5 秒或 10 秒的固定视频时长
2. **音频时长动态**：TTS 生成的音频时长取决于文本长度，可能是 3 秒、8 秒、15 秒或 20 秒
3. **音画不匹配**：需要保证音频完整播放的同时，视频流畅过渡

### 用户需求
- 一个图片对应一段文案，然后进行镜头的合成
- 如何保证音画同步？
- 如果音频时长与视频时长不匹配，如何处理？

## 解决方案

### 策略：视频适配音频（优先保证音频完整性）

#### 1. 音频时长 ≤ 视频时长
**处理方式：视频慢放**
- 如果音频 3 秒，视频 5 秒 → 视频慢放到 3 秒（速度 0.6x）
- 如果音频 4 秒，视频 5 秒 → 视频慢放到 4 秒（速度 0.8x）
- 限制慢放速度在 0.3x - 2.0x 之间，避免过慢或过快

#### 2. 音频时长 > 视频时长
**处理方式：视频循环播放**
- 如果音频 15 秒，视频 10 秒 → 视频循环 1 次 + 最后 5 秒慢放
- 如果音频 20 秒，视频 10 秒 → 视频循环 2 次
- 最后一段视频慢放到剩余时长

## 代码实现

### 1. 新增辅助函数

#### `_estimate_audio_duration(text, chars_per_second=3.5)`
根据文本长度估算音频时长
- 中文：约 3-4 字/秒
- 用于在生成视频前选择合适的时长

#### `_choose_video_duration(estimated_audio_duration)`
根据预估音频时长选择视频时长
- ≤ 5 秒 → 选择 5 秒视频
- > 5 秒 → 选择 10 秒视频

#### `_adjust_video_to_audio(video_clip, audio_duration)`
调整视频时长以匹配音频时长
- 音频 ≤ 视频：视频慢放
- 音频 > 视频：视频循环 + 最后一段慢放

### 2. 改进的函数

#### `generate_tts_audio()`
- **之前**：空实现，只返回空字符串
- **现在**：调用 TTS 服务生成真实音频
- 集成 `app.services.tts_service.generate_tts_audio`

#### `merge_videos_with_audio()`
- **之前**：简单拼接，音频按顺序添加，不处理时长不匹配
- **现在**：
  - 支持 `sync_strategy` 参数（"video_adapts_audio" 或 "audio_adapts_video"）
  - 默认使用 "video_adapts_audio" 策略
  - 自动调整每个视频片段以匹配对应音频
  - 详细的日志记录

#### `generate_story_video()`
- **改进**：
  - 根据文本预估音频时长
  - 选择合适的视频时长（5秒或10秒）
  - 调用改进的 `merge_videos_with_audio` 函数

## 使用示例

### 基本使用
```python
# 生成故事视频，自动处理音画同步
result = await generate_story_video(
    story_id="story_123",
    segments=segments,
    title="我的故事",
    enable_audio=True,
)
```

### 自定义同步策略
```python
# 使用视频适配音频策略（推荐）
await merge_videos_with_audio(
    video_clips=["clip1.mp4", "clip2.mp4"],
    audio_clips=["audio1.mp3", "audio2.mp3"],
    output_path="output.mp4",
    sync_strategy="video_adapts_audio",  # 视频适配音频
)

# 使用音频适配视频策略（备选）
await merge_videos_with_audio(
    video_clips=["clip1.mp4", "clip2.mp4"],
    audio_clips=["audio1.mp3", "audio2.mp3"],
    output_path="output.mp4",
    sync_strategy="audio_adapts_video",  # 音频倍速或截断
)
```

## 技术细节

### 视频慢放实现
```python
from moviepy.video.fx import speedx

speed_factor = video_duration / audio_duration
adjusted_video = video_clip.fx(speedx, speed_factor).subclip(0, audio_duration)
```

### 视频循环实现
```python
from moviepy import concatenate_videoclips

loops = int(audio_duration / video_duration)
remainder = audio_duration % video_duration

clips = [video_clip] * loops
if remainder > 0:
    last_clip = video_clip.fx(speedx, speed_factor).subclip(0, remainder)
    clips.append(last_clip)

final_video = concatenate_videoclips(clips)
```

## 关于"即梦 API 15 秒限制"的说明

根据代码分析，实际情况是：
- **视频生成**：即梦 API 支持 5 秒或 10 秒（不是 15 秒）
- **音频生成**：edge-tts 无时长限制，可以生成任意时长的音频

如果即梦 API 未来支持 15 秒视频，可以：
1. 在 `_choose_video_duration()` 中添加 15 秒选项
2. 在 `submit_video_clip_request()` 中支持 15 秒参数
3. 在 `_adjust_video_to_audio()` 中处理 15 秒的情况

## 优势

1. **音频完整性**：优先保证音频完整播放，不被截断
2. **视频流畅性**：通过慢放和循环，视频过渡自然
3. **自动化**：无需手动计算，系统自动处理
4. **灵活性**：支持两种同步策略，可根据需求选择

## 注意事项

1. **视频慢放限制**：moviepy 的 `speedx` 可以慢放到 0.3x，但过慢可能影响观感
2. **视频循环**：循环时注意过渡自然，避免突兀
3. **性能考虑**：视频处理需要时间，考虑异步处理
4. **音频倍速**：如果使用 "audio_adapts_video" 策略，倍速过快（>1.5x）可能影响理解

## 测试建议

1. **短音频测试**：3-4 秒音频 + 5 秒视频 → 验证慢放
2. **中等音频测试**：8 秒音频 + 10 秒视频 → 验证慢放
3. **长音频测试**：15-20 秒音频 + 10 秒视频 → 验证循环
4. **无音频测试**：验证无音频时的视频拼接

## 后续优化方向

1. **智能时长选择**：根据文本内容更精确地预估音频时长
2. **过渡效果**：视频循环时添加淡入淡出效果
3. **缓存优化**：缓存已生成的音频，避免重复生成
4. **并行处理**：视频和音频并行生成，提高效率
