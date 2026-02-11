# 互动故事书 ECS 部署指南

## 📋 前置条件

1. **域名解析已配置**
   - 确保 `story.ai-knowledgepoints.cn` 已解析到 ECS 公网 IP: `8.149.232.39`
   - 可以在本地测试: `ping story.ai-knowledgepoints.cn`

2. **端口已开放**
   - ECS 安全组需要开放端口: 80, 443, 1000-1010 (内部服务)

## 🚀 快速部署

### 第一步: 登录 ECS 并进入项目目录

```bash
ssh root@8.149.232.39
cd ~/interactive-storybook
```

### 第二步: 确保服务运行

**前端 (端口 1000):**
```bash
cd ~/interactive-storybook/frontend
npm install  # 如果是首次部署
nohup npm run dev > ../logs/frontend.log 2>&1 &
```

**后端 (端口 1001):**
```bash
cd ~/interactive-storybook/backend
pip install -r requirements.txt  # 如果是首次部署
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &
```

**即梦 API (端口 1002):**
```bash
# 如果使用了 jimeng-api Docker 服务
docker run -d -p 1002:3000 --name jimeng-api jimeng-api
```

### 第三步: 部署 Nginx 配置

```bash
cd ~/interactive-storybook
sudo bash deploy-to-ecs.sh
```

或者手动执行:

```bash
# 1. 复制配置文件
sudo cp nginx/storybook.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/storybook.conf /etc/nginx/sites-enabled/

# 2. 申请 SSL 证书 (首次需要)
sudo certbot --nginx -d story.ai-knowledgepoints.cn

# 3. 测试并重载 Nginx
sudo nginx -t
sudo systemctl reload nginx
```

### 第四步: 验证访问

```bash
# 测试本地服务
curl http://localhost:1000
curl http://localhost:1001/api

# 测试域名访问 (从本地电脑)
curl https://story.ai-knowledgepoints.cn
```

## 🔧 服务管理

### 查看日志

```bash
# 前端日志
tail -f ~/interactive-storybook/logs/frontend.log

# 后端日志
tail -f ~/interactive-storybook/logs/backend.log

# Nginx 访问日志
sudo tail -f /var/log/nginx/storybook-access.log

# Nginx 错误日志
sudo tail -f /var/log/nginx/storybook-error.log
```

### 重启服务

```bash
# 重启前端
pkill -f "next dev -p 1000"
cd ~/interactive-storybook/frontend
nohup npm run dev > ../logs/frontend.log 2>&1 &

# 重启后端
pkill -f "uvicorn.*1001"
cd ~/interactive-storybook/backend
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &

# 重启 Nginx
sudo systemctl restart nginx
```

### 设置开机自启

创建 systemd 服务文件:

```bash
# 前端服务
sudo tee /etc/systemd/system/storybook-frontend.service << 'EOF'
[Unit]
Description=Storybook Frontend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/interactive-storybook/frontend
ExecStart=/usr/bin/npm run dev
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 后端服务
sudo tee /etc/systemd/system/storybook-backend.service << 'EOF'
[Unit]
Description=Storybook Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/interactive-storybook/backend
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 1001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable storybook-frontend
sudo systemctl enable storybook-backend
sudo systemctl start storybook-frontend
sudo systemctl start storybook-backend
```

## 🌐 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | https://story.ai-knowledgepoints.cn | 主访问地址 |
| 后端 API | https://story.ai-knowledgepoints.cn/api | API 代理 |
| 本地前端 | http://localhost:1000 | 本地调试 |
| 本地后端 | http://localhost:1001 | 本地 API |

## 🛠️ 故障排查

### 1. 502 Bad Gateway

检查服务是否运行:
```bash
curl http://localhost:1000
curl http://localhost:1001/api
```

### 2. SSL 证书问题

重新申请证书:
```bash
sudo certbot renew --force-renewal -d story.ai-knowledgepoints.cn
sudo systemctl reload nginx
```

### 3. 端口被占用

查找并结束进程:
```bash
sudo lsof -i :1000
sudo kill -9 <PID>
```

### 4. Nginx 配置错误

测试配置:
```bash
sudo nginx -t
```

## 📁 文件说明

```
interactive-storybook/
├── nginx/
│   └── storybook.conf      # Nginx 配置文件
├── deploy-to-ecs.sh        # 自动部署脚本
├── DEPLOY.md               # 本部署指南
├── frontend/               # Next.js 前端
├── backend/                # FastAPI 后端
└── logs/                   # 日志目录
```

## 🔒 安全建议

1. **修改默认端口**: 生产环境建议修改内部服务端口
2. **防火墙配置**: 只开放必要的端口
3. **环境变量**: 确保 `.env` 文件权限设置为 600
4. **定期更新**: 及时更新系统和依赖包
