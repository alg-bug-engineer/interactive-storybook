#!/bin/bash
# 紧急回滚脚本 - 恢复到修改前的版本

set -e

echo "🔄 开始回滚到上一个稳定版本..."

cd "$(dirname "$0")"

# 回滚到上一个提交
git reset --hard HEAD~1

echo "✅ 代码已回滚到: $(git log --oneline -1)"
echo ""
echo "📌 接下来需要手动操作："
echo "   1. 如果本地前端正在运行,请重启: cd frontend && npm run dev"
echo "   2. 如果ECS上已经拉取了新代码，需要在ECS上执行:"
echo "      cd ~/interactive-storybook"
echo "      git pull  # 拉取回滚后的代码"
echo "      # 重启前后端服务"
