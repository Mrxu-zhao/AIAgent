from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    DONE = "done"


class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class KanbanTask:
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee: str = ""
    creator: str = ""
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    deadline: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class KanbanBoard:
    def __init__(self, db_path: str = ".hermes/kanban.db"):
        self.db_path = db_path
        if db_path != ":memory:":
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'todo',
                    priority INTEGER DEFAULT 2,
                    assignee TEXT,
                    creator TEXT,
                    dependencies TEXT,
                    tags TEXT,
                    created_at REAL,
                    updated_at REAL,
                    deadline REAL,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    action TEXT,
                    from_status TEXT,
                    to_status TEXT,
                    actor TEXT,
                    timestamp REAL
                )
                """
            )
            conn.commit()

    def create_task(
        self,
        title: str,
        description: str = "",
        assignee: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        deadline: Optional[float] = None,
    ) -> KanbanTask:
        now = time.time()
        task = KanbanTask(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            assignee=assignee,
            priority=priority,
            dependencies=dependencies or [],
            tags=tags or [],
            created_at=now,
            updated_at=now,
            deadline=deadline,
        )
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    task.id,
                    task.title,
                    task.description,
                    task.status.value,
                    task.priority.value,
                    task.assignee,
                    task.creator,
                    json.dumps(task.dependencies),
                    json.dumps(task.tags),
                    task.created_at,
                    task.updated_at,
                    task.deadline,
                    json.dumps(task.metadata),
                ),
            )
            conn.commit()
        return task

    def move_task(self, task_id: str, new_status: TaskStatus, actor: str = "system") -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return False
            old_status = row[0]
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (new_status.value, time.time(), task_id),
            )
            conn.execute(
                "INSERT INTO task_history (task_id, action, from_status, to_status, actor, timestamp) VALUES (?,?,?,?,?,?)",
                (task_id, "move", old_status, new_status.value, actor, time.time()),
            )
            conn.commit()
        return True

    def get_board_summary(self) -> Dict[str, Any]:
        with closing(self._connect()) as conn:
            summary = {}
            for status in TaskStatus:
                summary[status.value] = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE status = ?",
                    (status.value,),
                ).fetchone()[0]
            summary["total"] = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            return summary
