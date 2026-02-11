# 🚨 ECS 部署问题 - 立即修复

## ⚡ 快速开始（2分钟）

在你的 ECS 服务器上执行：

```bash
cd ~/interactive-storybook

# 如果使用 Git，先拉取最新代码
git pull

# 1. 修复 OpenAI 客户端问题（SOCKS 代理错误）
bash deploy-fix.sh

# 2. 修复 Docker 环境变量问题（502 错误的根本原因）
bash fix-docker-env.sh
```

就这么简单！两个脚本会自动完成所有修复和验证。

---

## 🔍 问题诊断结果

通过你提供的诊断信息，我们定位了 3 个问题：

### ✅ 问题 1 & 2: OpenAI 客户端错误（已修复）

**错误信息**:
```
Using SOCKS proxy, but the 'socksio' package is not installed
AttributeError: 'AsyncHttpxClientWrapper' object has no attribute '_mounts'
```

**修复**:
- ✅ 更新 `requirements.txt`: `httpx[socks]>=0.26.0`
- ✅ 优化 `llm_service.py`: 添加客户端生命周期管理

### ✅ 问题 3: Docker 环境变量未传递（已修复 - 最关键！）

**诊断发现**:
```bash
# ✅ .env 中有配置
JIMENG_SESSION_ID=e95b8014c19d0e8db73278f5ab76a297

# ❌ 但容器内没有这个变量
docker exec interactive-storybook-jimeng env | grep SESSION
(输出为空)
```

**根本原因**: `docker-compose.yml` 没有配置环境变量传递！

**修复**:
- ✅ 更新 `docker-compose.yml`: 添加 `environment` 配置
- ✅ 添加健康检查

---

## 📋 修复清单

| 修改的文件 | 改动内容 |
|-----------|---------|
| `backend/requirements.txt` | `httpx[socks]>=0.26.0` |
| `backend/app/services/llm_service.py` | 客户端生命周期管理 |
| `docker-compose.yml` | 添加环境变量传递 |

| 新增的脚本 | 用途 |
|-----------|------|
| `deploy-fix.sh` | 部署 OpenAI 客户端修复 |
| `fix-docker-env.sh` | 修复 Docker 环境变量 |
| `fix-jimeng.sh` | 通用故障排查 |
| `update-sessionid.sh` | 更新 SessionID |

---

## ✅ 验证修复

修复完成后，执行以下命令验证：

```bash
# 1. 检查 Python 依赖
pip3 list | grep -E "httpx|socksio"
# ✅ 应该看到 httpx 和 socksio

# 2. 检查 Docker 环境变量（最重要！）
docker exec interactive-storybook-jimeng env | grep SESSION
# ✅ 应该看到: JIMENG_SESSION_ID=e95b8014c19d0e8db73278f5ab76a297

# 3. 运行完整测试脚本（推荐）
bash test-jimeng-api.sh
# 这个脚本会测试所有 API 端点

# 4. 测试 Token 有效性（基于官方 API）
SESSION_ID=$(grep "JIMENG_SESSION_ID=" .env | cut -d'=' -f2)
curl -X POST http://localhost:1002/token/check \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$SESSION_ID\"}"
# ✅ 应该返回: {"live":true}

# 5. 测试文生图 API
curl -X POST http://localhost:1002/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SESSION_ID" \
  -d '{"prompt":"一只猫","model":"jimeng-4.5","ratio":"1:1","resolution":"1k"}'
# ✅ 应该返回包含图片 URL 的 JSON

# 6. 查看后端日志
tail -f ~/interactive-storybook/logs/backend.log
# ✅ 应该看到成功日志，没有 502 或 SOCKS 错误

# 7. 测试完整流程
# 访问 https://story.ai-knowledgepoints.cn
# 点击"开始故事"，应该能成功生成带插图的故事
```

---

## 🎯 预期结果

修复后的完整流程：

```
用户点击"开始故事"
  ↓
✅ LLM 调用成功（Moonshot API）
  ↓
✅ 生成故事大纲
  ↓
✅ 调用 jimeng-api 生成图片
  ↓
✅ jimeng-api 使用 SessionID 调用即梦 API
  ↓
✅ 返回图片 URL
  ↓
✅ 前端显示完整的故事和插图
```

**整个过程 10-30 秒，不再有 500/502 错误！**

---

## 📚 详细文档

如需了解更多细节或遇到其他问题，查看：

| 文档 | 内容 |
|------|------|
| `ECS_DEPLOYMENT_FIXES.md` | 📖 所有问题的汇总和修复方案 |
| `QUICK_FIX_GUIDE.md` | ⚡ 3分钟快速修复指南 |
| `FINAL_FIX.md` | 🔍 最新问题定位与完整修复方案 |
| `FIX_SUMMARY.md` | 🛠️ OpenAI 客户端修复详情 |
| `fix-jimeng-502.md` | 🐛 jimeng-api 502 错误详细诊断 |

---

## ❓ 常见问题

### Q: 修复后仍然 502？

可能是 SessionID 过期，运行：
```bash
bash update-sessionid.sh
```

### Q: 如何获取新的 SessionID？

1. 访问 https://jimeng.jianying.com/ 并登录
2. 按 F12，Application → Cookies → sessionid
3. 复制值，运行 `update-sessionid.sh` 并粘贴

### Q: 容器启动失败？

查看日志：
```bash
docker logs interactive-storybook-jimeng
```

### Q: 想要完全重建？

```bash
cd ~/interactive-storybook
docker-compose down
docker-compose up -d
bash restart.sh
```

---

## 💡 提示

- 所有脚本都有详细的输出和错误提示
- 脚本会自动备份配置文件
- 如果不确定，可以先查看脚本内容：`cat <脚本名>.sh`
- 所有修改都是向后兼容的，不会影响现有功能

---

## 🎉 开始修复

现在在你的 ECS 上执行：

```bash
cd ~/interactive-storybook
git pull
bash deploy-fix.sh
bash fix-docker-env.sh
```

然后访问你的网站测试故事生成功能！
