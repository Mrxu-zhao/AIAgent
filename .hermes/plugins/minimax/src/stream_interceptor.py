"""
Stream Interceptor — capture token-level streaming output.

Hermes Agent emits streaming tokens through AIAgent._fire_stream_delta().
Since the plugin hook system doesn't provide a per-token hook, we use a
class-level monkey-patch to intercept the call chain:

    Original: AIAgent._fire_stream_delta(text)
    Patched:  _patched_fire_stream_delta(self, text)
                → call original _fire_stream_delta(self, text)
                → forward chunk to claw-server via StateManager

The patch is applied once in register(). On hot-reload, the existing patch
detects the new forwarder/state_manager references and updates the closures
without re-wrapping.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .event_forwarder import EventForwarder
    from .state_manager import StateManager

logger = logging.getLogger(__name__)

LOG_PREFIX = "[MMLOG]"

_PATCH_MARKER = "_minimax_stream_patched"

# Mutable holder so hot-reload can update the references without re-patching
_interceptor_refs: dict = {
    "state_manager": None,
    "forwarder": None,
    "enabled": True,
}
_lock = threading.Lock()


def install_stream_interceptor(
    state_manager: "StateManager",
    forwarder: "EventForwarder",
    chunk_forward_enabled: bool = True,
    _retry: bool = False,
) -> bool:
    """Monkey-patch AIAgent._fire_stream_delta to intercept streaming tokens.

    On first call: wraps the original method.
    On subsequent calls (hot-reload): updates the closure references only.

    Returns True if the patch was (re-)applied.
    """
    _interceptor_refs["state_manager"] = state_manager
    _interceptor_refs["forwarder"] = forwarder
    _interceptor_refs["enabled"] = chunk_forward_enabled

    # Use sys.modules instead of a direct import to avoid circular import:
    # run_agent.py imports model_tools → discover_plugins() → this function,
    # so run_agent is still being initialized and AIAgent is not yet defined.
    run_agent_mod = sys.modules.get("run_agent")
    AIAgent = getattr(run_agent_mod, "AIAgent", None) if run_agent_mod else None

    if AIAgent is None:
        if not _retry:
            # Schedule one retry after run_agent finishes loading.
            threading.Timer(
                1.0,
                lambda: install_stream_interceptor(
                    state_manager, forwarder, chunk_forward_enabled, _retry=True
                ),
            ).start()
            logger.info("%s AIAgent not ready yet (circular import) — retry in 1s", LOG_PREFIX)
        else:
            logger.warning("%s AIAgent not found after retry — stream interception disabled", LOG_PREFIX)
        return False

    with _lock:
        if getattr(AIAgent._fire_stream_delta, _PATCH_MARKER, False):
            logger.info("%s Stream interceptor refs updated (hot-reload)", LOG_PREFIX)
            return True

        original_method = AIAgent._fire_stream_delta

        def _patched_fire_stream_delta(self_agent, text: str) -> None:
            # 1. Call original method FIRST so internal text transformations
            #    (e.g. _stream_needs_break prepending "\n\n") happen before
            #    we capture the delta. The original method fires display and
            #    TTS callbacks.
            original_method(self_agent, text)

            # 2. Forward the delta to claw-server
            if _interceptor_refs["enabled"] and text:
                try:
                    sm = _interceptor_refs["state_manager"]
                    fwd = _interceptor_refs["forwarder"]
                    if sm is not None and fwd is not None:
                        run_id = getattr(self_agent, "session_id", "") or ""
                        chunk_event = sm.accumulate_stream_delta(text, run_id=run_id)
                        if chunk_event is not None:
                            fwd.forward(chunk_event)
                except Exception as exc:
                    logger.debug("%s chunk forward error: %s", LOG_PREFIX, exc)

        _patched_fire_stream_delta.__name__ = "_fire_stream_delta"
        _patched_fire_stream_delta.__doc__ = original_method.__doc__
        setattr(_patched_fire_stream_delta, _PATCH_MARKER, True)

        AIAgent._fire_stream_delta = _patched_fire_stream_delta
        logger.info("%s Stream interceptor installed on AIAgent._fire_stream_delta", LOG_PREFIX)
        return True


def uninstall_stream_interceptor() -> bool:
    """Disable the stream interceptor (stops forwarding, doesn't remove patch)."""
    _interceptor_refs["enabled"] = False
    _interceptor_refs["state_manager"] = None
    _interceptor_refs["forwarder"] = None
    logger.info("%s Stream interceptor disabled", LOG_PREFIX)
    return True
