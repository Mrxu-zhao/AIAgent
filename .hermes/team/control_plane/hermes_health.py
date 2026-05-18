from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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


def check_hermes_health(
    command: str,
    probe_args: Optional[List[str]] = None,
    status_args: Optional[List[str]] = None,
    timeout_seconds: float = 1.0,
) -> HermesHealthReport:
    probe_args = list(probe_args or ["--help"])
    status_args = list(status_args or ["status"])
    try:
        probe_result = subprocess.run(
            [command, *probe_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return HermesHealthReport(
            ok=False,
            status="command_missing",
            command=command,
            message=f"command not found: {command}",
        )
    except subprocess.TimeoutExpired:
        return HermesHealthReport(
            ok=False,
            status="probe_failed",
            command=command,
            message=f"probe timeout: {command}",
        )

    available_commands = _extract_commands(f"{probe_result.stdout}\n{probe_result.stderr}")
    try:
        status_result = subprocess.run(
            [command, *status_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return HermesHealthReport(
            ok=False,
            status="probe_failed",
            command=command,
            available_commands=available_commands,
            message=f"status timeout: {command}",
            details={"probe_returncode": probe_result.returncode},
        )
    combined = f"{status_result.stdout}\n{status_result.stderr}"
    combined_lower = combined.lower()
    if "not configured" in combined_lower or "model: (not set)" in combined_lower:
        return HermesHealthReport(
            ok=False,
            status="not_configured",
            command=command,
            available_commands=available_commands,
            message=combined.strip() or "hermes not configured",
            details={"probe_returncode": probe_result.returncode, "status_returncode": status_result.returncode},
        )
    return HermesHealthReport(
        ok=True,
        status="healthy",
        command=command,
        available_commands=available_commands,
        message="hermes is healthy",
        details={"probe_returncode": probe_result.returncode, "status_returncode": status_result.returncode},
    )
