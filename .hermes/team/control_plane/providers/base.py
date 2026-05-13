class ExecutorProvider:
    def __init__(self, name: str, command: str, dispatch_args=None, dry_run: bool = False):
        self.name = name
        self.command = command
        self.dispatch_args = dispatch_args or []
        self.dry_run = dry_run

    def build_dispatch_command(self, agent_id: str, task: str):
        raise NotImplementedError
