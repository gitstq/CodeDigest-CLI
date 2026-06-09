"""
Formatter 模块单元测试。

测试 Markdown、JSON、XML 和纯文本格式的输出生成。
仅使用 Python 标准库 unittest 框架。
"""

import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codedigest.cli import (
    Formatter,
    FileEntry,
    Scanner,
    Tokenizer,
)


class _FormatterTestCase(unittest.TestCase):
    """Formatter 测试的基类，提供公共的临时目录设置。"""

    def setUp(self) -> None:
        """创建临时目录结构用于格式化测试。"""
        self.tmpdir = tempfile.mkdtemp(prefix="codedigest_fmt_test_")
        self.root = Path(self.tmpdir)

        (self.root / "main.py").write_text(
            'def greet(name: str) -> str:\n'
            '    return f"Hello, {name}!"\n'
            '\n'
            'if __name__ == "__main__":\n'
            '    print(greet("World"))\n',
            encoding="utf-8",
        )
        (self.root / "config.json").write_text(
            '{\n  "name": "test",\n  "version": "1.0"\n}\n',
            encoding="utf-8",
        )
        (self.root / "README.md").write_text(
            "# Test Project\n\nA sample project for testing.\n",
            encoding="utf-8",
        )

        subdir = self.root / "src"
        subdir.mkdir()
        (subdir / "utils.py").write_text(
            'def add(a: int, b: int) -> int:\n'
            '    return a + b\n',
            encoding="utf-8",
        )

        # 创建扫描器和文件条目
        scanner = Scanner(self.root, language="auto")
        self.entries = scanner.scan()
        self.formatter = Formatter(self.root, self.entries)

    def tearDown(self) -> None:
        """清理临时目录。"""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestMarkdownOutput(_FormatterTestCase):
    """测试 Markdown 格式输出。"""

    def test_output_contains_header(self) -> None:
        """测试输出包含标题头。"""
        output = self.formatter.format_markdown()
        self.assertIn("# Code Digest", output)

    def test_output_contains_directory_tree(self) -> None:
        """测试输出包含目录树。"""
        output = self.formatter.format_markdown()
        self.assertIn("## Directory Structure", output)
        self.assertIn("```", output)

    def test_output_contains_file_contents(self) -> None:
        """测试输出包含文件内容。"""
        output = self.formatter.format_markdown()
        self.assertIn("## File Contents", output)
        self.assertIn("def greet", output)
        self.assertIn("def add", output)

    def test_output_contains_code_fences(self) -> None:
        """测试输出包含代码围栏。"""
        output = self.formatter.format_markdown()
        self.assertIn("```py", output)
        self.assertIn("```json", output)

    def test_tree_only_omits_contents(self) -> None:
        """测试 tree-only 模式省略文件内容。"""
        output = self.formatter.format_markdown(tree_only=True)
        self.assertIn("## Directory Structure", output)
        self.assertNotIn("## File Contents", output)
        self.assertNotIn("def greet", output)

    def test_token_budget_truncation(self) -> None:
        """测试 token 预算截断。"""
        output = self.formatter.format_markdown(token_budget=50)
        self.assertIn("Token budget", output)

    def test_output_is_valid_string(self) -> None:
        """测试输出为有效字符串。"""
        output = self.formatter.format_markdown()
        self.assertIsInstance(output, str)
        self.assertTrue(len(output) > 0)


class TestJSONOutput(_FormatterTestCase):
    """测试 JSON 格式输出。"""

    def test_output_is_valid_json(self) -> None:
        """测试输出为有效 JSON。"""
        output = self.formatter.format_json()
        parsed = json.loads(output)
        self.assertIsInstance(parsed, dict)

    def test_output_contains_metadata(self) -> None:
        """测试输出包含元数据。"""
        output = self.formatter.format_json()
        parsed = json.loads(output)
        self.assertIn("path", parsed)
        self.assertIn("generated", parsed)
        self.assertIn("total_files", parsed)
        self.assertIn("tree", parsed)

    def test_output_contains_files(self) -> None:
        """测试输出包含文件列表。"""
        output = self.formatter.format_json()
        parsed = json.loads(output)
        self.assertIn("files", parsed)
        self.assertIsInstance(parsed["files"], list)
        self.assertTrue(len(parsed["files"]) > 0)

    def test_file_entries_have_required_fields(self) -> None:
        """测试文件条目包含必要字段。"""
        output = self.formatter.format_json()
        parsed = json.loads(output)
        for file_entry in parsed["files"]:
            self.assertIn("path", file_entry)
            self.assertIn("extension", file_entry)
            self.assertIn("size", file_entry)
            self.assertIn("priority", file_entry)
            self.assertIn("content", file_entry)

    def test_tree_only_omits_files(self) -> None:
        """测试 tree-only 模式省略文件内容。"""
        output = self.formatter.format_json(tree_only=True)
        parsed = json.loads(output)
        self.assertNotIn("files", parsed)
        self.assertIn("tree", parsed)

    def test_token_budget_truncation(self) -> None:
        """测试 token 预算截断。"""
        output = self.formatter.format_json(token_budget=30)
        parsed = json.loads(output)
        # 预算很小时，files 列表可能为空或很短
        if "files" in parsed:
            total_content = sum(len(f.get("content", "")) for f in parsed["files"])
            self.assertLess(total_content, 500)

    def test_json_indentation(self) -> None:
        """测试 JSON 输出有缩进。"""
        output = self.formatter.format_json()
        self.assertIn("  ", output)  # 缩进空格


class TestXMLOutput(_FormatterTestCase):
    """测试 XML 格式输出。"""

    def test_output_is_valid_xml(self) -> None:
        """测试输出为有效 XML。"""
        output = self.formatter.format_xml()
        # 解析 XML 验证有效性
        try:
            root = ET.fromstring(output)
            self.assertEqual(root.tag, "codedigest")
        except ET.ParseError:
            # 某些 XML 声明可能导致解析问题，尝试跳过
            if output.strip().startswith("<?xml"):
                root = ET.fromstring(output.split("\n", 1)[1])
                self.assertEqual(root.tag, "codedigest")
            else:
                raise

    def test_output_contains_metadata(self) -> None:
        """测试输出包含元数据属性。"""
        output = self.formatter.format_xml()
        # 使用字符串匹配检查属性
        self.assertIn("codedigest", output)
        self.assertIn("path=", output)
        self.assertIn("generated=", output)
        self.assertIn("total_files=", output)

    def test_output_contains_tree(self) -> None:
        """测试输出包含目录树。"""
        output = self.formatter.format_xml()
        self.assertIn("<tree>", output)
        self.assertIn("</tree>", output)

    def test_output_contains_files(self) -> None:
        """测试输出包含文件元素。"""
        output = self.formatter.format_xml()
        self.assertIn("<files>", output)
        self.assertIn("</files>", output)
        self.assertIn("<file ", output)

    def test_tree_only_omits_files(self) -> None:
        """测试 tree-only 模式省略文件内容。"""
        output = self.formatter.format_xml(tree_only=True)
        self.assertIn("<tree>", output)
        self.assertNotIn("<files>", output)

    def test_token_budget_truncation(self) -> None:
        """测试 token 预算截断。"""
        output = self.formatter.format_xml(token_budget=30)
        # 预算很小时，文件列表可能为空
        self.assertIn("codedigest", output)


class TestTextOutput(_FormatterTestCase):
    """测试纯文本格式输出。"""

    def test_output_contains_header(self) -> None:
        """测试输出包含标题头。"""
        output = self.formatter.format_text()
        self.assertIn("Code Digest", output)

    def test_output_contains_separator(self) -> None:
        """测试输出包含分隔线。"""
        output = self.formatter.format_text()
        self.assertIn("===", output)

    def test_output_contains_directory_tree(self) -> None:
        """测试输出包含目录树。"""
        output = self.formatter.format_text()
        self.assertIn("[Directory Structure]", output)

    def test_output_contains_file_contents(self) -> None:
        """测试输出包含文件内容。"""
        output = self.formatter.format_text()
        self.assertIn("[File Contents]", output)
        self.assertIn("def greet", output)

    def test_tree_only_omits_contents(self) -> None:
        """测试 tree-only 模式省略文件内容。"""
        output = self.formatter.format_text(tree_only=True)
        self.assertIn("[Directory Structure]", output)
        self.assertNotIn("[File Contents]", output)
        self.assertNotIn("def greet", output)

    def test_token_budget_truncation(self) -> None:
        """测试 token 预算截断。"""
        output = self.formatter.format_text(token_budget=50)
        self.assertIn("Token budget", output)

    def test_file_headers_show_metadata(self) -> None:
        """测试文件头显示元数据信息。"""
        output = self.formatter.format_text()
        self.assertIn("bytes", output)
        self.assertIn("priority=", output)

    def test_output_is_plain_text(self) -> None:
        """测试输出为纯文本（无 HTML/XML 标记）。"""
        output = self.formatter.format_text()
        self.assertNotIn("<html", output)
        self.assertNotIn("<?xml", output)


class TestFormatterEncoding(unittest.TestCase):
    """测试格式化器处理不同编码文件的能力。"""

    def setUp(self) -> None:
        """创建包含不同编码文件的临时目录。"""
        self.tmpdir = tempfile.mkdtemp(prefix="codedigest_enc_test_")
        self.root = Path(self.tmpdir)

        # UTF-8 文件
        (self.root / "utf8.py").write_text("# 你好世界\nprint('hello')\n", encoding="utf-8")

        # GBK 编码文件
        (self.root / "gbk.txt").write_bytes("这是GBK编码的文本".encode("gbk"))

        # Latin-1 编码文件
        (self.root / "latin1.txt").write_bytes("Café résumé".encode("latin-1"))

    def tearDown(self) -> None:
        """清理临时目录。"""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_utf8_file_in_markdown(self) -> None:
        """测试 UTF-8 文件在 Markdown 输出中正确显示。"""
        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        formatter = Formatter(self.root, entries)
        output = formatter.format_markdown()
        self.assertIn("你好世界", output)

    def test_gbk_file_in_markdown(self) -> None:
        """测试 GBK 文件在 Markdown 输出中正确显示。"""
        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        formatter = Formatter(self.root, entries)
        output = formatter.format_markdown()
        self.assertIn("这是GBK编码的文本", output)

    def test_latin1_file_in_json(self) -> None:
        """测试 Latin-1 文件在 JSON 输出中正确显示。"""
        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        formatter = Formatter(self.root, entries)
        output = formatter.format_json()
        parsed = json.loads(output)
        contents = [f["content"] for f in parsed.get("files", [])]
        all_content = " ".join(contents)
        self.assertIn("Café", all_content)


class TestFormatterEdgeCases(unittest.TestCase):
    """测试格式化器的边界情况。"""

    def test_empty_directory(self) -> None:
        """测试空目录的格式化输出。"""
        tmpdir = tempfile.mkdtemp(prefix="codedigest_empty_test_")
        try:
            root = Path(tmpdir)
            scanner = Scanner(root, language="auto")
            entries = scanner.scan()
            # 空目录没有文件，Formatter 应处理这种情况
            formatter = Formatter(root, entries)
            output = formatter.format_markdown()
            self.assertIn("Code Digest", output)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_single_file(self) -> None:
        """测试单文件目录的格式化输出。"""
        tmpdir = tempfile.mkdtemp(prefix="codedigest_single_test_")
        try:
            root = Path(tmpdir)
            (root / "only.py").write_text("x = 1\n", encoding="utf-8")
            scanner = Scanner(root, language="auto")
            entries = scanner.scan()
            formatter = Formatter(root, entries)
            output = formatter.format_markdown()
            self.assertIn("only.py", output)
            self.assertIn("x = 1", output)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_large_token_budget(self) -> None:
        """测试大 token 预算不截断。"""
        tmpdir = tempfile.mkdtemp(prefix="codedigest_large_budget_")
        try:
            root = Path(tmpdir)
            content = "x = 1\n" * 100
            (root / "big.py").write_text(content, encoding="utf-8")
            scanner = Scanner(root, language="auto")
            entries = scanner.scan()
            formatter = Formatter(root, entries)
            output = formatter.format_markdown(token_budget=1000000)
            self.assertIn(content.strip(), output)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
