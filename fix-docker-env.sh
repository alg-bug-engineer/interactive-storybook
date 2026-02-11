#!/bin/bash
# 修复 Docker 环境变量传递问题

set -e

echo "=========================================="
echo "修复 jimeng-api SessionID 传递问题"
echo "=========================================="
echo ""
echo "问题：docker-compose.yml 没有配置环境变量传递"
echo "修复：添加 environment 配置，传递 JIMENG_SESSION_ID"
echo ""

cd ~/interactive-storybook

echo "[1/5] 检查 .env 文件中的 SessionID..."
if grep -q "JIMENG_SESSION_ID=" .env; then
    SESSION_ID=$(grep "JIMENG_SESSION_ID=" .env | cut -d'=' -f2)
    echo "✅ 找到 SessionID: ${SESSION_ID:0:20}..."
else
    echo "❌ .env 中未找到 JIMENG_SESSION_ID"
    echo ""
    echo "请先配置 SessionID："
    echo "  nano ~/interactive-storybook/.env"
    echo "  添加: JIMENG_SESSION_ID=你的sessionid"
    exit 1
fi

echo ""
echo "[2/5] 备份当前 docker-compose.yml..."
cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ 已备份"

echo ""
echo "[3/5] 检查 docker-compose.yml 配置..."
if grep -q "JIMENG_SESSION_ID" docker-compose.yml; then
    echo "✅ docker-compose.yml 已包含环境变量配置"
else
    echo "⚠️  docker-compose.yml 缺少环境变量配置"
    echo "需要手动更新 docker-compose.yml 文件"
    echo "请参考 git 仓库中的最新版本，或在 jimeng-api 服务中添加："
    echo ""
    echo "    environment:"
    echo "      - JIMENG_SESSION_ID=\${JIMENG_SESSION_ID}"
    echo ""
    read -p "是否继续重启服务？(y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
        exit 0
    fi
fi

echo ""
echo "[4/5] 重启 jimeng-api 容器..."
docker-compose down jimeng-api
docker-compose up -d jimeng-api

echo ""
echo "[5/5] 等待服务启动（30秒）..."
for i in {30..1}; do
    echo -ne "\r剩余 $i 秒..."
    sleep 1
done
echo ""

echo ""
echo "=========================================="
echo "验证修复"
echo "=========================================="

echo ""
echo "[检查 1] 容器环境变量..."
ENV_CHECK=$(docker exec interactive-storybook-jimeng env | grep SESSION || echo "NOT_FOUND")
if [ "$ENV_CHECK" != "NOT_FOUND" ]; then
    echo "✅ 容器中已有 SESSION 环境变量"
    echo "   $ENV_CHECK"
else
    echo "❌ 容器中仍没有 SESSION 环境变量"
    echo ""
    echo "可能的原因："
    echo "1. docker-compose.yml 配置不正确"
    echo "2. .env 文件中 SessionID 格式有问题"
    echo ""
    echo "请检查："
    echo "  cat docker-compose.yml | grep -A5 jimeng-api"
    echo "  cat .env | grep JIMENG_SESSION_ID"
    exit 1
fi

echo ""
echo "[检查 2] 服务健康状态..."
sleep 5  # 额外等待服务完全启动
if curl -f -s http://localhost:1002/health > /dev/null 2>&1; then
    echo "✅ 健康检查通过"
else
    echo "⚠️  健康检查失败（服务可能还在启动中）"
fi

echo ""
echo "[检查 3] API 端点测试..."
TEST_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:1002/v1/images/generations \
    -H "Content-Type: application/json" \
    -d '{"prompt":"test cat","model":"jimeng-4.5","size":"1024x1024"}' 2>&1 || echo "000")

HTTP_CODE=$(echo "$TEST_RESPONSE" | tail -n 1)
RESPONSE_BODY=$(echo "$TEST_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "✅ API 测试成功（HTTP $HTTP_CODE）"
    echo ""
    echo "=========================================="
    echo "✅ 修复成功！jimeng-api 服务正常运行"
    echo "=========================================="
    echo ""
    echo "现在重启后端服务以应用所有更改..."
    cd ~/interactive-storybook
    bash restart.sh
    echo ""
    echo "✅ 所有服务已重启"
    echo ""
    echo "请访问前端页面测试故事生成功能"
elif [ "$HTTP_CODE" = "502" ]; then
    echo "❌ 仍返回 502 错误"
    echo ""
    echo "响应内容："
    echo "$RESPONSE_BODY"
    echo ""
    echo "可能的原因："
    echo "1. SessionID 已过期或无效"
    echo "2. 即梦 API 服务问题"
    echo ""
    echo "建议："
    echo "1. 更新 SessionID（运行 bash update-sessionid.sh）"
    echo "2. 查看容器日志："
    echo "   docker logs interactive-storybook-jimeng"
else
    echo "❌ API 测试失败（HTTP $HTTP_CODE）"
    echo ""
    echo "响应内容："
    echo "$RESPONSE_BODY"
    echo ""
    echo "查看容器日志："
    echo "  docker logs interactive-storybook-jimeng"
fi

echo ""
echo "=========================================="
echo "诊断命令"
echo "=========================================="
echo ""
echo "查看容器日志："
echo "  docker logs -f interactive-storybook-jimeng"
echo ""
echo "查看环境变量："
echo "  docker exec interactive-storybook-jimeng env | grep SESSION"
echo ""
echo "测试服务："
echo "  curl http://localhost:1002/health"
echo ""
