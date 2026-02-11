#!/bin/bash
# 基于官方文档的 jimeng-api 完整测试脚本

set -e

echo "=========================================="
echo "jimeng-api 完整测试脚本"
echo "基于官方文档: github.com/iptag/jimeng-api"
echo "=========================================="

cd ~/interactive-storybook

# 读取 SessionID
if [ -f .env ]; then
    SESSION_ID=$(grep "JIMENG_SESSION_ID=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    if [ -z "$SESSION_ID" ]; then
        echo "❌ .env 文件中未找到 JIMENG_SESSION_ID"
        exit 1
    fi
    echo "✅ SessionID: ${SESSION_ID:0:20}..."
else
    echo "❌ 未找到 .env 文件"
    exit 1
fi

echo ""
echo "=========================================="
echo "第一部分：基础检查"
echo "=========================================="

echo ""
echo "[1] 检查 Docker 容器状态..."
if docker ps | grep -q interactive-storybook-jimeng; then
    echo "✅ 容器正在运行"
    docker ps | grep jimeng
else
    echo "❌ 容器未运行"
    echo "启动容器："
    echo "  docker-compose up -d jimeng-api"
    exit 1
fi

echo ""
echo "[2] 检查容器内部端口监听..."
docker exec interactive-storybook-jimeng netstat -tlnp 2>/dev/null | grep 5100 || \
    echo "⚠️  无法检查端口（容器内可能没有 netstat）"

echo ""
echo "[3] 检查容器环境变量..."
ENV_CHECK=$(docker exec interactive-storybook-jimeng env | grep SESSION || echo "")
if [ -n "$ENV_CHECK" ]; then
    echo "✅ 容器中有 SESSION 环境变量"
    echo "   $ENV_CHECK"
else
    echo "❌ 容器中没有 SESSION 环境变量"
    echo ""
    echo "这是导致 502 错误的根本原因！"
    echo "请运行修复脚本："
    echo "  bash fix-docker-env.sh"
    exit 1
fi

echo ""
echo "=========================================="
echo "第二部分：API 端点测试（按官方文档）"
echo "=========================================="

BASE_URL="http://localhost:1002"

echo ""
echo "[1] 测试健康检查端点（非官方，但容器有）..."
if curl -f -s "$BASE_URL/health" > /dev/null 2>&1; then
    echo "✅ 健康检查通过"
else
    echo "⚠️  健康检查端点不可用（这个端点可能不存在）"
fi

echo ""
echo "[2] 测试 Token 检查 API..."
echo "POST /token/check"
TOKEN_CHECK=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/token/check" \
    -H "Content-Type: application/json" \
    -d "{\"token\": \"$SESSION_ID\"}" 2>&1)

HTTP_CODE=$(echo "$TOKEN_CHECK" | tail -n 1)
RESPONSE=$(echo "$TOKEN_CHECK" | head -n -1)

echo "HTTP 状态码: $HTTP_CODE"
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Token 检查成功"
    echo "响应: $RESPONSE"
    
    # 检查 token 是否有效
    if echo "$RESPONSE" | grep -q '"live":true'; then
        echo "✅ Token 有效 (live: true)"
    else
        echo "❌ Token 无效 (live: false)"
        echo "请更新 SessionID："
        echo "  bash update-sessionid.sh"
    fi
else
    echo "❌ Token 检查失败"
    echo "响应: $RESPONSE"
fi

echo ""
echo "[3] 测试获取积分 API..."
echo "POST /token/points"
POINTS=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/token/points" \
    -H "Authorization: Bearer $SESSION_ID" 2>&1)

HTTP_CODE=$(echo "$POINTS" | tail -n 1)
RESPONSE=$(echo "$POINTS" | head -n -1)

echo "HTTP 状态码: $HTTP_CODE"
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ 获取积分成功"
    echo "响应: $RESPONSE"
else
    echo "❌ 获取积分失败"
    echo "响应: $RESPONSE"
fi

echo ""
echo "[4] 测试文生图 API（核心功能）..."
echo "POST /v1/images/generations"
IMAGE_GEN=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/images/generations" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $SESSION_ID" \
    -d '{
        "model": "jimeng-4.5",
        "prompt": "一只可爱的小猫",
        "ratio": "1:1",
        "resolution": "1k"
    }' 2>&1)

HTTP_CODE=$(echo "$IMAGE_GEN" | tail -n 1)
RESPONSE=$(echo "$IMAGE_GEN" | head -n -1)

echo "HTTP 状态码: $HTTP_CODE"
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ 文生图 API 测试成功"
    echo "响应（前 200 字符）:"
    echo "$RESPONSE" | head -c 200
    echo "..."
elif [ "$HTTP_CODE" = "502" ]; then
    echo "❌ 返回 502 错误"
    echo "响应: $RESPONSE"
    echo ""
    echo "可能的原因："
    echo "1. SessionID 未正确传递到容器（最常见）"
    echo "2. SessionID 已过期或无效"
    echo "3. 即梦 API 服务异常"
    echo ""
    echo "建议："
    echo "1. 检查容器环境变量: docker exec interactive-storybook-jimeng env | grep SESSION"
    echo "2. 更新 SessionID: bash update-sessionid.sh"
    echo "3. 查看容器日志: docker logs interactive-storybook-jimeng"
else
    echo "❌ 文生图 API 测试失败"
    echo "响应: $RESPONSE"
fi

echo ""
echo "=========================================="
echo "第三部分：容器日志分析"
echo "=========================================="

echo ""
echo "查看最近 30 行容器日志..."
echo "---"
docker logs --tail 30 interactive-storybook-jimeng 2>&1
echo "---"

echo ""
echo "=========================================="
echo "测试总结"
echo "=========================================="

echo ""
echo "✅ 已完成的检查："
echo "  - Docker 容器状态"
echo "  - 容器环境变量"
echo "  - Token 检查 API"
echo "  - 获取积分 API"
echo "  - 文生图 API"
echo "  - 容器日志"

echo ""
echo "📚 更多测试示例请参考官方文档："
echo "  https://github.com/iptag/jimeng-api/blob/main/README.CN.md"

echo ""
echo "🔧 常用命令："
echo "  # 查看实时日志"
echo "  docker logs -f interactive-storybook-jimeng"
echo ""
echo "  # 重启容器"
echo "  docker restart interactive-storybook-jimeng"
echo ""
echo "  # 进入容器调试"
echo "  docker exec -it interactive-storybook-jimeng sh"
echo ""
echo "  # 测试 Token"
echo "  curl -X POST http://localhost:1002/token/check \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"token\": \"YOUR_SESSION_ID\"}'"
echo ""
