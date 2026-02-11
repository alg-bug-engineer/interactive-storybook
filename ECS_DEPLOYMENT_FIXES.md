# ECS 部署问题修复汇总

本文档汇总了在 ECS 部署过程中遇到的所有问题及其修复方案。

## 📋 问题清单

| # | 问题 | 状态 | 影响 |
|---|------|------|------|
| 1 | SOCKS 代理依赖缺失 | ✅ 已修复 | LLM 调用失败 |
| 2 | AsyncHttpxClientWrapper 错误 | ✅ 已修复 | 后端 500 错误 |
| 3 | Docker 环境变量未传递 | ✅ 已修复 | 图片生成 502 错误 |

## 🔧 问题 1 & 2: OpenAI 客户端错误

### 问题现象

```
{"detail":"Using SOCKS proxy, but the 'socksio' package is not installed."}
AttributeError: 'AsyncHttpxClientWrapper' object has no attribute '_mounts'
```

### 根本原因

1. ECS 环境中配置了 SOCKS 代理
2. `httpx` 未安装 SOCKS 支持包
3. OpenAI 客户端生命周期管理不当

### 修复方案

**1. 更新 `backend/requirements.txt`**

```diff
- httpx>=0.26.0
+ httpx[socks]>=0.26.0
```

**2. 优化 `backend/app/services/llm_service.py`**

- ✅ 创建统一的客户端初始化函数
- ✅ 配置合理的超时参数
- ✅ 在 finally 块中正确关闭客户端

**3. 部署到 ECS**

```bash
cd ~/interactive-storybook
bash deploy-fix.sh
```

详见：`FIX_SUMMARY.md`

---

## 🐳 问题 3: Docker 环境变量未传递（最关键！）

### 问题现象

```
✅ LLM 调用成功
✅ 故事大纲生成成功
❌ 图片生成失败：502 Bad Gateway
```

### 诊断发现

```bash
# ✅ 容器内服务正常运行
docker exec interactive-storybook-jimeng netstat -tlnp
# 显示：tcp 0.0.0.0:5100 LISTEN

# ❌ 但容器内没有 SESSION 环境变量
docker exec interactive-storybook-jimeng env | grep SESSION
# 输出为空！

# ✅ .env 文件中有配置
cat .env | grep JIMENG_SESSION_ID
# 输出：JIMENG_SESSION_ID=e95b8014c19d0e8db73278f5ab76a297
```

### 根本原因

`docker-compose.yml` 中 `jimeng-api` 服务没有配置环境变量传递：

```yaml
jimeng-api:
  image: ghcr.io/iptag/jimeng-api:latest
  ports:
    - "1002:5100"
  # ❌ 缺少 environment 配置
```

导致 `.env` 文件中的 `JIMENG_SESSION_ID` 无法传递到容器内部！

### 修复方案

**1. 更新 `docker-compose.yml`**

```yaml
jimeng-api:
  image: ghcr.io/iptag/jimeng-api:latest
  container_name: interactive-storybook-jimeng
  ports:
    - "1002:5100"
  environment:  # ✅ 添加环境变量传递
    - JIMENG_SESSION_ID=${JIMENG_SESSION_ID}
  restart: unless-stopped
  healthcheck:  # ✅ 添加健康检查
    test: ["CMD", "curl", "-f", "http://localhost:5100/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

**2. 部署到 ECS**

```bash
cd ~/interactive-storybook

# 方法 A: 一键修复脚本（推荐）
bash fix-docker-env.sh

# 方法 B: 手动修复
git pull  # 拉取最新配置
docker-compose down jimeng-api
docker-compose up -d jimeng-api
sleep 30
bash restart.sh
```

**3. 验证修复**

```bash
# 最重要：检查环境变量是否传递
docker exec interactive-storybook-jimeng env | grep SESSION
# ✅ 应该看到：JIMENG_SESSION_ID=你的sessionid

# 测试服务
curl http://localhost:1002/health
# ✅ 应该返回 200 OK

# 测试 API
curl -X POST http://localhost:1002/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{"prompt":"test","model":"jimeng-4.5"}'
# ✅ 应该返回包含任务 ID 的 JSON
```

详见：`FINAL_FIX.md`

---

## 🚀 完整部署流程

### 1. 初次部署或更新代码

```bash
cd ~/interactive-storybook
git pull
```

### 2. 修复 OpenAI 客户端问题

```bash
bash deploy-fix.sh
```

这个脚本会：
- 安装 `httpx[socks]`
- 重启后端和前端服务

### 3. 修复 Docker 环境变量问题

```bash
bash fix-docker-env.sh
```

这个脚本会：
- 验证 `.env` 配置
- 更新 `docker-compose.yml`（如果需要）
- 重启 jimeng-api 容器
- 验证环境变量已传递
- 测试服务是否正常

### 4. 验证所有服务

```bash
# 检查进程
ps aux | grep -E "uvicorn|next|node"

# 检查端口
netstat -tlnp | grep -E "1000|1001|1002"

# 检查 Docker 容器
docker ps | grep jimeng

# 检查 jimeng 环境变量
docker exec interactive-storybook-jimeng env | grep SESSION

# 测试服务
curl http://localhost:1002/health
curl http://localhost:1001/health
curl http://localhost:1000
```

### 5. 测试完整流程

访问 https://story.ai-knowledgepoints.cn，尝试生成故事，应该能够：
- ✅ 成功生成故事大纲
- ✅ 成功生成配图
- ✅ 不再出现 500/502 错误

---

## 📚 脚本说明

| 脚本 | 用途 | 使用场景 |
|------|------|----------|
| `deploy-fix.sh` | 修复 OpenAI 客户端问题 | 首次部署或更新代码后 |
| `fix-docker-env.sh` | 修复 Docker 环境变量问题 | jimeng-api 返回 502 时 |
| `fix-jimeng.sh` | 通用 jimeng-api 故障排查 | 图片生成失败时 |
| `update-sessionid.sh` | 更新 SessionID | SessionID 过期时 |
| `restart.sh` | 重启所有服务 | 日常重启 |

---

## 🔍 故障排查流程

### Step 1: 确定问题类型

```bash
# 查看后端日志
tail -f ~/interactive-storybook/logs/backend.log
```

- 看到 `SOCKS proxy` 或 `_mounts` 错误 → 执行 `deploy-fix.sh`
- 看到 `502 Bad Gateway` → 执行 `fix-docker-env.sh`
- 看到 `Unauthorized` 或 `Invalid session` → 执行 `update-sessionid.sh`

### Step 2: 运行对应的修复脚本

```bash
cd ~/interactive-storybook
bash <对应的脚本>.sh
```

### Step 3: 验证修复

```bash
# 重新测试故事生成
# 查看日志确认无错误
tail -f ~/interactive-storybook/logs/backend.log
```

### Step 4: 如果仍有问题

查看详细文档：
- `QUICK_FIX_GUIDE.md` - 3分钟快速修复
- `FINAL_FIX.md` - 完整问题分析和解决方案
- `FIX_SUMMARY.md` - OpenAI 客户端修复详情
- `fix-jimeng-502.md` - jimeng-api 502 错误详细诊断

---

## 📊 修复前后对比

### 修复前

```
用户点击"开始故事"
  ↓
✅ LLM 生成故事大纲（成功）
  ↓
❌ 图片生成失败
  - SOCKS proxy 错误
  - _mounts 错误
  - 502 Bad Gateway
  ↓
❌ 返回 500 错误给前端
```

### 修复后

```
用户点击"开始故事"
  ↓
✅ LLM 生成故事大纲（成功）
  ↓
✅ 图片生成（成功）
  - httpx[socks] 已安装
  - 客户端正确管理
  - SessionID 正确传递
  ↓
✅ 返回完整故事给前端
```

---

## ⚡ 快速参考

### 常用命令

```bash
# 查看所有服务状态
docker ps && ps aux | grep -E "uvicorn|next" | grep -v grep

# 查看所有日志
tail -f ~/interactive-storybook/logs/*.log

# 重启所有服务
cd ~/interactive-storybook && bash restart.sh

# 查看 jimeng 容器日志
docker logs -f interactive-storybook-jimeng

# 测试 jimeng API
curl http://localhost:1002/health
```

### 关键检查点

1. ✅ `httpx[socks]` 已安装
   ```bash
   pip3 list | grep httpx
   # 应该看到 httpx 和 socksio
   ```

2. ✅ Docker 环境变量已传递
   ```bash
   docker exec interactive-storybook-jimeng env | grep SESSION
   # 应该看到 JIMENG_SESSION_ID=...
   ```

3. ✅ 所有服务正常运行
   ```bash
   curl http://localhost:1000  # 前端
   curl http://localhost:1001/health  # 后端
   curl http://localhost:1002/health  # jimeng-api
   ```

---

## 🎉 预期结果

所有修复完成后：

1. ✅ 后端服务稳定运行，无 SOCKS 或 _mounts 错误
2. ✅ jimeng-api 容器正确接收 SessionID 环境变量
3. ✅ 图片生成成功，返回图片 URL
4. ✅ 用户可以正常生成带插图的互动故事
5. ✅ 整个流程在 10-30 秒内完成

---

## 📞 获取帮助

如果按照以上步骤修复后仍有问题，请提供：

1. 完整的错误日志
   ```bash
   tail -100 ~/interactive-storybook/logs/backend.log > /tmp/backend-error.log
   docker logs interactive-storybook-jimeng > /tmp/jimeng-error.log
   ```

2. 环境信息
   ```bash
   python3 --version
   pip3 list | grep -E "httpx|openai|socksio"
   docker --version
   docker-compose --version
   ```

3. 配置信息（去除敏感数据）
   ```bash
   docker exec interactive-storybook-jimeng env | grep -v SESSION
   cat docker-compose.yml
   ```

所有详细文档都在项目根目录，以 `.md` 结尾。
