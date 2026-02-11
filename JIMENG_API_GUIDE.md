# jimeng-api 完整使用和排查指南

基于官方文档：https://github.com/iptag/jimeng-api

## 📋 目录

- [快速诊断](#快速诊断)
- [官方 API 端点](#官方-api-端点)
- [常见问题排查](#常见问题排查)
- [SessionID 管理](#sessionid-管理)
- [测试脚本](#测试脚本)

---

## 🚀 快速诊断

运行完整测试脚本：

```bash
cd ~/interactive-storybook
bash test-jimeng-api.sh
```

这个脚本会自动检查：
- ✅ Docker 容器状态
- ✅ 容器环境变量
- ✅ Token 有效性
- ✅ 积分余额
- ✅ 文生图 API
- ✅ 容器日志

---

## 📖 官方 API 端点

### 1. Token 检查

检查 SessionID 是否有效：

```bash
curl -X POST http://localhost:1002/token/check \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_SESSION_ID"}'
```

**成功响应**：
```json
{
  "live": true
}
```

**失败响应**：
```json
{
  "live": false
}
```

### 2. 获取积分信息

查询当前积分余额：

```bash
curl -X POST http://localhost:1002/token/points \
  -H "Authorization: Bearer YOUR_SESSION_ID"
```

**成功响应**：
```json
[
  {
    "token": "your_token",
    "points": {
      "giftCredit": 10,
      "purchaseCredit": 0,
      "vipCredit": 0,
      "totalCredit": 10
    }
  }
]
```

### 3. 每日签到（领取积分）

手动触发签到：

```bash
curl -X POST http://localhost:1002/token/receive \
  -H "Authorization: Bearer YOUR_SESSION_ID"
```

**成功响应**：
```json
[
  {
    "token": "your_token",
    "credits": {
      "giftCredit": 10,
      "purchaseCredit": 0,
      "vipCredit": 0,
      "totalCredit": 10
    },
    "received": true
  }
]
```

### 4. 文生图（Text-to-Image）

生成图片的核心 API：

```bash
curl -X POST http://localhost:1002/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  -d '{
    "model": "jimeng-4.5",
    "prompt": "一只可爱的小猫",
    "ratio": "1:1",
    "resolution": "2k"
  }'
```

**参数说明**：
- `model`: 模型名称（默认：`jimeng-4.5`）
- `prompt`: 图片描述文本
- `ratio`: 图片比例（`1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `3:2`, `2:3`, `21:9`）
- `resolution`: 分辨率（`1k`, `2k`, `4k`）

**支持的模型**：
- `jimeng-5.0` - 最新版本
- `jimeng-4.6` - v4.6
- `jimeng-4.5` - v4.5（默认，推荐）
- `jimeng-4.1` - v4.1
- `jimeng-4.0` - v4.0
- `jimeng-3.1` - v3.1
- `jimeng-3.0` - v3.0

**成功响应**：
```json
{
  "created": 1703123456,
  "data": [
    {
      "url": "https://example.com/image.webp"
    }
  ]
}
```

### 5. 图生图（Image-to-Image）

基于已有图片生成新图片：

```bash
# 使用本地图片
curl -X POST http://localhost:1002/v1/images/compositions \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  -F "prompt=一只可爱的猫，动漫风格" \
  -F "model=jimeng-4.5" \
  -F "ratio=1:1" \
  -F "resolution=2k" \
  -F "images=@/path/to/your/image.jpg"

# 使用网络图片
curl -X POST http://localhost:1002/v1/images/compositions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  -d '{
    "model": "jimeng-4.5",
    "prompt": "转换为油画风格",
    "images": ["https://example.com/image.jpg"],
    "ratio": "1:1",
    "resolution": "2k"
  }'
```

---

## 🔍 常见问题排查

### 问题 1: 502 Bad Gateway

**症状**：
```bash
curl http://localhost:1002/v1/images/generations
# 返回 502
```

**原因**：
1. **环境变量未传递**（最常见 - 90%）
2. SessionID 过期或无效
3. 即梦 API 服务异常

**诊断步骤**：

```bash
# 1. 检查容器环境变量（最重要！）
docker exec interactive-storybook-jimeng env | grep SESSION

# ✅ 正确输出：JIMENG_SESSION_ID=xxx
# ❌ 错误输出：（空）
```

如果输出为空，说明环境变量没有传递到容器，这是根本原因！

**解决方法**：

```bash
# 修复环境变量配置
bash fix-docker-env.sh
```

**验证修复**：

```bash
# 再次检查环境变量
docker exec interactive-storybook-jimeng env | grep SESSION
# 应该看到：JIMENG_SESSION_ID=你的sessionid

# 测试 Token
curl -X POST http://localhost:1002/token/check \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_SESSION_ID"}'
# 应该返回: {"live":true}
```

### 问题 2: Token 无效 (live: false)

**症状**：
```json
{
  "live": false
}
```

**原因**：SessionID 已过期（通常 7-30 天）

**解决方法**：

```bash
# 使用交互式脚本更新 SessionID
bash update-sessionid.sh
```

或手动更新：

1. 访问 https://jimeng.jianying.com/ 并登录
2. 按 F12，Application → Cookies → sessionid
3. 复制新的 sessionid
4. 编辑 .env 文件：
   ```bash
   nano ~/interactive-storybook/.env
   # 修改: JIMENG_SESSION_ID=新的sessionid
   ```
5. 重启容器：
   ```bash
   docker restart interactive-storybook-jimeng
   ```

### 问题 3: 积分不足

**症状**：
```json
{
  "error": "积分不足"
}
```

**解决方法**：

```bash
# 1. 查看当前积分
curl -X POST http://localhost:1002/token/points \
  -H "Authorization: Bearer YOUR_SESSION_ID"

# 2. 手动签到领取积分
curl -X POST http://localhost:1002/token/receive \
  -H "Authorization: Bearer YOUR_SESSION_ID"

# 3. 前往官网查看
# https://jimeng.jianying.com/
```

### 问题 4: 容器无法启动

**症状**：
```bash
docker ps | grep jimeng
# 没有输出
```

**诊断**：

```bash
# 查看容器状态（包括已停止的）
docker ps -a | grep jimeng

# 查看容器日志
docker logs interactive-storybook-jimeng
```

**解决方法**：

```bash
# 重新启动
cd ~/interactive-storybook
docker-compose up -d jimeng-api

# 或完全重建
docker-compose down
docker-compose up -d
```

### 问题 5: 端口冲突

**症状**：
```
Error: Port 1002 is already in use
```

**诊断**：

```bash
# 检查端口占用
lsof -i :1002
netstat -tlnp | grep 1002
```

**解决方法**：

方法 A：停止占用端口的进程
```bash
kill -9 <PID>
```

方法 B：修改映射端口
```bash
# 编辑 docker-compose.yml
nano ~/interactive-storybook/docker-compose.yml

# 修改端口映射（例如改为 1003:5100）
ports:
  - "1003:5100"

# 同时更新 .env 中的配置
nano ~/interactive-storybook/.env
# 修改: JIMENG_API_BASE_URL=http://localhost:1003

# 重启容器
docker-compose up -d jimeng-api
```

---

## 🔑 SessionID 管理

### 获取 SessionID

**国内站（即梦）和国际站（dreamina）方法相同**：

1. 访问网站并登录：
   - 国内站：https://jimeng.jianying.com/
   - 国际站（美国）：https://www.dreamina.com/

2. 按 F12 打开开发者工具

3. 切换到 **Application** 标签（或 **存储** 标签）

4. 左侧找到 **Cookies** → 选择网站

5. 在右侧找到 `sessionid` 或 `session_id`

6. 复制它的值（一长串字母数字）

### SessionID 格式

根据官方文档，Token 格式为：

```
[代理URL@][地区前缀-]session_id
```

**示例**：
- 国内站，无代理：`session_id_xxx`
- 美国站，无代理：`us-session_id_xxx`
- 香港站，无代理：`hk-session_id_xxx`
- 国内站 + SOCKS5代理：`socks5://127.0.0.1:1080@session_id_xxx`

**我们的项目使用国内站，所以直接使用 SessionID 即可。**

### 有效期

- SessionID 通常 7-30 天有效
- 过期后需要重新获取
- 建议定期检查：
  ```bash
  curl -X POST http://localhost:1002/token/check \
    -H "Content-Type: application/json" \
    -d '{"token": "YOUR_SESSION_ID"}'
  ```

---

## 🧪 测试脚本

### 完整测试脚本

```bash
cd ~/interactive-storybook
bash test-jimeng-api.sh
```

包含所有诊断步骤。

### 快速验证

```bash
# 1. 容器状态
docker ps | grep jimeng

# 2. 环境变量
docker exec interactive-storybook-jimeng env | grep SESSION

# 3. Token 检查
curl -X POST http://localhost:1002/token/check \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_SESSION_ID"}'

# 4. 简单图片生成测试
curl -X POST http://localhost:1002/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  -d '{
    "model": "jimeng-4.5",
    "prompt": "test",
    "ratio": "1:1",
    "resolution": "1k"
  }'
```

---

## 📊 监控和调试

### 实时日志

```bash
# 查看实时日志
docker logs -f interactive-storybook-jimeng

# 查看最近 100 行
docker logs --tail 100 interactive-storybook-jimeng
```

### 进入容器调试

```bash
docker exec -it interactive-storybook-jimeng sh

# 在容器内
env | grep SESSION  # 检查环境变量
netstat -tlnp       # 检查端口
ps aux              # 检查进程
```

### 容器资源使用

```bash
# 查看资源使用情况
docker stats interactive-storybook-jimeng --no-stream
```

---

## 🎯 最佳实践

### 1. 定期检查 Token

建议每周检查一次 Token 有效性：

```bash
curl -X POST http://localhost:1002/token/check \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_SESSION_ID"}'
```

### 2. 监控积分余额

在生成图片前检查积分：

```bash
curl -X POST http://localhost:1002/token/points \
  -H "Authorization: Bearer YOUR_SESSION_ID"
```

### 3. 自动签到

可以配置 cron 定时任务自动签到：

```bash
# 编辑 crontab
crontab -e

# 添加每天早上 8 点签到
0 8 * * * curl -X POST http://localhost:1002/token/receive -H "Authorization: Bearer YOUR_SESSION_ID" >> /tmp/jimeng-signin.log 2>&1
```

### 4. 使用合适的分辨率

- 开发测试：使用 `1k` 节省积分和时间
- 生产环境：使用 `2k`（默认）平衡质量和速度
- 高质量需求：使用 `4k`（消耗更多积分和时间）

### 5. 错误重试

官方 API 包含智能重试机制，但建议在应用层也添加重试逻辑。

---

## 🔗 相关链接

- **官方文档**: https://github.com/iptag/jimeng-api/blob/main/README.CN.md
- **Telegram 交流群**: https://t.me/jimeng_api
- **即梦官网（国内站）**: https://jimeng.jianying.com/
- **Dreamina（国际站）**: https://www.dreamina.com/

---

## 📝 更新记录

- **2026-02-11**: 基于官方文档创建完整指南
- 添加 Token 检查 API 说明
- 添加积分管理说明
- 添加详细的故障排查步骤
- 添加测试脚本

---

## 💡 提示

- 所有 API 端点都需要 `Authorization: Bearer YOUR_SESSION_ID` 头
- SessionID 是敏感信息，请妥善保管
- 建议在 `.gitignore` 中排除 `.env` 文件
- 高峰期生成可能需要排队，最长等待 30 分钟
- 使用 `1k` 分辨率可以更快获得结果，适合测试
