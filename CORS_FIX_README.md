# CORS 问题修复说明

## 问题原因

生产环境前端页面（`https://story.ai-knowledgepoints.cn`）在请求 API 时，使用了硬编码的 `http://localhost:1001`，导致：

1. **跨域问题**: 不同域名/协议触发浏览器 CORS 检查
2. **localhost 错误**: 浏览器会在访问者自己的电脑（而非 ECS 服务器）上找 1001 端口
3. **连接失败**: `ERR_CONNECTION_CLOSED` 因为用户电脑上没有运行后端服务

## 修复方案

### 核心改动

**前端使用相对路径 `/api/*`，通过 Nginx 反向代理到后端**

```
浏览器请求: https://story.ai-knowledgepoints.cn/api/story/list
    ↓
Nginx (443端口): 匹配 location /api/
    ↓
反向代理: proxy_pass http://127.0.0.1:1001/api/story/list
    ↓
后端服务 (1001端口): 处理请求并返回
```

### 修改的文件

#### 1. `frontend/src/services/api.ts`
- 简化 `getApiUrl()` 逻辑
- 浏览器端返回空字符串 `''`，让所有请求变成相对路径
- 服务端渲染时返回 `http://localhost:1001`（SSR 内部通信）

#### 2. `frontend/src/components/VoiceSelector.tsx`
- 移除硬编码的 `localhost:1001`
- 直接使用后端返回的 `audio_url`（相对路径）

#### 3. `frontend/src/components/StoryScreen.tsx`
- 移除硬编码的 `localhost:1001`
- 直接使用后端返回的 `audio_url`（相对路径）

### Nginx 配置（已存在，无需修改）

`nginx/storybook.conf` 已经配置了 `/api/` 的反向代理：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:1001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## 部署步骤

### 方式1: 使用自动化脚本（推荐）

```bash
# 在本地项目根目录执行
bash fix-cors-final.sh
```

脚本会自动：
1. 提交代码到 GitHub
2. SSH 到 ECS 拉取最新代码
3. 重启前后端服务
4. 显示服务状态和日志

### 方式2: 手动部署

#### Step 1: 本地提交代码

```bash
cd ~/interactive-storybook
git add .
git commit -m "修复 CORS 问题 - 使用相对路径 /api"
git push origin main
```

#### Step 2: ECS 上更新代码

```bash
ssh root@8.149.232.39
cd ~/interactive-storybook
git pull origin main
```

#### Step 3: 重启服务

```bash
# 停止旧服务
pkill -f "next dev"
pkill -f "uvicorn.*1001"

# 创建日志目录（如果不存在）
mkdir -p ~/interactive-storybook/logs

# 启动后端
cd ~/interactive-storybook/backend
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &

# 启动前端
cd ~/interactive-storybook/frontend
nohup npm run dev > ../logs/frontend.log 2>&1 &

# 检查服务状态
ps aux | grep -E "(next dev|uvicorn.*1001)" | grep -v grep
```

## 验证修复

### 1. 本地测试（可选）

```bash
cd ~/interactive-storybook/frontend
npm run dev
```

访问 `http://localhost:1000`，按 F12 打开 Network 标签，检查 API 请求：
- ✅ 正确: `/api/story/styles`
- ❌ 错误: `http://localhost:1001/api/story/styles`

### 2. 生产环境验证

1. 访问 `https://story.ai-knowledgepoints.cn`
2. 按 F12 打开开发者工具
3. 切换到 **Network** 标签
4. 刷新页面
5. 检查 API 请求：
   - ✅ **Request URL**: `https://story.ai-knowledgepoints.cn/api/story/styles`
   - ✅ **Status**: `200 OK`
   - ❌ **不应该看到**: `localhost` 或 `CORS error`

### 3. 查看服务日志

```bash
# 后端日志
ssh root@8.149.232.39
tail -f ~/interactive-storybook/logs/backend.log

# 前端日志
tail -f ~/interactive-storybook/logs/frontend.log
```

## 常见问题

### Q1: 前端页面仍然无法访问？

**检查 Nginx 状态:**
```bash
ssh root@8.149.232.39
sudo nginx -t                    # 检查配置
sudo systemctl status nginx      # 检查服务状态
sudo systemctl restart nginx     # 重启 Nginx
```

### Q2: API 请求返回 502 Bad Gateway？

**说明后端服务未启动，检查:**
```bash
ps aux | grep uvicorn
tail -50 ~/interactive-storybook/logs/backend.log
```

### Q3: 前端页面空白，但没有错误？

**检查前端服务:**
```bash
ps aux | grep "next dev"
tail -50 ~/interactive-storybook/logs/frontend.log
```

### Q4: 仍然看到 localhost:1001 的请求？

**清除浏览器缓存:**
- Chrome: Ctrl+Shift+Delete → 清除缓存的图片和文件
- 或使用无痕模式 (Ctrl+Shift+N)

## 回滚方案

如果修复后仍有问题，可以回滚到上一个版本：

```bash
cd ~/interactive-storybook
git log --oneline -5              # 查看最近的提交
git reset --hard HEAD~1           # 回滚到上一个提交
git push -f origin main           # 强制推送（慎用）

# 在 ECS 上也需要回滚
ssh root@8.149.232.39
cd ~/interactive-storybook
git fetch origin
git reset --hard origin/main
# 然后重启服务...
```

## 技术细节

### 为什么浏览器会拦截 localhost 请求？

1. **同源策略**: 浏览器要求协议+域名+端口完全相同
   - 页面: `https://story.ai-knowledgepoints.cn` (443)
   - API: `http://localhost:1001` (1001)
   - 结果: 跨域 ❌

2. **localhost 定义**: 永远指访问者自己的电脑
   - 用户在家里访问网站 → 浏览器在用户家里的电脑找 1001 端口
   - ECS 服务器的 1001 端口对用户不可见 → 连接失败

### 为什么相对路径可以解决？

使用相对路径 `/api/*` 后：
- 浏览器自动拼接为: `https://story.ai-knowledgepoints.cn/api/*`
- 请求到达 Nginx (443 端口)
- Nginx 根据配置转发到本地 1001 端口
- 对浏览器来说是同源请求，无 CORS 问题 ✅
- 实际请求到后端，功能正常 ✅

## 联系与反馈

如果遇到其他问题，请提供：
1. 浏览器控制台截图（F12 → Console 和 Network 标签）
2. 后端日志: `tail -50 ~/interactive-storybook/logs/backend.log`
3. 前端日志: `tail -50 ~/interactive-storybook/logs/frontend.log`
4. Nginx 错误日志: `tail -50 /var/log/nginx/storybook-error.log`
