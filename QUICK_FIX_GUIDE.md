# 🚀 快速修复指南

## 问题现象

```
✅ LLM 调用成功（Moonshot API）
✅ 故事大纲生成成功
❌ 图片生成失败：502 Bad Gateway
```

## ⚠️ 最新发现！根本原因

**Docker 环境变量未传递** - 这是导致 502 错误的真正原因！

通过诊断发现：
- ✅ `.env` 文件中有 `JIMENG_SESSION_ID=e95b8014c19d0e8db73278f5ab76a297`
- ❌ 容器内部没有 `JIMENG_SESSION_ID` 环境变量
- **原因**：`docker-compose.yml` 缺少环境变量传递配置

## 次要原因

**SessionID 过期** - 如果环境变量配置正确后仍有问题，可能是 SessionID 过期（通常 7-30 天）

## 🔧 快速修复（3 分钟）

### 🌟 方案 0：修复 Docker 环境变量（必须先做！）

**这是根本问题，必须先修复！**

在 ECS 上执行：

```bash
cd ~/interactive-storybook

# 如果使用 Git，先拉取最新代码
git pull

# 运行修复脚本
bash fix-docker-env.sh
```

脚本会自动：
1. ✅ 检查 `.env` 配置
2. ✅ 备份 `docker-compose.yml`
3. ✅ 验证配置正确性
4. ✅ 重启 jimeng-api 容器
5. ✅ 验证环境变量已传递到容器
6. ✅ 测试服务是否正常
7. ✅ 重启后端服务

**修复后验证**：
```bash
# 确认环境变量已传递
docker exec interactive-storybook-jimeng env | grep SESSION
# 应该看到：JIMENG_SESSION_ID=你的sessionid
```

### 方案 1：通用故障排查脚本

如果方案 0 执行后仍有问题，运行：

```bash
cd ~/interactive-storybook
bash fix-jimeng.sh
```

脚本会自动：
1. 检查容器状态
2. 查看日志诊断问题
3. 重启服务
4. 测试服务是否恢复
5. 给出具体建议

### 方案 2：手动更新 SessionID

**Step 1: 获取新的 SessionID**

1. 打开浏览器，访问 https://jimeng.jianying.com/
2. 登录账号
3. 按 `F12` 打开开发者工具
4. `Application` → `Cookies` → 选择网站
5. 找到 `sessionid`，复制其值

**Step 2: 更新配置**

```bash
# 方法 A: 使用交互式脚本（推荐）
cd ~/interactive-storybook
bash update-sessionid.sh
# 按提示粘贴新的 SessionID

# 方法 B: 手动编辑（如果熟悉 vim/nano）
nano ~/interactive-storybook/.env
# 修改这一行：
# JIMENG_SESSION_ID=你的新sessionid
# 保存退出（Ctrl+X, Y, Enter）
```

**Step 3: 重启服务**

```bash
cd ~/interactive-storybook
docker restart interactive-storybook-jimeng
sleep 20  # 等待启动
bash restart.sh  # 重启后端
```

**Step 4: 验证**

```bash
curl http://localhost:1002/health
# 应该返回 200 OK
```

### 方案 3：简单重启（可能有效）

有时候只是临时故障，重启即可：

```bash
cd ~/interactive-storybook
docker restart interactive-storybook-jimeng
sleep 20
bash restart.sh
```

## 📊 诊断命令

```bash
# 查看容器状态
docker ps | grep jimeng

# 查看日志（最重要！）
docker logs --tail 50 interactive-storybook-jimeng

# 测试服务
curl http://localhost:1002/health

# 检查端口
netstat -tlnp | grep 1002
```

## ❓ 常见问题

### Q1: 重启后还是 502

**可能原因**：SessionID 确实过期了

**解决**：必须更新 SessionID（见方案 2）

### Q2: 容器启动失败

```bash
# 查看详细日志
docker logs interactive-storybook-jimeng

# 完全重建
cd ~/interactive-storybook
docker-compose down
docker-compose up -d
```

### Q3: 端口冲突

```bash
# 检查端口占用
lsof -i :1002

# 如果被占用，修改端口
# 编辑 docker-compose.yml，改为其他端口如 1003:5100
# 同时更新 .env 中的 JIMENG_API_BASE_URL=http://localhost:1003
```

### Q4: 想临时使用付费 API

编辑 `.env`，确保配置了火山即梦官方 API：

```env
VOLCANO_JIMENG_AK=your_ak
VOLCANO_JIMENG_SK=your_sk
VOLCANO_JIMENG_REQ_KEY=jimeng_t2i_v40
```

系统会根据用户等级自动选择合适的服务。

## 🎯 验证修复成功

1. **检查服务**：
   ```bash
   curl http://localhost:1002/health
   # 返回 200 OK
   ```

2. **测试故事生成**：
   - 访问前端页面
   - 点击"开始故事"
   - 应该能够正常生成带插图的故事

3. **查看日志**：
   ```bash
   tail -f ~/interactive-storybook/logs/backend.log
   # 应该看到 [图片生成] 成功的日志
   ```

## 📞 仍有问题？

如果上述方案都无效，请收集以下信息：

```bash
# 1. 容器状态
docker ps -a | grep jimeng

# 2. 完整日志
docker logs interactive-storybook-jimeng > /tmp/jimeng-logs.txt

# 3. 环境配置（去除敏感信息）
cat ~/interactive-storybook/.env | grep JIMENG | sed 's/=.*/=***/'

# 4. 系统资源
free -h
df -h
```

然后查看详细文档：`fix-jimeng-502.md`

## 📚 相关文档

- `fix-jimeng-502.md` - 详细的诊断和修复指南
- `FIX_SUMMARY.md` - OpenAI 客户端修复说明
- `deploy-fix.sh` - 部署后端依赖修复脚本
- `fix-jimeng.sh` - jimeng-api 自动修复脚本
- `update-sessionid.sh` - SessionID 更新脚本

## ⏱️ 预计修复时间

- 简单重启：1 分钟
- 更新 SessionID：3 分钟
- 完全重建容器：5 分钟

大多数情况下，更新 SessionID 即可解决问题。
