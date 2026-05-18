import re
import subprocess

from hermes_health import check_hermes_health
from providers.base import ExecutorProvider


class HermesProvider(ExecutorProvider):
    def __init__(
        self,
        command: str = "hermes",
        dispatch_args=None,
        dispatch_profiles=None,
        preferred_commands=None,
        auto_detect: bool = False,
        probe_args=None,
    ):
        super().__init__(
            name="hermes",
            command=command,
            dispatch_args=dispatch_args or [],
            dry_run=False,
        )
        self.dispatch_profiles = dict(
            dispatch_profiles
            or {
                "team": ["team", "dispatch", "-a", "{agent}", "-t", "{task}"],
                "chat": ["chat", "-q", "[agent:{agent}] {task}", "-Q", "--source", "tool"],
            }
        )
        self.preferred_commands = list(preferred_commands or ["chat", "team"])
        self.auto_detect = auto_detect
        self.probe_args = list(probe_args or ["--help"])

    def _probe_available_commands(self):
        try:
            result = subprocess.run(
                [self.command, *self.probe_args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except FileNotFoundError:
            return set()
        output = f"{result.stdout}\n{result.stderr}".lower()
        return set(re.findall(r"[a-z][a-z0-9-]+", output))

    def _resolve_dispatch_template(self):
        if self.dispatch_args:
            return list(self.dispatch_args)
        if not self.auto_detect and "team" in self.dispatch_profiles:
            return list(self.dispatch_profiles["team"])
        if self.auto_detect:
            available = self._probe_available_commands()
            for candidate in self.preferred_commands:
                if candidate in available and candidate in self.dispatch_profiles:
                    return list(self.dispatch_profiles[candidate])
            if not available and "team" in self.dispatch_profiles:
                return list(self.dispatch_profiles["team"])
        for candidate in self.preferred_commands:
            if candidate in self.dispatch_profiles:
                return list(self.dispatch_profiles[candidate])
        raise ValueError("no hermes dispatch template configured")

    def validate_health(self):
        report = check_hermes_health(self.command, probe_args=self.probe_args)
        if not report.ok and report.status != "command_missing":
            raise ValueError(f"hermes_health:{report.status}:{report.message}")
        return report

    def build_dispatch_command(self, agent_id: str, task: str):
        template = self._resolve_dispatch_template()
        rendered = []
        for token in template:
            rendered.append(str(token).format(agent=agent_id, task=task))
        return [self.command, *rendered]
