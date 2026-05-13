class RBACPolicy:
    def __init__(self, rules):
        self.rules = rules

    def is_allowed(self, role: str, action: str) -> bool:
        return action in self.rules.get(role, set())


def build_default_rbac_policy() -> RBACPolicy:
    return RBACPolicy(
        {
            "admin": {"control_plane.run", "control_plane.dispatch", "provider.execute_sensitive", "monitor.export"},
            "operator": {"control_plane.run", "control_plane.dispatch", "monitor.export"},
            "viewer": {"monitor.read"},
        }
    )
