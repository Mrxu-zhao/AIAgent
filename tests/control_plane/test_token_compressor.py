import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from runtime.token_compressor import MemoryTreeManager, TokenCompressor


class TokenCompressorTests(unittest.TestCase):
    def test_tool_output_is_compressed(self):
        compressor = TokenCompressor()
        text = "\n".join(f"line {index}" for index in range(120))
        result = compressor.compress(text, "tool")
        self.assertLess(result.comp_tokens, result.orig_tokens)

    def test_memory_tree_produces_long_term_summary(self):
        tree = MemoryTreeManager(short_term=20, medium_term=40, long_term=40)
        for index in range(10):
            tree.add({"role": "user", "content": f"message {index} " * 5})
        context = tree.get_context()
        self.assertTrue(any(item["content"].startswith("[长期记忆]") for item in context))


if __name__ == "__main__":
    unittest.main()
