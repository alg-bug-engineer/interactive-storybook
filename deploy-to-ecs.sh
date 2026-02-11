#!/bin/bash
# ===================================================================
# 互动故事书 ECS 部署脚本
# ===================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    error "请使用 sudo 或 root 用户运行此脚本"
    exit 1
fi

cd ~/interactive-storybook

# ===================================================================
# 1. 确保服务正在运行
# ===================================================================
log "检查服务状态..."

# 检查前端是否在运行
if ! pgrep -f "next dev -p 1000" > /dev/null; then
    warn "前端服务未运行，正在启动..."
    cd frontend
    nohup npm run dev > ../logs/frontend.log 2>&1 &
    cd ..
    sleep 3
    log "前端服务已启动 (端口 1000)"
else
    log "前端服务已在运行 (端口 1000)"
fi

# 检查后端是否在运行
if ! pgrep -f "uvicorn.*1001" > /dev/null; then
    warn "后端服务未运行，正在启动..."
    cd backend
    nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &
    cd ..
    sleep 3
    log "后端服务已启动 (端口 1001)"
else
    log "后端服务已在运行 (端口 1001)"
fi

# ===================================================================
# 2. 配置 Nginx
# ===================================================================
log "配置 Nginx..."

# 创建日志目录
mkdir -p /var/log/nginx
mkdir -p /var/www/html

# 复制配置文件
cp nginx/storybook.conf /etc/nginx/sites-available/storybook.conf

# 启用站点
ln -sf /etc/nginx/sites-available/storybook.conf /etc/nginx/sites-enabled/storybook.conf

# 测试 Nginx 配置
if nginx -t; then
    log "Nginx 配置测试通过"
else
    error "Nginx 配置测试失败，请检查配置"
    exit 1
fi

# ===================================================================
# 3. 申请 SSL 证书 (如果还没有)
# ===================================================================
if [ ! -d "/etc/letsencrypt/live/story.ai-knowledgepoints.cn" ]; then
    log "正在为 story.ai-knowledgepoints.cn 申请 SSL 证书..."
    
    # 确保 certbot 已安装
    if ! command -v certbot &> /dev/null; then
        log "安装 Certbot..."
        apt-get update
        apt-get install -y certbot python3-certbot-nginx
    fi
    
    # 临时禁用 SSL 配置，申请证书
    sed -i 's/listen 443 ssl http2;/listen 80;/' /etc/nginx/sites-enabled/storybook.conf
    sed -i 's/ssl_certificate/# ssl_certificate/' /etc/nginx/sites-enabled/storybook.conf
    sed -i 's/ssl_certificate_key/# ssl_certificate_key/' /etc/nginx/sites-enabled/storybook.conf
    sed -i 's/include \/etc\/letsencrypt/# include \/etc\/letsencrypt/' /etc/nginx/sites-enabled/storybook.conf
    sed -i 's/ssl_dhparam/# ssl_dhparam/' /etc/nginx/sites-enabled/storybook.conf
    
    nginx -s reload
    
    # 申请证书
    certbot --nginx -d story.ai-knowledgepoints.cn --agree-tos --non-interactive --email admin@ai-knowledgepoints.cn
    
    # 恢复完整配置
    cp nginx/storybook.conf /etc/nginx/sites-available/storybook.conf
    ln -sf /etc/nginx/sites-available/storybook.conf /etc/nginx/sites-enabled/storybook.conf
else
    log "SSL 证书已存在"
fi

# ===================================================================
# 4. 重启 Nginx
# ===================================================================
log "重启 Nginx..."
systemctl restart nginx
systemctl enable nginx

log "Nginx 状态:"
systemctl status nginx --no-pager

# ===================================================================
# 5. 配置防火墙
# ===================================================================
log "配置防火墙..."
if command -v ufw &> /dev/null; then
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    log "UFW 防火墙已配置"
fi

# ===================================================================
# 6. 验证部署
# ===================================================================
log "验证部署..."
echo ""
echo "=============================================="
echo "部署状态:"
echo "=============================================="
echo ""

# 检查端口监听
echo "端口监听情况:"
netstat -tlnp | grep -E ':(1000|1001|1002|80|443)' || ss -tlnp | grep -E ':(1000|1001|1002|80|443)'

echo ""
echo "服务进程:"
echo "前端 (端口 1000):"
pgrep -f "next dev -p 1000" && echo "  ✓ 运行中" || echo "  ✗ 未运行"

echo "后端 (端口 1001):"
pgrep -f "uvicorn.*1001" && echo "  ✓ 运行中" || echo "  ✗ 未运行"

echo ""
echo "访问地址:"
echo "  HTTPS: https://story.ai-knowledgepoints.cn"
echo "  HTTP:  http://story.ai-knowledgepoints.cn (会自动重定向到 HTTPS)"
echo ""
echo "本地测试:"
echo "  curl -I http://localhost:1000     # 前端"
echo "  curl -I http://localhost:1001/api # 后端"
echo ""
echo "日志文件:"
echo "  前端日志: ~/interactive-storybook/logs/frontend.log"
echo "  后端日志: ~/interactive-storybook/logs/backend.log"
echo "  Nginx访问: /var/log/nginx/storybook-access.log"
echo "  Nginx错误: /var/log/nginx/storybook-error.log"
echo ""
echo "=============================================="

log "部署完成!"
