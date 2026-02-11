# 修复 jimeng-api 502 错误

## 问题现象

- ✅ LLM 故事生成正常
- ❌ 图片生成失败：`502 Bad Gateway`
- Docker 容器显示 `healthy`，但实际无法响应请求

## 原因分析

502 错误通常由以下原因引起：

1. **容器内服务未启动**：Docker 健康检查可能配置不当，容器运行但服务未真正启动
2. **SessionID 失效**：即梦 API 的 SessionID 过期或无效
3. **端口映射问题**：容器内部端口 5100 到宿主机 1002 的映射异常
4. **内存/资源不足**：容器启动但因资源不足无法正常工作

## 诊断步骤

### 1. 检查容器日志（最重要）

```bash
docker logs --tail 100 interactive-storybook-jimeng
```

**查找关键信息**：
- ❌ 错误信息：`Error`, `Failed`, `Exception`
- ❌ SessionID 问题：`Invalid session`, `Authentication failed`
- ✅ 正常启动：`Server started`, `Listening on`

### 2. 检查容器内部端口

```bash
docker exec interactive-storybook-jimeng netstat -tlnp
# 或
docker exec interactive-storybook-jimeng ss -tlnp
```

**期望输出**：应该看到端口 5100 在 LISTEN 状态

### 3. 测试服务可访问性

```bash
# 测试健康检查端点
curl http://localhost:1002/health

# 测试 API 端点
curl -X POST http://localhost:1002/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test", "model": "jimeng-4.5"}'
```

### 4. 检查 SessionID 配置

```bash
# 查看容器环境变量
docker exec interactive-storybook-jimeng env | grep SESSION

# 查看 .env 文件中的配置
cat ~/interactive-storybook/.env | grep JIMENG_SESSION_ID
```

## 常见解决方案

### 方案 1: 重启 jimeng-api 容器（最快）

```bash
cd ~/interactive-storybook
docker-compose restart jimeng
# 或
docker restart interactive-storybook-jimeng

# 等待 10 秒让服务完全启动
sleep 10

# 检查日志
docker logs --tail 30 interactive-storybook-jimeng

# 测试服务
curl http://localhost:1002/health
```

### 方案 2: 更新 SessionID（如果过期）

SessionID 会过期，需要定期更新：

```bash
# 1. 访问 https://jimeng.jianying.com/ 或 https://www.dreamina.com/
# 2. 登录账号
# 3. 打开浏览器开发者工具（F12）
# 4. Application -> Cookies -> sessionid
# 5. 复制新的 sessionid 值

# 更新 .env 文件
cd ~/interactive-storybook
nano .env
# 修改 JIMENG_SESSION_ID=新的sessionid值

# 重启容器使其生效
docker-compose down
docker-compose up -d

# 检查启动状态
docker-compose logs -f jimeng
```

### 方案 3: 完全重建容器（如果问题持续）

```bash
cd ~/interactive-storybook

# 停止并删除容器
docker-compose down

# 拉取最新镜像
docker pull ghcr.io/iptag/jimeng-api:latest

# 重新启动
docker-compose up -d

# 查看启动日志
docker-compose logs -f jimeng
```

### 方案 4: 检查资源限制

```bash
# 查看容器资源使用
docker stats interactive-storybook-jimeng --no-stream

# 如果内存不足，编辑 docker-compose.yml 增加资源限制
cd ~/interactive-storybook
nano docker-compose.yml
```

在 `jimeng` 服务中添加：
```yaml
services:
  jimeng:
    # ... 其他配置 ...
    deploy:
      resources:
        limits:
          memory: 2G  # 增加内存限制
        reservations:
          memory: 1G
```

## 检查 docker-compose.yml 配置

确保配置正确：

```yaml
services:
  jimeng:
    container_name: interactive-storybook-jimeng
    image: ghcr.io/iptag/jimeng-api:latest
    ports:
      - "1002:5100"  # 确保端口映射正确
    environment:
      - JIMENG_SESSION_ID=${JIMENG_SESSION_ID}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5100/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## 快速修复脚本

创建自动化修复脚本：

```bash
cat > ~/fix-jimeng.sh << 'SCRIPT_EOF'
#!/bin/bash
set -e

echo "=========================================="
echo "修复 jimeng-api 502 错误"
echo "=========================================="

cd ~/interactive-storybook

echo -e "\n[1/5] 检查当前状态..."
docker logs --tail 20 interactive-storybook-jimeng

echo -e "\n[2/5] 重启容器..."
docker restart interactive-storybook-jimeng

echo -e "\n[3/5] 等待服务启动（30秒）..."
sleep 30

echo -e "\n[4/5] 检查启动日志..."
docker logs --tail 30 interactive-storybook-jimeng

echo -e "\n[5/5] 测试服务..."
if curl -f http://localhost:1002/health 2>/dev/null; then
    echo "✅ jimeng-api 服务正常"
else
    echo "❌ 服务仍有问题，请检查日志："
    echo "   docker logs interactive-storybook-jimeng"
    exit 1
fi

echo -e "\n=========================================="
echo "修复完成！"
echo "=========================================="
SCRIPT_EOF

chmod +x ~/fix-jimeng.sh
bash ~/fix-jimeng.sh
```

## 验证修复

修复后执行以下命令验证：

```bash
# 1. 容器状态
docker ps | grep jimeng

# 2. 服务健康检查
curl http://localhost:1002/health

# 3. 测试图片生成
curl -X POST http://localhost:1002/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a cute cat",
    "model": "jimeng-4.5",
    "size": "1024x1024"
  }'

# 4. 重启后端服务
cd ~/interactive-storybook
bash restart.sh

# 5. 测试完整流程
# 访问前端页面，尝试生成故事
```

## 常见问题

### Q1: 容器一直重启
**原因**：SessionID 无效或配置错误
**解决**：更新 SessionID（见方案 2）

### Q2: 端口已被占用
```bash
# 检查端口占用
netstat -tlnp | grep 1002
# 或
lsof -i :1002

# 如果被占用，修改 docker-compose.yml 中的端口映射
# 例如改为 "1003:5100"，同时更新 .env 中的 JIMENG_API_BASE_URL
```

### Q3: 镜像拉取失败
```bash
# 使用国内镜像源
docker pull ghcr.nju.edu.cn/iptag/jimeng-api:latest
# 然后重新标记
docker tag ghcr.nju.edu.cn/iptag/jimeng-api:latest ghcr.io/iptag/jimeng-api:latest
```

## 临时方案：使用火山即梦官方 API

如果本地服务问题持续，可以临时切换到付费 API：

```bash
# 编辑 .env，确保配置了火山即梦 API
cd ~/interactive-storybook
nano .env
```

确保有以下配置：
```env
VOLCANO_JIMENG_AK=your_access_key
VOLCANO_JIMENG_SK=your_secret_key
VOLCANO_JIMENG_REQ_KEY=jimeng_t2i_v40
```

系统会自动根据用户等级选择合适的服务。

## 调试模式

如果问题复杂，使用调试模式启动：

```bash
cd ~/interactive-storybook

# 停止后台容器
docker-compose down

# 前台启动，查看实时日志
docker-compose up jimeng

# 在另一个终端测试
curl http://localhost:1002/health
```

按 `Ctrl+C` 停止后，再用 `docker-compose up -d` 后台启动。
