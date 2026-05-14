import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DocumentationContractsTests(unittest.TestCase):
    def test_control_plane_readme_links_to_overview_and_runtime_governance(self):
        readme = (ROOT / ".hermes" / "team" / "control_plane" / "README.md").read_text(encoding="utf-8")

        self.assertIn("docs/architecture/control-plane-overview.md", readme)
        self.assertIn("docs/contracts/handoff-contract.md", readme)
        self.assertIn("docs/contracts/provider-contracts.md", readme)
        self.assertIn("docs/runtime/runtime-governance.md", readme)
        self.assertIn("docs/runtime/handoff-and-continuation.md", readme)

    def test_overview_and_contract_docs_exist_with_expected_topics(self):
        overview = (ROOT / "docs" / "architecture" / "control-plane-overview.md").read_text(encoding="utf-8")
        handoff_contract = (ROOT / "docs" / "contracts" / "handoff-contract.md").read_text(encoding="utf-8")
        provider_contracts = (ROOT / "docs" / "contracts" / "provider-contracts.md").read_text(encoding="utf-8")

        self.assertIn("phase1-7", overview)
        self.assertIn("当前推荐入口", overview)
        self.assertIn("已支持边界", overview)
        self.assertIn("未支持边界", overview)

        self.assertIn("control_plane/protocols/handoff.py", handoff_contract)
        self.assertIn("control_plane/protocols/handoff.schema.json", handoff_contract)
        self.assertIn("MessageType.HANDOFF", handoff_contract)
        self.assertIn("selected_backend", handoff_contract)
        self.assertIn("backend_reason", handoff_contract)

        self.assertIn("providers/hermes.py", provider_contracts)
        self.assertIn("providers/openclaw.py", provider_contracts)
        self.assertIn("executor_backend", provider_contracts)
        self.assertIn("selected_backend", provider_contracts)
        self.assertIn("target_backend", provider_contracts)

    def test_runtime_docs_describe_state_layout_and_query_surface(self):
        runtime_governance = (ROOT / "docs" / "runtime" / "runtime-governance.md").read_text(encoding="utf-8")
        handoff_runtime = (ROOT / "docs" / "runtime" / "handoff-and-continuation.md").read_text(encoding="utf-8")

        self.assertIn("state/fixtures/", runtime_governance)
        self.assertIn("state/runs/workflow_runtime/", runtime_governance)
        self.assertIn("state/runs/handoffs/", runtime_governance)
        self.assertIn("state/runs/tool-runtime/", runtime_governance)
        self.assertIn("viewer", runtime_governance)
        self.assertIn("operator/admin", runtime_governance)

        self.assertIn("TaskCard", handoff_runtime)
        self.assertIn("workflow continuation", handoff_runtime)
        self.assertIn("query workflow", handoff_runtime)
        self.assertIn("query handoff", handoff_runtime)
        self.assertIn("query audit", handoff_runtime)

    def test_repository_agents_guardrail_doc_exists_with_required_anchors(self):
        agents_doc = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("README.md", agents_doc)
        self.assertIn("CODE_WIKI.md", agents_doc)
        self.assertIn(".hermes/team/control_plane/", agents_doc)
        self.assertIn(".hermes/team/调度框架/", agents_doc)
        self.assertIn("已读文件", agents_doc)
        self.assertIn("确认事实", agents_doc)
        self.assertIn("验证", agents_doc)


if __name__ == "__main__":
    unittest.main()
