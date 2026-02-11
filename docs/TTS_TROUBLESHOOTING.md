# TTS 故障排除指南

## 问题：edge-tts 返回 403 错误

### 错误信息
```
WSServerHandshakeError: 403, message='Invalid response status'
url='wss://speech.platform.bing.com/...'
```

### 原因分析

1. **Microsoft 服务端更新**
   - Microsoft Edge TTS 服务可能更新了认证机制
   - edge-tts 库版本过旧

2. **请求频率限制**
   - 短时间内并发请求过多
   - 触发了 Microsoft 的限流机制

3. **网络环境**
   - 某些地区/网络可能限制访问 Microsoft 服务
   - 代理或防火墙阻止 WebSocket 连接

4. **临时服务中断**
   - Microsoft 服务偶尔会出现短暂不可用

---

## 解决方案

### 方案 1: 升级 edge-tts（推荐）

```bash
# 升级到最新版本
pip install --upgrade edge-tts

# 验证版本
pip show edge-tts

# 测试是否正常
python backend/test_tts.py
```

**预期版本**: >= 6.1.12 或更高

---

### 方案 2: 使用命令行测试

直接用 edge-tts 命令行工具测试：

```bash
# 列出可用音色
edge-tts --list-voices | grep "zh-CN"

# 生成测试音频
edge-tts --voice zh-CN-XiaoxiaoNeural --text "你好，这是一个测试" --write-media test.mp3

# 如果成功，会生成 test.mp3 文件
```

---

### 方案 3: 等待重试（已实现）

我已经在代码中添加了重试机制：
- 自动重试 3 次
- 指数退避延迟（2s, 4s, 8s）
- 避免并发请求触发限流

**操作**：无需操作，系统会自动重试。

---

### 方案 4: 使用国内镜像源

如果是网络问题，尝试切换 pip 源：

```bash
# 使用清华镜像
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple edge-tts --upgrade

# 或使用阿里云镜像
pip install -i https://mirrors.aliyun.com/pypi/simple edge-tts --upgrade
```

---

### 方案 5: 检查网络连接

```bash
# 测试能否访问 Microsoft 服务
curl -I https://speech.platform.bing.com

# 如果返回 403 或超时，说明网络受限
```

**解决办法**：
- 关闭代理/VPN
- 更换网络环境
- 联系网络管理员

---

### 方案 6: 备用 TTS 方案（终极方案）

如果 edge-tts 完全不可用，可以切换到其他 TTS 库：

#### 6.1 使用 gTTS（Google TTS）

**优点**：稳定、免费、无需认证
**缺点**：需要网络连接、音色选择少

```bash
pip install gtts
```

修改 `backend/app/services/tts_service.py`：
```python
from gtts import gTTS

async def generate_tts_audio_gtts(text: str, output_path: str) -> str:
    """使用 Google TTS 生成音频"""
    tts = gTTS(text=text, lang='zh-CN', slow=False)
    tts.save(output_path)
    return output_path
```

#### 6.2 使用 pyttsx3（离线 TTS）

**优点**：完全离线、无需网络
**缺点**：音质一般、音色选择少

```bash
pip install pyttsx3
```

```python
import pyttsx3

def generate_tts_audio_offline(text: str, output_path: str) -> str:
    """使用离线 TTS 生成音频"""
    engine = pyttsx3.init()
    engine.save_to_file(text, output_path)
    engine.runAndWait()
    return output_path
```

#### 6.3 使用商业 TTS API

如果对音质要求高，可以考虑：
- **阿里云 TTS**：https://www.aliyun.com/product/nls
- **腾讯云 TTS**：https://cloud.tencent.com/product/tts
- **百度 TTS**：https://ai.baidu.com/tech/speech/tts
- **讯飞 TTS**：https://www.xfyun.cn/services/online_tts

---

## 当前状态检查

### 检查 edge-tts 是否可用

```bash
cd backend
python test_tts.py
```

**预期输出**：
```
✅ edge-tts 已安装
🧪 测试 TTS 生成...
✅ 生成成功！文件大小: 12345 bytes
✅ TTS 服务正常
```

### 检查后端服务

访问：http://localhost:1001/api/voices/list

**预期响应**：
```json
{
  "voices": [...],
  "default_voice_id": "zh-CN-XiaoxiaoNeural",
  "tts_available": true
}
```

如果 `tts_available` 为 `false`，说明 edge-tts 未安装或有问题。

---

## 临时降级方案

如果音色系统暂时不可用，可以：

1. **使用浏览器内置 TTS**（已实现）
   - `useNarrator` hook 使用 Web Speech API
   - 无需后端支持
   - 音色选择受浏览器限制

2. **禁用音色选择功能**
   - 隐藏音色选择器
   - 只使用文字展示
   - 等待 TTS 服务恢复

3. **仅允许查看，不支持试听**
   - 显示音色列表
   - 不提供试听功能
   - 说明"音色试听暂时不可用"

---

## 常见问题

### Q1: 为什么启动时报 403 错误？
**A**: 启动时会预生成 3 个推荐音色的预览，如果 edge-tts 不可用会报错。这不影响主程序运行，音色会在首次试听时按需生成。

### Q2: 试听时一直加载怎么办？
**A**: 可能是 TTS 生成失败。检查：
1. 后端日志是否有错误
2. 运行 `python backend/test_tts.py` 测试
3. 尝试切换到其他音色

### Q3: 部分音色可用，部分不可用？
**A**: 可能是：
1. Microsoft 服务针对特定音色有限制
2. 网络不稳定导致随机失败
3. 建议使用成功率高的音色（如晓晓）

### Q4: 升级 edge-tts 后还是 403？
**A**: 
1. 等待 5-10 分钟再试（可能被临时限流）
2. 重启后端服务
3. 清除缓存：`rm -rf backend/data/audio/preview/*`
4. 考虑切换到备用 TTS 方案

---

## 监控与日志

### 查看 TTS 日志

后端日志会显示详细的 TTS 生成信息：

```
[TTS] 开始生成语音 (尝试 1/3): voice=zh-CN-XiaoxiaoNeural
[TTS] ✅ 语音生成成功
[TTS] ⚠️ 生成失败 (尝试 2/3): 403...
```

### 关键指标

- **成功率**: 应该 > 90%
- **生成时长**: 应该 < 5 秒
- **重试次数**: 应该 < 10%

如果这些指标异常，说明 TTS 服务不稳定。

---

## 联系支持

如果以上方案都无法解决问题：

1. 提供完整的错误日志
2. 说明网络环境（是否使用代理）
3. 说明 edge-tts 版本（`pip show edge-tts`）
4. 提供测试脚本的输出（`python backend/test_tts.py`）

---

**最后更新**: 2026-02-10  
**文档版本**: v1.0
