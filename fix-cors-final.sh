#!/bin/bash
# CORS 问题最终修复脚本
# 功能：同步代码到 ECS 并重启服务

set -e

ECS_IP="8.149.232.39"
ECS_USER="root"
ECS_DIR="~/interactive-storybook"

echo "========================================"
echo "🔧 CORS 问题修复脚本"
echo "========================================"
echo ""

# 1. 检查本地修改
echo "📝 检查本地修改状态..."
git status --short

echo ""
read -p "是否提交并推送这些修改到 GitHub？(y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📦 提交代码..."
    git add .
    git commit -m "修复 CORS 问题 - 使用相对路径 /api 代替 localhost" || echo "没有需要提交的修改"
    
    echo "⬆️  推送到 GitHub..."
    git push origin main
fi

echo ""
echo "========================================"
echo "🚀 开始部署到 ECS"
echo "========================================"

# 2. SSH 到 ECS 并执行更新
ssh ${ECS_USER}@${ECS_IP} << 'ENDSSH'
set -e

echo ""
echo "📥 拉取最新代码..."
cd ~/interactive-storybook
git pull origin main

echo ""
echo "🛑 停止现有服务..."
# 停止前端
pkill -f "next dev" || echo "前端服务未运行"
# 停止后端  
pkill -f "uvicorn.*1001" || echo "后端服务未运行"

sleep 2

echo ""
echo "🔄 重启后端服务 (端口 1001)..."
cd ~/interactive-storybook/backend
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   后端 PID: $BACKEND_PID"

sleep 3

echo ""
echo "🔄 重启前端服务 (端口 1000)..."
cd ~/interactive-storybook/frontend
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   前端 PID: $FRONTEND_PID"

sleep 5

echo ""
echo "========================================"
echo "✅ 服务重启完成"
echo "========================================"

echo ""
echo "📊 服务状态检查:"
ps aux | grep -E "(next dev|uvicorn.*1001)" | grep -v grep || echo "⚠️  未检测到服务进程"

echo ""
echo "📝 最近的日志 (后端):"
tail -20 ~/interactive-storybook/logs/backend.log

echo ""
echo "📝 最近的日志 (前端):"
tail -20 ~/interactive-storybook/logs/frontend.log

ENDSSH

echo ""
echo "========================================"
echo "🎉 部署完成！"
echo "========================================"
echo ""
echo "🔍 验证步骤："
echo "   1. 访问: https://story.ai-knowledgepoints.cn"
echo "   2. 按 F12 打开开发者工具"
echo "   3. 切换到 Network 标签"
echo "   4. 刷新页面，检查 API 请求："
echo "      ✅ 应该是: /api/story/styles"
echo "      ❌ 不应该: http://localhost:1001/..."
echo ""
echo "📋 如果还有问题，执行以下命令查看日志："
echo "   ssh ${ECS_USER}@${ECS_IP}"
echo "   tail -f ~/interactive-storybook/logs/backend.log"
echo "   tail -f ~/interactive-storybook/logs/frontend.log"
echo ""
