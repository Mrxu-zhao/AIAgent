# Control Plane 主线可靠性治理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `control_plane` 增加 Hermes 健康检查、配置显式刷新、持久总线跨进程锁和兼容层主线收敛能力，修复实战中暴露的 `not configured`、配置视图不一致和多进程状态覆盖问题。

**Architecture:** 以 `.hermes/team/control_plane/` 为唯一可靠性主线，新增 `hermes_health.py` 和 `file_lock.py` 两个基础模块；`config.py`、`providers/hermes.py`、`persistent_bus.py`、`cli.py` 在此基础上增强；`调度框架` 兼容层只调用主线组件，不再自建新逻辑。

**Tech Stack:** Python 3, dataclasses, pathlib, json, subprocess, tempfile, unittest, unittest.mock

---

## 文件结构总览

```text
.hermes/team/control_plane/
├── config.py                         # 增加缓存清理与显式 reload
├── hermes_health.py                  # 新增：Hermes 健康检查
├── file_lock.py                      # 新增：跨进程锁与原子写
├── persistent_bus.py                 # 接入文件锁与锁内重载
├── providers/
│   ├── hermes.py                     # 接入健康检查并分层错误
│   └── registry.py                   # 保持 provider 构建一致
├── adapters.py                       # 透传 provider 健康诊断
└── cli.py                            # 新增 hermes-health 和执行前预检

.hermes/team/调度框架/core/
├── message_bus.py                    # 兼容层继续委托主线 bus
└── monitor.py                        # 展示主线健康摘要

tests/control_plane/
├── test_hermes_health.py             # 新增：健康检查测试
├── test_file_lock.py                 # 新增：文件锁/原子写测试
├── test_persistent_bus_concurrency.py # 新增：多实例写入一致性测试
└── 现有相关测试文件                    # 修改以覆盖 CLI / config reload
```

---

### Task 1: 配置刷新能力

**Files:**
- Modify: `.hermes/team/control_plane/config.py`
- Test: `tests/control_plane/test_config.py` 或新增 `tests/control_plane/test_config_reload.py`

- [ ] **Step 1: 写失败测试**

```python
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from config import (
    clear_control_plane_config_cache,
    load_control_plane_config,
    reload_control_plane_config,
)


class ControlPlaneConfigReloadTests(unittest.TestCase):
    def tearDown(self):
        clear_control_plane_config_cache()

    def test_reload_picks_up_environment_override(self):
        clear_control_plane_config_cache()
        with patch.dict(os.environ, {"HERMES_COMMAND": "hermes-a"}, clear=False):
            config_a = load_control_plane_config()
        with patch.dict(os.environ, {"HERMES_COMMAND": "hermes-b"}, clear=False):
            config_b = reload_control_plane_config()
        self.assertEqual(config_a.executors["hermes"]["command"], "hermes-a")
        self.assertEqual(config_b.executors["hermes"]["command"], "hermes-b")

    def test_reload_picks_up_override_file_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps({"default_executor": "hermes"}), encoding="utf-8")
            clear_control_plane_config_cache()
            first = load_control_plane_config(str(config_path))
            config_path.write_text(json.dumps({"default_executor": "openclaw"}), encoding="utf-8")
            second = reload_control_plane_config(str(config_path))
        self.assertEqual(first.default_executor, "hermes")
        self.assertEqual(second.default_executor, "openclaw")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_config_reload -v`
Expected: FAIL，提示 `clear_control_plane_config_cache` 或 `reload_control_plane_config` 不存在。

- [ ] **Step 3: 写最小实现**

```python
def clear_control_plane_config_cache() -> None:
    load_control_plane_config.cache_clear()


def reload_control_plane_config(config_path: Optional[str] = None) -> ControlPlaneConfig:
    clear_control_plane_config_cache()
    return load_control_plane_config(config_path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_config_reload -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/config.py tests/control_plane/test_config_reload.py
git commit -m "feat: add control plane config reload helpers"
```

---

### Task 2: Hermes 健康检查基础模块

**Files:**
- Create: `.hermes/team/control_plane/hermes_health.py`
- Test: `tests/control_plane/test_hermes_health.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from hermes_health import check_hermes_health


class HermesHealthTests(unittest.TestCase):
    @patch("hermes_health.subprocess.run")
    def test_marks_missing_command(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        report = check_hermes_health("missing-hermes")
        self.assertFalse(report.ok)
        self.assertEqual(report.status, "command_missing")

    @patch("hermes_health.subprocess.run")
    def test_marks_not_configured(self, mock_run):
        mock_run.side_effect = [
            type("R", (), {"stdout": "chat team", "stderr": "", "returncode": 0})(),
            type("R", (), {"stdout": "Model: (not set)", "stderr": "not configured", "returncode": 1})(),
        ]
        report = check_hermes_health("hermes")
        self.assertFalse(report.ok)
        self.assertEqual(report.status, "not_configured")
        self.assertIn("not configured", report.message.lower())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_hermes_health -v`
Expected: FAIL，提示 `hermes_health` 模块不存在。

- [ ] **Step 3: 写最小实现**

```python
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class HermesHealthReport:
    ok: bool
    status: str
    command: str
    available_commands: List[str] = field(default_factory=list)
    message: str = ""
    details: Dict[str, object] = field(default_factory=dict)


def _extract_commands(output: str) -> List[str]:
    return sorted(set(re.findall(r"[a-z][a-z0-9-]+", output.lower())))


def check_hermes_health(command: str, probe_args=None, status_args=None) -> HermesHealthReport:
    probe_args = list(probe_args or ["--help"])
    status_args = list(status_args or ["status"])
    try:
        probe = subprocess.run(
            [command, *probe_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return HermesHealthReport(False, "command_missing", command, message=f"command not found: {command}")
    available = _extract_commands(f"{probe.stdout}\n{probe.stderr}")
    status = subprocess.run(
        [command, *status_args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    combined = f"{status.stdout}\n{status.stderr}".lower()
    if "not configured" in combined or "model: (not set)" in combined:
        return HermesHealthReport(
            False,
            "not_configured",
            command,
            available_commands=available,
            message=combined.strip() or "hermes not configured",
            details={"returncode": status.returncode},
        )
    return HermesHealthReport(
        True,
        "healthy",
        command,
        available_commands=available,
        message="hermes is healthy",
        details={"probe_returncode": probe.returncode, "status_returncode": status.returncode},
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_hermes_health -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/hermes_health.py tests/control_plane/test_hermes_health.py
git commit -m "feat: add hermes health checks"
```

---

### Task 3: HermesProvider 接入健康检查

**Files:**
- Modify: `.hermes/team/control_plane/providers/hermes.py`
- Test: `tests/control_plane/test_hermes_health.py` 或新增 `tests/control_plane/test_hermes_provider.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from providers.hermes import HermesProvider


class HermesProviderTests(unittest.TestCase):
    @patch("providers.hermes.check_hermes_health")
    def test_build_dispatch_command_fails_fast_when_not_configured(self, mock_check):
        mock_check.return_value = type(
            "Report",
            (),
            {"ok": False, "status": "not_configured", "message": "not configured", "available_commands": []},
        )()
        provider = HermesProvider(command="hermes", auto_detect=True)
        with self.assertRaises(ValueError) as ctx:
            provider.build_dispatch_command("architect", "设计模块")
        self.assertIn("not_configured", str(ctx.exception))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_hermes_provider -v`
Expected: FAIL，当前 provider 不会在此处给出结构化错误。

- [ ] **Step 3: 写最小实现**

```python
from hermes_health import check_hermes_health


class HermesProvider(ExecutorProvider):
    ...
    def _validate_health(self):
        report = check_hermes_health(self.command, probe_args=self.probe_args)
        if not report.ok:
            raise ValueError(f"hermes_health:{report.status}:{report.message}")
        return report

    def build_dispatch_command(self, agent_id: str, task: str):
        self._validate_health()
        template = self._resolve_dispatch_template()
        ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_hermes_provider -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/providers/hermes.py tests/control_plane/test_hermes_provider.py
git commit -m "feat: validate hermes health before dispatch"
```

---

### Task 4: 跨进程文件锁与原子写

**Files:**
- Create: `.hermes/team/control_plane/file_lock.py`
- Test: `tests/control_plane/test_file_lock.py`

- [ ] **Step 1: 写失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from file_lock import atomic_write_text


class FileLockTests(unittest.TestCase):
    def test_atomic_write_replaces_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("old", encoding="utf-8")
            atomic_write_text(path, "new")
            self.assertEqual(path.read_text(encoding="utf-8"), "new")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_file_lock -v`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 写最小实现**

```python
from __future__ import annotations

import os
import time
from pathlib import Path


class FileLock:
    def __init__(self, path: Path, poll_interval: float = 0.05):
        self.path = Path(path)
        self.poll_interval = poll_interval
        self._fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                time.sleep(self.poll_interval)

    def __exit__(self, exc_type, exc, tb):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        if self.path.exists():
            self.path.unlink()


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding=encoding)
    os.replace(temp_path, path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_file_lock -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/file_lock.py tests/control_plane/test_file_lock.py
git commit -m "feat: add control plane file lock helpers"
```

---

### Task 5: PersistentMessageBus 接入锁和锁内重载

**Files:**
- Modify: `.hermes/team/control_plane/persistent_bus.py`
- Test: `tests/control_plane/test_persistent_bus_concurrency.py`

- [ ] **Step 1: 写失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from persistent_bus import PersistentMessageBus


class PersistentBusConcurrencyTests(unittest.TestCase):
    def test_two_instances_merge_registered_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            bus_a = PersistentMessageBus(base_dir)
            bus_b = PersistentMessageBus(base_dir)
            bus_a.register_agent("architect")
            bus_b.register_agent("backend-1")
            bus_c = PersistentMessageBus(base_dir)
            stats = bus_c.stats()
        self.assertIn("architect", stats["pending_counts"])
        self.assertIn("backend-1", stats["pending_counts"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_persistent_bus_concurrency -v`
Expected: FAIL，当前实现可能只保留最后一次写入的 agent 状态。

- [ ] **Step 3: 写最小实现**

```python
from file_lock import FileLock, atomic_write_text


class PersistentMessageBus:
    def __init__(...):
        ...
        self._lock_path = self.base_dir / ".bus.lock"

    def _with_disk_state(self, mutator):
        with FileLock(self._lock_path):
            self.load_from_disk()
            mutator()
            self._persist_state_locked()

    def register_agent(self, agent_id: str):
        def _mutate():
            self._registered_agents.add(agent_id)
            self._pending.setdefault(agent_id, [])
            self._unacked.setdefault(agent_id, {})
        self._with_disk_state(_mutate)

    def _persist_state_locked(self):
        payload = {...}
        atomic_write_text(
            self._state_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_persistent_bus_concurrency -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/persistent_bus.py tests/control_plane/test_persistent_bus_concurrency.py
git commit -m "feat: harden persistent message bus with file locks"
```

---

### Task 6: CLI 增加显式诊断入口

**Files:**
- Modify: `.hermes/team/control_plane/cli.py`
- Test: `tests/control_plane/test_framework_cli.py` 或新增 `tests/control_plane/test_hermes_health_cli.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import cli


class HermesHealthCliTests(unittest.TestCase):
    @patch("cli.check_hermes_health")
    def test_hermes_health_command_returns_report(self, mock_check):
        mock_check.return_value = type(
            "Report",
            (),
            {"ok": False, "status": "not_configured", "message": "not configured", "available_commands": ["chat"]},
        )()
        result = cli._run_hermes_health_command(type("Args", (), {"json": False})())
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_configured")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_hermes_health_cli -v`
Expected: FAIL，CLI 入口不存在。

- [ ] **Step 3: 写最小实现**

```python
from hermes_health import check_hermes_health


def _run_hermes_health_command(args):
    config = load_control_plane_config()
    hermes_conf = config.executors.get("hermes", {})
    report = check_hermes_health(str(hermes_conf.get("command", "hermes")))
    payload = {
        "ok": report.ok,
        "status": report.status,
        "message": report.message,
        "available_commands": list(report.available_commands),
    }
    if not getattr(args, "json", False):
        print(f"[{payload['status']}] {payload['message']}")
    return payload
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_hermes_health_cli -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/cli.py tests/control_plane/test_hermes_health_cli.py
git commit -m "feat: add hermes health cli command"
```

---

### Task 7: 兼容层主线收敛

**Files:**
- Modify: `.hermes/team/调度框架/core/message_bus.py`
- Modify: `.hermes/team/调度框架/core/monitor.py`
- Test: 现有兼容层回归测试；必要时新增 `tests/control_plane/test_monitor_dashboard.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from 调度框架.core.monitor import Monitor


class MonitorDashboardTests(unittest.TestCase):
    @patch("调度框架.core.monitor.check_hermes_health")
    def test_dashboard_contains_hermes_health_summary(self, mock_check):
        mock_check.return_value = type(
            "Report",
            (),
            {"ok": True, "status": "healthy", "message": "ok", "available_commands": ["chat", "team"]},
        )()
        monitor = Monitor()
        payload = monitor.get_dashboard_data()
        self.assertIn("hermes_health", payload)
        self.assertEqual(payload["hermes_health"]["status"], "healthy")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_monitor_dashboard -v`
Expected: FAIL，dashboard 还未暴露主线健康摘要。

- [ ] **Step 3: 写最小实现**

```python
from hermes_health import check_hermes_health


class Monitor:
    ...
    def _collect_hermes_health(self) -> Dict[str, object]:
        config = load_control_plane_config()
        hermes_conf = config.executors.get("hermes", {})
        report = check_hermes_health(str(hermes_conf.get("command", "hermes")))
        return {
            "ok": report.ok,
            "status": report.status,
            "message": report.message,
            "available_commands": list(report.available_commands),
        }

    def get_dashboard_data(self) -> Dict:
        ...
        payload["hermes_health"] = self._collect_hermes_health()
        return payload
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_monitor_dashboard -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/调度框架/core/monitor.py tests/control_plane/test_monitor_dashboard.py
git commit -m "feat: surface hermes health in dashboard"
```

---

### Task 8: 全量回归与文档对齐

**Files:**
- Modify: 相关 README / 文档
- Validate: 所有已修改文件

- [ ] **Step 1: 运行定向测试**

Run: `python -m unittest tests.control_plane.test_config_reload tests.control_plane.test_hermes_health tests.control_plane.test_hermes_provider tests.control_plane.test_file_lock tests.control_plane.test_persistent_bus_concurrency tests.control_plane.test_hermes_health_cli tests.control_plane.test_monitor_dashboard -v`
Expected: PASS

- [ ] **Step 2: 运行 control_plane 全量回归**

Run: `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`
Expected: PASS

- [ ] **Step 3: 运行 Ruff 检查**

Run: `python -m ruff check .hermes/team/control_plane .hermes/team/调度框架/core .hermes/team/调度框架/cli/team-cli.py tests/control_plane`
Expected: All checks passed

- [ ] **Step 4: 更新文档**

```markdown
- 在 `.hermes/team/control_plane/README.md` 或相关运行文档中补充：
  - `hermes-health` 用法
  - 配置 reload 语义
  - 持久总线多进程一致性约束
  - 兼容层已收敛到主线组件
```

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/README.md docs/superpowers/specs/2026-05-18-control-plane-mainline-reliability-design.md docs/superpowers/plans/2026-05-18-control-plane-mainline-reliability.md
git commit -m "docs: document control plane reliability hardening"
```

---

## 完成定义

- [ ] `config.py` 具备显式 reload / clear 能力
- [ ] `hermes_health.py` 输出结构化健康报告
- [ ] `HermesProvider` 在派发前执行健康检查
- [ ] `PersistentMessageBus` 使用文件锁与原子写
- [ ] CLI 暴露显式 `hermes` 健康诊断入口
- [ ] `调度框架` 兼容层展示并复用主线健康能力
- [ ] 新增测试全部通过
- [ ] `tests/control_plane` 全量回归通过
- [ ] Ruff 检查通过
