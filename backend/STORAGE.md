# 故事数据存储说明

## 📦 存储架构

### 当前实现：内存 + 文件持久化

| 数据类型 | 存储位置 | 格式 | 持久化 |
|---------|---------|------|--------|
| 故事数据 | `data/stories/{story_id}.json` | JSON | ✅ 是 |
| 故事索引 | `data/stories/_index.json` | JSON数组 | ✅ 是 |
| 用户信息 | `data/users/{hash}.json` | JSON | ✅ 是 |
| 登录token | `data/tokens.json` | JSON | ✅ 是 |
| 压缩图片 | `data/images/{hash}.jpg` | JPEG | ✅ 是 |

---

## 🔄 工作流程

### 1. 应用启动
```
uvicorn app.main:app
  ↓
lifespan 启动事件
  ↓
load_stories_from_disk()
  ↓
从 data/stories/ 加载所有 .json 文件
  ↓
内存中重建 _stories 和 _story_order
```

### 2. 用户生成故事
```
POST /api/story/start
  ↓
生成故事大纲和插画
  ↓
save_story(state)
  ├─ 保存到内存: _stories[story_id] = state
  ├─ 更新索引: _story_order.append(story_id)
  ├─ 写入文件: data/stories/{story_id}.json
  └─ 写入索引: data/stories/_index.json
```

### 3. 用户刷新浏览器
```
浏览器刷新
  ↓
前端重新加载
  ↓
GET /api/story/list (获取画廊)
  ↓
后端从内存返回故事列表
  ↓
用户点击某个故事
  ↓
GET /api/story/{story_id}
  ↓
后端返回完整故事数据（含当前进度）
  ↓
前端恢复到之前的阅读位置
```

### 4. 后端重启
```
服务重启
  ↓
load_stories_from_disk()
  ↓
所有故事从文件恢复到内存
  ↓
画廊数据完好无损 ✅
```

---

## 📁 文件格式示例

### 故事文件：`data/stories/abc123de.json`
```json
{
  "id": "abc123de",
  "title": "小兔子的冒险",
  "theme": "勇气与友谊",
  "characters": [
    {
      "name": "小白",
      "species": "兔子",
      "trait": "勇敢善良",
      "appearance": "white fluffy rabbit with blue eyes"
    }
  ],
  "setting": {
    "location": "森林",
    "time": "春天的早晨",
    "weather": "晴朗",
    "visual_description": "sunny forest with flowers"
  },
  "segments": [
    {
      "id": "0",
      "text": "在一个春天的早晨...",
      "scene_description": "rabbit in sunny forest",
      "emotion": "warm",
      "interaction_point": null,
      "image_url": "http://localhost:1001/static/images/abc123.jpg"
    }
  ],
  "current_index": 0,
  "status": "narrating"
}
```

### 索引文件：`data/stories/_index.json`
```json
["story_id_1", "story_id_2", "story_id_3"]
```
（按创建时间顺序，新的在后）

---

## ✅ 优势

1. **持久化存储**：后端重启不丢失数据
2. **断点续看**：用户刷新浏览器能继续观看
3. **简单可靠**：无需数据库，文件系统存储
4. **易于备份**：直接复制 `data/` 目录
5. **易于调试**：JSON 格式可直接查看编辑
6. **性能优化**：内存缓存 + 文件持久化

---

## 🚀 扩展方向

### 短期优化
- [ ] 添加文件锁（防止并发写入冲突）
- [ ] 定期清理过期故事（如 30 天未访问）
- [ ] 故事数据压缩（减小文件大小）

### 长期优化（生产环境）
- [ ] 迁移到数据库（PostgreSQL/MongoDB）
- [ ] 添加用户关联（每个用户有自己的画廊）
- [ ] Redis 缓存热门故事
- [ ] CDN 托管图片资源
- [ ] 分布式存储（如 OSS/S3）

---

## 📊 数据迁移

如需迁移到数据库：

```python
# 从文件导入到数据库
from pathlib import Path
import json

for file in Path("data/stories").glob("*.json"):
    if file.name == "_index.json":
        continue
    data = json.loads(file.read_text())
    story = Story(**data)
    db.session.add(story)
db.session.commit()
```

---

## 🔧 维护命令

```bash
# 查看所有故事
ls data/stories/*.json | wc -l

# 清理某个故事
rm data/stories/abc123de.json

# 重建索引（如果损坏）
python -c "
from app.utils.store import STORIES_DIR, INDEX_FILE
import json
ids = [f.stem for f in STORIES_DIR.glob('*.json') if f.name != '_index.json']
INDEX_FILE.write_text(json.dumps(ids))
"

# 备份所有数据
tar -czf backup_$(date +%Y%m%d).tar.gz data/
```
