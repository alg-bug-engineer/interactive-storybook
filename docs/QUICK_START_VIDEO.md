# 视频生成功能快速开始

## 功能概述

本功能可以将交互式故事书的所有图片自动生成为连贯的视频，支持：

- ✅ **异步生成**：在用户浏览故事时后台自动生成视频片段
- ✅ **首尾帧过渡**：使用即梦 API 生成平滑的图片过渡动画
- ✅ **情感连贯**：根据故事情感自动调整镜头运动
- ✅ **实时进度**：前端实时显示生成进度
- ✅ **一键下载**：生成完成后直接下载 MP4 视频

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

新增依赖包括：
- `moviepy` - 视频处理
- `imageio` - 图像处理
- `imageio-ffmpeg` - FFmpeg 支持

### 2. 更新环境变量

编辑 `.env` 文件，确认以下配置：

```env
# 启用视频生成功能
ENABLE_VIDEO_GENERATION=true

# 视频输出目录（可选，默认 /tmp/storybook_videos）
VIDEO_OUTPUT_DIR=/tmp/storybook_videos
```

### 3. 启动服务

```bash
# 后端
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

# 前端
cd frontend
npm run dev
```

### 4. 使用流程

1. **创建故事**：在前端点击"开始新故事"
2. **浏览故事**：完整浏览故事的所有段落
   - 系统会在后台自动生成视频片段
   - 当浏览到第 N 段时，自动生成第 (N-2) 到 (N-1) 段的视频
3. **生成视频**：故事完成后，点击右上角"生成视频"按钮
4. **等待完成**：观察进度条，等待视频生成完成
5. **下载视频**：生成完成后点击"下载视频"按钮

## 工作原理

### 异步视频片段生成

```
用户浏览流程：
段落 0 → 段落 1 → 段落 2 → 段落 3 ...
                    ↓
                  后台生成：
                  片段 0→1
                              ↓
                            后台生成：
                            片段 1→2
```

**优势**：
- 不阻塞用户交互
- 提前生成片段，最终合成更快
- 充分利用等待时间

### 视频生成流程

```
1. 生成视频片段 (70%)
   └─ 遍历所有相邻段落
      └─ 调用即梦 API 生成视频
         └─ 下载视频到本地

2. 合并视频 (75-85%)
   └─ 使用 moviepy 拼接所有片段

3. 添加音频 (85-95%, 可选)
   └─ TTS 生成语音
      └─ 合成到视频

4. 输出视频 (100%)
   └─ 导出 MP4 文件
```

## API 使用示例

### 生成视频

```bash
curl -X POST http://localhost:8100/api/video/generate \
  -H "Content-Type: application/json" \
  -d '{
    "story_id": "abc123",
    "enable_audio": false
  }'
```

### 查询进度

```bash
curl http://localhost:8100/api/video/status/abc123
```

响应：

```json
{
  "story_id": "abc123",
  "status": "generating_clips",
  "progress": 45,
  "total_clips": 5,
  "generated_clips": 2,
  "video_url": null,
  "error": null
}
```

### 下载视频

```bash
curl -O http://localhost:8100/api/video/download/abc123
```

## 测试脚本

使用提供的测试脚本快速验证功能：

```bash
cd backend
python test_video_api.py
```

脚本会自动：
1. 创建测试故事
2. 浏览所有段落
3. 启动视频生成
4. 监控生成进度
5. 显示下载链接

## 配置说明

### 视频参数

在 `video_service.py` 中可以调整：

```python
# 视频片段时长（秒）
duration: float = 3.0

# 视频分辨率
resolution = "2k"  # 可选: 1k, 2k, 4k

# 帧率
fps = 24

# 编码参数
codec = "libx264"
audio_codec = "aac"
preset = "medium"
```

### 运动提示词

根据故事情感自动生成，可在 `video_service.py` 中自定义：

```python
motion_prompt = f"{current_seg.emotion} mood transition, smooth cinematic camera movement"
```

情感映射：
- `happy` → 温暖明亮的阳光过渡
- `excited` → 动态活力的镜头运动
- `mysterious` → 柔和神秘的雾气效果
- `warm` → 温馨舒适的氛围
- `tense` → 戏剧性的阴影对比

## 故障排查

### 问题：视频生成失败

**可能原因**：
1. 即梦 API 不支持视频生成
2. 图片 URL 失效
3. 依赖未安装

**解决方案**：

1. 检查即梦 API 是否支持视频：

```bash
curl -X POST http://localhost:5100/v1/videos/generations \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "jimeng-video-1.5",
    "start_image": "https://example.com/img1.jpg",
    "end_image": "https://example.com/img2.jpg",
    "duration": 3.0
  }'
```

2. 检查 moviepy 是否安装：

```bash
python -c "import moviepy; print('MoviePy installed:', moviepy.__version__)"
```

3. 查看后端日志：

```bash
# 搜索错误信息
tail -f logs/app.log | grep -E "(ERROR|视频服务)"
```

### 问题：视频无法下载

**检查项**：
1. 生成状态是否为 `completed`
2. `video_url` 是否有值
3. 文件是否存在

```bash
# 查询状态
curl http://localhost:8100/api/video/status/YOUR_STORY_ID

# 检查文件
ls -lh /tmp/storybook_videos/
```

### 问题：生成速度慢

**优化建议**：
1. 减少视频时长：`duration=2.0`
2. 降低分辨率：`resolution="1k"`
3. 减少段落数量
4. 使用更快的视频生成服务

## 替代方案

如果即梦 API 不支持视频生成，可以使用：

### 方案 1: Runway Gen-3

```python
# 替换 generate_video_clip() 函数
async def generate_video_clip_runway(start_image, end_image):
    url = "https://api.runwayml.com/v1/gen3/generations"
    headers = {"Authorization": f"Bearer {RUNWAY_API_KEY}"}
    payload = {
        "mode": "gen3a_turbo",
        "promptImage": start_image,
        "endImage": end_image,
    }
    # ...
```

### 方案 2: Pika Labs

```python
async def generate_video_clip_pika(start_image, end_image):
    # 使用 Pika API
    # ...
```

### 方案 3: 简化为幻灯片

如果不需要平滑过渡，可以直接使用图片生成幻灯片：

```python
def create_slideshow(images, output_path):
    clips = []
    for img_path in images:
        clip = ImageClip(img_path, duration=3)
        # 添加 Ken Burns 效果
        clip = clip.resize(lambda t: 1 + 0.05 * t)
        clips.append(clip)
    
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(output_path, fps=24)
```

## 高级功能

### 添加 TTS 音频

实现 `generate_tts_audio()` 函数：

```python
async def generate_tts_audio(text: str, output_path: str) -> str:
    # 使用 Azure TTS
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_KEY,
        region=AZURE_REGION
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config
    )
    synthesizer.speak_text_async(text).get()
    return output_path
```

### 自定义镜头运动

```python
# 在 generate_video_clip() 中添加更多控制
motion_prompts = {
    "zoom_in": "smooth zoom in, focus on center",
    "zoom_out": "gradual zoom out, reveal scene",
    "pan_left": "gentle pan left, cinematic movement",
    "pan_right": "smooth pan right, storytelling flow",
}
```

### 添加转场效果

```python
from moviepy.video.fx.all import fadein, fadeout

for i, clip in enumerate(clips):
    if i > 0:
        clip = clip.fadein(0.5)  # 淡入 0.5 秒
    if i < len(clips) - 1:
        clip = clip.fadeout(0.5)  # 淡出 0.5 秒
    clips[i] = clip
```

## 性能优化

### 并行生成片段

```python
# 同时生成多个片段
tasks = []
for i in range(len(segments) - 1):
    task = generate_video_clip(segments[i], segments[i+1])
    tasks.append(task)

results = await asyncio.gather(*tasks)
```

### 使用 GPU 加速

```python
# MoviePy 使用 GPU 编码
video.write_videofile(
    output_path,
    codec="h264_nvenc",  # NVIDIA GPU
    # codec="h264_amf",  # AMD GPU
    # codec="h264_qsv",  # Intel GPU
)
```

### 缓存策略

```python
# 缓存已生成的视频片段
import hashlib

def get_clip_cache_key(seg1, seg2):
    return hashlib.md5(f"{seg1.id}-{seg2.id}".encode()).hexdigest()

# 检查缓存
cache_key = get_clip_cache_key(current_seg, next_seg)
cached_url = redis.get(f"clip:{cache_key}")
if cached_url:
    return cached_url
```

## 部署建议

### 生产环境配置

```env
# 使用持久化存储
VIDEO_OUTPUT_DIR=/var/storybook/videos

# 启用 CDN
VIDEO_CDN_URL=https://cdn.example.com/videos

# 限制并发任务
MAX_CONCURRENT_VIDEO_TASKS=3
```

### Docker 部署

```dockerfile
FROM python:3.10-slim

# 安装 FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 创建视频输出目录
RUN mkdir -p /var/storybook/videos

VOLUME /var/storybook/videos
```

## 支持与反馈

遇到问题？请：
1. 查看 `VIDEO_FEATURE.md` 详细文档
2. 运行 `test_video_api.py` 测试脚本
3. 查看后端日志文件
4. 提交 Issue 或 Pull Request

祝你使用愉快！🎥✨
