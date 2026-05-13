import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import governance.approval as approval_module  # noqa: E402
import governance.audit as audit_module  # noqa: E402
import governance.rbac as rbac_module  # noqa: E402


class GovernanceTests(unittest.TestCase):
    def test_rbac_allows_admin_and_blocks_unknown_action(self):
        policy = rbac_module.build_default_rbac_policy()

        self.assertTrue(policy.is_allowed("admin", "control_plane.run"))
        self.assertFalse(policy.is_allowed("viewer", "provider.execute_sensitive"))

    def test_approval_gate_requires_sensitive_commands(self):
        gate = approval_module.ApprovalGate(sensitive_actions={"provider.execute_sensitive"})

        self.assertTrue(gate.requires_approval("provider.execute_sensitive"))
        self.assertFalse(gate.requires_approval("control_plane.run"))

    def test_audit_logger_writes_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = audit_module.AuditLogger(Path(tmp) / "audit.jsonl")
            logger.log("dispatch", {"actor": "admin"})

            entries = logger.read_all()
            self.assertEqual(entries[0]["action"], "dispatch")


if __name__ == "__main__":
    unittest.main()
