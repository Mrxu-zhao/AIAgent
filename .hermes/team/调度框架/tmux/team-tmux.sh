#!/bin/bash
#===============================================================================
# tmux 团队调度框架
# 在 tmux 中启动多个 Agent 并行工作
#===============================================================================

set -e

TMUX_SESSION="team"

# Agent配置
BACKEND_AGENTS=("backend-1" "backend-2" "backend-3")
FRONTEND_AGENTS=("frontend-1" "frontend-2" "frontend-3")
ALL_AGENTS=("architect" "dba" "requirements-analyst" "backend-1" "backend-2" "backend-3" "frontend-1" "frontend-2" "frontend-3" "ucd" "qa-functional" "qa-performance" "devops")

# Agent中文名
declare -A AGENT_NAMES=(
  ["architect"]="张欣怡-架构师"
  ["dba"]="周嘉诚-DBA"
  ["backend-1"]="陈启明-后端"
  ["backend-2"]="王浩然-后端"
  ["backend-3"]="赵文杰-后端"
  ["frontend-1"]="李思雨-前端"
  ["frontend-2"]="周晓明-前端"
  ["frontend-3"]="林雅婷-前端"
  ["ucd"]="吴俊杰-设计"
  ["qa-functional"]="郑晓彤-测试"
  ["qa-performance"]="孙美玲-性能"
  ["devops"]="黄志远-运维"
  ["requirements-analyst"]="吴雪梅-需求"
)

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
  echo -e "${BLUE}tmux 团队调度框架${NC}"
  echo ""
  echo "用法: $0 <命令> [参数]"
  echo ""
  echo "命令:"
  echo "  start              启动团队工作区"
  echo "  stop               停止团队工作区"
  echo "  status             查看团队状态"
  echo "  send <agent> <msg> 向指定Agent发送消息"
  echo "  send-all <msg>     向所有Agent广播消息"
  echo "  log <agent>        查看指定Agent日志"
  echo "  new <agent>        为指定Agent新建session"
  echo "  help               显示帮助"
}

# 检查tmux是否可用
check_tmux() {
  if ! command -v tmux &> /dev/null; then
    echo -e "${RED}错误: tmux 未安装${NC}"
    exit 1
  fi
}

# 检查session是否存在
session_exists() {
  tmux has-session -t "$1" 2>/dev/null
}

# 启动团队工作区
start_team() {
  check_tmux
  
  if session_exists "$TMUX_SESSION"; then
    echo -e "${GREEN}团队工作区已存在，正在附加...${NC}"
    tmux attach -t "$TMUX_SESSION"
    return
  fi
  
  echo -e "${GREEN}创建团队工作区...${NC}"
  
  # 创建主session，分为多个window
  tmux new-session -d -s "$TMUX_SESSION" -n "团队控制台"
  
  # 创建PM控制台
  tmux send-keys -t "$TMUX_SESSION:0" "echo '=== 徐钊研发团队控制台 ===' && echo '使用 Ctrl+b 然后按数字切换窗口' && echo '1-架构师 2-DBA 3-需求 4-6后端 7-9前端 a-测试 o-运维'" C-m
  
  # 创建各Agent窗口
  local win=1
  for agent in "${ALL_AGENTS[@]}"; do
    tmux new-window -t "$TMUX_SESSION" -n "${AGENT_NAMES[$agent]}"
    tmux send-keys -t "$TMUX_SESSION:$win" "hermes --profile $agent chat -q" C-m
    ((win++))
  done
  
  # 创建测试窗口
  tmux new-window -t "$TMUX_SESSION" -n "郑晓彤-测试"
  tmux send-keys -t "$TMUX_SESSION:$win" "hermes --profile qa-functional chat -q" C-m
  ((win++))
  tmux new-window -t "$TMUX_SESSION" -n "孙美玲-性能"
  tmux send-keys -t "$TMUX_SESSION:$win" "hermes --profile qa-performance chat -q" C-m
  ((win++))
  tmux new-window -t "$TMUX_SESSION" -n "黄志远-运维"
  tmux send-keys -t "$TMUX_SESSION:$win" "hermes --profile devops chat -q" C-m
  
  echo -e "${GREEN}团队工作区已创建！${NC}"
  echo "窗口布局:"
  echo "  0 - 团队控制台"
  echo "  1 - 张欣怡(架构师)"
  echo "  2 - 周嘉诚(DBA)"
  echo "  3 - 吴雪梅(需求)"
  echo "  4-6 - 后端组(陈启明/王浩然/赵文杰)"
  echo "  7-9 - 前端组(李思雨/周晓明/林雅婷)"
  echo "  a - 吴俊杰(UCD)"
  echo "  o - 郑晓彤/孙美玲/黄志远"
  echo ""
  echo "运行 'tmux attach -t $TMUX_SESSION' 进入"
}

# 停止团队工作区
stop_team() {
  check_tmux
  
  if session_exists "$TMUX_SESSION"; then
    echo -e "${GREEN}正在停止团队工作区...${NC}"
    tmux kill-session -t "$TMUX_SESSION"
    echo -e "${GREEN}团队工作区已停止${NC}"
  else
    echo -e "${BLUE}团队工作区不存在${NC}"
  fi
}

# 查看状态
status_team() {
  check_tmux
  
  if session_exists "$TMUX_SESSION"; then
    echo -e "${GREEN}团队工作区状态:${NC}"
    tmux list-windows -t "$TMUX_SESSION"
  else
    echo -e "${BLUE}团队工作区未运行${NC}"
    echo "运行 '$0 start' 启动"
  fi
}

# 发送消息
send_msg() {
  local agent="$1"
  local msg="$2"
  
  if [[ -z "$agent" || -z "$msg" ]]; then
    echo -e "${RED}用法: $0 send <agent> <消息>${NC}"
    return 1
  fi
  
  # 查找窗口索引
  local win_idx=0
  for a in "${ALL_AGENTS[@]}"; do
    if [[ "$a" == "$agent" ]]; then
      break
    fi
    ((win_idx++))
  done
  
  tmux send-keys -t "$TMUX_SESSION:$win_idx" "$msg" C-m
  echo -e "${GREEN}消息已发送到 ${AGENT_NAMES[$agent]}${NC}"
}

# 主逻辑
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
    send_msg "$2" "$3"
    ;;
  send-all)
    for agent in "${ALL_AGENTS[@]}"; do
      send_msg "$agent" "$2"
    done
    ;;
  log)
    tmux capture-pane -t "$TMUX_SESSION:${2:-0}" -p | tail -50
    ;;
  new)
    local agent="$2"
    if [[ -n "$agent" ]]; then
      tmux new-window -t "$TMUX_SESSION" -n "${AGENT_NAMES[$agent]}"
      tmux send-keys -t "$TMUX_SESSION:${#ALL_AGENTS[@]}" "hermes --profile $agent chat -q" C-m
    fi
    ;;
  help|"")
    usage
    ;;
  *)
    echo -e "${RED}未知命令: $1${NC}"
    usage
    ;;
esac
