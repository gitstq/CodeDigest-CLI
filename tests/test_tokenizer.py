"""
Tokenizer 模块单元测试。

测试 token 估算准确性、预算控制和 CJK 与英文的估算差异。
仅使用 Python 标准库 unittest 框架。
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codedigest.cli import Tokenizer


class TestTokenEstimationAccuracy(unittest.TestCase):
    """测试 token 估算的准确性。"""

    def test_empty_string(self) -> None:
        """测试空字符串的 token 估算为零。"""
        self.assertEqual(Tokenizer.estimate_tokens(""), 0)

    def test_single_word(self) -> None:
        """测试单个英文单词的 token 估算。"""
        # "hello" 是 5 个字符，约 5/4 ≈ 1 token
        tokens = Tokenizer.estimate_tokens("hello")
        self.assertGreater(tokens, 0)
        self.assertLessEqual(tokens, 3)  # 合理范围

    def test_long_english_text(self) -> None:
        """测试长英文文本的 token 估算。"""
        text = "The quick brown fox jumps over the lazy dog. " * 100
        tokens = Tokenizer.estimate_tokens(text)
        # 约 4500 字符 / 4 ≈ 1125 tokens
        self.assertGreater(tokens, 800)
        self.assertLess(tokens, 1500)

    def test_code_like_text(self) -> None:
        """测试代码类文本的 token 估算。"""
        code = (
            "def fibonacci(n: int) -> int:\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    return fibonacci(n - 1) + fibonacci(n - 2)\n"
        ) * 20
        tokens = Tokenizer.estimate_tokens(code)
        self.assertGreater(tokens, 0)
        # 代码中包含大量 ASCII 字符，约 4 字符/token
        expected_approx = len(code) / 4
        self.assertAlmostEqual(tokens, expected_approx, delta=expected_approx * 0.3)

    def test_whitespace_only(self) -> None:
        """测试纯空白字符的 token 估算。"""
        tokens = Tokenizer.estimate_tokens("   \n\t  \n")
        self.assertGreater(tokens, 0)

    def test_special_characters(self) -> None:
        """测试特殊字符的 token 估算。"""
        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        tokens = Tokenizer.estimate_tokens(text)
        self.assertGreater(tokens, 0)

    def test_mixed_content(self) -> None:
        """测试混合内容的 token 估算。"""
        text = (
            "# This is a Python comment\n"
            "def hello():\n"
            "    print('Hello, World!')\n"
            "    # 中文注释\n"
            "    return 42\n"
        )
        tokens = Tokenizer.estimate_tokens(text)
        self.assertGreater(tokens, 0)


class TestBudgetControl(unittest.TestCase):
    """测试 token 预算控制功能。"""

    def test_within_budget(self) -> None:
        """测试文本在预算内时不被截断。"""
        text = "Hello, World!"
        budget = 100
        result, used = Tokenizer.truncate_to_budget(text, budget)
        self.assertEqual(result, text)
        self.assertGreater(used, 0)
        self.assertLessEqual(used, budget)

    def test_exceeds_budget(self) -> None:
        """测试超出预算时文本被截断。"""
        text = "The quick brown fox jumps over the lazy dog. " * 1000
        budget = 50
        result, used = Tokenizer.truncate_to_budget(text, budget)
        self.assertLess(len(result), len(text))
        self.assertIn("truncated", result)
        self.assertLessEqual(used, budget + 20)  # 允许截断消息的少量溢出

    def test_zero_budget(self) -> None:
        """测试零预算时返回空字符串。"""
        text = "Hello, World!"
        result, used = Tokenizer.truncate_to_budget(text, 0)
        self.assertEqual(result, "")
        self.assertEqual(used, 0)

    def test_budget_with_prior_usage(self) -> None:
        """测试有已使用 token 时正确计算剩余预算。"""
        text = "Hello, World! " * 100
        budget = 200
        prior_used = 150
        result, used = Tokenizer.truncate_to_budget(text, budget, prior_used)
        self.assertLess(len(result), len(text))
        self.assertGreater(used, prior_used)
        self.assertLessEqual(used, budget + 20)

    def test_exact_budget(self) -> None:
        """测试文本恰好等于预算时不截断。"""
        text = "a" * 400  # 约 100 tokens
        budget = 100
        result, used = Tokenizer.truncate_to_budget(text, budget)
        # 文本约 100 tokens，应在预算内
        self.assertEqual(result, text)

    def test_very_small_budget(self) -> None:
        """测试极小预算。"""
        text = "This is a longer piece of text that should be truncated."
        budget = 5
        result, used = Tokenizer.truncate_to_budget(text, budget)
        self.assertLess(len(result), len(text))
        self.assertLessEqual(used, budget + 20)

    def test_truncation_preserves_newlines(self) -> None:
        """测试截断不会在多字节字符中间断开。"""
        text = "你好世界\n" * 100
        budget = 30
        result, used = Tokenizer.truncate_to_budget(text, budget)
        # 不应以不完整的字符结尾（截断消息除外）
        self.assertTrue(result.endswith("truncated to fit token budget]") or
                        result.endswith("\n"))


class TestCJKVsEnglish(unittest.TestCase):
    """测试 CJK 与英文 token 估算的差异。"""

    def test_cjk_more_tokens_than_same_length_english(self) -> None:
        """测试相同字符数的 CJK 文本比英文文本产生更多 token。"""
        # 100 个中文字符 vs 100 个英文字符
        cjk_text = "这是一段中文测试文本，用于验证中日韩字符的token估算准确性。" * 3
        eng_text = "This is an English test text for verifying token estimation accuracy." * 3

        # 使两者长度相近
        cjk_text = cjk_text[:100]
        eng_text = eng_text[:100]

        cjk_tokens = Tokenizer.estimate_tokens(cjk_text)
        eng_tokens = Tokenizer.estimate_tokens(eng_text)

        # CJK 文本应产生更多 token（因为 ~1.5 字符/token vs ~4 字符/token）
        self.assertGreater(cjk_tokens, eng_tokens)

    def test_cjk_token_ratio(self) -> None:
        """测试 CJK 文本的 token 比率约为 1.5 字符/token。"""
        text = "中文测试文本" * 50  # 250 个中文字符
        tokens = Tokenizer.estimate_tokens(text)
        # 250 / 1.5 ≈ 166 tokens (int 截断)
        expected = int(250 / 1.5)
        self.assertAlmostEqual(tokens, expected, delta=expected * 0.3)

    def test_english_token_ratio(self) -> None:
        """测试英文文本的 token 比率约为 4 字符/token。"""
        text = "Hello world " * 50  # 600 个字符
        tokens = Tokenizer.estimate_tokens(text)
        # 600 / 4 = 150 tokens
        expected = 600 / 4
        self.assertAlmostEqual(tokens, expected, delta=expected * 0.2)

    def test_mixed_cjk_english(self) -> None:
        """测试混合 CJK 和英文的 token 估算。"""
        text = "def 函数名(参数):\n    '''这是一个中文文档字符串'''\n    return 参数 + 1\n"
        tokens = Tokenizer.estimate_tokens(text)
        self.assertGreater(tokens, 0)
        # 混合文本应介于纯英文和纯 CJK 之间
        eng_only = Tokenizer.estimate_tokens(text.replace("函数名", "func_name").replace("参数", "arg").replace("这是一个中文文档字符串", "This is a docstring"))
        cjk_only = Tokenizer.estimate_tokens("函数名参数这是一个中文文档字符串")
        # 混合文本的 token 数应大于纯英文替换版本
        self.assertGreater(tokens, eng_only * 0.8)

    def test_is_cjk_detection(self) -> None:
        """测试 CJK 字符检测。"""
        self.assertTrue(Tokenizer._is_cjk("中"))
        self.assertTrue(Tokenizer._is_cjk("日"))
        self.assertTrue(Tokenizer._is_cjk("한"))
        self.assertTrue(Tokenizer._is_cjk("あ"))
        self.assertFalse(Tokenizer._is_cjk("A"))
        self.assertFalse(Tokenizer._is_cjk("1"))
        self.assertFalse(Tokenizer._is_cjk(" "))
        self.assertFalse(Tokenizer._is_cjk("@"))


if __name__ == "__main__":
    unittest.main()
