# Bug 修复记录：TTS 403 错误和音频路径问题

## 日期
2026-02-10 14:15

## 问题描述

### 问题 1: edge-tts 403 错误
**症状：**
```
WSServerHandshakeError: 403, message='Invalid response status'
```

**原因：**
1. 启动时并发请求 3 个音色预览，触发 Microsoft TTS 服务限流
2. 缺少重试机制

### 问题 2: 音频文件 404 错误
**症状：**
```
GET /api/audio//api/audio/data/audio/preview/zh-CN-XiaoxiaoNeural.mp3 HTTP/1.1" 404 Not Found
```

**原因：**
- 后端返回：`/api/audio/data/audio/preview/xxx.mp3`
- 前端 `getAudioUrl()` 又拼接：`${API}/api/audio/${path}`
- 结果：路径重复

---

## 解决方案

### 修复 1: TTS 重试和限流避免

#### 1.1 添加重试机制
**文件：** `backend/app/services/tts_service.py`

**修改：** `generate_tts_audio()` 函数
- 新增 `max_retries` 参数（默认 3 次）
- 指数退避策略：2s, 4s, 8s
- 详细的错误日志

```python
async def generate_tts_audio(
    text: str,
    output_path: str,
    voice_id: str = DEFAULT_VOICE_ID,
    rate: str = "+0%",
    volume: str = "+0%",
    max_retries: int = 3,  # 新增
) -> str:
    # ... 重试逻辑
    for attempt in range(max_retries):
        try:
            # ... TTS 生成
            if attempt > 0:
                delay = 2 ** attempt  # 指数退避
                await asyncio.sleep(delay)
            # ...
        except Exception as e:
            last_error = e
            # ... 重试
```

#### 1.2 串行预生成 + 延迟
**文件：** `backend/app/services/tts_service.py`

**修改：** `pregenerate_all_previews()` 函数
- 从并发改为串行
- 每次生成后延迟 1 秒

```python
async def pregenerate_all_previews():
    # 从并发改为串行
    for voice in AVAILABLE_VOICES:
        if not voice.get("is_recommended"):
            continue
        
        await generate_preview_audio(voice["id"])  # 串行
        await asyncio.sleep(1)  # 延迟 1 秒
```

**效果：**
```
✅ 预生成成功：3/3 个音色
- 晓晓 (zh-CN-XiaoxiaoNeural) ✅
- 晓伊 (zh-CN-XiaoyiNeural) ✅
- 云健 (zh-CN-YunjianNeural) ✅
```

---

### 修复 2: 音频路径重复

#### 2.1 前端修改
**文件：** `frontend/src/components/VoiceSelector.tsx`

**修改前：**
```typescript
const data = await previewVoice(voiceId);
const audioUrl = getAudioUrl(data.audio_url);  // ❌ 重复拼接
```

**修改后：**
```typescript
const data = await previewVoice(voiceId);
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:1001";
const audioUrl = `${API}${data.audio_url}`;  // ✅ 直接拼接
```

**路径流程：**
```
后端返回: /api/audio/data/audio/preview/zh-CN-XiaoxiaoNeural.mp3
前端拼接: http://localhost:1001 + /api/audio/data/audio/preview/zh-CN-XiaoxiaoNeural.mp3
最终URL:  http://localhost:1001/api/audio/data/audio/preview/zh-CN-XiaoxiaoNeural.mp3 ✅
```

---

## 测试验证

### 后端测试
```bash
cd backend
python test_tts.py
```

**预期输出：**
```
✅ edge-tts 已安装
🧪 测试 TTS 生成...
✅ 生成成功！文件大小: 57168 bytes
```

### API 测试
```bash
# 1. 获取音色列表
curl http://localhost:1001/api/voices/list

# 2. 试听音色
curl http://localhost:1001/api/voices/preview/zh-CN-XiaoxiaoNeural

# 3. 访问音频文件
curl http://localhost:1001/api/audio/data/audio/preview/zh-CN-XiaoxiaoNeural.mp3 --output test.mp3
```

### 前端测试
1. 打开 http://localhost:1000
2. 点击右上角 🎙️ 按钮
3. 点击任意音色的"▶️ 试听"
4. ✅ 应该能听到预览音频

---

## 修改文件清单

### 后端（2 个文件）
1. `backend/app/services/tts_service.py`
   - 新增重试机制
   - 修改预生成策略（串行 + 延迟）
   
2. `backend/test_tts.py` - 新增
   - TTS 测试工具

### 前端（1 个文件）
1. `frontend/src/components/VoiceSelector.tsx`
   - 修复音频 URL 拼接

### 文档（1 个文件）
1. `docs/BUGFIX_TTS_403_AND_AUDIO_PATH.md` - 本文档

---

## 后续优化建议

### 短期（1-2 天）
1. ✅ 监控 TTS 成功率
2. ✅ 添加前端错误提示优化
3. ⏳ 考虑音频 CDN 缓存

### 中期（1-2 周）
1. ⏳ 备用 TTS 方案（如 gTTS、Azure TTS）
2. ⏳ 音频预加载策略优化
3. ⏳ 添加音频格式压缩（MP3 -> Opus）

### 长期（1 个月+）
1. ⏳ 自建 TTS 服务（避免外部依赖）
2. ⏳ 音色质量评分系统
3. ⏳ 用户自定义音色上传

---

## 相关文档
- [PRD: 音色系统产品需求](./PRD_VOICE_SYSTEM.md)
- [部署指南: 音色系统部署](./VOICE_SYSTEM_DEPLOYMENT.md)
- [完成总结: Phase 0-2](./PHASE_0-2_COMPLETION_SUMMARY.md)

---

**修复者**: AI Assistant  
**测试者**: 待测试  
**状态**: ✅ 已修复，待验证
