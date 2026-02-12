#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

BACKEND_PORT="1001"
FRONTEND_PORT="1000"
BACKEND_PYTHON_BIN=""

usage() {
  cat <<EOF
用法:
  ./restart.sh start
  ./restart.sh stop
  ./restart.sh restart
EOF
}

ensure_deps() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "[restart] 未找到 npm"
    exit 1
  fi

  # 自动选择可用 Python（支持 BACKEND_PYTHON 覆盖）
  local candidates=()
  if [[ -n "${BACKEND_PYTHON:-}" ]]; then
    candidates+=("$BACKEND_PYTHON")
  fi
  candidates+=("/Users/zhangqilai/miniconda3/envs/lc/bin/python" "python3" "python")

  local candidate
  for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
      if "$candidate" -c "import uvicorn, fastapi, pydantic_settings" >/dev/null 2>&1; then
        BACKEND_PYTHON_BIN="$candidate"
        break
      fi
    fi
  done

  if [[ -z "$BACKEND_PYTHON_BIN" ]]; then
    echo "[restart] 未找到可用的后端 Python 解释器（需安装 uvicorn/fastapi/pydantic_settings）"
    echo "[restart] 可设置环境变量 BACKEND_PYTHON 指向你的解释器，例如："
    echo "  BACKEND_PYTHON=/Users/zhangqilai/miniconda3/envs/lc/bin/python ./restart.sh start"
    exit 1
  fi
}

pids_on_port() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

is_backend_running() {
  [[ -n "$(pids_on_port "$BACKEND_PORT")" ]]
}

is_frontend_running() {
  [[ -n "$(pids_on_port "$FRONTEND_PORT")" ]]
}

start_backend() {
  if is_backend_running; then
    echo "[restart] 后端已在运行 ($BACKEND_PORT)"
    return
  fi
  echo "[restart] 启动后端 http://localhost:1001 ..."
  (
    cd "$ROOT_DIR/backend"
    env -u http_proxy -u https_proxy -u all_proxy -u no_proxy \
      -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY \
      nohup "$BACKEND_PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 1001 > "$LOG_DIR/backend.log" 2>&1 &
  )
}

start_frontend() {
  if is_frontend_running; then
    echo "[restart] 前端已在运行 ($FRONTEND_PORT)"
    return
  fi
  echo "[restart] 启动前端 http://localhost:1000 ..."
  (
    cd "$ROOT_DIR/frontend"
    env -u http_proxy -u https_proxy -u all_proxy -u no_proxy \
      -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY \
      nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
  )
}

stop_backend() {
  if is_backend_running; then
    echo "[restart] 停止后端 ($BACKEND_PORT)"
    local pids
    pids="$(pids_on_port "$BACKEND_PORT")"
    if [[ -n "$pids" ]]; then
      kill $pids >/dev/null 2>&1 || true
    fi
  else
    echo "[restart] 后端未运行"
  fi
}

stop_frontend() {
  if is_frontend_running; then
    echo "[restart] 停止前端 ($FRONTEND_PORT)"
    local pids
    pids="$(pids_on_port "$FRONTEND_PORT")"
    if [[ -n "$pids" ]]; then
      kill $pids >/dev/null 2>&1 || true
    fi
  else
    echo "[restart] 前端未运行"
  fi
}

start_all() {
  ensure_deps
  start_backend
  start_frontend
  echo "[restart] 后端解释器: $BACKEND_PYTHON_BIN"
  echo "[restart] 完成。日志文件："
  echo "  - $LOG_DIR/backend.log"
  echo "  - $LOG_DIR/frontend.log"
}

stop_all() {
  stop_frontend
  stop_backend
}

ACTION="${1:-restart}"

case "$ACTION" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  *)
    usage
    exit 1
    ;;
esac
