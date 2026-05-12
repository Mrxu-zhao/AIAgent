class HermesExecutorAdapter:
    def __init__(self, hermes_command="hermes", dispatch_script=None):
        self.hermes_command = hermes_command
        self.dispatch_script = dispatch_script

    def build_dispatch_command(self, agent_id: str, task: str):
        return [
            self.hermes_command,
            "team",
            "dispatch",
            "-a",
            agent_id,
            "-t",
            task,
        ]


class OpenClawExecutorAdapter:
    def build_dispatch_command(self, agent_id: str, task: str):
        raise NotImplementedError("OpenClaw adapter is reserved for a future phase")
