from config import load_control_plane_config
from providers.hermes import HermesProvider
from providers.openclaw import OpenClawProvider
from providers.registry import build_default_provider_registry


class HermesExecutorAdapter:
    def __init__(self, hermes_command="hermes", dispatch_script=None):
        self.hermes_command = hermes_command
        self.dispatch_script = dispatch_script
        self.provider = HermesProvider(command=hermes_command)

    def build_dispatch_command(self, agent_id: str, task: str):
        return self.provider.build_dispatch_command(agent_id, task)


class OpenClawExecutorAdapter:
    def __init__(self, openclaw_command="openclaw", dry_run=True, dispatch_args=None):
        self.provider = OpenClawProvider(
            command=openclaw_command,
            dry_run=dry_run,
            dispatch_args=dispatch_args,
        )

    def build_dispatch_command(self, agent_id: str, task: str):
        return self.provider.build_dispatch_command(agent_id, task)


def get_default_executor_adapter():
    config = load_control_plane_config()
    registry = build_default_provider_registry()
    provider = registry.get(config.default_executor)
    if provider.name == "openclaw":
        return OpenClawExecutorAdapter(
            openclaw_command=provider.command,
            dry_run=provider.dry_run,
            dispatch_args=provider.dispatch_args,
        )
    return HermesExecutorAdapter(hermes_command=provider.command)
