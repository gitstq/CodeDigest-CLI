"""文件扫描模块 - 递归扫描目录，收集文件元数据并按优先级排序。

本模块负责：
- 递归扫描指定目录，收集文件元数据（路径、大小、扩展名、修改时间）
- 解析 .gitignore 规则并过滤匹配的文件
- 根据扩展名包含/排除列表过滤文件
- 根据目录排除模式过滤目录
- 对扫描到的文件进行优先级评分和排序
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class FileEntry:
    """文件条目数据类，包含文件的元数据和优先级信息。

    Attributes:
        path: 文件的绝对路径
        relative_path: 相对于扫描根目录的路径
        size: 文件大小（字节）
        extension: 文件扩展名（含点号，如 '.py'）
        modified_time: 文件最后修改时间
        priority: 优先级评分（数值越大优先级越高）
        category: 文件分类（entry/config/source/test/generated/other）
    """

    path: str
    relative_path: str
    size: int
    extension: str
    modified_time: datetime
    priority: int = 0
    category: str = "other"

    def __lt__(self, other: "FileEntry") -> bool:
        """排序比较：优先级高的排在前面，同级按路径字典序。"""
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.relative_path < other.relative_path


class GitignoreParser:
    """简易 .gitignore 规则解析器。

    仅使用 Python 标准库实现，支持常见的 gitignore 模式语法：
    - 普通文件名匹配
- 目录匹配（以 / 结尾）
- 否定模式（以 ! 开头）
- 通配符（* 和 **）
- 注释行（以 # 开头）

    注意：此实现为简化版本，不支持所有 gitignore 高级特性。
    """

    def __init__(self, base_dir: str) -> None:
        """初始化 gitignore 解析器。

        Args:
            base_dir: .gitignore 文件所在的根目录路径。
        """
        self.base_dir = base_dir
        self.rules: List[Tuple[str, bool, bool]] = []  # (pattern, is_negation, is_dir_only)

    def parse(self, gitignore_path: Optional[str] = None) -> None:
        """解析 .gitignore 文件中的规则。

        Args:
            gitignore_path: .gitignore 文件的路径。如果为 None，则使用 base_dir/.gitignore。
        """
        if gitignore_path is None:
            gitignore_path = os.path.join(self.base_dir, ".gitignore")

        if not os.path.isfile(gitignore_path):
            return

        with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n\r")
                stripped = line.strip()

                # 跳过空行和注释
                if not stripped or stripped.startswith("#"):
                    continue

                # 处理否定模式
                is_negation = False
                if stripped.startswith("!"):
                    is_negation = True
                    stripped = stripped[1:]

                # 处理目录模式（以 / 结尾）
                is_dir_only = stripped.endswith("/")
                if is_dir_only:
                    stripped = stripped.rstrip("/")

                # 跳过空模式
                if not stripped:
                    continue

                self.rules.append((stripped, is_negation, is_dir_only))

    def is_ignored(self, relative_path: str, is_dir: bool = False) -> bool:
        """判断给定路径是否应被忽略。

        Args:
            relative_path: 相对于 base_dir 的文件/目录路径。
            is_dir: 是否为目录。

        Returns:
            True 表示应被忽略，False 表示不应被忽略。
        """
        ignored = False

        for pattern, is_negation, is_dir_only in self.rules:
            # 目录专用规则：匹配目录本身以及目录下的文件
            if is_dir_only:
                # 检查路径是否以该目录名开头（匹配目录下的文件）
                path_parts = relative_path.replace("\\", "/").split("/")
                if pattern in path_parts:
                    if is_negation:
                        ignored = False
                    else:
                        ignored = True
                    continue
                # 也检查是否精确匹配目录名
                if is_dir and relative_path.replace("\\", "/") == pattern:
                    if is_negation:
                        ignored = False
                    else:
                        ignored = True
                    continue

            if self._match_pattern(pattern, relative_path):
                if is_negation:
                    ignored = False
                else:
                    ignored = True

        return ignored

    def _match_pattern(self, pattern: str, path: str) -> bool:
        """将 gitignore 模式与路径进行匹配。

        Args:
            pattern: gitignore 模式字符串。
            path: 相对路径字符串。

        Returns:
            是否匹配成功。
        """
        # 标准化路径分隔符
        path = path.replace("\\", "/")

        # 如果模式以 / 开头，仅匹配根目录级别
        if pattern.startswith("/"):
            pattern = pattern[1:]
            regex = self._pattern_to_regex(pattern)
            return bool(re.match(regex, path))

        # 如果模式包含 /，则匹配完整路径
        if "/" in pattern:
            regex = self._pattern_to_regex(pattern)
            return bool(re.search(regex, path))

        # 否则匹配路径中任意位置的文件名部分
        regex = self._pattern_to_regex(pattern)
        # 检查路径的每个组成部分
        parts = path.split("/")
        for part in parts:
            if re.match(regex, part):
                return True

        return False

    def _pattern_to_regex(self, pattern: str) -> str:
        """将 gitignore 模式转换为正则表达式。

        Args:
            pattern: gitignore 模式字符串。

        Returns:
            对应的正则表达式字符串。
        """
        # 转义正则特殊字符（保留 * 和 ?）
        result = ""
        i = 0
        while i < len(pattern):
            c = pattern[i]

            if c == "*":
                if i + 1 < len(pattern) and pattern[i + 1] == "*":
                    # ** 匹配任意多级目录
                    if i + 2 < len(pattern) and pattern[i + 2] == "/":
                        result += "(.*/)?"
                        i += 3
                        continue
                    else:
                        result += ".*"
                        i += 2
                        continue
                else:
                    # * 匹配除 / 外的任意字符
                    result += "[^/]*"
            elif c == "?":
                result += "[^/]"
            elif c == "[":
                # 字符类，直接传递
                j = i + 1
                if j < len(pattern) and pattern[j] == "!":
                    j += 1
                if j < len(pattern) and pattern[j] == "]":
                    j += 1
                while j < len(pattern) and pattern[j] != "]":
                    j += 1
                if j < len(pattern):
                    result += pattern[i : j + 1].replace("!", "^", 1)
                    i = j + 1
                    continue
                else:
                    result += re.escape(c)
            elif c in r"\.+^${}()|<>":
                result += re.escape(c)
            else:
                result += c

            i += 1

        return f"^{result}$"


class FileScanner:
    """文件扫描器，递归扫描目录并收集文件元数据。

    支持的功能：
    - 递归目录扫描
    - .gitignore 规则过滤
    - 扩展名包含/排除过滤
    - 目录排除模式
    - 优先级评分排序

    Usage:
        scanner = FileScanner(
            include_exts={".py", ".js"},
            exclude_dirs={"node_modules", ".git"},
        )
        files = scanner.scan("/path/to/project")
    """

    # 入口文件名集合 - 最高优先级
    ENTRY_FILES: Set[str] = {
        "main.py", "index.py", "app.py", "manage.py", "run.py",
        "index.js", "app.js", "server.js", "main.js", "cli.js",
        "index.ts", "app.ts", "server.ts", "main.ts",
        "main.go", "cmd.go",
        "main.rs", "lib.rs",
        "Main.java", "Application.java",
        "index.html", "index.jsx", "index.tsx", "App.jsx", "App.tsx",
        "Makefile", "justfile",
        "setup.py", "setup.cfg", "pyproject.toml",
    }

    # 配置文件名集合 - 高优先级
    CONFIG_FILES: Set[str] = {
        "package.json", "requirements.txt", "Pipfile", "Pipfile.lock",
        "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
        "build.gradle", "pom.xml", "settings.gradle",
        "tsconfig.json", ".eslintrc", ".eslintrc.js", ".eslintrc.json",
        ".prettierrc", ".prettierrc.js", ".prettierrc.json",
        "webpack.config.js", "webpack.config.ts",
        "vite.config.ts", "vite.config.js",
        "rollup.config.js", "rollup.config.ts",
        "jest.config.js", "jest.config.ts",
        "pytest.ini", "tox.ini", "setup.cfg",
        "mypy.ini", ".mypy.ini",
        "pyproject.toml", "poetry.lock",
        "docker-compose.yml", "docker-compose.yaml",
        "Dockerfile", "Dockerfile.dev", "Dockerfile.prod",
        ".env", ".env.local", ".env.development", ".env.production",
        "composer.json", "Gemfile", "Gemfile.lock",
        "mix.exs", "rebar.config",
        "CMakeLists.txt", "Makefile.am", "configure.ac",
        ".clang-format", ".clang-tidy",
        "rustfmt.toml", ".rustfmt.toml",
        "rust-toolchain.toml",
    }

    # 测试文件模式 - 低优先级
    TEST_PATTERNS: List[str] = [
        "test_", "_test.", "tests/", "test/",
        "spec_", "_spec.", "specs/", "spec/",
        "__tests__/", ".test.", ".spec.",
    ]

    # 生成/构建文件模式 - 最低优先级
    GENERATED_PATTERNS: List[str] = [
        "dist/", "build/", "out/", ".next/", ".nuxt/",
        "__pycache__/", ".cache/", ".tmp/",
        "node_modules/", "vendor/", "venv/", ".venv/",
        ".tox/", "coverage/", ".coverage/",
        "*.min.js", "*.min.css", "*.bundle.js",
        "*.map", "*.lock",
    ]

    # 源代码扩展名集合 - 中优先级
    SOURCE_EXTENSIONS: Set[str] = {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".go", ".rs", ".java", ".kt", ".kts", ".scala",
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx",
        ".cs", ".vb", ".fs", ".fsi",
        ".rb", ".php", ".pl", ".pm", ".r", ".R",
        ".swift", ".m", ".mm",
        ".dart", ".lua", ".vim", ".el",
        ".ex", ".exs", ".erl", ".hrl",
        ".hs", ".ml", ".mli", ".fs",
        ".clj", "cljs", ".edn",
        ".sc", ".scala",
        ".sol", ".vy",
        ".tf", ".hcl",
        ".sql", ".rdb",
        ".sh", ".bash", ".zsh", ".fish",
        ".ps1", ".bat", ".cmd",
        ".proto", ".graphql", ".gql",
        ".wasm",
    }

    # 文档/数据扩展名
    DOC_EXTENSIONS: Set[str] = {
        ".md", ".rst", ".txt", ".adoc", ".asciidoc",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".xml", ".csv", ".tsv",
    }

    def __init__(
        self,
        include_exts: Optional[Set[str]] = None,
        exclude_exts: Optional[Set[str]] = None,
        exclude_dirs: Optional[Set[str]] = None,
        respect_gitignore: bool = True,
        max_depth: Optional[int] = None,
    ) -> None:
        """初始化文件扫描器。

        Args:
            include_exts: 仅包含这些扩展名的文件。为 None 时包含所有。
            exclude_exts: 排除这些扩展名的文件。
            exclude_dirs: 排除这些目录名。
            respect_gitignore: 是否遵守 .gitignore 规则。
            max_depth: 最大扫描深度。None 表示无限制。
        """
        self.include_exts = include_exts
        self.exclude_exts = exclude_exts or set()
        self.exclude_dirs = exclude_dirs or {
            ".git", "__pycache__", "node_modules", ".svn",
            ".hg", "dist", "build", ".tox", ".eggs", "*.egg-info",
        }
        self.respect_gitignore = respect_gitignore
        self.max_depth = max_depth
        self._gitignore_parser: Optional[GitignoreParser] = None

    def scan(self, root_dir: str) -> List[FileEntry]:
        """扫描指定目录，返回按优先级排序的文件列表。

        Args:
            root_dir: 要扫描的根目录路径。

        Returns:
            按优先级排序的 FileEntry 列表。

        Raises:
            FileNotFoundError: 如果根目录不存在。
            NotADirectoryError: 如果根路径不是目录。
        """
        root_dir = os.path.abspath(root_dir)

        if not os.path.exists(root_dir):
            raise FileNotFoundError(f"目录不存在: {root_dir}")
        if not os.path.isdir(root_dir):
            raise NotADirectoryError(f"路径不是目录: {root_dir}")

        # 初始化 gitignore 解析器
        if self.respect_gitignore:
            self._gitignore_parser = GitignoreParser(root_dir)
            self._gitignore_parser.parse()

        entries: List[FileEntry] = []
        self._scan_recursive(root_dir, root_dir, 0, entries)

        # 按优先级排序
        entries.sort()
        return entries

    def _scan_recursive(
        self,
        current_dir: str,
        root_dir: str,
        current_depth: int,
        entries: List[FileEntry],
    ) -> None:
        """递归扫描目录。

        Args:
            current_dir: 当前正在扫描的目录。
            root_dir: 扫描的根目录。
            current_depth: 当前递归深度。
            entries: 收集文件条目的列表。
        """
        if self.max_depth is not None and current_depth > self.max_depth:
            return

        try:
            items = sorted(os.listdir(current_dir))
        except PermissionError:
            return

        for item in items:
            full_path = os.path.join(current_dir, item)
            relative_path = os.path.relpath(full_path, root_dir)

            # 标准化路径分隔符
            relative_path_normalized = relative_path.replace("\\", "/")

            try:
                is_dir = os.path.isdir(full_path)
            except (OSError, PermissionError):
                continue

            # 检查 gitignore 规则
            if self._gitignore_parser and self._gitignore_parser.is_ignored(
                relative_path_normalized, is_dir=is_dir
            ):
                continue

            # 检查目录排除
            if is_dir:
                if item in self.exclude_dirs:
                    continue
                # 检查生成文件目录模式
                if self._matches_patterns(relative_path_normalized, self.GENERATED_PATTERNS):
                    continue
                # 递归扫描子目录
                self._scan_recursive(full_path, root_dir, current_depth + 1, entries)
            else:
                # 文件处理
                entry = self._create_file_entry(full_path, relative_path_normalized)
                if entry is not None:
                    entries.append(entry)

    def _create_file_entry(
        self, full_path: str, relative_path: str
    ) -> Optional[FileEntry]:
        """创建文件条目对象。

        Args:
            full_path: 文件的完整路径。
            relative_path: 相对路径。

        Returns:
            FileEntry 对象，如果文件被过滤则返回 None。
        """
        # 获取文件信息
        try:
            stat = os.stat(full_path)
        except (OSError, PermissionError):
            return None

        _, ext = os.path.splitext(relative_path)
        size = stat.st_size
        modified_time = datetime.fromtimestamp(stat.st_mtime)

        # 扩展名过滤
        if self.include_exts is not None and ext not in self.include_exts:
            return None
        if ext in self.exclude_exts:
            return None

        # 检查生成文件模式
        if self._matches_patterns(relative_path, self.GENERATED_PATTERNS):
            return None

        # 计算优先级
        priority, category = self._calculate_priority(relative_path, ext)

        return FileEntry(
            path=full_path,
            relative_path=relative_path,
            size=size,
            extension=ext,
            modified_time=modified_time,
            priority=priority,
            category=category,
        )

    def _calculate_priority(
        self, relative_path: str, ext: str
    ) -> Tuple[int, str]:
        """计算文件的优先级评分和分类。

        优先级等级：
        - 100: 入口文件（main.py, index.js 等）
        - 80: 配置文件（package.json, requirements.txt 等）
        - 60: 源代码文件
        - 40: 文档/数据文件
        - 20: 测试文件
        - 0: 生成/构建文件

        Args:
            relative_path: 文件的相对路径。
            ext: 文件扩展名。

        Returns:
            (优先级评分, 分类名称) 元组。
        """
        filename = os.path.basename(relative_path)

        # 入口文件检查
        if filename in self.ENTRY_FILES:
            return (100, "entry")

        # 配置文件检查
        if filename in self.CONFIG_FILES:
            return (80, "config")

        # 测试文件检查
        if self._matches_patterns(relative_path, self.TEST_PATTERNS):
            return (20, "test")

        # 生成文件检查
        if self._matches_patterns(relative_path, self.GENERATED_PATTERNS):
            return (0, "generated")

        # 源代码文件
        if ext in self.SOURCE_EXTENSIONS:
            return (60, "source")

        # 文档/数据文件
        if ext in self.DOC_EXTENSIONS:
            return (40, "doc")

        return (10, "other")

    @staticmethod
    def _matches_patterns(path: str, patterns: List[str]) -> bool:
        """检查路径是否匹配给定的模式列表。

        Args:
            path: 要检查的路径。
            patterns: 模式列表。

        Returns:
            是否匹配任一模式。
        """
        path_lower = path.lower().replace("\\", "/")
        for pattern in patterns:
            pattern_lower = pattern.lower()

            # 目录模式（以 / 结尾）
            if pattern_lower.endswith("/"):
                if path_lower.startswith(pattern_lower) or f"/{pattern_lower}" in path_lower:
                    return True
                continue

            # 通配符模式
            if "*" in pattern_lower or "?" in pattern_lower:
                # 简单通配符匹配
                regex = pattern_lower.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                if re.search(regex, path_lower):
                    return True
                continue

            # 精确文件名匹配
            if path_lower == pattern_lower or path_lower.endswith(f"/{pattern_lower}"):
                return True
            # 前缀匹配（如 "test_" 匹配 "test_foo.py"）
            basename = os.path.basename(path_lower)
            if basename.startswith(pattern_lower):
                return True

        return False
