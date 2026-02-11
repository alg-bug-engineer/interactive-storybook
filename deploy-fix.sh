#!/bin/bash
# 部署修复脚本 - 解决 SOCKS 代理和 AsyncHttpxClientWrapper 错误

set -e  # 遇到错误立即退出

echo "=========================================="
echo "开始部署修复..."
echo "=========================================="

# 进入后端目录
cd ~/interactive-storybook/backend

echo ""
echo "[1/4] 安装/更新 Python 依赖（包含 httpx[socks]）..."
pip3 install --upgrade -r requirements.txt

echo ""
echo "[2/4] 停止旧服务..."
pkill -f "uvicorn.*1001" || true
pkill -f "next dev -p 1000" || true

# 等待进程完全停止
sleep 3

echo ""
echo "[3/4] 重启后端服务..."
cd ~/interactive-storybook/backend
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!

echo ""
echo "[4/4] 重启前端服务..."
cd ~/interactive-storybook/frontend
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "后端 PID: $BACKEND_PID"
echo "前端 PID: $FRONTEND_PID"
echo ""
echo "检查日志："
echo "  后端: tail -f ~/interactive-storybook/logs/backend.log"
echo "  前端: tail -f ~/interactive-storybook/logs/frontend.log"
echo ""
echo "验证服务："
echo "  后端: curl http://localhost:1001/health"
echo "  前端: curl http://localhost:1000"
echo ""
