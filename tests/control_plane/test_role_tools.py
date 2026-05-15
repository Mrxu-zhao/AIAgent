import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.role_tools.architect_tools import (
    generate_architecture_doc_handler,
    review_api_design_handler,
)
from tools.role_tools.backend_tools import (
    generate_controller_handler,
    generate_mapper_handler,
    generate_service_handler,
)
from tools.role_tools.dba_tools import analyze_slow_query_handler, generate_ddl_handler
from tools.role_tools.devops_tools import (
    generate_dockerfile_handler,
    generate_k8s_manifests_handler,
)
from tools.role_tools.frontend_tools import (
    generate_api_client_handler,
    generate_vue_component_handler,
)
from tools.role_tools.qa_tools import generate_test_cases_handler
from tools.role_tools.requirements_tools import generate_prd_handler
from tools.role_tools.ucd_tools import generate_design_spec_handler
from tools.spec import ToolExecutionContext


class BackendToolsTests(unittest.TestCase):
    def test_generate_controller_creates_spring_controller(self):
        context = ToolExecutionContext(task_id="bt-1", agent_id="backend-dev", backend="hermes")
        result = generate_controller_handler(
            context,
            {
                "class_name": "UserController",
                "package": "com.example.controller",
                "endpoint": "/api/users",
                "entity_name": "User",
            },
        )
        self.assertTrue(result.ok)
        self.assertIn("@RestController", result.content)
        self.assertIn("UserController", result.content)
        self.assertIn("/api/users", result.content)

    def test_generate_service_creates_spring_service(self):
        context = ToolExecutionContext(task_id="bt-2", agent_id="backend-dev", backend="hermes")
        result = generate_service_handler(
            context,
            {
                "class_name": "UserService",
                "package": "com.example.service",
                "entity_name": "User",
            },
        )
        self.assertTrue(result.ok)
        self.assertIn("@Service", result.content)
        self.assertIn("UserService", result.content)

    def test_generate_mapper_creates_mybatis_mapper(self):
        context = ToolExecutionContext(task_id="bt-3", agent_id="backend-dev", backend="hermes")
        result = generate_mapper_handler(
            context,
            {
                "class_name": "UserMapper",
                "package": "com.example.mapper",
                "entity_name": "User",
                "table_name": "t_user",
            },
        )
        self.assertTrue(result.ok)
        self.assertIn("@Mapper", result.content)
        self.assertIn("UserMapper", result.content)


class FrontendToolsTests(unittest.TestCase):
    def test_generate_vue_component(self):
        context = ToolExecutionContext(task_id="ft-1", agent_id="frontend-dev", backend="hermes")
        result = generate_vue_component_handler(
            context,
            {"component_name": "UserList", "props": ["users"], "emits": ["select"]},
        )
        self.assertTrue(result.ok)
        self.assertIn("<template>", result.content)
        self.assertIn("userlist-container", result.content)

    def test_generate_api_client(self):
        context = ToolExecutionContext(task_id="ft-2", agent_id="frontend-dev", backend="hermes")
        result = generate_api_client_handler(
            context,
            {"api_name": "User", "endpoint": "/api/users", "methods": ["GET", "POST"]},
        )
        self.assertTrue(result.ok)
        self.assertIn("useUserApi", result.content)
        self.assertIn("/api/users", result.content)


class ArchitectToolsTests(unittest.TestCase):
    def test_generate_architecture_doc(self):
        context = ToolExecutionContext(task_id="at-1", agent_id="architect", backend="hermes")
        result = generate_architecture_doc_handler(
            context,
            {"system_name": "Order System", "requirements": "Support 10k orders per day"},
        )
        self.assertTrue(result.ok)
        self.assertIn("Order System", result.content)
        self.assertIn("架构设计", result.content)

    def test_review_api_design(self):
        context = ToolExecutionContext(task_id="at-2", agent_id="architect", backend="hermes")
        result = review_api_design_handler(
            context,
            {"api_spec": "GET /api/users"},
        )
        self.assertTrue(result.ok)
        self.assertIn("RESTful", result.content)


class DBAToolsTests(unittest.TestCase):
    def test_generate_ddl(self):
        context = ToolExecutionContext(task_id="dt-1", agent_id="dba", backend="hermes")
        result = generate_ddl_handler(
            context,
            {
                "table_name": "t_user",
                "columns": [
                    {"name": "username", "type": "VARCHAR(50)", "required": True, "comment": "用户名"},
                    {"name": "email", "type": "VARCHAR(100)", "required": False, "comment": "邮箱"},
                ],
                "table_comment": "用户表",
            },
        )
        self.assertTrue(result.ok)
        self.assertIn("CREATE TABLE", result.content)
        self.assertIn("t_user", result.content)

    def test_analyze_slow_query(self):
        context = ToolExecutionContext(task_id="dt-2", agent_id="dba", backend="hermes")
        result = analyze_slow_query_handler(
            context,
            {"sql": "SELECT * FROM t_user WHERE name = 'test'", "explain": "ALL"},
        )
        self.assertTrue(result.ok)
        self.assertIn("慢查询", result.content)


class QAToolsTests(unittest.TestCase):
    def test_generate_test_cases(self):
        context = ToolExecutionContext(task_id="qt-1", agent_id="qa-functional", backend="hermes")
        result = generate_test_cases_handler(
            context,
            {"requirement": "用户登录功能", "feature": "用户登录"},
        )
        self.assertTrue(result.ok)
        self.assertIn("测试用例", result.content)
        self.assertIn("TC-001", result.content)


class DevOpsToolsTests(unittest.TestCase):
    def test_generate_dockerfile_for_spring_boot(self):
        context = ToolExecutionContext(task_id="dot-1", agent_id="devops", backend="hermes")
        result = generate_dockerfile_handler(
            context,
            {"app_type": "spring-boot", "app_name": "user-service", "port": 8080},
        )
        self.assertTrue(result.ok)
        self.assertIn("FROM eclipse-temurin", result.content)

    def test_generate_k8s_manifests(self):
        context = ToolExecutionContext(task_id="dot-2", agent_id="devops", backend="hermes")
        result = generate_k8s_manifests_handler(
            context,
            {"service_name": "user-service", "image": "user-service:v1", "port": 8080, "replicas": 3},
        )
        self.assertTrue(result.ok)
        self.assertIn("Deployment", result.content)
        self.assertIn("Service", result.content)


class UCDToolsTests(unittest.TestCase):
    def test_generate_design_spec(self):
        context = ToolExecutionContext(task_id="ut-1", agent_id="ucd", backend="hermes")
        result = generate_design_spec_handler(
            context,
            {"feature": "用户中心", "platform": "web"},
        )
        self.assertTrue(result.ok)
        self.assertIn("设计规范", result.content)


class RequirementsToolsTests(unittest.TestCase):
    def test_generate_prd(self):
        context = ToolExecutionContext(task_id="rt-1", agent_id="requirements-analyst", backend="hermes")
        result = generate_prd_handler(
            context,
            {"feature": "用户登录", "background": "需要支持手机号+验证码登录"},
        )
        self.assertTrue(result.ok)
        self.assertIn("产品需求文档", result.content)
        self.assertIn("用户故事", result.content)
