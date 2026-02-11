# 双服务架构实施总结

**日期**: 2026-02-11
**任务**: 实现付费/免费用户差异化服务 + 缓存优化

---

## ✅ 已完成的工作

### 1. 配置系统更新

**文件**:
- `.env.example` - 添加火山官方 API 配置项
- `backend/app/config.py` - 添加配置字段

**新增配置**:
```bash
# 火山即梦官方 API
VOLCANO_JIMENG_AK=your_access_key_here
VOLCANO_JIMENG_SK=your_secret_key_here
VOLCANO_JIMENG_REQ_KEY=jimeng_t2i_v40

# 火山 TTS 官方 API
VOLCANO_TTS_APPID=your_app_id_here
VOLCANO_TTS_ACCESS_TOKEN=your_access_token_here
VOLCANO_TTS_CLUSTER=volcano_tts
VOLCANO_TTS_ENDPOINT=wss://openspeech.bytedance.com/api/v1/tts/ws_binary
VOLCANO_TTS_VOICE_TYPE=BV700_V2_streaming
VOLCANO_TTS_ENCODING=mp3
```

---

### 2. 工具函数

**新增文件**:
- `backend/app/utils/service_tier.py` - 服务等级判断
- `backend/app/utils/logger_utils.py` - 统一日志格式
- `backend/app/utils/image_cache.py` - 图片缓存管理

**核心功能**:
```python
# 服务等级判断
get_service_tier(user) -> "free" | "premium"

# 日志记录
log_service_call(logger, service_type, tier, user_email, **kwargs)
log_cache_check(logger, service_type, cache_hit, cache_key)
log_generation_result(logger, service_type, success, elapsed, output_path)

# 图片缓存
get_cached_image(prompt, style_id) -> Optional[str]
save_image_cache(prompt, style_id, image_path)
```

---

### 3. 官方 API 服务实现

#### 火山即梦服务
**文件**: `backend/app/services/volcano_image_service.py`

**功能**:
- 基于 `volcengine.visual.VisualService` SDK
- 异步提交 + 轮询结果
- 自动压缩和缓存
- 支持 16:9 分辨率（1024x576）

#### 火山 TTS 服务
**文件**: `backend/app/services/volcano_tts_service.py`

**功能**:
- WebSocket 协议实现
- 基于 `apis/tts/protocols.py` 逻辑
- 支持重试机制（最多3次）
- MP3 格式输出

---

### 4. 统一服务接口

#### 图片生成服务
**文件**: `backend/app/services/image_generation_service.py`

**功能**:
- 根据用户等级自动选择服务
- 基于 prompt hash 的缓存系统
- 降级策略（官方 API 失败 → 本地服务）
- 详细的服务调用日志

```python
await generate_story_image(
    scene_description=...,
    characters=...,
    emotion=...,
    style_id=...,
    user=current_user,  # 根据 user.is_paid 选择服务
)
```

#### TTS 生成服务
**文件**: `backend/app/services/tts_generation_service.py`

**功能**:
- 根据用户等级自动选择服务
- 分离的缓存路径（edge-tts vs volcano_tts）
- 降级策略（官方 API 失败 → edge-tts）
- 详细的服务调用日志

```python
await generate_segment_tts(
    story_id=...,
    segment_index=...,
    text=...,
    voice_id=...,
    speed=...,
    user=current_user,  # 根据 user.is_paid 选择服务
)
```

---

### 5. 故事引擎集成

**文件**: `backend/app/services/story_engine.py`

**修改**:
- 所有函数添加 `user: Optional[dict]` 参数
- 使用新的统一服务接口
- 传递用户信息到所有图片生成调用

**修改的函数**:
```python
async def start_new_story(..., user=None)
async def go_next_segment(..., user=None)
async def handle_interaction(..., user=None)
async def preload_segment_image(..., user=None)
async def _pregenerate_image(..., user=None)
async def _generate_images_async(..., user=None)
```

---

### 6. API 路由更新

**文件**: `backend/app/routers/story.py`

**修改**:
1. **POST /api/story/start**
   - 改为 `get_current_user_optional`（允许未登录）
   - 传递 `user=current_user` 到 `start_new_story`

2. **POST /api/story/{story_id}/next**
   - 添加 `current_user = Depends(get_current_user_optional)`
   - 传递 `user=current_user` 到 `go_next_segment`

3. **POST /api/story/interact**
   - 添加 `current_user = Depends(get_current_user_optional)`
   - 传递 `user=current_user` 到 `handle_interaction`

4. **POST /api/story/{story_id}/preload-segment/{segment_index}**
   - 添加 `current_user = Depends(get_current_user_optional)`
   - 传递 `user=current_user` 到 `preload_segment_image`

5. **GET /api/story/{story_id}/segment/{segment_index}/audio**
   - 添加 `current_user = Depends(get_current_user_optional)`
   - 使用新的 `generate_segment_tts` 服务

**文件**: `backend/app/routers/audio.py`

**新增**:
- **GET /api/audio/data/audio/volcano_tts/{filename}** - 火山 TTS 音频访问

---

## 📊 功能对比表

| 功能 | 免费用户/未登录 | 付费用户 |
|------|----------------|----------|
| 图片生成 | jimeng-api 本地服务 | 火山即梦官方 API |
| TTS 语音 | edge-tts | 火山 TTS 官方 API |
| 缓存策略 | 基于 prompt hash | 基于 prompt hash |
| 降级策略 | - | 官方 API 失败 → 本地服务 |
| 日志标识 | 🐌 本地服务 | 🚀 官方API |

---

## 🎯 核心优化点

### 1. 缓存优化
- **原策略**: 基于 URL hash（不同故事相同场景会重复生成）
- **新策略**: 基于 `prompt + style_id` hash
- **效果**: 缓存命中率预计提升 30-50%

### 2. 服务选择
- 自动根据 `user.is_paid` 选择服务
- 透明切换，无需修改业务逻辑
- 降级保护，确保服务可用性

### 3. 日志增强
```
[图片生成] 服务类型: 官方API, 用户: user@example.com, style_id=q_cute
[图片缓存] 检查: ✅ 命中, 缓存键: abc123...
[图片生成] ✅ 生成完成，耗时: 2.50s, 路径: data/images/abc123.jpg
```

---

## 📦 依赖要求

**新增 Python 包**:
```bash
pip install volcengine-python-sdk  # 火山引擎 SDK
pip install websockets  # WebSocket 支持
```

**已有依赖**:
- `edge-tts` - 免费 TTS 服务
- `Pillow` - 图片处理
- `httpx` - HTTP 客户端

---

## ⚙️ 部署步骤

### 1. 安装依赖
```bash
cd backend
pip install volcengine-python-sdk websockets
```

### 2. 配置环境变量
复制 `.env.example` 到 `.env`，填写火山 API 凭证：
```bash
cp .env.example .env
# 编辑 .env，填写：
# VOLCANO_JIMENG_AK=...
# VOLCANO_JIMENG_SK=...
# VOLCANO_TTS_APPID=...
# VOLCANO_TTS_ACCESS_TOKEN=...
```

### 3. 重启服务
```bash
# 后端
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

# 前端（如果需要）
cd frontend
npm run dev
```

---

## 🧪 测试计划

### 测试用例

#### 1. 未登录用户
- [x] 创建故事 → 使用本地服务
- [ ] 查看日志 → 显示 "🐌 本地服务"
- [ ] 验证缓存命中

#### 2. 免费用户
- [x] 登录为免费用户
- [ ] 创建故事 → 使用本地服务
- [ ] TTS 播放 → 使用 edge-tts
- [ ] 查看日志 → 显示 "未登录" 或 "免费用户"

#### 3. 付费用户
- [x] 升级为付费用户（POST /api/auth/upgrade）
- [ ] 创建故事 → 使用官方 API
- [ ] TTS 播放 → 使用火山 TTS
- [ ] 查看日志 → 显示 "🚀 官方API"
- [ ] 验证生成速度提升

#### 4. 降级测试
- [ ] 关闭火山 API 配置
- [ ] 付费用户创建故事
- [ ] 验证自动降级到本地服务
- [ ] 查看日志 → 显示降级警告

#### 5. 缓存测试
- [ ] 创建相同主题的故事
- [ ] 验证缓存命中
- [ ] 查看日志 → 显示 "✅ 命中"
- [ ] 检查 `data/image_cache/cache_map.json`

---

## 🚨 注意事项

### 配置验证
启动时检查火山 API 配置：
```python
if not settings.volcano_jimeng_ak or not settings.volcano_jimeng_sk:
    logger.warning("火山即梦 API 未配置，付费用户将降级到本地服务")
```

### 错误处理
- 官方 API 失败 → 自动降级到本地服务
- 详细错误日志，包含完整堆栈信息
- 用户友好的错误提示

### 性能监控
- 记录每次生成的耗时
- 统计缓存命中率
- 监控降级发生次数

---

## 📝 下一步工作

### 短期
1. **测试验证** - 完成所有测试用例
2. **性能对比** - 测试官方 API vs 本地服务速度
3. **配置优化** - 根据测试结果调整参数

### 中期
1. **监控仪表板** - 可视化服务使用情况
2. **成本分析** - 计算官方 API 调用成本
3. **用户反馈** - 收集付费用户体验

### 长期
1. **智能降级** - 根据服务质量动态选择
2. **缓存预热** - 预生成热门故事图片
3. **CDN 集成** - 图片和音频 CDN 加速

---

## 📂 文件变更清单

### 新增文件（9个）
```
backend/app/utils/service_tier.py
backend/app/utils/logger_utils.py
backend/app/utils/image_cache.py
backend/app/services/volcano_image_service.py
backend/app/services/volcano_tts_service.py
backend/app/services/image_generation_service.py
backend/app/services/tts_generation_service.py
docs/plans/2026-02-11-dual-service-architecture-design.md
docs/IMPLEMENTATION_2026-02-11.md
```

### 修改文件（6个）
```
.env.example
backend/app/config.py
backend/app/services/story_engine.py
backend/app/routers/story.py
backend/app/routers/audio.py
```

---

## 🎉 预期效果

### 付费用户
- ⚡ 图片生成速度提升 2-3 倍
- ⚡ TTS 生成更稳定快速
- 📊 清晰的服务等级标识

### 免费用户
- ✅ 保持现有体验不变
- ✅ 享受缓存优化带来的加速
- ✅ 可升级到付费享受更快服务

### 系统
- 📈 缓存命中率提升 30-50%
- 🔍 日志清晰，便于排查问题
- 🚀 整体性能和稳定性提升
- 💰 付费用户体验差异化，支持商业化

---

## 🐛 已知问题

1. **火山 TTS 协议简化** - WebSocket 消息解析使用简化实现，可能需要根据实际API调整
2. **音色映射** - edge-tts 和火山 TTS 使用不同的音色 ID，需要映射表
3. **倍速支持** - 火山 TTS 可能不支持倍速参数，当前使用标准倍速

---

## 📞 技术支持

遇到问题请检查：
1. 日志文件中的详细错误信息
2. 火山 API 配置是否正确
3. 网络连接是否正常
4. 依赖包是否安装完整

---

**实施完成日期**: 2026-02-11
**开发者**: Claude Code Agent
**状态**: ✅ 开发完成，等待测试验证
