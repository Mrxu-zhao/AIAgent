from config import load_control_plane_config
from providers.hermes import HermesProvider
from providers.openclaw import OpenClawProvider


class ExecutorProviderRegistry:
    def __init__(self):
        self._providers = {}

    def register(self, provider):
        self._providers[provider.name] = provider
        return provider

    def get(self, name: str):
        return self._providers[name]

    def list_providers(self):
        return sorted(self._providers.keys())


def build_default_provider_registry() -> ExecutorProviderRegistry:
    config = load_control_plane_config()
    registry = ExecutorProviderRegistry()
    hermes_conf = config.executors["hermes"]
    openclaw_conf = config.executors["openclaw"]
    registry.register(
        HermesProvider(
            command=str(hermes_conf.get("command", "hermes")),
            dispatch_args=list(hermes_conf.get("dispatch_args", ["team", "dispatch"])),
        )
    )
    registry.register(
        OpenClawProvider(
            command=str(openclaw_conf.get("command", "openclaw")),
            dry_run=str(openclaw_conf.get("mode", "dry-run")) != "live",
            dispatch_args=list(openclaw_conf.get("dispatch_args", ["dispatch"])),
        )
    )
    return registry
