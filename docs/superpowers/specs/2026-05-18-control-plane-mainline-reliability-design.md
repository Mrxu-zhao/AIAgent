# Control Plane 主线可靠性治理设计文档

> **日期**: 2026-05-18
> **目标**: 解决 `hermes not configured`、配置不刷新、多进程状态竞争和兼容层分叉导致的主线可靠性问题
> **范围**: `control_plane` 主线增强 + `调度框架` 薄适配收敛，不扩展业务能力，不重做整套架构

---

## 1. 背景与问题

最近一次多 Agent 实战交付中，`requirements-analyst` 与 `ucd` 阶段可以正常执行，随后 `architect`、`dba`、`backend-1` 等阶段开始持续出现 `hermes not configured`。同一轮实战还暴露出以下框架级问题：

- `HermesProvider` 只探测命令是否存在与子命令是否可用，不区分“命令不存在”“CLI 可启动但未配置”“模板未配置”“执行期失败”。
- `load_control_plane_config()` 使用 `lru_cache`，运行期修改 `config.json` 或环境变量后，进程内不会自动刷新配置。
- `PersistentMessageBus` 基于 `messages.jsonl` 追加写入和 `state.json` 整体重写，但没有跨进程文件锁；多个后台进程同时运行时，容易出现状态覆盖和视图不一致。
- `MessageBus`、`Monitor`、`RecoveryManager` 仍采用兼容层进程内单例，dashboard 与总线状态天然偏向“单进程正确”，在多进程实战中不稳健。
- 兼容层直接依赖这些进程内对象，导致主线 `control_plane` 与历史 `调度框架` 都在维护部分运行时状态，主线约束不够清晰。

这些问题已经影响仓库主线目标：`control_plane` 应该是当前推荐入口，但实战中的执行可靠性、配置一致性和故障诊断还没有形成可验证闭环。

---

## 2. 设计目标

### 2.1 目标

本次治理要完成以下四件事：

1. 让 `hermes` 执行前检查具备明确的健康分层，能把“未安装”“未配置”“模板缺失”“命令执行失败”区分开。
2. 让 `control_plane` 配置具备显式刷新能力，默认行为稳定，必要时可由 CLI/兼容层主动刷新。
3. 让消息总线状态持久化在多进程下具备基本一致性，避免 `state.json` 被最后写入者覆盖。
4. 让兼容层向主线收敛：运行时可靠性逻辑、健康检查、配置刷新、文件锁都放在 `control_plane`，`调度框架` 只保留适配调用。

### 2.2 成功标准

- `HermesProvider` 或其上层调用方能返回结构化健康状态，而不是只在异常分支抛模糊错误。
- CLI 能提供可复用的 `hermes` 健康检查入口，并在执行前输出可解释诊断。
- 配置读取新增显式缓存清理/刷新路径，测试覆盖环境变量覆盖和文件覆盖刷新。
- `PersistentMessageBus` 在并发读写下不再通过裸 `write_text()` 覆盖共享状态，改为带文件锁与原子替换的持久化路径。
- 兼容层单例不再自行发散新逻辑，而是通过主线公共组件读取健康状态、配置和持久总线。
- 新增测试覆盖上述关键路径，并保持原有 `control_plane` 回归基线不退化。

### 2.3 非目标

- 不引入外部数据库或消息队列。
- 不把兼容层一次性删除或完全迁移。
- 不改造 Hermes CLI 自身实现，只增强本仓库对 Hermes 的探测、适配和报错。
- 不处理项目业务功能，例如 `Happy Letters` 前后端逻辑。

---

## 3. 主线收敛约束

本次设计遵循以下约束：

- **主线优先**: 新增可靠性能力必须放在 `.hermes/team/control_plane/`。
- **兼容层薄适配**: `.hermes/team/调度框架/` 只负责调用主线能力，不再复制健康检查、配置缓存和持久化细节。
- **最小迁移成本**: 不改变现有 CLI 主命令语义，新增的是更强的前置检查、诊断和一致性保障。
- **可验证优先**: 每个设计点都必须能通过单元测试或小范围集成测试复现和验证。

---

## 4. 方案对比

### 4.1 方案 A: 局部补丁

- 在 `HermesProvider` 中继续加条件分支。
- 在 `config.py` 中手工去掉 `lru_cache`。
- 在 `PersistentMessageBus` 中补少量 try/except。

优点：

- 改动最小。

缺点：

- 逻辑仍然分散。
- 兼容层和主线都可能继续各修各的。
- 难形成统一诊断与测试面。

### 4.2 方案 B: 适度重构并收敛主线

- 在 `control_plane` 新增统一的 Hermes 健康检查组件。
- 在 `config.py` 中保留缓存，但补 `clear/reload` 能力和可控入口。
- 在 `persistent_bus.py` 中引入主线级文件锁与原子写工具。
- 兼容层改为消费这些主线组件。

优点：

- 能同时解决可靠性与主线收敛问题。
- 风险可控，不需要大迁移。
- 测试边界清晰。

缺点：

- 需要调整若干入口文件。

### 4.3 方案 C: 大规模平台化重构

- 彻底拆分运行时、监控、消息总线和 CLI。
- 全量替换兼容层单例模型。

优点：

- 长期形态更理想。

缺点：

- 超出本轮故障治理范围。
- 回归风险高，周期长。

### 4.4 推荐方案

选择 **方案 B: 适度重构并收敛主线**。

原因：

- 它正好符合当前用户要求的“主线收敛”。
- 它能覆盖这次实战暴露的四个核心问题，而不把任务扩大为平台重写。
- 它保留现有运行方式和主要命令接口，适合本仓库当前阶段。

---

## 5. 设计概览

### 5.1 模块划分

本次新增或调整以下主线模块：

- `control_plane/hermes_health.py`
  - 统一执行 `hermes` 健康检查。
  - 输出结构化状态，例如 `command_missing`、`not_configured`、`dispatch_template_missing`、`healthy`。
- `control_plane/config.py`
  - 保留默认配置构建逻辑。
  - 新增显式 `clear_control_plane_config_cache()` 与 `reload_control_plane_config()`。
- `control_plane/file_lock.py`
  - 提供跨进程文件锁和原子写帮助函数。
- `control_plane/persistent_bus.py`
  - 使用文件锁与原子替换写入共享状态。
  - 在关键读写前后做磁盘刷新，降低多进程覆盖风险。
- `control_plane/providers/hermes.py`
  - 与 `hermes_health.py` 对接。
  - 派发前先做健康检查，并把结果映射为更明确的错误。
- `control_plane/cli.py`
  - 新增 `hermes-health` 或等价入口，供显式诊断和执行前预检复用。
- `调度框架/core/message_bus.py`
  - 不再直接扩展持久化细节，只继续委托给主线总线。
- `调度框架/core/monitor.py`
  - 监控与 dashboard 读取主线级快照/诊断结果，而不是自行维护另一套可靠性判断。

### 5.2 数据流变化

#### 当前

```text
dispatch/execute
-> HermesProvider 仅 probe --help
-> build dispatch command
-> command_runner 执行
-> 失败时 stderr/returncode 透传
```

#### 目标

```text
dispatch/execute
-> hermes_health.check(command, config)
-> 返回结构化健康状态
-> 健康则构造 dispatch command
-> command_runner 执行
-> 若失败则区分为配置问题 / 模板问题 / 进程退出 / 命令缺失
-> CLI、executor、monitor 统一消费该诊断
```

---

## 6. 详细设计

### 6.1 Hermes 健康检查

新增 `HermesHealthReport` 数据结构，建议字段：

- `ok: bool`
- `status: str`
- `command: str`
- `available_commands: list[str]`
- `message: str`
- `details: dict[str, object]`

状态枚举至少包括：

- `healthy`
- `command_missing`
- `not_configured`
- `probe_failed`
- `dispatch_template_missing`

建议检查顺序：

1. 执行 `hermes --help`，判断命令是否存在。
2. 若命令存在，解析可用子命令集合。
3. 执行轻量级状态探针，例如 `hermes status` 或仓库已知的安全探针命令；若输出包含 `not configured`、`model: (not set)` 等关键字，则标记为 `not_configured`。
4. 校验当前配置能否映射到有效 `dispatch_profiles`。
5. 生成结构化报告。

`HermesProvider` 不再把“探测不到可用模板”直接等同于全部未配置，而是：

- 先拿健康报告。
- 若 `status != healthy`，抛出带稳定错误码的异常或返回结构化错误。
- 只有在健康且模板仍缺失时，才报 `dispatch_template_missing`。

### 6.2 配置缓存与刷新

`config.py` 当前缓存策略的问题不在于“用了缓存”，而在于“没有受控刷新入口”。设计调整为：

- 保留 `load_control_plane_config()` 作为默认入口。
- 新增：
  - `clear_control_plane_config_cache()`
  - `reload_control_plane_config(config_path: Optional[str] = None)`
- CLI 显式诊断命令和兼容层入口在需要重新读取时调用刷新接口。
- 测试保证：
  - 环境变量 `HERMES_COMMAND` 修改后，通过 reload 可见。
  - 覆盖文件 `config.json` 修改后，通过 reload 可见。
  - 普通热路径仍复用缓存，不引入无意义重复解析。

### 6.3 文件锁与原子写

新增 `file_lock.py`，提供：

- `FileLock(path)`
- `locked_json_update(path, update_fn)`
- `atomic_write_text(path, content)`

Windows 下优先使用标准库能力实现锁文件方案，要求：

- 同一时刻只有一个进程写 `state.json`。
- `messages.jsonl` 追加与 `state.json` 刷新共用统一锁域。
- 写入时先写临时文件，再原子替换目标文件。

### 6.4 PersistentMessageBus 一致性

调整 `PersistentMessageBus`：

- 初始化时加载磁盘状态仍保留。
- `send()`、`receive()`、`ack()`、`requeue()`、`register_agent()`、`unregister_agent()` 的持久化路径改为：
  - 获取跨进程锁
  - 重载磁盘最新状态
  - 在内存上合并变更
  - 原子写回状态
- `messages.jsonl` 追加写入也纳入同一锁，避免 `history` 与 `state` 偏离。
- `load_from_disk()` 保持只负责装载，不包含写入副作用。

这里不追求分布式一致性，只要达到“单机多进程下基本正确、不被最后写入者轻易覆盖”的目标即可。

### 6.5 兼容层收敛

兼容层不新建第二套可靠性实现，只做两件事：

- `message_bus.py`
  - 继续作为兼容 API 外观。
  - 所有持久化安全与配置刷新逻辑都委托主线模块。
- `monitor.py`
  - dashboard 中新增主线 Hermes 健康摘要，例如最近一次检查状态、默认执行器命令、配置来源。
  - 不在兼容层新增独立配置或探测缓存。

这意味着故障排查入口会从“兼容层各看各的”收敛为“主线统一判断，兼容层只展示结果”。

### 6.6 CLI 诊断与执行前预检

在 `control_plane/cli.py` 新增显式命令，用于：

- 单独检查 `hermes` 健康状态。
- 输出结构化 JSON 或摘要文本。
- 在 `dispatch --execute`、`control-plane-run` 这类真实执行路径前复用。

执行策略：

- 若健康状态为 `healthy`，照常执行。
- 若为 `not_configured`，给出明确建议，例如当前命令、探针输出摘要、建议检查配置来源。
- 若为 `command_missing`，提示 `HERMES_COMMAND` 或 venv 路径问题。
- 若为 `dispatch_template_missing`，提示检查 `executors.hermes.dispatch_profiles`。

### 6.7 可观测性

本轮不大改 metrics 框架，只补最小可靠性指标：

- 最近一次 `hermes` 健康状态
- 健康检查失败次数
- 文件锁等待/冲突次数
- 持久总线写入失败次数

dashboard 可展示简化摘要，不要求新建完整监控页面。

---

## 7. 文件变更清单

### 7.1 新增文件

- `.hermes/team/control_plane/hermes_health.py`
- `.hermes/team/control_plane/file_lock.py`
- `tests/control_plane/test_hermes_health.py`
- `tests/control_plane/test_file_lock.py`
- `tests/control_plane/test_persistent_bus_concurrency.py`

### 7.2 修改文件

- `.hermes/team/control_plane/config.py`
- `.hermes/team/control_plane/providers/hermes.py`
- `.hermes/team/control_plane/providers/registry.py`
- `.hermes/team/control_plane/adapters.py`
- `.hermes/team/control_plane/cli.py`
- `.hermes/team/control_plane/persistent_bus.py`
- `.hermes/team/调度框架/core/message_bus.py`
- `.hermes/team/调度框架/core/monitor.py`
- 相关 README 或运行文档

---

## 8. 测试设计

### 8.1 单元测试

- `test_hermes_health.py`
  - 模拟命令缺失
  - 模拟 `--help` 正常但 `status` 输出 `not configured`
  - 模拟模板缺失
  - 模拟健康路径
- `test_config_reload`
  - 修改环境变量与覆盖文件，验证 `reload` 生效
- `test_file_lock.py`
  - 验证锁文件互斥
  - 验证原子写不会留下半文件

### 8.2 集成测试

- `test_persistent_bus_concurrency.py`
  - 两个 bus 实例在同一目录下顺序模拟多进程并发写
  - 验证 `registered_agents`、`pending`、`unacked` 不被覆盖
- CLI 诊断测试
  - 验证健康命令输出状态码与文本摘要

### 8.3 回归测试

- 运行 `tests/control_plane` 全量回归
- 运行与 `调度框架` 兼容入口相关的现有测试
- Ruff 检查最近修改文件

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 健康探针命令选型不稳 | 误判 `not configured` | 将探针与关键字判断封装并加测试桩 |
| 文件锁实现跨平台细节复杂 | Windows 下锁失效 | 采用最小锁文件协议并补 Windows 环境测试 |
| 配置刷新被滥用 | 热路径性能退化 | 默认仍走缓存，只在显式入口 reload |
| 兼容层改动影响旧命令 | 兼容回归 | 保持接口名称不变，只替换内部实现 |

---

## 10. 完成定义

- [ ] `hermes` 健康检查具备结构化状态输出
- [ ] 执行前预检接入真实执行路径
- [ ] 配置缓存具备显式清理与重载能力
- [ ] `PersistentMessageBus` 使用文件锁与原子写
- [ ] 兼容层通过主线组件复用可靠性逻辑
- [ ] 新增测试覆盖关键可靠性场景
- [ ] 原有主线回归测试不退化
- [ ] 文档明确主线收敛后的使用方式
