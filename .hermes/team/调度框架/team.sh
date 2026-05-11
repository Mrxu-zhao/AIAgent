#!/bin/bash
#===============================================================================
# 团队调度框架主入口
# 一站式管理所有Agent调度
#===============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISPATCH_SCRIPT="$SCRIPT_DIR/scripts/team-dispatch.sh"
TMUX_SCRIPT="$SCRIPT_DIR/tmux/team-tmux.sh"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Agent配置
declare -A AGENT_NAMES=(
  ["architect"]="张欣怡"
  ["dba"]="周嘉诚"
  ["backend-1"]="陈启明"
  ["backend-2"]="王浩然"
  ["backend-3"]="赵文杰"
  ["frontend-1"]="李思雨"
  ["frontend-2"]="周晓明"
  ["frontend-3"]="林雅婷"
  ["ucd"]="吴俊杰"
  ["qa-functional"]="郑晓彤"
  ["qa-performance"]="孙美玲"
  ["devops"]="黄志远"
  ["requirements-analyst"]="吴雪梅"
)

declare -A AGENT_ROLES=(
  ["architect"]="系统架构师"
  ["dba"]="数据库设计师"
  ["backend-1"]="后端开发"
  ["backend-2"]="后端开发"
  ["backend-3"]="后端开发"
  ["frontend-1"]="前端开发"
  ["frontend-2"]="前端开发"
  ["frontend-3"]="前端开发"
  ["ucd"]="UCD设计师"
  ["qa-functional"]="功能测试"
  ["qa-performance"]="性能测试"
  ["devops"]="运维"
  ["requirements-analyst"]="需求分析师"
)

# 打印横幅
print_banner() {
  echo -e "${BLUE}"
  cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     徐钊研发团队 Agent 调度框架 v1.0                       ║
║                                                           ║
║     项目经理: 秦燕                                         ║
║     团队成员: 13人                                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF
  echo -e "${NC}"
}

# 打印主菜单
print_menu() {
  echo -e "${BLUE}=== 团队调度主菜单 ===${NC}\n"
  echo "  1. 列出所有Agent"
  echo "  2. 查看Agent状态"
  echo "  3. 调度Agent执行任务"
  echo "  4. 续聊现有session"
  echo "  5. tmux团队视图"
  echo "  6. 查看工作流"
  echo "  7. 快速启动项目"
  echo ""
  echo "  0. 退出"
  echo ""
}

# 列出Agent
list_agents() {
  echo -e "${BLUE}=== 团队成员列表 ===${NC}\n"
  printf "%-4s %-15s %-12s\n" "ID" "名字" "角色"
  printf "%-4s %-15s %-12s\n" "----" "----" "----"
  
  local idx=1
  for agent in "${!AGENT_NAMES[@]}"; do
    printf "%-4d %-15s %-12s\n" "$idx" "${AGENT_NAMES[$agent]}" "${AGENT_ROLES[$agent]}"
    ((idx++))
  done
}

# 查看状态
show_status() {
  echo -e "${BLUE}=== Agent Session 状态 ===${NC}\n"
  hermes sessions list 2>/dev/null | head -30 || echo "无session记录"
}

# 调度任务
dispatch_task() {
  echo -e "${BLUE}=== 选择要调度的Agent ===${NC}\n"
  local idx=1
  declare -a AGENT_LIST
  
  for agent in "${!AGENT_NAMES[@]}"; do
    echo "  $idx. ${AGENT_NAMES[$agent]} (${AGENT_ROLES[$agent]})"
    AGENT_LIST+=("$agent")
    ((idx++))
  done
  
  echo ""
  read -p "请选择 (1-${#AGENT_LIST[@]}): " choice
  
  if [[ "$choice" -ge 1 && "$choice" -le ${#AGENT_LIST[@]} ]]; then
    local selected_agent="${AGENT_LIST[$((choice-1))]}"
    echo ""
    read -p "请输入任务描述: " task
    
    if [[ -n "$task" ]]; then
      echo -e "${GREEN}正在调度 ${AGENT_NAMES[$selected_agent]}...${NC}"
      hermes --profile "$selected_agent" chat -p "$task"
    fi
  fi
}

# 续聊session
resume_session() {
  echo -e "${BLUE}=== 选择要续聊的Agent ===${NC}\n"
  local idx=1
  declare -a AGENT_LIST
  
  for agent in "${!AGENT_NAMES[@]}"; do
    echo "  $idx. ${AGENT_NAMES[$agent]}"
    AGENT_LIST+=("$agent")
    ((idx++))
  done
  
  echo ""
  read -p "请选择 (1-${#AGENT_LIST[@]}): " choice
  
  if [[ "$choice" -ge 1 && "$choice" -le ${#AGENT_LIST[@]} ]]; then
    local selected_agent="${AGENT_LIST[$((choice-1))]}"
    echo -e "${GREEN}正在连接 ${AGENT_NAMES[$selected_agent]}...${NC}"
    hermes --continue "$selected_agent" chat
  fi
}

# tmux视图
show_tmux() {
  if command -v tmux &> /dev/null; then
    "$TMUX_SCRIPT" status
  else
    echo -e "${RED}tmux 未安装${NC}"
  fi
}

# 查看工作流
show_workflow() {
  cat "$SCRIPT_DIR/workflows/project-workflow.md"
}

# 快速启动
quick_start() {
  echo -e "${BLUE}=== 快速启动项目 ===${NC}\n"
  echo "  1. 需求分析流程"
  echo "  2. 技术设计流程"
  echo "  3. 开发流程"
  echo "  4. 测试流程"
  echo "  5. 交付流程"
  echo ""
  echo "  0. 返回"
  echo ""
  read -p "请选择流程: " choice
  
  case "$choice" in
    1) hermes --profile requirements-analyst chat -p "启动需求分析流程" ;;
    2) hermes --profile architect chat -p "启动技术设计流程" ;;
    3) hermes --profile backend-1 chat -p "启动开发流程" ;;
    4) hermes --profile qa-functional chat -p "启动测试流程" ;;
    5) hermes --profile devops chat -p "启动交付流程" ;;
  esac
}

# 主循环
main() {
  print_banner
  
  while true; do
    print_menu
    read -p "请选择 (0-7): " choice
    
    case "$choice" in
      1) list_agents; echo "" ;;
      2) show_status; echo "" ;;
      3) dispatch_task; echo "" ;;
      4) resume_session; echo "" ;;
      5) show_tmux; echo "" ;;
      6) show_workflow | less ;;
      7) quick_start; echo "" ;;
      0) echo -e "${GREEN}再见!${NC}"; exit 0 ;;
      *) echo -e "${RED}无效选择${NC}" ;;
    esac
  done
}

main "$@"
