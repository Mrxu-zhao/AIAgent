#!/bin/bash
#===============================================================================
# 团队 Agent 调度脚本
# 使用方式: ./team-dispatch.sh <agent> [task]
# 示例: 
#   ./team-dispatch.sh architect "设计用户模块架构"
#   ./team-dispatch.sh backend-1 "开发登录接口"
#   ./team-dispatch.sh --session architect    # 续聊指定agent
#   ./team-dispatch.sh --list                # 列出所有agent
#===============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Agent列表
AGENTS=(
  "architect:张欣怡:系统架构师"
  "dba:周嘉诚:数据库设计师"
  "backend-1:陈启明:后端开发"
  "backend-2:王浩然:后端开发"
  "backend-3:赵文杰:后端开发"
  "frontend-1:李思雨:前端开发"
  "frontend-2:周晓明:前端开发"
  "frontend-3:林雅婷:前端开发"
  "ucd:吴俊杰:UCD设计师"
  "qa-functional:郑晓彤:功能测试"
  "qa-performance:孙美玲:性能测试"
  "devops:黄志远:运维"
  "requirements-analyst:吴雪梅:需求分析师"
)

# Agent映射
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

# Agent角色映射
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

# Agent别名
declare -A AGENT_ALIASES=(
  ["架构师"]="architect"
  ["张欣怡"]="architect"
  ["dba"]="dba"
  ["周嘉诚"]="dba"
  ["后端1"]="backend-1"
  ["陈启明"]="backend-1"
  ["后端2"]="backend-2"
  ["王浩然"]="backend-2"
  ["后端3"]="backend-3"
  ["赵文杰"]="backend-3"
  ["前端1"]="frontend-1"
  ["李思雨"]="frontend-1"
  ["前端2"]="frontend-2"
  ["周晓明"]="frontend-2"
  ["前端3"]="frontend-3"
  ["林雅婷"]="frontend-3"
  ["ucd"]="ucd"
  ["吴俊杰"]="ucd"
  ["测试"]="qa-functional"
  ["郑晓彤"]="qa-functional"
  ["性能"]="qa-performance"
  ["孙美玲"]="qa-performance"
  ["运维"]="devops"
  ["黄志远"]="devops"
  ["需求"]="requirements-analyst"
  ["吴雪梅"]="requirements-analyst"
  # 角色别名
  ["后端"]="backend-1"
  ["前端"]="frontend-1"
  ["测试组"]="qa-functional"
)

# 打印用法
usage() {
  echo -e "${BLUE}团队 Agent 调度脚本${NC}"
  echo ""
  echo "用法: $0 [选项] [agent] [任务描述]"
  echo ""
  echo "选项:"
  echo "  --list, -l              列出所有Agent"
  echo "  --session, -s <agent>   查看/续聊指定Agent的session"
  echo "  --new, -n <agent>       新建指定Agent的session"
  echo "  --status                查看所有Agent状态"
  echo "  --help, -h              显示帮助"
  echo ""
  echo "示例:"
  echo "  $0 architect '设计用户模块架构'"
  echo "  $0 后端1 '开发登录接口'"
  echo "  $0 -s architect"
  echo "  $0 -l"
  echo ""
  echo "可用Agent (共 ${#AGENTS[@]} 个):"
  for info in "${AGENTS[@]}"; do
    IFS=':' read -r id name role <<< "$info"
    echo "  $id ($name - $role)"
  done
}

# 解析agent别名
resolve_agent() {
  local input="$1"
  if [[ -n "${AGENT_ALIASES[$input]}" ]]; then
    echo "${AGENT_ALIASES[$input]}"
  else
    echo "$input"
  fi
}

# 列出所有Agent
list_agents() {
  echo -e "${BLUE}=== 徐钊研发团队 Agent 列表 ===${NC}\n"
  printf "%-22s %-10s %-15s\n" "Agent ID" "名字" "角色"
  printf "%-22s %-10s %-15s\n" "--------" "----" "----"
  for info in "${AGENTS[@]}"; do
    IFS=':' read -r id name role <<< "$info"
    printf "%-22s %-10s %-15s\n" "$id" "$name" "$role"
  done
}

# 查看Agent状态
agent_status() {
  echo -e "${BLUE}=== Agent Session 状态 ===${NC}\n"
  hermes sessions list 2>/dev/null | head -20 || echo "无session记录"
}

# 新建session
new_session() {
  local agent="$1"
  shift
  local task="$*"
  
  if [[ -z "$agent" ]]; then
    echo -e "${RED}错误: 请指定Agent${NC}"
    usage
    exit 1
  fi
  
  agent=$(resolve_agent "$agent")
  
  echo -e "${GREEN}正在启动 ${AGENT_NAMES[$agent]:-$agent}...${NC}"
  if [[ -n "$task" ]]; then
    echo -e "${YELLOW}任务: $task${NC}"
    echo ""
    hermes --profile "$agent" chat -q "$task"
  else
    hermes --profile "$agent" chat
  fi
}

# 续聊session
continue_session() {
  local agent="$1"
  
  if [[ -z "$agent" ]]; then
    echo -e "${RED}错误: 请指定Agent${NC}"
    usage
    exit 1
  fi
  
  agent=$(resolve_agent "$agent")
  
  echo -e "${GREEN}正在连接 ${AGENT_NAMES[$agent]:-$agent} 的session...${NC}"
  hermes --continue "$agent" chat
}

# 执行任务
dispatch() {
  local agent="$1"
  shift
  local task="$*"
  
  if [[ -z "$agent" ]]; then
    echo -e "${RED}错误: 请指定Agent${NC}"
    usage
    exit 1
  fi
  
  if [[ -z "$task" ]]; then
    echo -e "${RED}错误: 请提供任务描述${NC}"
    usage
    exit 1
  fi
  
  agent=$(resolve_agent "$agent")
  
  echo -e "${GREEN}调度 ${AGENT_NAMES[$agent]:-$agent} (${AGENT_ROLES[$agent]})${NC}"
  echo -e "${YELLOW}任务: $task${NC}"
  echo ""
  
  hermes --profile "$agent" chat -q "$task"
}

# 主逻辑
case "${1:-}" in
  --list|-l)
    list_agents
    ;;
  --status)
    agent_status
    ;;
  --session|-s)
    continue_session "$2"
    ;;
  --new|-n)
    new_session "${@:2}"
    ;;
  --help|-h)
    usage
    ;;
  "")
    usage
    ;;
  *)
    dispatch "$@"
    ;;
esac
