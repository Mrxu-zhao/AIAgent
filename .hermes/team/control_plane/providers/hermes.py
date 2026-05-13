from providers.base import ExecutorProvider


class HermesProvider(ExecutorProvider):
    def __init__(self, command: str = "hermes", dispatch_args=None):
        super().__init__(
            name="hermes",
            command=command,
            dispatch_args=dispatch_args or ["team", "dispatch"],
            dry_run=False,
        )

    def build_dispatch_command(self, agent_id: str, task: str):
        return [self.command, *self.dispatch_args, "-a", agent_id, "-t", task]
