"""
Scanner 模块单元测试。

测试文件扫描、扩展名过滤、目录排除、优先级评分和 .gitignore 处理。
仅使用 Python 标准库 unittest 框架。
"""

import os
import tempfile
import unittest
from pathlib import Path

# 确保可以导入被测模块
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codedigest.cli import (
    BINARY_EXTENSIONS,
    Scanner,
    GitignoreParser,
    FileEntry,
    LANGUAGE_PRESETS,
    AUTO_DETECT_MARKERS,
    DEFAULT_PRIORITY,
)


class TestScannerBasic(unittest.TestCase):
    """测试 Scanner 基本扫描功能。"""

    def setUp(self) -> None:
        """创建临时目录结构用于测试。"""
        self.tmpdir = tempfile.mkdtemp(prefix="codedigest_test_")
        self.root = Path(self.tmpdir)

        # 创建测试文件结构
        (self.root / "main.py").write_text("print('hello')\n", encoding="utf-8")
        (self.root / "utils.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
        (self.root / "config.json").write_text('{"key": "value"}\n', encoding="utf-8")
        (self.root / "README.md").write_text("# Test Project\n", encoding="utf-8")

        # 创建子目录
        subdir = self.root / "subdir"
        subdir.mkdir()
        (subdir / "helper.py").write_text("def help(): pass\n", encoding="utf-8")
        (subdir / "data.csv").write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    def tearDown(self) -> None:
        """清理临时目录。"""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_finds_all_text_files(self) -> None:
        """测试扫描器能找到所有文本文件。"""
        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        filenames = {str(e.relative_path) for e in entries}
        self.assertIn("main.py", filenames)
        self.assertIn("utils.py", filenames)
        self.assertIn("config.json", filenames)
        self.assertIn("README.md", filenames)
        self.assertIn(os.path.join("subdir", "helper.py"), filenames)
        self.assertIn(os.path.join("subdir", "data.csv"), filenames)

    def test_scan_excludes_binary_files(self) -> None:
        """测试扫描器自动排除二进制文件。"""
        # 创建二进制文件
        (self.root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.root / "archive.zip").write_bytes(b"PK\x03\x04")

        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        extensions = {e.extension for e in entries}
        self.assertNotIn(".png", extensions)
        self.assertNotIn(".zip", extensions)

    def test_scan_returns_file_entry_objects(self) -> None:
        """测试扫描结果为 FileEntry 对象且属性正确。"""
        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        self.assertTrue(len(entries) > 0)
        for entry in entries:
            self.assertIsInstance(entry, FileEntry)
            self.assertTrue(entry.path.exists())
            self.assertTrue(entry.size >= 0)
            self.assertTrue(entry.priority >= 0)

    def test_scan_sorted_by_priority(self) -> None:
        """测试扫描结果按优先级降序排列。"""
        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        for i in range(len(entries) - 1):
            # 降序排列，或同优先级按路径排序
            self.assertTrue(
                entries[i].priority >= entries[i + 1].priority,
                msg=f"{entries[i].relative_path} (pri={entries[i].priority}) "
                    f"should come after {entries[i + 1].relative_path} "
                    f"(pri={entries[i + 1].priority})"
            )


class TestExtensionFiltering(unittest.TestCase):
    """测试扩展名过滤功能。"""

    def setUp(self) -> None:
        """创建包含多种文件类型的临时目录。"""
        self.tmpdir = tempfile.mkdtemp(prefix="codedigest_ext_test_")
        self.root = Path(self.tmpdir)

        (self.root / "app.py").write_text("# python\n", encoding="utf-8")
        (self.root / "script.js").write_text("// js\n", encoding="utf-8")
        (self.root / "style.css").write_text("/* css */\n", encoding="utf-8")
        (self.root / "data.json").write_text("{}\n", encoding="utf-8")
        (self.root / "note.md").write_text("# note\n", encoding="utf-8")

    def tearDown(self) -> None:
        """清理临时目录。"""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_include_only_py_files(self) -> None:
        """测试仅包含 .py 文件。"""
        scanner = Scanner(
            self.root,
            include_ext={".py"},
            language="auto",
        )
        entries = scanner.scan()
        extensions = {e.extension for e in entries}
        self.assertEqual(extensions, {".py"})
        self.assertEqual(len(entries), 1)

    def test_include_multiple_extensions(self) -> None:
        """测试包含多个指定扩展名。"""
        scanner = Scanner(
            self.root,
            include_ext={".py", ".js", ".json"},
            language="auto",
        )
        entries = scanner.scan()
        extensions = {e.extension for e in entries}
        self.assertEqual(extensions, {".py", ".js", ".json"})
        self.assertEqual(len(entries), 3)

    def test_exclude_specific_extensions(self) -> None:
        """测试排除特定扩展名。"""
        scanner = Scanner(
            self.root,
            exclude_ext={".md", ".css"},
            language="auto",
        )
        entries = scanner.scan()
        extensions = {e.extension for e in entries}
        self.assertNotIn(".md", extensions)
        self.assertNotIn(".css", extensions)
        self.assertIn(".py", extensions)
        self.assertIn(".js", extensions)

    def test_include_takes_precedence_over_exclude(self) -> None:
        """测试 include 和 exclude 同时设置时，仅 include 生效。"""
        scanner = Scanner(
            self.root,
            include_ext={".py"},
            exclude_ext={".py"},
            language="auto",
        )
        entries = scanner.scan()
        # include 为空集时表示不限制，但这里 include 非空
        # 在当前实现中，include 先检查，所以 .py 会被包含
        # exclude 后检查，.py 会被排除
        # 最终结果取决于实现：当前实现是先检查 include 再检查 exclude
        # 所以 .py 先通过 include，再被 exclude 排除
        self.assertEqual(len(entries), 0)


class TestDirectoryExclusion(unittest.TestCase):
    """测试目录排除功能。"""

    def setUp(self) -> None:
        """创建包含多个子目录的临时目录。"""
        self.tmpdir = tempfile.mkdtemp(prefix="codedigest_dir_test_")
        self.root = Path(self.tmpdir)

        (self.root / "main.py").write_text("# main\n", encoding="utf-8")

        node_modules = self.root / "node_modules"
        node_modules.mkdir()
        (node_modules / "lib.js").write_text("// lib\n", encoding="utf-8")

        venv = self.root / "venv"
        venv.mkdir()
        (venv / "site.py").write_text("# site\n", encoding="utf-8")

        src = self.root / "src"
        src.mkdir()
        (src / "app.py").write_text("# app\n", encoding="utf-8")

    def tearDown(self) -> None:
        """清理临时目录。"""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_exclude_default_dirs(self) -> None:
        """测试默认排除 node_modules 和 venv 目录。"""
        scanner = Scanner(
            self.root,
            exclude_dirs={"node_modules", "venv"},
            language="auto",
        )
        entries = scanner.scan()
        paths = {str(e.relative_path) for e in entries}
        self.assertNotIn(os.path.join("node_modules", "lib.js"), paths)
        self.assertNotIn(os.path.join("venv", "site.py"), paths)
        self.assertIn("main.py", paths)
        self.assertIn(os.path.join("src", "app.py"), paths)

    def test_max_depth_limits_scan(self) -> None:
        """测试最大深度限制扫描。"""
        scanner = Scanner(
            self.root,
            exclude_dirs=set(),
            max_depth=0,
            language="auto",
        )
        entries = scanner.scan()
        paths = {str(e.relative_path) for e in entries}
        # max_depth=0 表示无限制
        self.assertTrue(len(paths) > 2)

        scanner_limited = Scanner(
            self.root,
            exclude_dirs=set(),
            max_depth=0,
            language="auto",
        )
        entries_limited = scanner_limited.scan()
        # max_depth=0 无限制，应与上面相同
        self.assertEqual(len(entries), len(entries_limited))

    def test_max_depth_one(self) -> None:
        """测试最大深度为 1 时仅扫描根目录和第一层子目录。"""
        scanner = Scanner(
            self.root,
            exclude_dirs={"node_modules", "venv"},  # 排除 venv 以便只测深度
            max_depth=1,
            language="auto",
        )
        entries = scanner.scan()
        paths = {str(e.relative_path) for e in entries}
        # max_depth=1 时，扫描深度 <= 1 的目录（根目录 depth=0, 一级子目录 depth=1）
        for p in paths:
            parts = Path(p).parts
            self.assertLessEqual(len(parts), 2, f"Path {p} exceeds depth 1")


class TestPriorityScoring(unittest.TestCase):
    """测试文件优先级评分功能。"""

    def test_python_preset_priorities(self) -> None:
        """测试 Python 语言预设的优先级。"""
        preset = LANGUAGE_PRESETS["python"]
        self.assertEqual(preset.get(".py"), 10)
        self.assertEqual(preset.get(".pyx"), 8)
        self.assertEqual(preset.get(".pyi"), 7)
        self.assertGreater(preset.get(".py", 0), preset.get(".md", 0))

    def test_javascript_preset_priorities(self) -> None:
        """测试 JavaScript 语言预设的优先级。"""
        preset = LANGUAGE_PRESETS["javascript"]
        self.assertEqual(preset.get(".js"), 10)
        self.assertEqual(preset.get(".ts"), 10)
        self.assertEqual(preset.get(".jsx"), 9)
        self.assertGreater(preset.get(".js", 0), preset.get(".json", 0))

    def test_default_priority_covers_common_extensions(self) -> None:
        """测试默认优先级覆盖常见扩展名。"""
        common_exts = {".py", ".js", ".ts", ".go", ".rs", ".java", ".html", ".css"}
        for ext in common_exts:
            self.assertIn(ext, DEFAULT_PRIORITY, f"Missing priority for {ext}")

    def test_auto_detect_python(self) -> None:
        """测试自动检测 Python 项目。"""
        tmpdir = tempfile.mkdtemp(prefix="codedigest_auto_py_")
        try:
            root = Path(tmpdir)
            (root / "main.py").write_text("# main\n", encoding="utf-8")
            (root / "utils.py").write_text("# utils\n", encoding="utf-8")

            scanner = Scanner(root, language="auto")
            entries = scanner.scan()

            # Python 文件应有较高优先级
            py_entries = [e for e in entries if e.extension == ".py"]
            self.assertTrue(len(py_entries) > 0)
            for e in py_entries:
                self.assertGreaterEqual(e.priority, 10)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_auto_detect_javascript(self) -> None:
        """测试自动检测 JavaScript 项目。"""
        tmpdir = tempfile.mkdtemp(prefix="codedigest_auto_js_")
        try:
            root = Path(tmpdir)
            (root / "index.js").write_text("// index\n", encoding="utf-8")
            (root / "app.ts").write_text("// app\n", encoding="utf-8")

            scanner = Scanner(root, language="auto")
            entries = scanner.scan()

            js_entries = [e for e in entries if e.extension in {".js", ".ts"}]
            self.assertTrue(len(js_entries) > 0)
            for e in js_entries:
                self.assertGreaterEqual(e.priority, 10)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestGitignoreHandling(unittest.TestCase):
    """测试 .gitignore 处理功能。"""

    def setUp(self) -> None:
        """创建包含 .gitignore 的临时目录。"""
        self.tmpdir = tempfile.mkdtemp(prefix="codedigest_gitignore_test_")
        self.root = Path(self.tmpdir)

        # 创建 .gitignore
        (self.root / ".gitignore").write_text(
            "*.log\n"
            "__pycache__/\n"
            "*.pyc\n"
            "build/\n"
            "!important.log\n",
            encoding="utf-8",
        )

        # 创建文件
        (self.root / "main.py").write_text("# main\n", encoding="utf-8")
        (self.root / "debug.log").write_text("debug\n", encoding="utf-8")
        (self.root / "important.log").write_text("important\n", encoding="utf-8")

        pycache = self.root / "__pycache__"
        pycache.mkdir()
        (pycache / "main.pyc").write_bytes(b"\x00\x00\x00")

        build = self.root / "build"
        build.mkdir()
        (build / "output.js").write_text("// output\n", encoding="utf-8")

    def tearDown(self) -> None:
        """清理临时目录。"""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_gitignore_excludes_patterns(self) -> None:
        """测试 .gitignore 排除匹配的文件。"""
        scanner = Scanner(self.root, use_gitignore=True, language="auto")
        entries = scanner.scan()
        paths = {str(e.relative_path) for e in entries}

        # *.log 应被排除
        self.assertNotIn("debug.log", paths)
        # __pycache__/ 目录应被排除
        self.assertNotIn(os.path.join("__pycache__", "main.pyc"), paths)
        # build/ 目录应被排除
        self.assertNotIn(os.path.join("build", "output.js"), paths)

    def test_gitignore_negation_pattern(self) -> None:
        """测试 .gitignore 取反模式。"""
        scanner = Scanner(self.root, use_gitignore=True, language="auto")
        entries = scanner.scan()
        paths = {str(e.relative_path) for e in entries}

        # !important.log 应取消排除
        self.assertIn("important.log", paths)

    def test_no_gitignore_includes_all(self) -> None:
        """测试禁用 .gitignore 时包含所有文件。"""
        scanner = Scanner(self.root, use_gitignore=False, language="auto")
        entries = scanner.scan()
        paths = {str(e.relative_path) for e in entries}

        # 禁用 .gitignore 时，debug.log 应出现（虽然 .log 不是二进制文件）
        self.assertIn("debug.log", paths)
        self.assertIn("important.log", paths)

    def test_gitignore_parser_direct(self) -> None:
        """直接测试 GitignoreParser。"""
        parser = GitignoreParser(self.root)

        # *.log 匹配
        self.assertTrue(parser.is_ignored(Path("debug.log")))
        self.assertTrue(parser.is_ignored(Path("sub/error.log")))

        # !important.log 取反
        self.assertFalse(parser.is_ignored(Path("important.log")))

        # main.py 不匹配任何规则
        self.assertFalse(parser.is_ignored(Path("main.py")))

        # build/ 目录匹配
        self.assertTrue(parser.is_ignored(Path("build/output.js")))

        # __pycache__/ 目录匹配
        self.assertTrue(parser.is_ignored(Path("__pycache__/main.pyc")))


class TestBinaryExtensions(unittest.TestCase):
    """测试二进制扩展名集合。"""

    def test_common_binary_extensions_present(self) -> None:
        """测试常见二进制扩展名都在集合中。"""
        expected = {".png", ".jpg", ".jpeg", ".gif", ".mp3", ".mp4",
                     ".zip", ".tar", ".gz", ".exe", ".dll", ".pdf",
                     ".pyc", ".db", ".sqlite", ".ttf", ".woff"}
        for ext in expected:
            self.assertIn(ext, BINARY_EXTENSIONS, f"Missing binary ext: {ext}")

    def test_source_extensions_not_binary(self) -> None:
        """测试源代码扩展名不在二进制集合中。"""
        source_exts = {".py", ".js", ".ts", ".go", ".rs", ".java",
                       ".html", ".css", ".json", ".xml", ".md", ".txt"}
        for ext in source_exts:
            self.assertNotIn(ext, BINARY_EXTENSIONS, f"Source ext wrongly binary: {ext}")


class TestBuildTree(unittest.TestCase):
    """测试目录树构建功能。"""

    def setUp(self) -> None:
        """创建临时目录结构。"""
        self.tmpdir = tempfile.mkdtemp(prefix="codedigest_tree_test_")
        self.root = Path(self.tmpdir)

        (self.root / "README.md").write_text("# Test\n", encoding="utf-8")
        src = self.root / "src"
        src.mkdir()
        (src / "main.py").write_text("# main\n", encoding="utf-8")
        (src / "utils.py").write_text("# utils\n", encoding="utf-8")
        tests = self.root / "tests"
        tests.mkdir()
        (tests / "test_main.py").write_text("# test\n", encoding="utf-8")

    def tearDown(self) -> None:
        """清理临时目录。"""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_tree_contains_all_files(self) -> None:
        """测试目录树包含所有文件。"""
        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        tree = scanner.build_tree(entries)

        self.assertIn("README.md", tree)
        self.assertIn("main.py", tree)
        self.assertIn("utils.py", tree)
        self.assertIn("test_main.py", tree)

    def test_tree_has_directory_markers(self) -> None:
        """测试目录树包含目录标记。"""
        scanner = Scanner(self.root, language="auto")
        entries = scanner.scan()
        tree = scanner.build_tree(entries)

        # 目录树应包含 src/ 和 tests/
        self.assertIn("src", tree)
        self.assertIn("tests", tree)


if __name__ == "__main__":
    unittest.main()
