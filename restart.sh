# 停止旧服务
pkill -f "next dev -p 1000"
pkill -f "uvicorn.*1001"

# 重启服务
cd ~/interactive-storybook/backend
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > ../logs/backend.log 2>&1 &

cd ~/interactive-storybook/frontend
nohup npm run dev -p 1000 -H 0.0.0.0 > ../logs/frontend.log 2>&1 &