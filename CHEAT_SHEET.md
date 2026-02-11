# 🚀 快速参考手册

## 一键修复

```bash
cd ~/interactive-storybook
git pull
bash deploy-fix.sh && bash fix-docker-env.sh
```

---

## 📊 快速诊断

```bash
# 运行完整测试
bash test-jimeng-api.sh

# 检查关键状态
docker ps | grep jimeng                                          # 容器运行？
docker exec interactive-storybook-jimeng env | grep SESSION     # 环境变量？
curl -X POST http://localhost:1002/token/check \                # Token 有效？
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_SESSION_ID"}'
```

---

## 🔧 常用命令

### 容器管理

```bash
# 重启容器
docker restart interactive-storybook-jimeng

# 查看日志
docker logs -f interactive-storybook-jimeng

# 查看最近 50 行
docker logs --tail 50 interactive-storybook-jimeng

# 进入容器
docker exec -it interactive-storybook-jimeng sh

# 重建容器
cd ~/interactive-storybook
docker-compose down
docker-compose up -d
```

### 服务管理

```bash
# 重启所有服务
cd ~/interactive-storybook
bash restart.sh

# 查看进程
ps aux | grep -E "uvicorn|next|node" | grep -v grep

# 查看端口
netstat -tlnp | grep -E "1000|1001|1002"
```

### Token 管理

```bash
# 检查 Token
curl -X POST http://localhost:1002/token/check \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_SESSION_ID"}'

# 查看积分
curl -X POST http://localhost:1002/token/points \
  -H "Authorization: Bearer YOUR_SESSION_ID"

# 签到领积分
curl -X POST http://localhost:1002/token/receive \
  -H "Authorization: Bearer YOUR_SESSION_ID"

# 更新 SessionID
bash update-sessionid.sh
```

---

## 🐛 常见错误

| 错误 | 诊断 | 修复 |
|------|------|------|
| **502 Bad Gateway** | `docker exec ... env \| grep SESSION` | `bash fix-docker-env.sh` |
| **Token 无效** | `curl .../token/check` | `bash update-sessionid.sh` |
| **SOCKS proxy 错误** | `pip3 list \| grep httpx` | `bash deploy-fix.sh` |
| **容器未运行** | `docker ps \| grep jimeng` | `docker-compose up -d` |
| **端口冲突** | `lsof -i :1002` | 修改 docker-compose.yml 端口 |

---

## 📍 关键检查点

### ✅ 修复后必须验证

```bash
# 1. 环境变量已传递
docker exec interactive-storybook-jimeng env | grep SESSION
# 期望：JIMENG_SESSION_ID=xxx

# 2. Token 有效
curl -X POST http://localhost:1002/token/check \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_SESSION_ID"}'
# 期望：{"live":true}

# 3. 文生图测试成功
curl -X POST http://localhost:1002/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  -d '{"prompt":"猫","model":"jimeng-4.5","ratio":"1:1","resolution":"1k"}'
# 期望：HTTP 200 + JSON with URL
```

---

## 📂 重要文件

| 文件 | 用途 |
|------|------|
| `.env` | 环境变量配置（包含 SessionID） |
| `docker-compose.yml` | Docker 服务配置 |
| `backend/requirements.txt` | Python 依赖 |
| `logs/backend.log` | 后端日志 |

---

## 🔗 快速链接

| 资源 | 链接 |
|------|------|
| jimeng-api 官方文档 | https://github.com/iptag/jimeng-api |
| 即梦官网 | https://jimeng.jianying.com/ |
| 前端页面 | https://story.ai-knowledgepoints.cn |

---

## 📝 修复脚本

| 脚本 | 用途 | 使用场景 |
|------|------|----------|
| `deploy-fix.sh` | 修复 OpenAI 客户端 | SOCKS/httpx 错误 |
| `fix-docker-env.sh` | 修复 Docker 环境变量 | 502 错误 |
| `test-jimeng-api.sh` | 完整测试 | 验证所有功能 |
| `fix-jimeng.sh` | 通用故障排查 | 图片生成失败 |
| `update-sessionid.sh` | 更新 SessionID | Token 过期 |
| `restart.sh` | 重启服务 | 日常重启 |

---

## 💡 最佳实践

1. **修复前先诊断**：`bash test-jimeng-api.sh`
2. **修复后必验证**：检查环境变量、Token、API
3. **定期检查 Token**：每周一次
4. **监控日志**：`tail -f logs/backend.log`
5. **备份配置**：修改前备份 `.env` 和 `docker-compose.yml`

---

## ⚡ 紧急恢复

如果服务完全无法使用：

```bash
cd ~/interactive-storybook

# 1. 停止所有服务
docker-compose down
pkill -f "uvicorn.*1001"
pkill -f "next dev -p 1000"

# 2. 更新代码
git pull

# 3. 重新部署
bash deploy-fix.sh
bash fix-docker-env.sh

# 4. 验证
bash test-jimeng-api.sh
```

---

## 📞 获取帮助

查看详细文档：

- `README_FIXES.md` - 快速开始（2分钟）
- `ECS_DEPLOYMENT_FIXES.md` - 完整修复汇总
- `JIMENG_API_GUIDE.md` - jimeng-api 使用指南
- `FINAL_FIX.md` - 问题定位与解决
- `QUICK_FIX_GUIDE.md` - 3分钟快速修复
