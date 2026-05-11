"""
Configuration management for the minimax plugin.

Reads sandbox identity and claw-server connection info from:
  1. /root/.hermes-sandbox/sandbox.json  (primary, written by orchestrator)
  2. Environment variables (override / fallback)

The config is lazily loaded and cached. If sandbox_key is empty on first
read, the cache is *not* stored so subsequent calls retry (the orchestrator
may write the file after plugin load).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "/root/.hermes-sandbox/sandbox.json"
CONFIG_PATH = os.environ.get("CLAW_SANDBOX_CONFIG_PATH", DEFAULT_CONFIG_PATH)

DEFAULT_BRIDGE_PORT = 9090
DEFAULT_CLAW_SERVER_URL = "http://claw-server.internal"

_cached_config: Optional[dict] = None


def _load_file_config() -> dict:
    """Read and parse the sandbox JSON config file."""
    path = Path(CONFIG_PATH)
    if not path.exists():
        logger.debug("Config file not found: %s", CONFIG_PATH)
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning("Failed to parse config file %s: %s", CONFIG_PATH, exc)
    return {}


def get_config() -> dict:
    """Return the merged configuration (file + env overrides).

    Caches the result after the first successful load with a non-empty
    sandbox_key. Subsequent calls return the cached config.
    """
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    file_cfg = _load_file_config()

    config = {
        "sandbox_key": os.environ.get("CLAW_SANDBOX_KEY", "") or file_cfg.get("sandbox_key", ""),
        "claw_server_url": (
            os.environ.get("CLAW_SERVER_URL", "")
            or file_cfg.get("claw_server_url", "")
            or DEFAULT_CLAW_SERVER_URL
        ),
        "bridge_port": int(
            os.environ.get("CLAW_BRIDGE_PORT", "")
            or file_cfg.get("bridge_port", DEFAULT_BRIDGE_PORT)
        ),
        "mcp_server_url": os.environ.get("CLAW_MCP_SERVER_URL", "") or file_cfg.get("mcp_server_url", ""),
        "additional_hooks": file_cfg.get("additional_hooks", {}),
    }

    if config["sandbox_key"]:
        _cached_config = config
    else:
        logger.debug("sandbox_key is empty, config will not be cached (retry on next call)")

    return config


def get_sandbox_key() -> str:
    return get_config().get("sandbox_key", "")


def get_claw_server_url() -> str:
    url = get_config().get("claw_server_url", DEFAULT_CLAW_SERVER_URL)
    return url.rstrip("/")


def get_bridge_port() -> int:
    return get_config().get("bridge_port", DEFAULT_BRIDGE_PORT)


def get_mcp_server_url() -> str:
    return get_config().get("mcp_server_url", "")


def get_additional_hooks_config() -> dict:
    """Return the additional_hooks configuration block.

    Structure (mirroring maxclaw-sandbox):
      {
        "enabled": true,
        "hooks": {
          "pre_api_request": true,
          "post_api_request": true,
          "gateway_event": true,
          ...
        }
      }

    Environment variable CLAW_ADDITIONAL_HOOKS_ENABLED=true acts as a
    shortcut for the global switch when the config block is absent.
    """
    cfg = get_config()
    ah = cfg.get("additional_hooks", {})
    if not isinstance(ah, dict):
        ah = {}

    if "enabled" not in ah:
        env_val = os.environ.get("CLAW_ADDITIONAL_HOOKS_ENABLED", "").lower()
        ah["enabled"] = env_val in ("true", "1", "yes")

    return ah


def is_additional_hook_enabled(hook_name: str) -> bool:
    """Check if a specific additional hook is enabled.

    When the global switch is off, all additional hooks are disabled.
    When the global switch is on, individual hooks default to enabled
    unless explicitly set to false.
    """
    ah = get_additional_hooks_config()
    if not ah.get("enabled", False):
        return False
    hooks = ah.get("hooks", {})
    return hooks.get(hook_name, True)


def reset_config_cache() -> None:
    """Force re-read of config on next access (used after hot-reload)."""
    global _cached_config
    _cached_config = None
