# 有声互动故事书

面向少儿的 AI 有声互动故事书：随机生成童话故事，即梦 AI 配图，语音朗读，关键节点文字互动。

## 技术栈

- **前端**: Next.js 14 + React 18 + Tailwind CSS + Framer Motion
- **后端**: FastAPI + Python 3.10+
- **即梦**: 方案 B — 开源 [jimeng-api](https://github.com/iptag/jimeng-api) 本地服务
- **故事生成**: OpenAI 兼容 API（如 OpenAI / 火山方舟 / 其他）

## 快速开始

### 1. 即梦 API（方案 B）

在项目根目录启动即梦转发服务（需先获取 sessionid）：

```bash
# 拉取并运行 jimeng-api
docker-compose up -d jimeng-api
# 服务地址: http://localhost:5100
```

获取 **sessionid**：浏览器登录 [即梦](https://jimeng.jianying.com) 或 [Dreamina](https://dreamina.capcut.com)，F12 → Application → Cookies → 复制 `sessionid`。

### 2. 环境变量

```bash
# 复制示例并填写
cp .env.example .env
```

必填项：

- `JIMENG_API_BASE_URL` — 即梦服务地址，默认 `http://localhost:5100`
- `JIMENG_SESSION_ID` — 即梦登录后的 sessionid
- `LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL` — 任选一个 OpenAI 兼容的 LLM（用于生成/续写故事）

后端会从 **项目根目录** 的 `.env` 读配置；若在 `backend/` 下运行，可再建 `backend/.env` 或先 `export` 根目录 `.env`。

### 3. 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

API 文档: http://localhost:8100/docs

### 4. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:3000

## 项目结构

```
interactive-storybook/
├── docker-compose.yml    # 即梦 jimeng-api 服务
├── .env.example
├── backend/              # FastAPI
│   ├── app/
│   │   ├── config.py
│   │   ├── main.py
│   │   ├── models/
│   │   ├── data/         # 主题/角色/场景池
│   │   ├── routers/      # story, video
│   │   ├── services/     # 即梦、LLM、故事引擎、视频生成
│   │   └── utils/
│   ├── requirements.txt
│   └── test_video_api.py # 视频功能测试脚本
└── frontend/             # Next.js
    └── src/
        ├── app/
        ├── components/   # 故事展示、插画、互动面板、语音、视频生成
        ├── hooks/
        ├── services/
        └── types/
```

## 主要 API

### 故事相关

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | `/api/story/start` | 开始新故事，返回首段与配图 |
| GET  | `/api/story/{id}`   | 获取故事状态与当前段 |
| POST | `/api/story/{id}/next` | 下一页 |
| POST | `/api/story/interact`  | 提交互动回答，续写并配图 |

### 视频生成（NEW）

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | `/api/video/generate` | 生成完整故事视频（异步） |
| GET  | `/api/video/status/{id}` | 查询视频生成进度 |
| GET  | `/api/video/download/{id}` | 下载生成的视频 |
| GET  | `/api/video/clips/{id}` | 查看已生成的视频片段 |

## 即梦方案 B 说明

- 使用 [iptag/jimeng-api](https://github.com/iptag/jimeng-api) 镜像，对接即梦/豆梦官网。
- 认证方式：请求头 `Authorization: Bearer <sessionid>`。
- 后端在 `app/services/jimeng_service.py` 中调用 `POST /v1/images/generations`，参数见该仓库文档。

## 新功能：视频生成 🎥

将完整故事自动生成为连贯视频，支持：

- ✅ **异步生成**：浏览故事时后台自动生成视频片段
- ✅ **首尾帧过渡**：基于即梦 API 的平滑图片过渡
- ✅ **实时进度**：前端显示生成进度和状态
- ✅ **一键下载**：生成完成后直接下载 MP4

**使用方法**：
1. 完整浏览故事到结束
2. 点击右上角"生成视频"按钮
3. 等待进度条完成
4. 下载视频

详细说明：[QUICK_START_VIDEO.md](./QUICK_START_VIDEO.md) | [VIDEO_FEATURE.md](./VIDEO_FEATURE.md)

## 常见问题

1. **前端代理失败 "socket hang up"**  
   ✅ 已修复：前端现在直接调用 `http://localhost:8100`，无需 rewrites。  
   - 确保后端正在运行：`curl http://localhost:8100/health`
   - 重启前端以应用新配置
   - 详见 `TROUBLESHOOTING.md`

2. **即梦返回 401**  
   检查 `JIMENG_SESSION_ID` 是否正确、是否过期，需重新登录获取。

3. **故事生成失败**  
   检查 `LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL` 是否配置正确且可访问。

4. **后端无法启动**  
   - 检查 Python 版本（需要 3.10+）
   - 确保依赖已安装：`pip install -r requirements.txt`
   - 检查 `.env` 文件是否存在且配置正确

5. **视频生成失败**
   - 确认即梦 API 是否支持视频生成
   - 检查 `moviepy` 是否安装：`pip install moviepy`
   - 查看后端日志中的错误信息
   - 参考 [QUICK_START_VIDEO.md](./QUICK_START_VIDEO.md) 故障排查部分
