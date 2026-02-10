# 视频生成功能说明

## 功能概述

为交互式故事书添加了完整的视频生成功能，可以将故事的所有图片串联成一个连贯的视频，支持异步生成和实时进度显示。

## 核心特性

### 1. 异步视频片段生成

- **智能预生成**：当用户浏览到第 N 段时，系统自动在后台生成第 (N-2) 到 (N-1) 段的视频片段
- **不阻塞交互**：视频生成完全异步，不影响用户继续浏览故事
- **资源优化**：提前生成视频片段，最终合成时速度更快

### 2. 基于即梦 API 的首尾帧视频生成

使用即梦 API 的视频生成功能（`/v1/videos/generations`），支持：

- 首尾帧图片输入
- 自定义视频时长
- 运动提示词（motion prompt）
- 情感连贯性（根据故事情感自动生成过渡效果）

### 3. 完整视频合成

- **视频拼接**：使用 `moviepy` 将所有视频片段按顺序合并
- **音频支持**：预留 TTS 音频接口（可选）
- **高质量输出**：H.264 编码，AAC 音频，24fps

### 4. 实时进度显示

- 生成状态追踪（生成片段、合并、添加音频）
- 进度百分比
- 已生成片段数 / 总片段数
- 错误提示

## 技术架构

### 后端（FastAPI）

```
backend/
├── app/
│   ├── services/
│   │   └── video_service.py      # 视频生成核心服务
│   ├── routers/
│   │   └── video.py               # 视频 API 路由
│   └── models/
│       └── story.py               # 添加 video_clips 字段
```

**主要 API**：

- `POST /api/video/generate` - 启动视频生成任务
- `GET /api/video/status/{story_id}` - 查询生成进度
- `GET /api/video/download/{story_id}` - 下载视频
- `GET /api/video/clips/{story_id}` - 查看已生成的片段

### 前端（Next.js + React）

```
frontend/src/
├── components/
│   └── VideoGenerator.tsx         # 视频生成组件
├── services/
│   └── api.ts                     # 视频 API 调用
└── components/
    └── StoryScreen.tsx            # 集成视频生成按钮
```

**主要功能**：

- 视频生成按钮（仅在故事完成后启用）
- 进度模态框
- 自动轮询状态更新
- 下载视频

## 工作流程

### 1. 异步片段生成（用户浏览时）

```
用户浏览故事 → 切换到第 3 段
  ↓
后台触发：生成第 1→2 段的视频片段
  ↓
视频片段 URL 保存到 story.video_clips
```

**实现位置**：`story_engine.py` 的 `go_next_segment()` 函数

```python
# 当到达第 3 段时，生成第 1->2 段的视频
if idx >= 2:
    prev_idx = idx - 2
    asyncio.create_task(_generate_video_clip_async(story_id, prev_idx))
```

### 2. 完整视频生成（故事完成后）

```
用户点击"生成视频" → 启动后台任务
  ↓
步骤 1: 生成所有缺失的视频片段
  - 遍历所有相邻段落对
  - 调用即梦 API 生成视频
  - 下载视频到临时目录
  ↓
步骤 2: 合并视频片段
  - 使用 moviepy 拼接所有片段
  ↓
步骤 3: 添加音频（可选）
  - TTS 生成语音
  - 合成到视频
  ↓
步骤 4: 输出最终视频
  - 保存到临时目录
  - 返回下载链接
```

### 3. 进度追踪

前端每 3 秒轮询一次状态：

```typescript
const statusData = await getVideoStatus(storyId);
// 返回：
// - status: generating_clips | merging | adding_audio | completed | failed
// - progress: 0-100
// - generated_clips / total_clips
// - video_url (完成后)
```

## 使用指南

### 后端安装依赖

```bash
cd backend
pip install -r requirements.txt
```

新增依赖：
- `moviepy>=1.0.3` - 视频处理
- `imageio>=2.31.0` - 图像处理
- `imageio-ffmpeg>=0.4.9` - FFmpeg 支持

### 前端使用

1. 用户完成整个故事
2. 点击右上角"生成视频"按钮
3. 等待进度条显示生成进度
4. 生成完成后点击"下载视频"

## 即梦 API 配置

### 图片生成 API（已实现）

```
POST {JIMENG_API_BASE_URL}/v1/images/generations
```

### 视频生成 API（新增）

```
POST {JIMENG_API_BASE_URL}/v1/videos/generations
Authorization: Bearer {JIMENG_SESSION_ID}

{
  "model": "jimeng-video-1.5",
  "start_image": "https://...",
  "end_image": "https://...",
  "duration": 3.0,
  "prompt": "smooth transition, cinematic camera movement"
}
```

**注意**：请确认即梦 API 是否支持视频生成功能。如果不支持，需要：

1. 使用其他视频生成服务（如 Runway、Pika）
2. 或者简化为图片幻灯片 + 转场效果

## 优化建议

### 1. 镜头连贯性

当前实现：根据故事情感（emotion）生成运动提示词

```python
motion_prompt = f"{current_seg.emotion} mood, {next_seg.emotion} transition, smooth cinematic movement"
```

可以进一步优化：
- 添加镜头运动方式（zoom in/out, pan left/right）
- 根据场景变化调整过渡速度
- 添加关键帧控制

### 2. 音频集成

当前状态：预留接口，未实现 TTS

建议接入：
- Azure TTS
- Google Cloud Text-to-Speech
- OpenAI TTS API
- 火山引擎 TTS

### 3. 性能优化

- 缓存已生成的视频片段
- 使用 CDN 加速视频下载
- 压缩视频文件大小
- 支持不同分辨率导出

### 4. 用户体验

- 添加视频预览功能
- 支持自定义视频时长
- 支持选择部分段落生成
- 添加字幕支持

## 故障排查

### 视频生成失败

1. **检查即梦 API 是否支持视频生成**
   ```bash
   curl -X POST {JIMENG_API_BASE_URL}/v1/videos/generations \
     -H "Authorization: Bearer {SESSION_ID}" \
     -H "Content-Type: application/json" \
     -d '{"model":"jimeng-video-1.5","start_image":"...","end_image":"..."}'
   ```

2. **检查依赖是否安装**
   ```bash
   python -c "import moviepy; print(moviepy.__version__)"
   ```

3. **查看后端日志**
   ```bash
   # 搜索 [视频服务] 相关日志
   tail -f logs/app.log | grep 视频服务
   ```

### 视频无法下载

- 检查临时目录权限
- 确认视频文件路径存在
- 查看 `/api/video/status/{story_id}` 返回的 `video_url`

### 进度卡住不动

- 检查后台任务是否崩溃
- 增加超时时间（目前 10 分钟）
- 查看即梦 API 请求是否超时

## 未来扩展

- [ ] 支持自定义视频模板
- [ ] 添加背景音乐
- [ ] 支持多语言字幕
- [ ] 社交媒体分享功能
- [ ] 视频编辑功能（裁剪、滤镜）
- [ ] 批量生成多个故事视频

## 常见问题

**Q: 即梦 API 不支持视频生成怎么办？**

A: 可以使用备选方案：
1. 使用 Runway Gen-2 / Gen-3 API
2. 使用 Pika Labs API
3. 简化为图片幻灯片（Ken Burns 效果）

**Q: 视频生成太慢怎么办？**

A: 优化策略：
1. 减少视频片段时长（3秒 → 2秒）
2. 降低分辨率（2K → 1K）
3. 使用更快的视频生成模型
4. 并行生成多个片段

**Q: 如何添加音频？**

A: 实现 `generate_tts_audio()` 函数：

```python
async def generate_tts_audio(text: str, output_path: str) -> str:
    # 调用 TTS API
    audio_data = await tts_api.synthesize(text)
    with open(output_path, "wb") as f:
        f.write(audio_data)
    return output_path
```

## 贡献者

如需帮助或反馈，请提 Issue 或 Pull Request。
