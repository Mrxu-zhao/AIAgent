#!/bin/bash
# Legacy tmux view kept as an adapter over unified entrypoints.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRAMEWORK_CLI="$FRAMEWORK_ROOT/cli/team-cli.py"
CONTROL_PLANE_CLI="$FRAMEWORK_ROOT/../control_plane/cli.py"
PYTHON_BIN="${PYTHON_BIN:-python}"
TMUX_SESSION="${TMUX_SESSION:-team-control-plane}"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
  cat <<EOF
tmux 团队适配层

用法: $0 <命令>
  start            启动控制平面观察会话
  stop             停止会话
  status           查看窗口状态
  send <win> <msg> 向指定窗口发送消息
  log [win]        查看窗口日志
  help             显示帮助
EOF
}

check_tmux() {
  if ! command -v tmux >/dev/null 2>&1; then
    echo -e "${RED}错误: tmux 未安装${NC}"
    exit 1
  fi
}

session_exists() {
  tmux has-session -t "$TMUX_SESSION" 2>/dev/null
}

start_team() {
  check_tmux
  if session_exists; then
    echo -e "${GREEN}会话已存在，正在附加...${NC}"
    exec tmux attach -t "$TMUX_SESSION"
  fi

  echo -e "${GREEN}创建控制平面 tmux 视图...${NC}"
  tmux new-session -d -s "$TMUX_SESSION" -n "monitor"
  tmux send-keys -t "$TMUX_SESSION:0" \
    "$PYTHON_BIN $CONTROL_PLANE_CLI monitor --dashboard" C-m

  tmux new-window -t "$TMUX_SESSION" -n "interactive"
  tmux send-keys -t "$TMUX_SESSION:1" \
    "$PYTHON_BIN $FRAMEWORK_CLI interactive" C-m

  tmux new-window -t "$TMUX_SESSION" -n "batch"
  tmux send-keys -t "$TMUX_SESSION:2" \
    "$PYTHON_BIN $CONTROL_PLANE_CLI control-plane-run --max-workers 2" C-m

  tmux new-window -t "$TMUX_SESSION" -n "validate"
  tmux send-keys -t "$TMUX_SESSION:3" \
    "$PYTHON_BIN $CONTROL_PLANE_CLI validate --replicas 2 --max-workers 2" C-m

  echo -e "${GREEN}控制平面 tmux 视图已创建${NC}"
  echo "窗口:"
  echo "  0 - monitor"
  echo "  1 - interactive"
  echo "  2 - batch"
  echo "  3 - validate"
}

stop_team() {
  check_tmux
  if session_exists; then
    tmux kill-session -t "$TMUX_SESSION"
    echo -e "${GREEN}已停止 ${TMUX_SESSION}${NC}"
  else
    echo -e "${BLUE}会话不存在${NC}"
  fi
}

status_team() {
  check_tmux
  if session_exists; then
    tmux list-windows -t "$TMUX_SESSION"
  else
    echo -e "${BLUE}会话未运行，输出当前团队状态${NC}"
    "$PYTHON_BIN" "$FRAMEWORK_CLI" status
  fi
}

send_msg() {
  local window="${1:-}"
  shift || true
  local msg="${*:-}"
  if [[ -z "$window" || -z "$msg" ]]; then
    echo -e "${RED}用法: $0 send <window> <消息>${NC}"
    exit 1
  fi
  tmux send-keys -t "$TMUX_SESSION:$window" "$msg" C-m
}

show_log() {
  local window="${1:-0}"
  tmux capture-pane -t "$TMUX_SESSION:$window" -p | tail -50
}

case "${1:-}" in
  start)
    start_team
    ;;
  stop)
    stop_team
    ;;
  status)
    status_team
    ;;
  send)
    shift
    send_msg "$@"
    ;;
  log)
    show_log "${2:-0}"
    ;;
  help|"")
    usage
    ;;
  *)
    echo -e "${RED}未知命令: $1${NC}"
    usage
    exit 1
    ;;
esac
