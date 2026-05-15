"""Tests for quality gate checker."""
import builtins
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

# Import directly from file path to avoid control_plane/__init__.py issues
import importlib.util

_quality_gate_path = os.path.join(
    os.path.dirname(__file__), "../../.hermes/team/control_plane/delivery/quality_gate.py"
)
_spec = importlib.util.spec_from_file_location("quality_gate", _quality_gate_path)
_quality_gate = importlib.util.module_from_spec(_spec)
# Set module in sys.modules before exec to fix dataclass forward ref
sys.modules["quality_gate"] = _quality_gate
_spec.loader.exec_module(_quality_gate)

GateStatus = _quality_gate.GateStatus
QualityGateChecker = _quality_gate.QualityGateChecker


class TestQualityGateChecker(unittest.TestCase):
    def setUp(self):
        base = os.path.join(os.path.dirname(__file__), "../../.hermes/team/control_plane/delivery")
        self.checker = QualityGateChecker(contracts_dir=os.path.join(base, "contracts"))
        self._temp_dirs = []

    def tearDown(self):
        for path in self._temp_dirs:
            shutil.rmtree(path, ignore_errors=True)

    def _make_checker_with_contract(self, role, contract_body):
        temp_dir = tempfile.mkdtemp(prefix="quality-gate-contract-")
        self._temp_dirs.append(temp_dir)
        contract_path = os.path.join(temp_dir, f"{role}.yaml")
        with open(contract_path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(contract_body).strip() + "\n")
        return QualityGateChecker(contracts_dir=temp_dir)

    def test_backend_all_pass(self):
        deliverables = {
            "coverage": 85,
            "code": "def hello():\n    return 'world'\n",
            "api_doc": "Endpoint: /api/hello\nMethod: GET\nRequest: None\nResponse: string",
        }
        report = self.checker.check("backend", deliverables)
        self.assertEqual(report.role, "backend")
        self.assertEqual(report.overall_status, GateStatus.PASS)
        self.assertGreater(len(report.results), 0)
        for r in report.results:
            self.assertIn(r.status, (GateStatus.PASS, GateStatus.SKIP))

    def test_backend_contract_loads_without_pyyaml_dependency(self):
        deliverables = {
            "coverage": 85,
            "code": "def hello():\n    return 'world'\n",
            "api_doc": "Endpoint: /api/hello\nMethod: GET\nRequest: None\nResponse: string",
        }
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "yaml":
                raise ModuleNotFoundError("No module named 'yaml'")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=guarded_import):
            report = self.checker.check("backend", deliverables)

        self.assertEqual(report.role, "backend")
        self.assertEqual(report.overall_status, GateStatus.PASS)
        self.assertEqual(
            [result.gate_name for result in report.results],
            ["单测覆盖", "代码评审", "接口文档"],
        )

    def test_backend_coverage_fail(self):
        deliverables = {
            "coverage": 50,
            "code": "def hello():\n    return 'world'\n",
            "api_doc": "Endpoint: /api/hello\nMethod: GET\nRequest: None\nResponse: string",
        }
        report = self.checker.check("backend", deliverables)
        self.assertEqual(report.overall_status, GateStatus.FAIL)
        coverage_result = [r for r in report.results if r.gate_name == "单测覆盖"]
        self.assertTrue(coverage_result)
        self.assertEqual(coverage_result[0].status, GateStatus.FAIL)

    def test_backend_missing_deliverables(self):
        deliverables = {}
        report = self.checker.check("backend", deliverables)
        self.assertEqual(report.overall_status, GateStatus.FAIL)

    def test_analyst_contract_passes(self):
        deliverables = {
            "review_minutes": "结论: 通过\n参与人: 产品, 架构, UCD",
            "acceptance_criteria": [
                {"id": "AC-1", "description": "Given user exists, When query runs, Then result is returned"},
                {"id": "AC-2", "description": "可测试且结果明确"},
            ],
            "scope_boundary": {
                "in_scope": ["用户管理", "角色分配"],
                "out_of_scope": ["结算中心"],
            },
        }
        report = self.checker.check("analyst", deliverables)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_architect_contract_passes(self):
        deliverables = {
            "design_doc": "Overview: 架构\nArchitecture: 分层\nData Model: 用户实体\nInterface: /api/users",
            "adr_doc": "ADR-001\nStatus: Accepted\nDecision: 采用事件驱动",
            "api_doc": "Endpoint: /api/users\nMethod: GET\nRequest: page,size\nResponse: list",
        }
        report = self.checker.check("architect", deliverables)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_dba_contract_passes(self):
        deliverables = {
            "ddl": (
                "CREATE TABLE users (id BIGINT PRIMARY KEY, created_at DATETIME, updated_at DATETIME);"
                "\nCREATE INDEX idx_users_name ON users(name);"
            ),
            "explain_report": [
                {"sql": "SELECT * FROM users WHERE name = ?", "type": "range", "rows": 10},
            ],
            "index_plan": {"indexes": ["idx_users_name"], "covered_queries": ["users_by_name"]},
        }
        report = self.checker.check("dba", deliverables)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_frontend_contract_passes(self):
        deliverables = {
            "code": "export const ok = () => true;\n",
            "tests": [{"name": "component renders", "passed": True}],
            "performance_metrics": {"first_screen_ms": 1200, "bundle_kb": 250},
        }
        report = self.checker.check("frontend", deliverables)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_ucd_contract_passes(self):
        deliverables = {
            "design_doc": "Overview: 目标\nArchitecture: 流程\nData Model: 表单项\nInterface: 页面交互",
            "handoff_doc": "页面: 用户列表\n状态: 空态/加载/错误\n资源: Figma链接\n标注: 完整",
            "usability_plan": "目标用户\n场景脚本\n成功标准\n观察记录",
        }
        report = self.checker.check("ucd", deliverables)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_qa_functional_contract_passes(self):
        deliverables = {
            "test_cases": [
                {"title": "创建用户", "steps": ["打开页面", "填写表单"], "expected": "创建成功"}
            ],
            "coverage": 90,
            "bug_reports": [
                {
                    "title": "创建用户失败",
                    "steps": ["打开页面", "点击保存"],
                    "expected": "成功",
                    "actual": "报错",
                }
            ],
        }
        report = self.checker.check("qa-functional", deliverables)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_qa_performance_contract_passes(self):
        deliverables = {
            "perf_plan": "目标\n场景\n并发模型\n数据准备\n监控指标",
            "performance_metrics": {"tps": 320, "p95_ms": 180, "error_rate": 0.01},
            "bottleneck_analysis": {
                "confirmed": True,
                "bottlenecks": [{"component": "mysql", "evidence": "CPU 85%"}],
            },
        }
        report = self.checker.check("qa-performance", deliverables)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_devops_contract_passes(self):
        deliverables = {
            "deployment_config": "deploy:\n  strategy: rolling\nrollback: enabled\nhealthcheck: /health",
            "monitoring_config": "alerts:\n  - cpu\n  - error_rate\ndashboards:\n  - api",
            "emergency_plan": "drill: done\nrollback: documented\nowner: sre",
        }
        report = self.checker.check("devops", deliverables)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_code_review_todo(self):
        deliverables = {
            "code": "def hello():\n    # TODO: implement\n    pass\n",
        }
        report = self.checker.check("backend", deliverables)
        code_review = [r for r in report.results if r.gate_name == "代码评审"]
        self.assertTrue(code_review)
        self.assertIn(code_review[0].status, (GateStatus.WARN, GateStatus.FAIL))

    def test_api_doc_missing_section(self):
        deliverables = {
            "api_doc": "Endpoint: /api/hello\nMethod: GET",
        }
        report = self.checker.check("backend", deliverables)
        api_doc = [r for r in report.results if r.gate_name == "接口文档"]
        self.assertTrue(api_doc)
        self.assertIn(api_doc[0].status, (GateStatus.WARN, GateStatus.FAIL))

    def test_self_checklist_pass(self):
        checker = self._make_checker_with_contract(
            "custom",
            """
            role: custom
            name: 自定义
            delivery_contract:
              quality_gates:
                - gate: 自检清单
                  tool: self_checklist
                  required: true
            """,
        )
        deliverables = {
            "self_checklist": [
                {"text": "Formatted", "checked": True},
                {"text": "Tests pass", "checked": True},
            ],
        }
        report = checker.check("custom", deliverables)
        checklist = [r for r in report.results if r.gate_name == "自检清单"]
        self.assertEqual(checklist[0].status, GateStatus.PASS)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_lint_long_line(self):
        checker = self._make_checker_with_contract(
            "custom",
            """
            role: custom
            name: 自定义
            delivery_contract:
              quality_gates:
                - gate: 静态检查
                  tool: lint_check
                  required: true
            """,
        )
        deliverables = {
            "code": "x = '" + "a" * 130 + "'\n",
        }
        report = checker.check("custom", deliverables)
        lint = [r for r in report.results if r.gate_name == "静态检查"]
        self.assertEqual(lint[0].status, GateStatus.FAIL)
        self.assertEqual(report.overall_status, GateStatus.FAIL)

    def test_test_execution_pass(self):
        checker = self._make_checker_with_contract(
            "custom",
            """
            role: custom
            name: 自定义
            delivery_contract:
              quality_gates:
                - gate: 测试执行
                  tool: test_execution
                  required: true
            """,
        )
        deliverables = {
            "tests": [
                {"name": "test_a", "passed": True},
                {"name": "test_b", "passed": True},
            ],
        }
        report = checker.check("custom", deliverables)
        test_gate = [r for r in report.results if r.gate_name == "测试执行"]
        self.assertEqual(test_gate[0].status, GateStatus.PASS)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_security_scan_dangerous_call(self):
        checker = self._make_checker_with_contract(
            "custom",
            """
            role: custom
            name: 自定义
            delivery_contract:
              quality_gates:
                - gate: 安全扫描
                  tool: security_scan
                  required: true
            """,
        )
        deliverables = {
            "code": "import os\nos.system('ls')\n",
        }
        report = checker.check("custom", deliverables)
        sec = [r for r in report.results if r.gate_name == "安全扫描"]
        self.assertEqual(sec[0].status, GateStatus.FAIL)
        self.assertEqual(report.overall_status, GateStatus.FAIL)

    def test_design_review_pass(self):
        checker = self._make_checker_with_contract(
            "custom",
            """
            role: custom
            name: 自定义
            delivery_contract:
              quality_gates:
                - gate: 设计评审
                  tool: design_review
                  required: true
            """,
        )
        deliverables = {
            "design_doc": "Overview: ...\nArchitecture: ...\nData Model: ...\nInterface: ...",
        }
        report = checker.check("custom", deliverables)
        design = [r for r in report.results if r.gate_name == "设计评审"]
        self.assertEqual(design[0].status, GateStatus.PASS)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_db_review_missing_index(self):
        checker = self._make_checker_with_contract(
            "custom",
            """
            role: custom
            name: 自定义
            delivery_contract:
              quality_gates:
                - gate: 数据库评审
                  tool: db_review
                  required: true
            """,
        )
        deliverables = {
            "ddl": "CREATE TABLE users (id INT PRIMARY KEY);",
        }
        report = checker.check("custom", deliverables)
        db = [r for r in report.results if r.gate_name == "数据库评审"]
        self.assertEqual(db[0].status, GateStatus.FAIL)
        self.assertEqual(report.overall_status, GateStatus.FAIL)

    def test_pr_review_pass(self):
        checker = self._make_checker_with_contract(
            "custom",
            """
            role: custom
            name: 自定义
            delivery_contract:
              quality_gates:
                - gate: PR审查
                  tool: pr_review
                  required: true
            """,
        )
        deliverables = {
            "pr_description": "Summary: ...\nChanges: ...\nTesting: ...",
        }
        report = checker.check("custom", deliverables)
        pr = [r for r in report.results if r.gate_name == "PR审查"]
        self.assertEqual(pr[0].status, GateStatus.PASS)
        self.assertEqual(report.overall_status, GateStatus.PASS)

    def test_unknown_required_gate_tool_fails(self):
        checker = self._make_checker_with_contract(
            "custom-unknown",
            """
            role: custom-unknown
            name: 自定义
            delivery_contract:
              quality_gates:
                - gate: 未知门禁
                  tool: unknown_gate_tool
                  required: true
            """,
        )
        report = checker.check("custom-unknown", {})
        self.assertEqual(report.overall_status, GateStatus.FAIL)
        self.assertTrue(all(result.status == GateStatus.FAIL for result in report.results))

    def test_report_to_dict(self):
        deliverables = {
            "coverage": 90,
            "code": "def hello():\n    return 'world'\n",
            "api_doc": "Endpoint: /api/hello\nMethod: GET\nRequest: None\nResponse: string",
        }
        report = self.checker.check("backend", deliverables)
        d = report.to_dict()
        self.assertEqual(d["role"], "backend")
        self.assertIn(d["overall_status"], ("pass", "warn", "fail", "skip"))
        self.assertIn("summary", d)
        self.assertIn("results", d)

    def test_unknown_role(self):
        with self.assertRaises(FileNotFoundError):
            self.checker.check("nonexistent", {})


if __name__ == "__main__":
    unittest.main()
