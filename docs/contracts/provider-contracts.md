# Provider Contracts

## 真源

- Hermes provider：`.hermes/team/control_plane/providers/hermes.py`
- OpenClaw provider：`.hermes/team/control_plane/providers/openclaw.py`
- 注册入口：`.hermes/team/control_plane/providers/registry.py`

外部说明中可简称为 `providers/hermes.py` 与 `providers/openclaw.py`。

## 调度命令格式

- HermesProvider 默认构造：`hermes team dispatch -a <agent_id> -t <task>`
- OpenClawProvider 默认构造：`openclaw dispatch --dry-run --agent <agent_id> --task <task>`
- 当 OpenClaw 配置为 live 模式时，`--dry-run` 切换为 `--execute`

## executor_backend 到 provider 的映射

- `executor_backend=hermes` 时，使用 `HermesProvider`
- `executor_backend=openclaw` 时，使用 `OpenClawProvider`
- 默认 provider 由 `config.py` 中的 `default_executor` 和 `executors` 配置决定

## backend 选择优先级

- `selected_backend` 表示调度器最终落下的后端选择
- `target_backend` 表示 handoff payload 中声明的目标后端
- 当二者同时存在时，执行面优先读取 `selected_backend`，并保留 `target_backend` 作为原始意图
- `backend_reason` 用于记录为什么最终没有直接采用 `target_backend`

## 兼容边界

- 当前 `Hermes` 为主执行路径。
- 当前 `OpenClaw` 已有 dry-run MVP，真实 live 执行仍需结合治理能力逐步放开。
