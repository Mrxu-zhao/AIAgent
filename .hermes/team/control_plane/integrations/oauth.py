from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

OAUTH_SERVICES: Dict[str, Dict[str, Any]] = {
    "github": {"name": "GitHub", "scopes": ["repo", "read:user"]},
    "gmail": {"name": "Gmail", "scopes": ["gmail.readonly", "gmail.send"]},
    "google_calendar": {"name": "Google Calendar", "scopes": ["calendar.readonly", "calendar.events"]},
    "notion": {"name": "Notion", "scopes": []},
    "slack": {"name": "Slack", "scopes": ["chat:write", "users:read"]},
    "trello": {"name": "Trello", "scopes": ["read", "write"]},
}


@dataclass
class OAuthToken:
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    token_type: str = "Bearer"
    scope: str = ""


class OAuthManager:
    def __init__(self):
        self.exchange_mode = "deferred"

    def list_services(self) -> List[str]:
        return sorted(OAUTH_SERVICES.keys())

    def info(self, service: str) -> Dict[str, Any]:
        config = OAUTH_SERVICES.get(service)
        if config is None:
            return {"error": f"Unknown service: {service}"}
        return {
            "name": config["name"],
            "scopes": list(config["scopes"]),
            "exchange_mode": self.exchange_mode,
        }


def list_services() -> List[str]:
    return sorted(OAUTH_SERVICES.keys())
