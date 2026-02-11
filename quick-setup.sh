#!/bin/bash
# 互动故事书 - ECS 快速配置脚本
# 使用方法: sudo bash quick-setup.sh

set -e

echo "=========================================="
echo "互动故事书 ECS 快速配置"
echo "=========================================="

# 创建日志目录
mkdir -p ~/interactive-storybook/logs

# ============================================================
# 1. 创建 Nginx 配置
# ============================================================
echo "[1/4] 创建 Nginx 配置..."

cat > /etc/nginx/sites-available/storybook.conf << 'EOF'
# --- HTTP: 80 端口 ---
server {
    listen 80;
    server_name story.ai-knowledgepoints.cn;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# --- HTTPS: 443 端口 ---
server {
    listen 443 ssl http2;
    server_name story.ai-knowledgepoints.cn;

    ssl_certificate /etc/letsencrypt/live/story.ai-knowledgepoints.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/story.ai-knowledgepoints.cn/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    access_log /var/log/nginx/storybook-access.log;
    error_log /var/log/nginx/storybook-error.log;

    client_max_body_size 100M;

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:1001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 前端 Next.js
    location / {
        proxy_pass http://127.0.0.1:1000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 静态资源缓存
    location /_next/static {
        proxy_pass http://127.0.0.1:1000;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }
}
EOF

# 启用配置
ln -sf /etc/nginx/sites-available/storybook.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# ============================================================
# 2. 申请 SSL 证书
# ============================================================
echo "[2/4] 检查并申请 SSL 证书..."

if [ ! -d "/etc/letsencrypt/live/story.ai-knowledgepoints.cn" ]; then
    # 先使用 HTTP 配置启动 Nginx
    cat > /tmp/http-only.conf << 'EOF'
server {
    listen 80;
    server_name story.ai-knowledgepoints.cn;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    location / {
        proxy_pass http://127.0.0.1:1000;
    }
}
EOF
    cp /tmp/http-only.conf /etc/nginx/sites-enabled/storybook.conf
    mkdir -p /var/www/html
    nginx -s reload 2>/dev/null || nginx
    
    # 申请证书
    certbot --nginx -d story.ai-knowledgepoints.cn --agree-tos --non-interactive --email admin@ai-knowledgepoints.cn || true
    
    # 恢复完整配置
    cp /etc/nginx/sites-available/storybook.conf /etc/nginx/sites-enabled/
else
    echo "SSL 证书已存在，跳过申请"
fi

# ============================================================
# 3. 测试并重载 Nginx
# ============================================================
echo "[3/4] 测试并重载 Nginx..."

if nginx -t; then
    systemctl reload nginx || systemctl start nginx
    echo "✓ Nginx 配置成功"
else
    echo "✗ Nginx 配置测试失败"
    exit 1
fi

# ============================================================
# 4. 验证服务
# ============================================================
echo "[4/4] 验证服务..."

echo ""
echo "服务状态:"
echo "---------"

# 检查前端
if curl -s http://localhost:1000 > /dev/null 2>&1; then
    echo "✓ 前端服务 (端口 1000) - 运行中"
else
    echo "✗ 前端服务 (端口 1000) - 未运行"
    echo "  请手动启动: cd ~/interactive-storybook/frontend && nohup npm run dev > ../logs/frontend.log 2>&1 &"
fi

# 检查后端
if curl -s http://localhost:1001 > /dev/null 2>&1; then
    echo "✓ 后端服务 (端口 1001) - 运行中"
else
    echo "✗ 后端服务 (端口 1001) - 未运行"
    echo "  请手动启动: cd ~/interactive-storybook/backend && nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &"
fi

# 检查 Nginx
if systemctl is-active --quiet nginx; then
    echo "✓ Nginx - 运行中"
else
    echo "✗ Nginx - 未运行"
fi

echo ""
echo "=========================================="
echo "配置完成!"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  🌐 https://story.ai-knowledgepoints.cn"
echo ""
echo "如果服务未启动，请执行:"
echo "  cd ~/interactive-storybook/frontend && nohup npm run dev > ../logs/frontend.log 2>&1 &"
echo "  cd ~/interactive-storybook/backend && nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &"
echo ""
