import unittest
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import providers.hermes as hermes_provider_module  # noqa: E402


class HermesProviderHealthTests(unittest.TestCase):
    @patch("providers.hermes.check_hermes_health")
    def test_validate_health_fails_fast_when_hermes_not_configured(self, mock_check):
        mock_check.return_value = type(
            "Report",
            (),
            {
                "ok": False,
                "status": "not_configured",
                "message": "not configured",
                "available_commands": ["chat"],
            },
        )()
        provider = hermes_provider_module.HermesProvider(command="hermes", auto_detect=True)

        with self.assertRaises(ValueError) as ctx:
            provider.validate_health()

        self.assertIn("not_configured", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
