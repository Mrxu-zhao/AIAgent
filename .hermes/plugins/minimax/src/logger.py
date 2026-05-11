"""
Logging middleware — unified, structured, single-line logging system.

All minimax business logs share the global prefix [MMLOG] for easy grep/filtering.
Scene-specific second-level tags identify the log source:

  [MMLOG][HOOK:IN]    — plugin hook callback received (raw kwargs + context)
  [MMLOG][HOOK:DONE]  — plugin hook callback completed successfully
  [MMLOG][HOOK:ERR]   — plugin hook callback failed (with exception + traceback)
  [MMLOG][FWD:SEND]   — event forward request to claw-server (full payload)
  [MMLOG][FWD:RESP]   — event forward response from claw-server (trace_id, status, duration)
  [MMLOG][HTTP:RECV]  — HTTP request received from claw-server (method, path, body)
  [MMLOG][HTTP:DONE]  — HTTP request completed (status, duration)
  [MMLOG][GW:RECV]    — gateway hook event received (event_type, context summary)
  [MMLOG][GW:FWD]     — gateway hook event forwarded (trace_id, status, duration)

Format: [MMLOG][TAG] key=value key=value payload={...json...}
Everything on a single line for log-collection and grep friendliness.

Ported from maxclaw-sandbox/extensions/minimax/src/logger.ts.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Any, Callable, Dict, Optional, Set

LOG_PREFIX = "[MMLOG]"

# ── Key=value formatter ───────────────────────────────────────────────────────

def _fmt(**pairs: Any) -> str:
    """Format key=value pairs into a single-line string."""
    parts = []
    for k, v in pairs.items():
        if v is None or v == "":
            continue
        sv = str(v)
        if " " in sv:
            parts.append(f'{k}="{sv}"')
        else:
            parts.append(f"{k}={sv}")
    return " ".join(parts)


# ── JSON serializer (single-line, safe) ───────────────────────────────────────

def _to_json(obj: Any) -> str:
    if obj is None:
        return "null"
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


# ── Heavy-field redaction ─────────────────────────────────────────────────────
# Only redact fields that are pure noise in logs (conversation history, system
# prompt). All other business data (content, result, tool_result, etc.) is
# printed in full. Add field names to the sets below to extend.

_REDACT_LIST_FIELDS: Set[str] = {
    "conversation_history",  # pre/post_llm_call — full conversation history
    "messages",              # session context, system messages
}

_REDACT_LARGE_FIELDS: Set[str] = {
    "system_prompt",         # large system prompt
}

# Fields whose content is important but can be very long; show head + tail.
_ELLIPSIS_FIELDS: Set[str] = {
    "result",          # post_tool_call — tool execution output
    "tool_result",     # HermesEvent tool_call_finish — tool result
    "assistant_response",  # post_llm_call — final LLM response
    "content",         # agent_message — full message content
}
_ELLIPSIS_THRESHOLD = 1024
_ELLIPSIS_HEAD = 256
_ELLIPSIS_TAIL = 256


def _ellipsis(s: str) -> str:
    if len(s) <= _ELLIPSIS_THRESHOLD:
        return s
    omitted = len(s) - _ELLIPSIS_HEAD - _ELLIPSIS_TAIL
    return f"{s[:_ELLIPSIS_HEAD]}...[omitted {omitted} chars]...{s[-_ELLIPSIS_TAIL:]}"


def _ellipsis_value(v: Any) -> Any:
    if isinstance(v, str):
        return _ellipsis(v)
    if v and isinstance(v, dict):
        try:
            s = json.dumps(v, ensure_ascii=False, default=str)
            if len(s) <= _ELLIPSIS_THRESHOLD:
                return v
            return _ellipsis(s)
        except Exception:
            return v
    return v


def _summarize_value(v: Any) -> str:
    if isinstance(v, str):
        return f"[string len={len(v)}]"
    if isinstance(v, list):
        return f"[list {len(v)} items]"
    if isinstance(v, dict):
        try:
            return f"[dict len={len(json.dumps(v, default=str))}]"
        except Exception:
            return "[dict]"
    return str(v)


def _redact_heavy_fields(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of obj with large/noisy fields redacted or ellipsis-ed."""
    out: Dict[str, Any] = {}
    for k, v in obj.items():
        if k in _REDACT_LIST_FIELDS and isinstance(v, list):
            out[k] = f"[{len(v)} items]"
        elif k in _REDACT_LARGE_FIELDS and v is not None:
            out[k] = _summarize_value(v)
        elif k in _ELLIPSIS_FIELDS and v is not None:
            out[k] = _ellipsis_value(v)
        else:
            out[k] = v
    return out


def _redact_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Redact heavy fields from a hook's kwargs dict."""
    return _redact_heavy_fields(kwargs)


# ── Hook middleware ───────────────────────────────────────────────────────────

def wrap_hook(
    log: logging.Logger,
    hook_name: str,
    handler: Callable,
) -> Callable:
    """Wrap a plugin hook handler with structured entry + completion logging.

    Entry  [MMLOG][HOOK:IN]:   hook name, tracking fields, full raw kwargs
    Done   [MMLOG][HOOK:DONE]: hook name, tracking fields, duration, optional return value
    Error  [MMLOG][HOOK:ERR]:  hook name, tracking fields, duration, error message + traceback
    """
    def wrapper(**kwargs: Any) -> Any:
        # Extract tracking fields from kwargs (hermes-agent convention)
        run_id = (
            kwargs.get("task_id")
            or kwargs.get("session_id")
            or ""
        )
        session_id = kwargs.get("session_id", "")
        model = kwargs.get("model", "")
        platform = kwargs.get("platform", "")

        tracking = _fmt(
            name=hook_name,
            run=run_id or None,
            sess=session_id or None,
            model=model or None,
            platform=platform or None,
        )

        redacted = _redact_kwargs(kwargs)
        log.warning(
            "%s[HOOK:IN] %s kwargs=%s",
            LOG_PREFIX, tracking, _to_json(redacted),
        )

        start = time.perf_counter()
        try:
            result = handler(**kwargs)
            dur_ms = int((time.perf_counter() - start) * 1000)
            done_kv = _fmt(name=hook_name, run=run_id or None, status="ok", dur=f"{dur_ms}ms")
            if result is not None:
                log.warning(
                    "%s[HOOK:DONE] %s result=%s",
                    LOG_PREFIX, done_kv, _to_json(result),
                )
            else:
                log.warning("%s[HOOK:DONE] %s", LOG_PREFIX, done_kv)
            return result
        except Exception as exc:
            dur_ms = int((time.perf_counter() - start) * 1000)
            err_msg = str(exc)
            tb = traceback.format_exc()
            err_kv = _fmt(name=hook_name, run=run_id or None, status="error", dur=f"{dur_ms}ms", err=err_msg[:200])
            log.warning("%s[HOOK:ERR] %s", LOG_PREFIX, err_kv)
            log.warning("%s[HOOK:ERR] traceback: %s", LOG_PREFIX, tb)
            # Do not re-raise: hooks must not crash hermes-agent

    wrapper.__name__ = handler.__name__ if hasattr(handler, "__name__") else hook_name
    return wrapper


# ── Event forward middleware ──────────────────────────────────────────────────

def log_fwd_send(
    log: logging.Logger,
    event_type: str,
    run_id: str,
    session_id: str,
    trace_id: str,
    payload: Any,
) -> None:
    """Log an outbound event before sending to claw-server.

    [MMLOG][FWD:SEND]: event type, run_id, session_id, trace_id, full payload
    """
    kv = _fmt(
        type=event_type,
        run=run_id or None,
        sess=session_id or None,
        trace=trace_id or None,
    )
    log.warning("%s[FWD:SEND] %s payload=%s", LOG_PREFIX, kv, _to_json(payload))


def log_fwd_resp(
    log: logging.Logger,
    event_type: str,
    run_id: str,
    trace_id: str,
    ok: bool,
    http_status: Optional[int],
    dur_ms: int,
    body: Any = None,
    error: Optional[str] = None,
) -> None:
    """Log the response from claw-server after forwarding an event.

    [MMLOG][FWD:RESP]: event type, run_id, trace_id, status, http code, duration, body/error
    """
    kv = _fmt(
        type=event_type,
        run=run_id or None,
        trace=trace_id or None,
        status="ok" if ok else "fail",
        http=http_status,
        dur=f"{dur_ms}ms",
    )
    if ok:
        log.warning("%s[FWD:RESP] %s body=%s", LOG_PREFIX, kv, _to_json(body))
    else:
        log.warning("%s[FWD:RESP] %s err=%s", LOG_PREFIX, kv, error or "unknown")


# ── HTTP Server logging ───────────────────────────────────────────────────────

def log_http_recv(
    log: logging.Logger,
    method: str,
    path: str,
    body: Optional[Dict[str, Any]],
) -> None:
    """Log an incoming HTTP request.

    [MMLOG][HTTP:RECV]: method, path, full request body (with heavy field redaction)
    """
    redacted_body = _redact_heavy_fields(body) if body else body
    log.info(
        "%s[HTTP:RECV] %s body=%s",
        LOG_PREFIX, _fmt(method=method, path=path), _to_json(redacted_body),
    )


def log_http_done(
    log: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    start_time: float,
    **extra: Any,
) -> None:
    """Log HTTP request completion.

    [MMLOG][HTTP:DONE]: method, path, status code, duration, extra context
    """
    dur_ms = int((time.perf_counter() - start_time) * 1000)
    kv = _fmt(
        method=method,
        path=path,
        status=status_code,
        dur=f"{dur_ms}ms",
        **{k: v for k, v in extra.items() if v is not None and v != ""},
    )
    line = f"{LOG_PREFIX}[HTTP:DONE] {kv}"
    if status_code >= 500:
        log.error(line)
    elif status_code >= 400:
        log.warning(line)
    else:
        log.info(line)


# ── Gateway hook logging ──────────────────────────────────────────────────────
# NOTE: log_gw_* helpers are defined here for documentation/reference.
# The gateway hook handler (hooks/minimax-gateway/handler.py) is a separate
# module that cannot import from this package, so it inlines the same patterns
# directly. If gateway logging ever moves into the plugin process, use these.
