# 双服务架构 + 缓存优化设计方案

**日期**: 2026-02-11
**目标**: 实现付费/免费用户差异化服务，优化缓存和预加载策略

---

## 1. 业务需求

### 用户分级服务
- **未登录用户**: 本地服务（jimeng-api + edge-tts）
- **免费用户**: 本地服务（jimeng-api + edge-tts）
- **付费用户**: 官方 API（火山即梦 + 火山 TTS）

### 性能优化目标
- ✅ 最小化用户等待时间
- ✅ 缓存优先，避免重复生成
- ✅ 智能预加载已知内容
- ✅ 日志清晰，便于排查

---

## 2. 技术架构

### 2.1 服务选择逻辑

```python
def get_service_tier(user: dict | None) -> Literal["free", "premium"]:
    """
    根据用户信息返回服务等级
    - None 或 is_paid=False → "free" (本地服务)
    - is_paid=True → "premium" (官方 API)
    """
```

### 2.2 图片生成服务

#### 本地服务 (jimeng-api)
- **当前实现**: `jimeng_service.py::generate_image()`
- **接口**: POST `{JIMENG_API_BASE_URL}/v1/images/generations`
- **认证**: Bearer {JIMENG_SESSION_ID}
- **保持现有逻辑**: 压缩、缓存等

#### 官方服务 (火山即梦)
- **新实现**: `volcano_image_service.py::generate_image_volcano()`
- **SDK**: `volcengine.visual.VisualService`
- **认证**: AK/SK (从 .env 读取)
- **流程**:
  1. 提交任务 (cv_sync2async_submit_task)
  2. 轮询结果 (cv_sync2async_get_result)
  3. 压缩保存

### 2.3 TTS 服务

#### 本地服务 (edge-tts)
- **当前实现**: `tts_service.py::generate_tts_audio()`
- **保持现有逻辑**: 缓存、重试等

#### 官方服务 (火山 TTS)
- **新实现**: `volcano_tts_service.py::generate_tts_volcano()`
- **协议**: WebSocket
- **认证**: appid + access_token (从 .env 读取)
- **基于**: `apis/tts/binary.py` 逻辑

---

## 3. 配置设计

### .env 新增配置

```bash
# ========== 火山引擎官方 API（付费用户） ==========
# 火山即梦官方 API 配置
VOLCANO_JIMENG_AK=your_access_key_here
VOLCANO_JIMENG_SK=your_secret_key_here

# 火山 TTS 官方 API 配置
VOLCANO_TTS_APPID=your_app_id_here
VOLCANO_TTS_ACCESS_TOKEN=your_access_token_here
VOLCANO_TTS_ENDPOINT=wss://openspeech.bytedance.com/api/v1/tts/ws_binary
```

### config.py 更新

```python
class Settings(BaseSettings):
    # 火山即梦官方 API
    volcano_jimeng_ak: str = ""
    volcano_jimeng_sk: str = ""

    # 火山 TTS 官方 API
    volcano_tts_appid: str = ""
    volcano_tts_access_token: str = ""
    volcano_tts_endpoint: str = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"
```

---

## 4. 缓存优化策略

### 4.1 图片缓存

**问题**: 当前基于 URL hash 缓存，不同故事相同场景会重复生成

**优化方案**: 基于 prompt + style_id hash 缓存

```python
def get_image_cache_key(prompt: str, style_id: str) -> str:
    """生成图片缓存键"""
    content = f"{prompt}|{style_id}"
    return hashlib.md5(content.encode()).hexdigest()[:16]

async def generate_image_with_cache(prompt: str, style_id: str, user: dict | None) -> str:
    """
    1. 计算缓存键
    2. 检查本地缓存
    3. 如有缓存，直接返回
    4. 无缓存，根据用户等级调用对应服务
    5. 保存缓存
    """
```

### 4.2 TTS 缓存

**保持现有逻辑**: 基于 `story_id + segment_index + voice_id`

**原因**:
- 同一段落在不同故事中可能内容不同
- 当前缓存已经工作良好

### 4.3 预加载策略

#### 图片预加载
```python
# 场景 1: 无互动故事（页数固定）
# - 生成首图后，后台异步生成所有剩余图片
async def _generate_images_async(story_id, start_idx, end_idx, ...):
    """已实现，保持不变"""

# 场景 2: 有互动故事
# - 生成当前图后，预生成下一张
# - 已实现，保持不变
```

#### 音频预加载
```python
# 当前播放时预生成下一段
# 已在 story.py::get_segment_audio() 中实现
# 保持不变
```

---

## 5. 日志增强

### 日志格式

```python
# 图片生成
logger.info(f"[图片生成] 服务类型: {'官方API' if tier == 'premium' else '本地服务'}, 用户: {user_email or '未登录'}")
logger.info(f"[图片生成] 缓存检查: {'命中' if cached else '未命中'}, 缓存键: {cache_key}")
logger.info(f"[图片生成] ✅ 生成完成，耗时: {elapsed:.2f}s, 路径: {image_path}")

# TTS 生成
logger.info(f"[TTS生成] 服务类型: {'官方API' if tier == 'premium' else 'edge-tts'}, 用户: {user_email or '未登录'}")
logger.info(f"[TTS生成] 缓存检查: {'命中' if cached else '未命中'}, 缓存键: {cache_key}")
logger.info(f"[TTS生成] ✅ 生成完成，耗时: {elapsed:.2f}s, 路径: {audio_path}")
```

---

## 6. API 路由修改

### 需要传递用户信息的接口

1. **POST /api/story/start**
   - 已有: `current_user: dict = Depends(get_current_user)`
   - 修改: 改为 `get_current_user_optional`（允许未登录）
   - 传递给: `start_new_story(user=current_user)`

2. **POST /api/story/{story_id}/next**
   - 新增: `current_user = Depends(get_current_user_optional)`
   - 传递给: `go_next_segment(story_id, user=current_user)`

3. **POST /api/story/interact**
   - 新增: `current_user = Depends(get_current_user_optional)`
   - 传递给: `handle_interaction(req, user=current_user)`

4. **GET /api/story/{story_id}/segment/{segment_index}/audio**
   - 已有用户信息检查，保持不变

---

## 7. 实施步骤

### Phase 1: 配置和基础设施
1. 更新 .env.example 和 config.py
2. 创建服务选择工具函数 `utils/service_tier.py`
3. 创建日志工具函数 `utils/logger_utils.py`

### Phase 2: 官方 API 集成
1. 实现火山即梦服务 `services/volcano_image_service.py`
2. 实现火山 TTS 服务 `services/volcano_tts_service.py`
3. 单元测试验证连通性

### Phase 3: 缓存优化
1. 实现基于 prompt 的图片缓存
2. 优化缓存查询逻辑
3. 添加缓存统计日志

### Phase 4: 服务整合
1. 修改 `jimeng_service.py` 集成服务选择
2. 修改 `tts_service.py` 集成服务选择
3. 修改 `story_engine.py` 传递用户信息

### Phase 5: API 路由更新
1. 修改所有故事相关 API，传递用户信息
2. 更新依赖注入逻辑

### Phase 6: 测试和优化
1. 测试未登录/免费/付费用户流程
2. 验证缓存命中率
3. 性能对比测试
4. 日志验证

---

## 8. 风险和注意事项

### 风险
1. **官方 API 认证失败**: 需要确保 AK/SK/Token 配置正确
2. **火山 TTS WebSocket 稳定性**: 可能需要重连逻辑
3. **缓存键冲突**: Prompt 微小差异导致缓存未命中
4. **向后兼容**: 现有免费用户体验不能变差

### 注意事项
1. **降级策略**: 官方 API 失败时自动降级到本地服务
2. **配置验证**: 启动时检查配置完整性
3. **错误处理**: 详细的错误日志和用户提示
4. **性能监控**: 记录各服务响应时间

---

## 9. 预期效果

### 付费用户
- ⚡ 图片生成速度提升 2-3 倍
- ⚡ TTS 生成更稳定快速
- 📊 清晰的日志标识

### 免费用户
- ✅ 保持现有体验
- ✅ 享受缓存优化带来的加速

### 系统
- 📈 缓存命中率提升 30-50%
- 🔍 日志清晰，便于排查问题
- 🚀 整体性能提升
