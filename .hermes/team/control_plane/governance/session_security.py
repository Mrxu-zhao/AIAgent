from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class SessionType(Enum):
    MAIN = "main"
    SECONDARY = "secondary"
    UNTRUSTED = "untrusted"


@dataclass
class SessionSecurityPolicy:
    session_type: SessionType = SessionType.MAIN
    require_confirm: bool = True
    allowed_toolsets: Set[str] = field(default_factory=set)
    denied_tools: Set[str] = field(default_factory=set)
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    allow_network: bool = True
    allow_system: bool = True


class SessionSecurityManager:
    SENSITIVE_TOOLS = {
        "write_file",
        "run_command",
        "delete_file",
        "kanban_create_task",
    }
    NETWORK_TOOLS = {"web_search", "web_fetch", "list_oauth_services"}
    SYSTEM_TOOLS = {"run_command"}

    def __init__(self):
        self._policies: Dict[str, SessionSecurityPolicy] = {}
        self._pairing_codes: Dict[str, str] = {}
        self._paired_sessions: Set[str] = set()

    def create_policy(self, session_id: str, session_type: str = "main") -> SessionSecurityPolicy:
        session_kind = SessionType(session_type)
        if session_kind == SessionType.MAIN:
            policy = SessionSecurityPolicy(
                session_type=session_kind,
                allowed_toolsets={"read", "write", "code", "collaboration", "integration"},
            )
        elif session_kind == SessionType.SECONDARY:
            policy = SessionSecurityPolicy(
                session_type=session_kind,
                allowed_toolsets={"read", "code", "collaboration"},
                denied_tools={"run_command", "delete_file"},
                allow_system=False,
            )
        else:
            policy = SessionSecurityPolicy(
                session_type=session_kind,
                allowed_toolsets={"read"},
                denied_tools={"write_file", "run_command", "delete_file", "kanban_create_task"},
                allow_network=False,
                allow_system=False,
            )
        self._policies[session_id] = policy
        return policy

    def generate_pairing_code(self, session_id: str) -> str:
        code = hashlib.sha256(f"{session_id}:{time.time()}".encode("utf-8")).hexdigest()[:8].upper()
        self._pairing_codes[session_id] = code
        return code

    def verify_pairing(self, session_id: str, code: str) -> bool:
        expected = self._pairing_codes.get(session_id)
        if expected and expected == code.upper():
            self._paired_sessions.add(session_id)
            return True
        return False

    def is_paired(self, session_id: str) -> bool:
        return session_id in self._paired_sessions

    def check_permission(
        self,
        session_id: str,
        tool_name: str,
        payload: Dict[str, Any],
        toolset: str = "generic",
    ) -> Tuple[bool, str]:
        policy = self._policies.get(session_id)
        if policy is None:
            policy = self.create_policy(session_id, "main")

        if policy.allowed_toolsets and toolset not in policy.allowed_toolsets:
            return False, f"Toolset denied: {toolset}"
        if tool_name in policy.denied_tools:
            return False, f"Tool denied: {tool_name}"
        if tool_name in self.SYSTEM_TOOLS and not policy.allow_system:
            return False, "System access denied"
        if tool_name in self.NETWORK_TOOLS and not policy.allow_network:
            return False, "Network access denied"

        path_value = payload.get("path") or payload.get("file_path")
        if path_value:
            allowed, reason = self._check_path(policy, str(path_value))
            if not allowed:
                return False, reason

        if tool_name in self.SENSITIVE_TOOLS and policy.session_type != SessionType.MAIN:
            return False, f"Sensitive tool denied for {policy.session_type.value} session"

        if tool_name in self.SENSITIVE_TOOLS and policy.require_confirm and not self.is_paired(session_id):
            return False, "Sensitive tool denied until session is paired"

        return True, "Allowed"

    def _check_path(self, policy: SessionSecurityPolicy, raw_path: str) -> Tuple[bool, str]:
        resolved = Path(raw_path).resolve()
        for denied in policy.denied_paths:
            denied_path = Path(denied).resolve()
            if resolved == denied_path or denied_path in resolved.parents:
                return False, f"Path denied: {raw_path}"
        if policy.allowed_paths:
            for allowed in policy.allowed_paths:
                allowed_path = Path(allowed).resolve()
                if resolved == allowed_path or allowed_path in resolved.parents:
                    return True, "Allowed"
            return False, f"Path denied: {raw_path}"
        return True, "Allowed"


_SESSION_SECURITY_MANAGER: Optional[SessionSecurityManager] = None


def get_session_security_manager() -> SessionSecurityManager:
    global _SESSION_SECURITY_MANAGER
    if _SESSION_SECURITY_MANAGER is None:
        _SESSION_SECURITY_MANAGER = SessionSecurityManager()
    return _SESSION_SECURITY_MANAGER
