from providers.base import ExecutorProvider


class OpenClawProvider(ExecutorProvider):
    def __init__(self, command: str = "openclaw", dry_run: bool = True, dispatch_args=None):
        super().__init__(
            name="openclaw",
            command=command,
            dispatch_args=dispatch_args or ["dispatch"],
            dry_run=dry_run,
        )

    def build_dispatch_command(self, agent_id: str, task: str):
        mode_flag = "--dry-run" if self.dry_run else "--execute"
        return [self.command, *self.dispatch_args, mode_flag, "--agent", agent_id, "--task", task]
