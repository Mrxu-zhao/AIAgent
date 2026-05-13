#!/bin/bash
# Legacy dispatch entrypoint kept as a thin adapter.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRAMEWORK_CLI="$FRAMEWORK_ROOT/cli/team-cli.py"
CONTROL_PLANE_ROOT="$FRAMEWORK_ROOT/../control_plane"
PYTHON_BIN="${PYTHON_BIN:-python}"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

usage() {
  cat <<EOF
团队 Agent 调度适配脚本

用法:
  $0 --list
  $0 --status
  $0 --session <agent>
  $0 --new <agent> [task]
  $0 <agent> <task>

说明:
  - 调度动作会转发到 cli/team-cli.py dispatch -a
  - agent 别名与列表来自仓库级控制平面配置
EOF
}

resolve_agent() {
  "$PYTHON_BIN" - "$1" "$CONTROL_PLANE_ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[2])
from config import load_control_plane_config

raw = sys.argv[1]
config = load_control_plane_config()
print(config.aliases.get(raw, raw))
PY
}

list_agents() {
  "$PYTHON_BIN" - "$CONTROL_PLANE_ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from config import load_control_plane_config

config = load_control_plane_config()
print("=== 控制平面 Agent 列表 ===")
print(f"{'Agent ID':<22} {'名称':<10} {'角色'}")
for agent_id, agent in config.agents.items():
    print(f"{agent_id:<22} {agent.name:<10} {agent.role}")
PY
}

show_status() {
  exec "$PYTHON_BIN" "$FRAMEWORK_CLI" status
}

continue_session() {
  local agent="${1:-}"
  if [[ -z "$agent" ]]; then
    echo -e "${RED}错误: 请指定Agent${NC}"
    usage
    exit 1
  fi
  agent="$(resolve_agent "$agent")"
  exec hermes --continue "$agent" chat
}

new_session() {
  local agent="${1:-}"
  shift || true
  local task="${*:-}"
  if [[ -z "$agent" ]]; then
    echo -e "${RED}错误: 请指定Agent${NC}"
    usage
    exit 1
  fi
  agent="$(resolve_agent "$agent")"
  if [[ -n "$task" ]]; then
    exec hermes --profile "$agent" chat -q "$task"
  fi
  exec hermes --profile "$agent" chat
}

dispatch() {
  local agent="${1:-}"
  shift || true
  local task="${*:-}"
  if [[ -z "$agent" || -z "$task" ]]; then
    echo -e "${RED}错误: 请同时提供Agent和任务描述${NC}"
    usage
    exit 1
  fi
  agent="$(resolve_agent "$agent")"
  echo -e "${GREEN}转发到统一 CLI: ${agent}${NC}"
  exec "$PYTHON_BIN" "$FRAMEWORK_CLI" dispatch -a "$agent" "$task"
}

case "${1:-}" in
  --list|-l)
    list_agents
    ;;
  --status)
    show_status
    ;;
  --session|-s)
    continue_session "${2:-}"
    ;;
  --new|-n)
    shift
    new_session "$@"
    ;;
  --help|-h|"")
    usage
    ;;
  *)
    dispatch "$@"
    ;;
esac
