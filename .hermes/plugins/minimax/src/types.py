"""
Shared type definitions for the minimax plugin.

All event types, request/response shapes, and internal state structures
used across the plugin modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

# ---------------------------------------------------------------------------
# Event types forwarded to claw-server
# ---------------------------------------------------------------------------

HermesEventType = Literal[
    # Core agent lifecycle
    "agent_message",          # Complete text (finish=True, with msg_id, content)
    "agent_message_chunk",    # Streaming chunk (delta, text, chunk_index)
    "tool_call_start",        # Tool call begins
    "tool_call_finish",       # Tool call ends
    "agent_end",              # Agent turn finished

    # Session lifecycle
    "session_start",
    "session_finalize",
    "session_reset",

    # LLM lifecycle
    "before_llm_call",
    "post_api_request",

    # Gateway-level events (transparent passthrough)
    "gateway_event",

    # Message lifecycle (mirroring maxclaw-sandbox)
    "message_received",       # User message arrived (from /send endpoint)

    # Operational
    "heartbeat",
    "status_update",
    "send_failure_alert",
]


@dataclass
class HermesEvent:
    """Canonical event structure forwarded to claw-server.

    Field names and JSON keys must match claw-server's ClawEvent struct.
    Timestamps are Unix milliseconds (int64), matching maxclaw-sandbox convention.
    """

    type: HermesEventType
    sandbox_key: str = ""
    run_id: str = ""
    session_id: str = ""
    timestamp: int = 0

    # agent_message
    msg_id: Optional[int] = None
    content: Optional[str] = None
    finish: Optional[bool] = None

    # agent_message_chunk
    chunk_index: Optional[int] = None
    delta: Optional[str] = None
    text: Optional[str] = None

    # tool_call_start / tool_call_finish
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[str] = None
    tool_result: Optional[str] = None
    tool_status: Optional[str] = None

    # agent_end
    success: Optional[bool] = None
    completed: Optional[bool] = None
    interrupted: Optional[bool] = None
    stop_reason: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    lifecycle_error: Optional[str] = None

    # status_update
    status: Optional[str] = None

    # before_llm_call
    user_message: Optional[str] = None
    model: Optional[str] = None
    is_first_turn: Optional[bool] = None

    # post_api_request (top-level to match ClawEvent json tags)
    api_duration: Optional[int] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

    # gateway_event
    gateway_event_type: Optional[str] = None
    gateway_context: Optional[Dict[str, Any]] = None

    # Context metadata
    message_provider: Optional[str] = None
    run_type: Optional[str] = None
    platform: Optional[str] = None
    user_id: Optional[str] = None
    is_first_message: Optional[bool] = None

    # send_failure_alert
    send_failure_count: Optional[int] = None

    # Arbitrary extra data
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict, omitting None values."""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                result[k] = v
        return result


# ---------------------------------------------------------------------------
# HTTP Server request/response types
# ---------------------------------------------------------------------------

@dataclass
class SendRequest:
    """Inbound request from claw-server to send a message to the agent."""
    sandbox_key: str = ""
    message: str = ""
    session_id: Optional[str] = None
    platform: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SlashRequest:
    """Inbound request from claw-server to execute a slash command."""
    sandbox_key: str = ""
    command: str = ""
    args: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class ConfigPatchRequest:
    """Inbound request from claw-server to update runtime config."""
    sandbox_key: str = ""
    patch: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal state types
# ---------------------------------------------------------------------------

@dataclass
class StreamBuffer:
    """Accumulated streaming text for a single run."""
    msg_id: Optional[int] = None
    text: str = ""
    chunk_count: int = 0
    last_timestamp: float = 0.0


@dataclass
class ToolCallEntry:
    """Cached before_tool_call info for matching with after_tool_call."""
    tool_call_id: str = ""
    tool_name: str = ""
    start_timestamp: float = 0.0
    msg_id: Optional[int] = None
    args_fingerprint: str = ""


@dataclass
class ForwardResult:
    """Result of forwarding an event to claw-server."""
    ok: bool = False
    status_code: int = 0
    body: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    blocked: bool = False  # moderation blocked flag
