class RBACPolicy:
    def __init__(self, rules):
        self.rules = rules

    def is_allowed(self, role: str, action: str) -> bool:
        return action in self.rules.get(role, set())


def build_default_rbac_policy() -> RBACPolicy:
    return RBACPolicy(
        {
            "admin": {
                "control_plane.run",
                "control_plane.dispatch",
                "provider.execute_sensitive",
                "provider.openclaw.live",
                "monitor.export",
                "query.workflow",
                "query.handoff",
                "query.audit.read",
                "tool.read.generic",
                "tool.read.knowledge",
                "tool.read.handoff",
                "tool.read.workflow",
                "tool.read.file",
                "tool.read.bus",
                "tool.write.generic",
                "tool.route",
                "tool.dispatch",
            },
            "operator": {
                "control_plane.run",
                "control_plane.dispatch",
                "monitor.export",
                "query.workflow",
                "query.handoff",
                "query.audit.read",
                "tool.read.generic",
                "tool.read.knowledge",
                "tool.read.handoff",
                "tool.read.workflow",
                "tool.read.file",
                "tool.read.bus",
                "tool.write.generic",
                "tool.route",
                "tool.dispatch",
            },
            "viewer": {
                "monitor.read",
                "query.workflow",
                "query.handoff",
                "query.audit.read",
                "tool.read.generic",
                "tool.read.knowledge",
                "tool.read.handoff",
                "tool.read.workflow",
                "tool.read.file",
                "tool.read.bus",
            },
        }
    )
