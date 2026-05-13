class ApprovalGate:
    def __init__(self, sensitive_actions=None):
        self.sensitive_actions = set(sensitive_actions or [])

    def requires_approval(self, action: str) -> bool:
        return action in self.sensitive_actions
