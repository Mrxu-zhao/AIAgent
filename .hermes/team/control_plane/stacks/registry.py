from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class StackConfig:
    name: str
    templates_dir: str
    commands: Dict[str, str] = field(default_factory=dict)
    file_extensions: List[str] = field(default_factory=list)


STACK_REGISTRY = {
    "backend": {
        "java-spring": StackConfig(
            name="Java Spring Boot",
            templates_dir="stacks/backend/java-spring/templates/",
            commands={"test": "mvn test", "lint": "mvn spotless:check", "build": "mvn package"},
            file_extensions=[".java", ".xml", ".properties", ".yml"],
        ),
        "go-gin": StackConfig(
            name="Go Gin",
            templates_dir="stacks/backend/go-gin/templates/",
            commands={"test": "go test ./...", "lint": "golangci-lint run", "build": "go build"},
            file_extensions=[".go", ".mod"],
        ),
        "python-fastapi": StackConfig(
            name="Python FastAPI",
            templates_dir="stacks/backend/python-fastapi/templates/",
            commands={"test": "pytest", "lint": "ruff check .", "build": "docker build"},
            file_extensions=[".py", ".toml", ".ini"],
        ),
    },
    "frontend": {
        "vue3": StackConfig(
            name="Vue 3",
            templates_dir="stacks/frontend/vue3/templates/",
            commands={"test": "vitest", "lint": "eslint", "build": "vite build"},
            file_extensions=[".vue", ".ts", ".js", ".css"],
        ),
        "react": StackConfig(
            name="React",
            templates_dir="stacks/frontend/react/templates/",
            commands={"test": "jest", "lint": "eslint", "build": "vite build"},
            file_extensions=[".tsx", ".ts", ".css"],
        ),
        "mini-program": StackConfig(
            name="微信小程序",
            templates_dir="stacks/frontend/mini-program/templates/",
            commands={"test": "jest", "lint": "eslint", "build": "npm run build"},
            file_extensions=[".js", ".wxml", ".wxss", ".json"],
        ),
        "harmony-arkts": StackConfig(
            name="鸿蒙 ArkTS",
            templates_dir="stacks/frontend/harmony-arkts/templates/",
            commands={"test": "ohpm test", "lint": "arkts-lint", "build": "hvigor build"},
            file_extensions=[".ets", ".ts", ".json"],
        ),
    },
    "database": {
        "mysql": StackConfig(
            name="MySQL",
            templates_dir="stacks/database/mysql/templates/",
            commands={"test": "mysql -e", "lint": "sqlfluff lint", "build": "flyway migrate"},
            file_extensions=[".sql"],
        ),
        "postgres": StackConfig(
            name="PostgreSQL",
            templates_dir="stacks/database/postgres/templates/",
            commands={"test": "psql -f", "lint": "sqlfluff lint", "build": "flyway migrate"},
            file_extensions=[".sql"],
        ),
        "redis": StackConfig(
            name="Redis",
            templates_dir="stacks/database/redis/templates/",
            commands={"test": "redis-cli", "lint": "redis-lint", "build": "redis-cli"},
            file_extensions=[".redis", ".txt"],
        ),
    },
}


def get_stack_config(category: str, stack_id: str) -> StackConfig:
    if category not in STACK_REGISTRY:
        raise ValueError(f"unknown category: {category}")
    if stack_id not in STACK_REGISTRY[category]:
        available = ", ".join(STACK_REGISTRY[category].keys())
        raise ValueError(f"unknown stack '{stack_id}' in {category}. Available: {available}")
    return STACK_REGISTRY[category][stack_id]


def list_stacks(category: str | None = None) -> Dict[str, List[str]]:
    if category:
        return {category: list(STACK_REGISTRY.get(category, {}).keys())}
    return {cat: list(stacks.keys()) for cat, stacks in STACK_REGISTRY.items()}
