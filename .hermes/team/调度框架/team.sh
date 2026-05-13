#!/bin/bash
# Thin adapter for the repository control plane.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_CLI="$SCRIPT_DIR/cli/team-cli.py"
CONTROL_PLANE_CLI="$SCRIPT_DIR/../control_plane/cli.py"
DISPATCH_SCRIPT="$SCRIPT_DIR/scripts/team-dispatch.sh"
TMUX_SCRIPT="$SCRIPT_DIR/tmux/team-tmux.sh"
PYTHON_BIN="${PYTHON_BIN:-python}"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

run_framework_cli() {
  "$PYTHON_BIN" "$FRAMEWORK_CLI" "$@"
}

run_control_plane_cli() {
  "$PYTHON_BIN" "$CONTROL_PLANE_CLI" "$@"
}

print_banner() {
  echo -e "${BLUE}=== 团队入口适配层 ===${NC}"
  echo "主控制平面: $CONTROL_PLANE_CLI"
  echo "兼容 CLI: $FRAMEWORK_CLI"
  echo ""
}

print_menu() {
  echo "  1. 查看团队状态"
  echo "  2. 查看监控仪表盘"
  echo "  3. 调度任务"
  echo "  4. 续聊现有 session"
  echo "  5. tmux 团队视图"
  echo "  6. 运行标准工作流"
  echo "  7. 运行控制平面批次"
  echo "  0. 退出"
  echo ""
}

resume_session() {
  local agent
  read -r -p "请输入 agent id: " agent
  if [[ -n "$agent" ]]; then
    hermes --continue "$agent" chat
  fi
}

dispatch_task() {
  local agent task
  read -r -p "请输入 agent id 或别名: " agent
  read -r -p "请输入任务描述: " task
  if [[ -n "$agent" && -n "$task" ]]; then
    "$DISPATCH_SCRIPT" "$agent" "$task"
  fi
}

main() {
  if [[ $# -gt 0 ]]; then
    case "$1" in
      interactive)
        run_framework_cli interactive
        exit $?
        ;;
      status)
        run_framework_cli status
        exit $?
        ;;
      monitor)
        shift
        run_control_plane_cli monitor "$@"
        exit $?
        ;;
      dispatch|workflow|control-plane-run|validate)
        run_control_plane_cli "$@"
        exit $?
        ;;
      tmux)
        shift
        exec "$TMUX_SCRIPT" "$@"
        ;;
      *)
        run_control_plane_cli "$@"
        exit $?
        ;;
    esac
  fi

  print_banner
  while true; do
    print_menu
    read -r -p "请选择 (0-7): " choice
    case "$choice" in
      1) run_framework_cli status ;;
      2) run_control_plane_cli monitor --dashboard ;;
      3) dispatch_task ;;
      4) resume_session ;;
      5) "$TMUX_SCRIPT" status ;;
      6) run_control_plane_cli workflow --name "legacy-team-menu" ;;
      7) run_control_plane_cli control-plane-run --max-workers 2 ;;
      0) echo -e "${GREEN}再见!${NC}"; exit 0 ;;
      *) echo -e "${RED}无效选择${NC}" ;;
    esac
    echo ""
  done
}

main "$@"
