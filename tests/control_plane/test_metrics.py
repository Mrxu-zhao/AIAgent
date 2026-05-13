import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import observability.metrics as metrics_module  # noqa: E402


class MetricsTests(unittest.TestCase):
    def test_metrics_registry_renders_prometheus_text(self):
        registry = metrics_module.MetricsRegistry()
        registry.set_gauge("improvement_dashboard_availability_ratio", 1.0)
        registry.inc_counter("improvement_test_files_total", 1)

        text = registry.render_prometheus_text()

        self.assertIn("improvement_dashboard_availability_ratio", text)
        self.assertIn("improvement_test_files_total", text)


if __name__ == "__main__":
    unittest.main()
