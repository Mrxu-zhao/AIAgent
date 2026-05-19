import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from intelligence.code_intelligence import CodeReviewer


class CodeIntelligenceTests(unittest.TestCase):
    def test_code_reviewer_detects_security_findings(self):
        reviewer = CodeReviewer()
        result = reviewer.review("password = 'secret'\neval(user_input)")
        self.assertGreaterEqual(len(result.security_concerns), 1)
        self.assertLess(result.score, 100.0)


if __name__ == "__main__":
    unittest.main()
