# 优化总结

## 1. 图片压缩优化 ✅

### 问题
- 生成的图片是 2k 分辨率，文件较大，前端加载慢

### 解决方案
1. **降低生成分辨率**：从 `2k` 降为 `1k`
2. **自动压缩**：生成后自动压缩为 JPEG 格式
3. **智能缩放**：最大宽度限制为 1280px（保持 16:9 比例）
4. **质量优化**：JPEG 压缩质量 85（平衡质量与文件大小）

### 技术实现
- 新增依赖：`Pillow>=10.0.0`
- 新增函数：`compress_and_save_image()` - 下载、压缩、保存图片
- 图片存储：`data/images/` 目录（自动创建）
- 静态文件服务：`/static/images/` 路径访问压缩后的图片

### 效果
- **文件大小**：预计减少 60-80%
- **加载速度**：显著提升（特别是移动端）
- **兼容性**：支持 base64 和 URL 两种图片格式

---

## 2. 视频生成 Bug 修复 ✅

### 问题
```
'code': -2000, 'message': 'Params body.duration invalid'
```

### 原因分析
- 即梦视频 API 要求 `duration` 参数为**整数**（int），而不是浮点数（float）
- 之前传入的是 `3.0`（float），导致参数校验失败

### 解决方案
1. **修改参数类型**：`duration: float = 3.0` → `duration: int = 3`
2. **强制类型转换**：`duration_int = int(duration)` 确保传给 API 的是整数
3. **增强日志**：详细记录请求参数、响应数据、错误原因

### 新增调试日志
```python
- 请求 URL、模型、时长（含类型）
- 完整 payload
- 原始响应（前 1000 字符）
- 响应头信息
- JSON 解析过程
- 多种可能的响应结构提取尝试
- 详细的错误原因分析
```

### 可能的后续问题
如果仍然报错，可能的原因：
1. **图片 URL 格式**：需要确保图片 URL 可被即梦 API 访问
2. **异步任务**：API 可能返回任务 ID，需要轮询查询结果
3. **duration 范围**：可能有 1-10 秒等限制
4. **模型版本**：`jimeng-video-1.5` 是否正确

---

## 3. 代码改动文件

### 后端
1. **`backend/requirements.txt`**
   - 新增：`Pillow>=10.0.0`（图片处理）

2. **`backend/app/main.py`**
   - 新增：静态文件服务 `/static/images/`

3. **`backend/app/services/jimeng_service.py`**
   - 新增：`compress_and_save_image()` 函数
   - 修改：`generate_image()` 支持 compress 参数
   - 修改：`generate_story_illustration()` 启用压缩，降低分辨率

4. **`backend/app/services/video_service.py`**
   - 修改：`generate_video_clip()` duration 改为 int 类型
   - 增强：大量调试日志
   - 修改：调用处 `duration=3` (int)

### 前端
无需修改，自动适配

---

## 4. 使用说明

### 安装新依赖
```bash
cd backend
pip install -r requirements.txt
```

### 重启服务
```bash
# 后端
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 1001

# 前端（如果已在运行，无需重启）
cd frontend
npm run dev
```

### 测试验证
1. **图片压缩**：
   - 生成新故事
   - 检查 `backend/data/images/` 目录是否有 `.jpg` 文件
   - 前端图片加载是否更快
   - 浏览器Network查看图片大小

2. **视频生成**：
   - 完成一个故事
   - 点击"一键转视频"
   - 查看后端日志，确认详细的请求/响应信息
   - 如果仍有错误，根据日志分析具体原因

---

## 5. 注意事项

1. **图片存储**：
   - 压缩后的图片保存在 `backend/data/images/`
   - 建议添加到 `.gitignore`
   - 生产环境可迁移到 CDN 或 OSS

2. **静态文件路径**：
   - 开发环境：`http://localhost:1001/static/images/{filename}.jpg`
   - 生产环境：需修改 `jimeng_service.py` 中的 URL 拼接逻辑

3. **视频调试**：
   - 查看详细日志定位问题
   - 可能需要调整 duration 值（1-5 秒）
   - 确认图片 URL 可访问

4. **性能优化**：
   - 图片压缩是异步的，不会阻塞故事生成
   - 首次压缩后会缓存，相同图片不会重复压缩
   - 静态文件服务高效（FastAPI StaticFiles）

---

## 6. 后续优化建议

1. **CDN 集成**：将压缩后的图片上传到 CDN
2. **WebP 格式**：支持 WebP（更小的文件，更好的质量）
3. **渐进式加载**：生成缩略图用于快速预览
4. **视频异步任务**：实现轮询机制查询视频生成状态
5. **缓存策略**：对图片和视频添加 HTTP 缓存头
