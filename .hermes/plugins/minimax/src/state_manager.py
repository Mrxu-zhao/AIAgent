"""
State Manager — stateful event processing pipeline.

Ported and simplified from maxclaw-sandbox's TypeScript StateManager. Handles:
- Streaming text accumulation (per-run buffer assembly)
- Event deduplication (fingerprint-based, 5s window)
- Tool call ID matching (before→after correlation)
- msg_id lifecycle (request from claw-server, reuse within a run)
- Finish-event deduplication (prevent duplicate finish=True)
- Send failure tracking + alerting (ported from maxclaw sendFailureCount)
- Run TTL cleanup (35-min expiry, prevents memory leaks)
- First agent message tracking
- Run type metadata (slash / normal)

The StateManager is the single source of mutable per-sandbox state. All
business logic / filtering decisions are deferred to claw-server.

Thread safety: all mutable state is guarded by a single reentrant lock,
since hermes-agent may invoke tool hooks from background threads.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from .config import get_sandbox_key
from .event_forwarder import EventForwarder, generate_msg_id
from .types import HermesEvent, StreamBuffer, ToolCallEntry

logger = logging.getLogger(__name__)

LOG_PREFIX = "[MMLOG]"

DEDUP_WINDOW_SECONDS = 5.0
HOOK_DEDUP_WINDOW_SECONDS = 2.0
DEDUP_MAX_ENTRIES = 5000

RUN_TTL_SECONDS = 35 * 60  # 35 minutes — matches maxclaw-sandbox
RUN_CLEANUP_INTERVAL_SECONDS = 60


def _now_ms() -> int:
    """Current time as Unix milliseconds (matches claw-server ClawEvent.Timestamp int64)."""
    return int(time.time() * 1000)


class StateManager:
    """Per-sandbox stateful event processing pipeline.

    All public methods are thread-safe.
    """

    def __init__(self, forwarder: EventForwarder) -> None:
        self._forwarder = forwarder
        self._lock = threading.RLock()

        # Run tracking
        self._current_run_id: str = ""
        self._current_session_id: str = ""

        # Stream assembly: run_id → StreamBuffer
        self._stream_buffers: Dict[str, StreamBuffer] = {}
        self._stream_max_seq: Dict[str, int] = {}

        # Dedup: finish events
        self._finish_sent: set[str] = set()

        # Dedup: generic events (fingerprint → timestamp)
        self._event_dedup: Dict[str, float] = {}

        # Dedup: hook events (md5 fingerprint → timestamp)
        self._hook_dedup: Dict[str, float] = {}

        # Tool call matching: tool_name → [ToolCallEntry]
        self._pending_tool_calls: Dict[str, List[ToolCallEntry]] = {}

        # msg_id cache: run_id → msg_id
        self._msg_id_cache: Dict[str, int] = {}

        # Operational: first agent message (ported from maxclaw isFirstAgentMessage)
        self._is_first_message: bool = True

        # Run activity tracking for TTL cleanup (ported from maxclaw runLastActivity)
        self._run_last_activity: Dict[str, float] = {}

        # Run type metadata (ported from maxclaw slashCommandRunIds)
        self._slash_run_ids: set[str] = set()

        # Moderation: blocked runs
        self._blocked_runs: set[str] = set()

        # Lifecycle error cache: run_id -> error message
        self._last_lifecycle_error: Dict[str, str] = {}

        # New/reset run tracking
        self._new_reset_run_ids: set[str] = set()

        # Agent interrupt support: track the agent's execution thread
        self._agent_thread_id: Optional[int] = None
        self._agent_ref = None  # direct ref to AIAgent (set from hooks)

        # Lifecycle
        self._start_time: float = time.time()
        self._destroyed = False
        self._cleanup_timer: Optional[threading.Timer] = None
        self._start_cleanup_timer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_run_context(self, run_id: str = "", session_id: str = "") -> None:
        """Update current run/session context (called from hook callbacks)."""
        with self._lock:
            if run_id:
                self._current_run_id = run_id
                self._touch_run(run_id)
            if session_id:
                self._current_session_id = session_id

    @property
    def current_run_id(self) -> str:
        """Return current run_id. Returns empty string if not set — never
        generates a random UUID on read (that would cause instability across
        multiple callers within the same turn)."""
        return self._current_run_id

    @property
    def current_session_id(self) -> str:
        return self._current_session_id

    # ------------------------------------------------------------------
    # First message tracking (ported from maxclaw isFirstAgentMessage)
    # ------------------------------------------------------------------

    def check_and_consume_first_message(self) -> bool:
        """Check if this is the first agent message and consume the flag.
        Returns True if it was the first message (caller should annotate)."""
        with self._lock:
            if self._is_first_message:
                self._is_first_message = False
                return True
            return False

    @property
    def is_first_message(self) -> bool:
        return self._is_first_message

    # ------------------------------------------------------------------
    # Run type metadata (ported from maxclaw slashCommandRunIds)
    # ------------------------------------------------------------------

    def mark_slash_run(self, run_id: str) -> None:
        """Mark a run_id as originating from a slash command."""
        if run_id:
            with self._lock:
                self._slash_run_ids.add(run_id)

    def mark_new_reset_run(self, run_id: str) -> None:
        """Mark a run_id as originating from a new/reset action."""
        if run_id:
            with self._lock:
                self._new_reset_run_ids.add(run_id)

    def get_run_type(self, run_id: str = "") -> str:
        """Return the run type label for the given run_id."""
        rid = run_id or self._current_run_id
        with self._lock:
            if rid in self._new_reset_run_ids:
                return "new_reset"
            if rid in self._slash_run_ids:
                return "slash"
        return ""

    # ------------------------------------------------------------------
    # Moderation
    # ------------------------------------------------------------------

    def mark_run_blocked(self, run_id: str) -> None:
        with self._lock:
            if run_id:
                self._blocked_runs.add(run_id)
                logger.info("%s run blocked by moderation: %s", LOG_PREFIX, run_id)

    def is_run_blocked(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._blocked_runs

    # ------------------------------------------------------------------
    # Status update
    # ------------------------------------------------------------------

    def emit_status_update(self, status: str = "Generating", **kwargs) -> HermesEvent:
        return HermesEvent(
            type="status_update",
            sandbox_key=get_sandbox_key(),
            run_id=self._current_run_id,
            session_id=self._current_session_id,
            timestamp=_now_ms(),
            status=status,
            platform=kwargs.get("platform", ""),
        )

    # ------------------------------------------------------------------
    # Lifecycle error cache
    # ------------------------------------------------------------------

    def cache_lifecycle_error(self, run_id: str, error: str) -> None:
        if run_id and error:
            with self._lock:
                self._last_lifecycle_error[run_id] = error
                logger.info("%s lifecycle error cached: run=%s err=%s", LOG_PREFIX, run_id, error[:200])

    def pop_lifecycle_error(self, run_id: str) -> Optional[str]:
        with self._lock:
            return self._last_lifecycle_error.pop(run_id, None)

    # ------------------------------------------------------------------
    # Agent interrupt support
    # ------------------------------------------------------------------

    def set_agent_ref(self, agent, thread_id: int) -> None:
        """Store a reference to the running AIAgent for abort support."""
        with self._lock:
            self._agent_ref = agent
            self._agent_thread_id = thread_id

    def try_interrupt_agent(self, reason: str = "abort") -> bool:
        """Attempt to interrupt the running agent.

        Uses hermes-agent's native AIAgent.interrupt() method
        (run_agent.py:2833-2872). This sets _interrupt_requested=True,
        signals tools to abort, and force-closes in-flight API connections.

        Discovery priority:
          1. GatewayRunner._running_agents dict (gateway/run.py:573)
          2. Cached agent reference from hook callbacks
          3. gc.get_objects() scan (fallback)

        Returns True if interrupt was dispatched.
        """
        with self._lock:
            agent = self._agent_ref
            thread_id = self._agent_thread_id

        # Path 1: Use _running_agents dict (most reliable)
        if agent is None:
            agent = self._find_agent_via_running_agents()

        # Path 2: Already have a cached ref (from hook callbacks)
        # (agent may be set from Path 1 above)

        # Path 3: gc.get_objects() fallback
        if agent is None:
            agent = self._find_agent_via_gc()

        if agent is not None:
            try:
                agent.interrupt(reason)
                logger.info("%s agent interrupted: reason=%s", LOG_PREFIX, reason)
                return True
            except Exception as exc:
                logger.warning("%s agent.interrupt() failed: %s", LOG_PREFIX, exc)

        # Last resort: set per-thread tool interrupt signal
        if thread_id is not None:
            try:
                from tools.interrupt import set_interrupt
                set_interrupt(True, thread_id)
                logger.info("%s tool interrupt set: thread=%s", LOG_PREFIX, thread_id)
                return True
            except Exception as exc:
                logger.warning("%s set_interrupt failed: %s", LOG_PREFIX, exc)

        return False

    def _find_agent_via_running_agents(self):
        """Find a running AIAgent via GatewayRunner._running_agents.

        This dict (gateway/run.py:573) maps session_key -> AIAgent for all
        active sessions. Since plugin runs in the same process as gateway,
        we can import the module and access the dict directly.
        """
        try:
            import sys
            gateway_run = sys.modules.get("gateway.run")
            if gateway_run is None:
                return None
            # GatewayRunner is a singleton; find it via module-level refs
            for attr_name in dir(gateway_run):
                obj = getattr(gateway_run, attr_name, None)
                if obj is not None and hasattr(obj, '_running_agents'):
                    agents = getattr(obj, '_running_agents', {})
                    for key, agent in agents.items():
                        if (hasattr(agent, 'interrupt')
                                and hasattr(agent, '_interrupt_requested')
                                and not getattr(agent, '_interrupt_requested', True)):
                            return agent
        except Exception:
            pass
        return None

    def _find_agent_via_gc(self):
        """Find a running AIAgent instance in this process via gc.

        Fallback when _running_agents is not accessible.
        Note: gc.get_objects() can be slow (10-50ms) in large heaps.
        """
        try:
            import gc
            for obj in gc.get_objects():
                if (type(obj).__name__ == 'AIAgent'
                        and hasattr(obj, '_interrupt_requested')
                        and hasattr(obj, 'interrupt')
                        and not getattr(obj, '_interrupt_requested', True)):
                    return obj
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Status info (for /health endpoint enhancement)
    # ------------------------------------------------------------------

    def get_status_info(self) -> Dict[str, Any]:
        """Return a snapshot of internal state for health/debug reporting."""
        with self._lock:
            return {
                "uptime_seconds": int(time.time() - self._start_time),
                "current_run_id": self._current_run_id,
                "current_session_id": self._current_session_id,
                "active_stream_buffers": len(self._stream_buffers),
                "pending_tool_calls": sum(len(v) for v in self._pending_tool_calls.values()),
                "event_dedup_cache_size": len(self._event_dedup),
                "hook_dedup_cache_size": len(self._hook_dedup),
                "tracked_runs": len(self._run_last_activity),
                "is_first_message": self._is_first_message,
            }

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def accumulate_stream_delta(self, delta: str, run_id: str = "") -> Optional[HermesEvent]:
        """Accumulate a stream delta and return a chunk event for forwarding.

        Returns an agent_message_chunk event, or None if deduped.
        """
        with self._lock:
            rid = run_id or self._current_run_id or "unknown"

            # Suppress streaming for moderation-blocked runs
            if rid in self._blocked_runs:
                return None

            self._touch_run(rid)

            buf = self._stream_buffers.get(rid)
            if buf is None:
                buf = StreamBuffer()
                self._stream_buffers[rid] = buf
                self._stream_max_seq[rid] = -1

            if not buf.msg_id:
                buf.msg_id = self._get_or_create_msg_id(rid)

            buf.text += delta
            buf.chunk_count += 1
            buf.last_timestamp = time.time()

            seq = self._stream_max_seq.get(rid, -1) + 1
            self._stream_max_seq[rid] = seq

            return HermesEvent(
                type="agent_message_chunk",
                sandbox_key=get_sandbox_key(),
                run_id=rid,
                session_id=self._current_session_id,
                timestamp=_now_ms(),
                msg_id=buf.msg_id,
                delta=delta,
                text=buf.text,
                chunk_index=seq,
            )

    def commit_streamed_text(
        self,
        run_id: str = "",
        final_text: str = "",
        timestamp: Optional[int] = None,
    ) -> Optional[HermesEvent]:
        """Commit accumulated streamed text as a finished agent_message.

        If final_text is provided, it takes precedence over the buffer
        (the hook may have a more complete version than the stream).
        Returns the finish event, or None if already sent.
        """
        with self._lock:
            rid = run_id or self._current_run_id
            buf = self._stream_buffers.get(rid)

            # Fallback: hermes-agent may use different IDs for task_id (tool hooks)
            # vs session_id (LLM hooks / stream interceptor). If the primary key
            # doesn't find a buffer, try finding one under a different key.
            if buf is None and rid:
                for other_rid, other_buf in self._stream_buffers.items():
                    if other_buf.text:
                        logger.debug(
                            "%s commit fallback: %s -> %s", LOG_PREFIX, rid, other_rid,
                        )
                        buf = other_buf
                        rid = other_rid
                        break

            if buf is None and not final_text:
                return None

            msg_id = (buf.msg_id if buf else None) or self._get_or_create_msg_id(rid)

            finish_key = f"{rid}:{msg_id}"
            if finish_key in self._finish_sent:
                logger.debug("%s finish already sent for %s", LOG_PREFIX, finish_key)
                return None
            self._finish_sent.add(finish_key)

            content = final_text or (buf.text if buf else "")
            max_seq = self._stream_max_seq.get(rid, 0)

            event = HermesEvent(
                type="agent_message",
                sandbox_key=get_sandbox_key(),
                run_id=rid,
                session_id=self._current_session_id,
                timestamp=timestamp or _now_ms(),
                msg_id=msg_id,
                content=content,
                finish=True,
                chunk_index=max_seq + 1,
            )

            self._cleanup_run_stream(rid)
            return event

    def _cleanup_run_stream(self, run_id: str) -> None:
        """Clean up stream state for a completed run. Caller must hold _lock."""
        self._stream_buffers.pop(run_id, None)
        self._stream_max_seq.pop(run_id, None)
        self._msg_id_cache.pop(run_id, None)

    # ------------------------------------------------------------------
    # Tool call matching
    # ------------------------------------------------------------------

    def register_before_tool_call(
        self,
        tool_name: str,
        tool_call_id: str,
        tool_args: str,
        run_id: str = "",
    ) -> int:
        """Cache a before_tool_call for later matching with after_tool_call.

        Returns the msg_id assigned to this tool call (for inclusion in the event).

        Uses generate_msg_id() directly instead of _get_or_create_msg_id() to
        avoid polluting the cache. This matches maxclaw-sandbox's behavior where
        processBeforeToolCall calls generateMsgIdFromServer() (not the caching
        getOrCreateRunMsgId). Without this, post-tool streaming would reuse
        the tool call's msg_id from cache.
        """
        with self._lock:
            rid = run_id or self._current_run_id
            # Clear cache so post-tool streaming gets a fresh msg_id
            self._msg_id_cache.pop(rid, None)
            # Generate msg_id directly — do NOT cache (unlike streaming chunks
            # which use _get_or_create_msg_id for per-run reuse)
            msg_id = generate_msg_id()
            if msg_id is None:
                import random
                msg_id = int(time.time() * 1000) * 1000 + random.randint(0, 999)
            entry = ToolCallEntry(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                start_timestamp=time.time(),
                msg_id=msg_id,
                args_fingerprint=self._canonical_fingerprint(tool_args),
            )
            self._pending_tool_calls.setdefault(tool_name, []).append(entry)
            return msg_id

    def match_after_tool_call(self, tool_name: str, tool_args: str = "") -> Optional[ToolCallEntry]:
        """Find and remove the matching before_tool_call entry."""
        with self._lock:
            entries = self._pending_tool_calls.get(tool_name, [])
            if not entries:
                return None

            fingerprint = self._canonical_fingerprint(tool_args) if tool_args else ""
            for i, entry in enumerate(entries):
                if fingerprint and entry.args_fingerprint == fingerprint:
                    return entries.pop(i)

            return entries.pop(0)

    @staticmethod
    def _canonical_fingerprint(data: str) -> str:
        """Compute a stable fingerprint from a JSON string."""
        try:
            normalized = json.dumps(json.loads(data), sort_keys=True, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            normalized = data
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    # ------------------------------------------------------------------
    # Event dedup
    # ------------------------------------------------------------------

    def is_event_duplicate(self, fingerprint: str) -> bool:
        """Check if an event with this fingerprint was recently processed."""
        with self._lock:
            self._prune_dedup_cache(self._event_dedup, DEDUP_WINDOW_SECONDS)
            if fingerprint in self._event_dedup:
                return True
            self._event_dedup[fingerprint] = time.time()
            return False

    def is_hook_duplicate(self, fingerprint: str) -> bool:
        """Check if a hook event with this fingerprint was recently processed."""
        with self._lock:
            self._prune_dedup_cache(self._hook_dedup, HOOK_DEDUP_WINDOW_SECONDS)
            if fingerprint in self._hook_dedup:
                return True
            self._hook_dedup[fingerprint] = time.time()
            return False

    @staticmethod
    def _prune_dedup_cache(cache: Dict[str, float], window: float) -> None:
        cutoff = time.time() - window
        stale = [k for k, ts in cache.items() if ts < cutoff]
        for k in stale:
            del cache[k]
        if len(cache) > DEDUP_MAX_ENTRIES:
            sorted_keys = sorted(cache, key=cache.get)
            for k in sorted_keys[: len(cache) - DEDUP_MAX_ENTRIES]:
                del cache[k]

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def on_session_start(self, session_id: str = "", **kwargs: Any) -> HermesEvent:
        """Handle session start. Reset per-session state."""
        with self._lock:
            self._current_session_id = session_id or self._current_session_id
            self._is_first_message = True
            return HermesEvent(
                type="session_start",
                sandbox_key=get_sandbox_key(),
                session_id=self._current_session_id,
                timestamp=_now_ms(),
                is_first_turn=True,
                platform=kwargs.get("platform", ""),
            )

    def on_session_end(self, **kwargs: Any) -> HermesEvent:
        """Handle session/turn end.

        Hermes passes completed/interrupted as booleans (unlike OpenClaw's
        stop_reason string). These MUST be top-level fields in the event
        to match claw-server ClawEvent json tags.
        """
        with self._lock:
            completed = kwargs.get("completed", False)
            interrupted = kwargs.get("interrupted", False)

            if interrupted:
                success = False
            elif completed:
                success = True
            else:
                success = True

            # Retrieve cached lifecycle error
            cached_error = self._last_lifecycle_error.pop(self._current_run_id, None)

            return HermesEvent(
                type="agent_end",
                sandbox_key=get_sandbox_key(),
                run_id=self._current_run_id,
                session_id=self._current_session_id,
                timestamp=_now_ms(),
                success=success,
                completed=completed or None,
                interrupted=interrupted or None,
                lifecycle_error=cached_error,
                model=kwargs.get("model", ""),
                platform=kwargs.get("platform", ""),
            )

    def on_session_finalize(self, **kwargs: Any) -> HermesEvent:
        return HermesEvent(
            type="session_finalize",
            sandbox_key=get_sandbox_key(),
            session_id=str(kwargs.get("session_id") or self._current_session_id or ""),
            timestamp=_now_ms(),
            platform=kwargs.get("platform", ""),
        )

    def on_session_reset(self, **kwargs: Any) -> HermesEvent:
        with self._lock:
            self._cleanup_all()
            return HermesEvent(
                type="session_reset",
                sandbox_key=get_sandbox_key(),
                session_id=str(kwargs.get("session_id") or self._current_session_id or ""),
                timestamp=_now_ms(),
                platform=kwargs.get("platform", ""),
            )

    def on_agent_end(self, run_id: str = "", **kwargs: Any) -> None:
        """Cleanup run-level state when agent finishes."""
        with self._lock:
            rid = run_id or self._current_run_id
            self._cleanup_run_stream(rid)
            self._pending_tool_calls.clear()
            self._finish_sent = {k for k in self._finish_sent if not k.startswith(f"{rid}:")}
            self._slash_run_ids.discard(rid)
            self._blocked_runs.discard(rid)
            self._last_lifecycle_error.pop(rid, None)
            self._new_reset_run_ids.discard(rid)
            self._run_last_activity.pop(rid, None)

    # ------------------------------------------------------------------
    # msg_id management
    # ------------------------------------------------------------------

    def _get_or_create_msg_id(self, run_id: str) -> int:
        """Get or request a msg_id for the current run. Caller must hold _lock."""
        cached = self._msg_id_cache.get(run_id)
        if cached is not None:
            return cached

        msg_id = generate_msg_id()
        if msg_id is None:
            import random
            msg_id = int(time.time() * 1000) * 1000 + random.randint(0, 999)
            logger.warning("%s claw-server unreachable, using fallback msg_id: %d", LOG_PREFIX, msg_id)

        self._msg_id_cache[run_id] = msg_id
        return msg_id

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_all(self) -> None:
        """Reset all mutable state (called on session reset). Caller must hold _lock."""
        self._stream_buffers.clear()
        self._stream_max_seq.clear()
        self._finish_sent.clear()
        self._event_dedup.clear()
        self._hook_dedup.clear()
        self._pending_tool_calls.clear()
        self._msg_id_cache.clear()
        self._run_last_activity.clear()
        self._slash_run_ids.clear()
        self._blocked_runs.clear()
        self._last_lifecycle_error.clear()
        self._new_reset_run_ids.clear()
        self._current_run_id = ""
        self._is_first_message = True

    # ------------------------------------------------------------------
    # Run activity tracking + TTL cleanup (ported from maxclaw runLastActivity)
    # ------------------------------------------------------------------

    def _touch_run(self, run_id: str) -> None:
        """Update activity timestamp for a run. Caller must hold _lock."""
        if run_id:
            self._run_last_activity[run_id] = time.time()

    def _start_cleanup_timer(self) -> None:
        """Start the periodic background cleanup timer."""
        if self._destroyed:
            return
        self._cleanup_timer = threading.Timer(
            RUN_CLEANUP_INTERVAL_SECONDS, self._periodic_cleanup,
        )
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _periodic_cleanup(self) -> None:
        """Periodically clean up stale run state (TTL-based)."""
        if self._destroyed:
            return
        try:
            self._cleanup_stale_runs()
        except Exception as exc:
            logger.warning("%s periodic cleanup error: %s", LOG_PREFIX, exc)
        finally:
            self._start_cleanup_timer()

    def _cleanup_stale_runs(self) -> None:
        """Remove state for runs that have been inactive longer than RUN_TTL_SECONDS."""
        with self._lock:
            cutoff = time.time() - RUN_TTL_SECONDS
            stale_runs = [
                rid for rid, ts in self._run_last_activity.items() if ts < cutoff
            ]
            for rid in stale_runs:
                self._cleanup_run_stream(rid)
                self._run_last_activity.pop(rid, None)
                self._slash_run_ids.discard(rid)
                self._finish_sent = {
                    k for k in self._finish_sent if not k.startswith(f"{rid}:")
                }
            if stale_runs:
                logger.info(
                    "%s TTL cleanup: removed %d stale runs", LOG_PREFIX, len(stale_runs),
                )

    def destroy(self) -> None:
        """Stop background cleanup and release resources."""
        self._destroyed = True
        if self._cleanup_timer is not None:
            self._cleanup_timer.cancel()
            self._cleanup_timer = None
        logger.info("%s StateManager destroyed", LOG_PREFIX)
