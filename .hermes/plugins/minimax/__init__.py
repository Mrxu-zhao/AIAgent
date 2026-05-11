"""
minimax — Hermes Agent sandbox communication hub.

This plugin bridges Hermes Agent with the claw-server business layer by:
1. Registering all available lifecycle hooks to capture events
2. Forwarding events to claw-server via HTTP POST (EventForwarder)
3. Intercepting streaming output at the token level via monkey-patch

Messages are injected by bridge-bootstrap writing directly to hermes's
stdin FIFO (/root/.hermes/hermes-stdin.fifo), simulating keyboard input.
No HTTP injection server needed in the plugin.

Design principles (inherited from maxclaw-sandbox):
- No business logic in the plugin — all filtering/routing in claw-server
- Events are annotated with context metadata, never dropped
- Plugin holds per-sandbox mutable state (stream buffers, dedup caches)
- claw-server remains stateless
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LOG_PREFIX = "[MMLOG]"


def _now_ms() -> int:
    """Current time as Unix milliseconds (matching claw-server int64 convention)."""
    return int(time.time() * 1000)


# Module-level singletons (survive hot-reload by being re-created)
_forwarder = None
_state_manager = None


def _write_pid_to_state() -> None:
    """Write hermes PID to maxhermes.json so bootstrap can send SIGTERM for session reset."""
    import os as _os, json as _json
    from pathlib import Path as _Path
    hermes_home = _os.environ.get("HERMES_HOME", "/root/.hermes")
    state_file = _Path(hermes_home) / "maxhermes.json"
    try:
        state = _json.loads(state_file.read_text()) if state_file.exists() else {}
    except Exception:
        state = {}
    state["hermes_pid"] = _os.getpid()
    try:
        tmp = state_file.with_suffix(".json.tmp")
        tmp.write_text(_json.dumps(state, indent=2, ensure_ascii=False))
        tmp.replace(state_file)
        logger.warning("%s hermes PID %d written to maxhermes.json", LOG_PREFIX, _os.getpid())
    except Exception as exc:
        logger.warning("%s failed to write PID: %s", LOG_PREFIX, exc)


def register(ctx) -> None:
    """Plugin entry point — called by Hermes PluginManager."""
    global _forwarder, _state_manager

    logger.info("%s plugin loading (sandbox hub mode)", LOG_PREFIX)

    # -- Tear down previous instances on hot reload ----------------------------
    if _state_manager is not None:
        try:
            _state_manager.destroy()
        except Exception:
            pass

    # -- Write PID so bootstrap can send SIGTERM for session reset ------------
    _write_pid_to_state()

    # -- Add stderr handler so [MMLOG] logs appear in container logs ----------
    # hermes CLI mode only logs to rotating files (no stderr handler).
    # Without this, all plugin WARNING logs are invisible in the container.
    import sys as _sys
    _plugin_logger = logging.getLogger("hermes_plugins.minimax")
    if not any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
        for h in _plugin_logger.handlers
    ):
        _sh = logging.StreamHandler(_sys.stderr)
        _sh.setLevel(logging.WARNING)
        _sh.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        _plugin_logger.addHandler(_sh)
        _plugin_logger.propagate = False  # don't double-log via root logger

    # -- Patch Claude Code identity to Hermes ---------------------------------
    try:
        import agent.anthropic_adapter as _aa
        _aa._CLAUDE_CODE_SYSTEM_PREFIX = "You are Hermes, an AI agent."
        logger.warning("%s patched _CLAUDE_CODE_SYSTEM_PREFIX → Hermes identity", LOG_PREFIX)
    except Exception as _e:
        logger.debug("%s could not patch Claude Code prefix: %s", LOG_PREFIX, _e)

    # -- Initialize sub-modules -----------------------------------------------
    from .src.event_forwarder import EventForwarder
    from .src.state_manager import StateManager
    from .src.stream_interceptor import install_stream_interceptor
    from .src.config import is_additional_hook_enabled
    from .src.logger import wrap_hook

    _forwarder = EventForwarder()
    _state_manager = StateManager(_forwarder)

    # -- Install streaming interceptor ----------------------------------------
    install_stream_interceptor(
        state_manager=_state_manager,
        forwarder=_forwarder,
        chunk_forward_enabled=True,
    )

    # -- Register all lifecycle hooks -----------------------------------------
    ctx.register_hook("pre_tool_call",    wrap_hook(logger, "pre_tool_call",    _make_pre_tool_call_handler(_forwarder, _state_manager)))
    ctx.register_hook("post_tool_call",   wrap_hook(logger, "post_tool_call",   _make_post_tool_call_handler(_forwarder, _state_manager)))
    ctx.register_hook("pre_llm_call",     wrap_hook(logger, "pre_llm_call",     _make_pre_llm_call_handler(_forwarder, _state_manager)))
    ctx.register_hook("post_llm_call",    wrap_hook(logger, "post_llm_call",    _make_post_llm_call_handler(_forwarder, _state_manager)))
    ctx.register_hook("on_session_start", wrap_hook(logger, "on_session_start", _make_session_start_handler(_forwarder, _state_manager)))
    ctx.register_hook("on_session_end",   wrap_hook(logger, "on_session_end",   _make_session_end_handler(_forwarder, _state_manager)))
    ctx.register_hook("on_session_reset", wrap_hook(logger, "on_session_reset", _make_session_reset_handler(_forwarder, _state_manager)))
    ctx.register_hook("on_session_finalize", wrap_hook(logger, "on_session_finalize", _make_session_finalize_handler(_forwarder, _state_manager)))

    core_hook_count = 8
    additional_hook_count = 0

    if is_additional_hook_enabled("pre_api_request"):
        ctx.register_hook("pre_api_request", wrap_hook(logger, "pre_api_request", _make_pre_api_request_handler(_forwarder, _state_manager)))
        additional_hook_count += 1
    if is_additional_hook_enabled("post_api_request"):
        ctx.register_hook("post_api_request", wrap_hook(logger, "post_api_request", _make_post_api_request_handler(_forwarder, _state_manager)))
        additional_hook_count += 1

    total_hooks = core_hook_count + additional_hook_count
    logger.warning(
        "%s plugin loaded: hooks=%d (core=%d, additional=%d), stream_intercept=True",
        LOG_PREFIX, total_hooks, core_hook_count, additional_hook_count,
    )


# ---------------------------------------------------------------------------
# Hook handler factories
# ---------------------------------------------------------------------------

def _safe_forward(forwarder, event, state_manager=None):
    """Forward an event, swallowing exceptions.

    If a state_manager is provided, automatically annotates the event with
    run_type metadata (ported from maxclaw message_provider / run_type).
    """
    if state_manager is not None and not event.run_type:
        run_type = state_manager.get_run_type(event.run_id)
        if run_type:
            event.run_type = run_type
    try:
        result = forwarder.forward(event)
        if result.blocked and state_manager is not None:
            state_manager.mark_run_blocked(event.run_id or "")
    except Exception as exc:
        logger.warning(
            "%s[HOOK] _safe_forward error: type=%s run=%s err=%s",
            LOG_PREFIX, event.type, event.run_id or "", exc,
        )


def _make_dedup_fingerprint(*parts) -> str:
    """Create a stable fingerprint for dedup. Uses canonical JSON for dicts."""
    segments = []
    for p in parts:
        if isinstance(p, dict):
            try:
                segments.append(json.dumps(p, sort_keys=True, ensure_ascii=False))
            except (TypeError, ValueError):
                segments.append(str(p))
        else:
            segments.append(str(p))
    raw = "|".join(segments)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _canonical_args_str(args: Any) -> str:
    """Convert tool args to canonical JSON string."""
    if args is None:
        return ""
    if isinstance(args, str):
        return args
    try:
        return json.dumps(args, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(args)


# ---------------------------------------------------------------------------
# pre_tool_call
#
# hermes-agent calls:
#   invoke_hook("pre_tool_call",
#       tool_name=function_name,
#       args=function_args,          # dict or str
#       task_id=task_id or "",
#       session_id=session_id or "",
#       tool_call_id=tool_call_id or "",
#   )
# ---------------------------------------------------------------------------

def _make_pre_tool_call_handler(forwarder, state_manager):
    from .src.types import HermesEvent
    from .src.config import get_sandbox_key

    def handler(
        tool_name: str = "",
        args: Any = None,
        task_id: str = "",
        session_id: str = "",
        tool_call_id: str = "",
        **kwargs,
    ):
        args_str = _canonical_args_str(args)
        fp = _make_dedup_fingerprint("pre_tool", tool_name, args_str, task_id)
        if state_manager.is_hook_duplicate(fp):
            return

        state_manager.set_run_context(run_id=task_id, session_id=session_id)

        # Commit pending streamed text before tool call starts
        finish_event = state_manager.commit_streamed_text(
            run_id=task_id,
            timestamp=_now_ms() - 1,
        )
        if finish_event:
            _safe_forward(forwarder, finish_event, state_manager)

        tcid = tool_call_id or str(uuid.uuid4())
        msg_id = state_manager.register_before_tool_call(
            tool_name=tool_name,
            tool_call_id=tcid,
            tool_args=args_str,
            run_id=task_id,
        )

        event = HermesEvent(
            type="tool_call_start",
            sandbox_key=get_sandbox_key(),
            run_id=task_id,
            session_id=session_id,
            timestamp=_now_ms(),
            tool_call_id=tcid,
            tool_name=tool_name,
            tool_args=args_str,
            tool_status="start",
            msg_id=msg_id,
        )
        _safe_forward(forwarder, event, state_manager)

        # Emit status_update so claw-server can push "Generating" status
        status_event = state_manager.emit_status_update("Generating")
        _safe_forward(forwarder, status_event, state_manager)

    return handler


# ---------------------------------------------------------------------------
# post_tool_call
#
# hermes-agent calls:
#   invoke_hook("post_tool_call",
#       tool_name=function_name,
#       args=function_args,
#       result=result,               # str (tool output)
#       task_id=task_id or "",
#       session_id=session_id or "",
#       tool_call_id=tool_call_id or "",
#   )
# ---------------------------------------------------------------------------

def _make_post_tool_call_handler(forwarder, state_manager):
    from .src.types import HermesEvent
    from .src.config import get_sandbox_key
    from .src.event_forwarder import generate_msg_id

    def handler(
        tool_name: str = "",
        args: Any = None,
        result: Any = "",
        task_id: str = "",
        session_id: str = "",
        tool_call_id: str = "",
        **kwargs,
    ):
        args_str = _canonical_args_str(args)
        fp = _make_dedup_fingerprint("post_tool", tool_name, args_str, task_id)
        if state_manager.is_hook_duplicate(fp):
            return

        matched = state_manager.match_after_tool_call(tool_name, args_str)

        tcid = tool_call_id or (matched.tool_call_id if matched else str(uuid.uuid4()))
        result_str = str(result) if result else ""
        if len(result_str) > 10000:
            result_str = result_str[:10000] + "...(truncated)"

        # msg_id must never be None/0 — chat-server rejects it.
        # Normal path: from matched entry. Fallback: generate fresh one.
        if matched:
            msg_id = matched.msg_id
        else:
            msg_id = generate_msg_id() or int(time.time() * 1000)

        event = HermesEvent(
            type="tool_call_finish",
            sandbox_key=get_sandbox_key(),
            run_id=task_id,
            session_id=session_id,
            timestamp=_now_ms(),
            tool_call_id=tcid,
            tool_name=tool_name,
            tool_args=args_str,
            tool_result=result_str,
            tool_status="finished",
            msg_id=msg_id,
            duration_ms=(
                int((time.time() - matched.start_timestamp) * 1000)
                if matched else None
            ),
        )
        _safe_forward(forwarder, event, state_manager)

    return handler


# ---------------------------------------------------------------------------
# pre_llm_call
#
# hermes-agent calls:
#   invoke_hook("pre_llm_call",
#       session_id=self.session_id,
#       user_message=original_user_message,
#       conversation_history=list(messages),
#       is_first_turn=(not bool(conversation_history)),
#       model=self.model,
#       platform=getattr(self, "platform", None) or "",
#       sender_id=getattr(self, "_user_id", None) or "",
#   )
# ---------------------------------------------------------------------------

def _make_pre_llm_call_handler(forwarder, state_manager):
    from .src.types import HermesEvent
    from .src.config import get_sandbox_key

    def handler(
        session_id: str = "",
        user_message: str = "",
        conversation_history: list = None,
        is_first_turn: bool = False,
        model: str = "",
        platform: str = "",
        sender_id: str = "",
        **kwargs,
    ):
        # Capture agent reference for abort support.
        # pre_llm_call runs in the agent's execution thread (run_agent.py:7813).
        # We use _find_agent_via_running_agents() first (cheap dict lookup),
        # then fall back to gc only if needed.
        try:
            import threading
            tid = threading.current_thread().ident
            if state_manager._agent_ref is None or state_manager._agent_thread_id != tid:
                agent = state_manager._find_agent_via_running_agents()
                if agent is None:
                    agent = state_manager._find_agent_via_gc()
                if agent is not None:
                    state_manager.set_agent_ref(agent, tid)
        except Exception:
            pass

        run_id = session_id or state_manager.current_run_id
        state_manager.set_run_context(run_id=run_id, session_id=session_id)

        # Forward incoming user message so it appears in the web UI.
        # Only fire for IM/gateway platforms, NOT CLI. In CLI mode
        # claw-server already stores the message upstream (SendHermes).
        # hermes sets self.platform = "cli" in CLI mode.
        if user_message and platform and platform != "cli":
            msg_recv_event = HermesEvent(
                type="message_received",
                sandbox_key=get_sandbox_key(),
                run_id=run_id,
                session_id=session_id,
                timestamp=_now_ms(),
                content=user_message[:2000],
                user_id=sender_id,
                platform=platform,
                metadata={"source": "hermes-plugin"},
            )
            _safe_forward(forwarder, msg_recv_event, state_manager)

        event = HermesEvent(
            type="before_llm_call",
            sandbox_key=get_sandbox_key(),
            run_id=run_id,
            session_id=session_id,
            timestamp=_now_ms(),
            user_message=user_message[:2000] if user_message else "",
            model=model,
            is_first_turn=is_first_turn,
            platform=platform,
            user_id=sender_id,
        )
        _safe_forward(forwarder, event, state_manager)

        # pre_llm_call can return context to inject into the user message.
        # Return None — no injection by default. claw-server can instruct
        # context injection via the HTTP /config endpoint if needed.
        return None

    return handler


# ---------------------------------------------------------------------------
# post_llm_call
#
# hermes-agent calls:
#   invoke_hook("post_llm_call",
#       session_id=self.session_id,
#       user_message=original_user_message,
#       assistant_response=final_response,
#       conversation_history=list(messages),
#       model=self.model,
#       platform=getattr(self, "platform", None) or "",
#   )
# ---------------------------------------------------------------------------

def _make_post_llm_call_handler(forwarder, state_manager):
    from .src.types import HermesEvent
    from .src.config import get_sandbox_key

    def handler(
        session_id: str = "",
        user_message: str = "",
        assistant_response: str = "",
        conversation_history: list = None,
        model: str = "",
        platform: str = "",
        **kwargs,
    ):
        run_id = session_id or state_manager.current_run_id

        # Commit any pending streamed text, preferring the final response
        # from the hook (which is the complete text after all tool-calling
        # turns, potentially longer than the streaming buffer).
        finish_event = state_manager.commit_streamed_text(
            run_id=run_id,
            final_text=assistant_response,
        )
        if finish_event:
            finish_event.model = model
            _safe_forward(forwarder, finish_event, state_manager)
        else:
            # No streaming happened (non-streaming API or already committed)
            event = HermesEvent(
                type="agent_message",
                sandbox_key=get_sandbox_key(),
                run_id=run_id,
                session_id=session_id,
                timestamp=_now_ms(),
                content=assistant_response,
                finish=True,
                model=model,
            )
            _safe_forward(forwarder, event, state_manager)

    return handler


# ---------------------------------------------------------------------------
# pre_api_request
#
# hermes-agent calls:
#   invoke_hook("pre_api_request",
#       task_id=effective_task_id,
#       session_id=self.session_id or "",
#       platform=self.platform or "",
#       model=self.model,
#       provider=self.provider,
#       base_url=self.base_url,
#       api_mode=self.api_mode,
#       api_call_count=api_call_count,
#       message_count=len(api_messages),
#       tool_count=len(self.tools or []),
#       approx_input_tokens=approx_tokens,
#       request_char_count=total_chars,
#       max_tokens=self.max_tokens,
#   )
# ---------------------------------------------------------------------------

def _make_pre_api_request_handler(forwarder, state_manager):
    from .src.types import HermesEvent
    from .src.config import get_sandbox_key

    def handler(
        task_id: str = "",
        session_id: str = "",
        platform: str = "",
        model: str = "",
        provider: str = "",
        base_url: str = "",
        api_mode: str = "",
        api_call_count: int = 0,
        message_count: int = 0,
        tool_count: int = 0,
        approx_input_tokens: int = 0,
        request_char_count: int = 0,
        max_tokens: Any = None,
        **kwargs,
    ):
        event = HermesEvent(
            type="gateway_event",
            sandbox_key=get_sandbox_key(),
            run_id=task_id,
            session_id=session_id,
            timestamp=_now_ms(),
            gateway_event_type="pre_api_request",
            model=model,
            platform=platform,
            metadata={
                "task_id": task_id,
                "provider": provider,
                "api_mode": api_mode,
                "api_call_count": api_call_count,
                "message_count": message_count,
                "tool_count": tool_count,
                "approx_input_tokens": approx_input_tokens,
                "request_char_count": request_char_count,
                "max_tokens": max_tokens,
            },
        )
        _safe_forward(forwarder, event, state_manager)

    return handler


# ---------------------------------------------------------------------------
# post_api_request
#
# hermes-agent calls:
#   invoke_hook("post_api_request",
#       task_id=effective_task_id,
#       session_id=self.session_id or "",
#       platform=self.platform or "",
#       model=self.model,
#       provider=self.provider,
#       base_url=self.base_url,
#       api_mode=self.api_mode,
#       api_call_count=api_call_count,
#       api_duration=api_duration,
#       finish_reason=finish_reason,
#       message_count=len(api_messages),
#       response_model=getattr(response, "model", None),
#       usage=self._usage_summary_for_api_request_hook(response),
#       assistant_content_chars=len(_assistant_text),
#       assistant_tool_call_count=len(_assistant_tool_calls),
#   )
# ---------------------------------------------------------------------------

def _make_post_api_request_handler(forwarder, state_manager):
    from .src.types import HermesEvent
    from .src.config import get_sandbox_key

    def handler(
        task_id: str = "",
        session_id: str = "",
        platform: str = "",
        model: str = "",
        provider: str = "",
        base_url: str = "",
        api_mode: str = "",
        api_call_count: int = 0,
        api_duration: float = 0.0,
        finish_reason: str = "",
        message_count: int = 0,
        response_model: str = "",
        usage: Any = None,
        assistant_content_chars: int = 0,
        assistant_tool_call_count: int = 0,
        **kwargs,
    ):
        event = HermesEvent(
            type="post_api_request",
            sandbox_key=get_sandbox_key(),
            run_id=task_id,
            session_id=session_id,
            timestamp=_now_ms(),
            model=model,
            platform=platform,
            api_duration=int(api_duration * 1000) if api_duration else None,
            finish_reason=finish_reason or None,
            usage=usage if isinstance(usage, dict) else None,
            metadata={
                "task_id": task_id,
                "provider": provider,
                "api_mode": api_mode,
                "api_call_count": api_call_count,
                "message_count": message_count,
                "response_model": response_model,
                "assistant_content_chars": assistant_content_chars,
                "assistant_tool_call_count": assistant_tool_call_count,
            },
        )
        _safe_forward(forwarder, event, state_manager)

        # Cache lifecycle error for inclusion in agent_end event
        if finish_reason and finish_reason in ("error", "content_filter"):
            state_manager.cache_lifecycle_error(
                run_id=task_id,
                error=f"API error: finish_reason={finish_reason}",
            )

    return handler


# ---------------------------------------------------------------------------
# Session hooks
#
# on_session_start: invoke_hook("on_session_start",
#     session_id=self.session_id, model=self.model, platform=...)
# on_session_end: invoke_hook("on_session_end",
#     session_id=self.session_id, completed=completed,
#     interrupted=interrupted, model=self.model, platform=...)
# on_session_finalize: invoke_hook("on_session_finalize",
#     session_id=_old_sid, platform=...)      # session_id may be None!
# on_session_reset: invoke_hook("on_session_reset",
#     session_id=_new_sid, platform=...)       # session_id may be None!
# ---------------------------------------------------------------------------

def _make_session_start_handler(forwarder, state_manager):
    def handler(session_id: str = "", model: str = "", platform: str = "", **kwargs):
        event = state_manager.on_session_start(session_id=session_id or "", platform=platform)
        _safe_forward(forwarder, event, state_manager)
    return handler


def _make_session_end_handler(forwarder, state_manager):
    def handler(
        session_id: str = "",
        completed: bool = False,
        interrupted: bool = False,
        model: str = "",
        platform: str = "",
        **kwargs,
    ):
        event = state_manager.on_session_end(
            platform=platform, completed=completed,
            interrupted=interrupted, model=model,
        )
        state_manager.on_agent_end(run_id=session_id or "")
        _safe_forward(forwarder, event, state_manager)
    return handler


def _make_session_finalize_handler(forwarder, state_manager):
    def handler(session_id=None, platform: str = "", **kwargs):
        # Flush any pending streamed text before finalization
        try:
            finish_event = state_manager.commit_streamed_text(
                run_id=state_manager.current_run_id,
            )
            if finish_event:
                _safe_forward(forwarder, finish_event, state_manager)
        except Exception as exc:
            logger.warning("%s session_finalize: commit_streamed_text failed: %s", LOG_PREFIX, exc)

        # Forward the finalize event
        event = state_manager.on_session_finalize(
            session_id=session_id, platform=platform,
        )
        _safe_forward(forwarder, event, state_manager)

        # Clean up all state (gateway is shutting down)
        try:
            state_manager.destroy()
        except Exception:
            pass
    return handler


def _make_session_reset_handler(forwarder, state_manager):
    def handler(session_id=None, platform: str = "", **kwargs):
        event = state_manager.on_session_reset(
            session_id=session_id, platform=platform,
        )
        _safe_forward(forwarder, event, state_manager)
    return handler
