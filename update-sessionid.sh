#!/bin/bash
# 更新即梦 SessionID 的交互式脚本

set -e

echo "=========================================="
echo "更新即梦 API SessionID"
echo "=========================================="
echo ""
echo "SessionID 会定期过期，需要手动更新"
echo ""
echo "📋 获取新 SessionID 的步骤："
echo ""
echo "1. 打开浏览器，访问以下任一网站："
echo "   - https://jimeng.jianying.com/"
echo "   - https://www.dreamina.com/"
echo ""
echo "2. 登录你的账号"
echo ""
echo "3. 按 F12 打开开发者工具"
echo ""
echo "4. 切换到 Application 标签（或 存储 标签）"
echo ""
echo "5. 左侧找到 Cookies -> 选择网站"
echo ""
echo "6. 在右侧找到 'sessionid' 或 'session_id'"
echo ""
echo "7. 复制它的值（通常是一长串字母数字）"
echo ""
echo "=========================================="
echo ""

# 显示当前 SessionID
if [ -f ~/interactive-storybook/.env ]; then
    CURRENT_SESSION=$(grep "JIMENG_SESSION_ID=" ~/interactive-storybook/.env | cut -d'=' -f2 | tr -d '"')
    echo "当前 SessionID（前20个字符）: ${CURRENT_SESSION:0:20}..."
    echo ""
fi

read -p "请粘贴新的 SessionID（或按 Ctrl+C 取消）: " NEW_SESSION

if [ -z "$NEW_SESSION" ]; then
    echo "❌ SessionID 不能为空"
    exit 1
fi

# 去除可能的引号和空格
NEW_SESSION=$(echo "$NEW_SESSION" | tr -d '"' | tr -d "'" | xargs)

echo ""
echo "新 SessionID（前20个字符）: ${NEW_SESSION:0:20}..."
echo ""
read -p "确认更新？(y/n): " CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "❌ 已取消"
    exit 0
fi

echo ""
echo "[1/4] 备份当前 .env 文件..."
cp ~/interactive-storybook/.env ~/interactive-storybook/.env.backup.$(date +%Y%m%d_%H%M%S)

echo ""
echo "[2/4] 更新 SessionID..."
cd ~/interactive-storybook

# 使用 sed 更新 SessionID
if grep -q "JIMENG_SESSION_ID=" .env; then
    # 已存在，替换
    sed -i "s|JIMENG_SESSION_ID=.*|JIMENG_SESSION_ID=$NEW_SESSION|g" .env
else
    # 不存在，添加
    echo "JIMENG_SESSION_ID=$NEW_SESSION" >> .env
fi

echo "✅ SessionID 已更新"

echo ""
echo "[3/4] 重启 jimeng-api 容器..."
if docker ps | grep -q interactive-storybook-jimeng; then
    docker restart interactive-storybook-jimeng
    echo "✅ 容器已重启"
else
    echo "⚠️ jimeng 容器未运行，尝试启动..."
    docker-compose up -d jimeng
fi

echo ""
echo "[4/4] 等待服务启动（20秒）..."
sleep 20

echo ""
echo "测试服务..."
if curl -f -s http://localhost:1002/health > /dev/null 2>&1; then
    echo "✅ jimeng-api 服务正常"
    echo ""
    echo "=========================================="
    echo "✅ SessionID 更新成功！"
    echo "=========================================="
    echo ""
    echo "现在重启后端服务..."
    cd ~/interactive-storybook
    bash restart.sh
    echo ""
    echo "✅ 所有服务已重启，请测试故事生成功能"
else
    echo "❌ 服务仍有问题"
    echo ""
    echo "请检查容器日志："
    echo "  docker logs interactive-storybook-jimeng"
    echo ""
    echo "可能的原因："
    echo "1. SessionID 仍然无效（请确认是否复制了完整的 sessionid）"
    echo "2. 网络连接问题"
    echo "3. 容器配置问题"
fi
