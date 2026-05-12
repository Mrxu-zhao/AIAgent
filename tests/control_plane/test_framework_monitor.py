import threading
import unittest

from tests.control_plane.test_support import load_framework_module


monitor_module = load_framework_module("monitor")


class MonitorRegressionTests(unittest.TestCase):
    def test_dashboard_returns_without_deadlock(self):
        monitor = monitor_module.Monitor()
        result = {"done": False}

        def run():
            monitor.get_dashboard_data()
            result["done"] = True

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(1.0)

        self.assertTrue(result["done"], "dashboard 璋冪敤搴斿湪 1 绉掑唴杩斿洖")


if __name__ == "__main__":
    unittest.main()

