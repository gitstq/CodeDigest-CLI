"""
CodeDigest-CLI 主命令行模块。

提供代码仓库扫描、token 预算管理和多格式输出功能。
仅使用 Python 标准库，支持 ANSI 彩色输出和进度指示器。
"""

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from codedigest import __version__

# ---------------------------------------------------------------------------
# ANSI 颜色工具
# ---------------------------------------------------------------------------

class Colors:
    """ANSI 终端颜色管理器，自动检测终端是否支持颜色。"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLACK = "\033[40m"

    def __init__(self) -> None:
        self._enabled: Optional[bool] = None

    @property
    def enabled(self) -> bool:
        """检测终端是否支持 ANSI 颜色输出。"""
        if self._enabled is None:
            self._enabled = self._detect_color_support()
        return self._enabled

    @staticmethod
    def _detect_color_support() -> bool:
        """检测当前终端是否支持颜色。"""
        # 如果明确设置了 NO_COLOR 环境变量，则禁用颜色
        if os.environ.get("NO_COLOR"):
            return False
        # 检测是否为 TTY 终端
        if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            # Windows 下检查 ANSI 支持
            if os.name == "nt":
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
                    return kernel32.GetConsoleMode(kernel32.GetStdHandle(-11)) & 7 != 0
                except Exception:
                    return False
            return True
        return False

    def style(self, text: str, *codes: str) -> str:
        """对文本应用 ANSI 样式。如果终端不支持颜色，则原样返回。"""
        if not self.enabled:
            return text
        return "".join(codes) + text + self.RESET

    def bold(self, text: str) -> str:
        return self.style(text, self.BOLD)

    def red(self, text: str) -> str:
        return self.style(text, self.RED)

    def green(self, text: str) -> str:
        return self.style(text, self.GREEN)

    def yellow(self, text: str) -> str:
        return self.style(text, self.YELLOW)

    def blue(self, text: str) -> str:
        return self.style(text, self.BLUE)

    def cyan(self, text: str) -> str:
        return self.style(text, self.CYAN)

    def dim(self, text: str) -> str:
        return self.style(text, self.DIM)

    def magenta(self, text: str) -> str:
        return self.style(text, self.MAGENTA)


# 全局颜色实例
colors = Colors()

# ---------------------------------------------------------------------------
# 进度指示器
# ---------------------------------------------------------------------------

class ProgressIndicator:
    """简单的终端进度指示器，显示扫描进度动画。"""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    INTERVAL = 0.08  # 每帧间隔（秒）

    def __init__(self, message: str = "Scanning") -> None:
        self._message = message
        self._running = False
        self._frame_idx = 0

    def __enter__(self) -> "ProgressIndicator":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    def start(self) -> None:
        """启动进度动画。"""
        if not colors.enabled:
            return
        self._running = True
        self._tick()

    def stop(self) -> None:
        """停止进度动画并清除当前行。"""
        self._running = False
        if colors.enabled:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    def _tick(self) -> None:
        """刷新一帧动画。"""
        if not self._running:
            return
        frame = self.FRAMES[self._frame_idx % len(self.FRAMES)]
        sys.stdout.write(
            f"\r{colors.cyan(frame)} {colors.dim(self._message + '...')}"
        )
        sys.stdout.flush()
        self._frame_idx += 1
        if self._running:
            time.sleep(self.INTERVAL)
            self._tick()


# ---------------------------------------------------------------------------
# .gitignore 解析器
# ---------------------------------------------------------------------------

class GitignoreParser:
    """解析 .gitignore 文件并匹配文件路径。"""

    def __init__(self, base_path: Path) -> None:
        self._patterns: List[Tuple[str, bool]] = []  # (pattern, is_negation)
        gitignore_path = base_path / ".gitignore"
        if gitignore_path.is_file():
            self._parse(gitignore_path)

    def _parse(self, gitignore_path: Path) -> None:
        """逐行解析 .gitignore 文件。"""
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.rstrip("\n\r")
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    is_negation = stripped.startswith("!")
                    if is_negation:
                        stripped = stripped[1:]
                    # 移除首尾空格
                    stripped = stripped.strip()
                    if stripped:
                        self._patterns.append((stripped, is_negation))
        except (OSError, IOError):
            pass

    def is_ignored(self, relative_path: Path) -> bool:
        """判断给定相对路径是否应被忽略。"""
        path_str = str(relative_path).replace("\\", "/")
        name = relative_path.name

        ignored = False
        for pattern, is_negation in self._patterns:
            if self._match(pattern, path_str, name):
                ignored = not is_negation
        return ignored

    @staticmethod
    def _match(pattern: str, path_str: str, name: str) -> bool:
        """将 gitignore 模式与路径进行匹配。"""
        # 目录匹配（以 / 结尾）
        if pattern.endswith("/"):
            dir_pattern = pattern.rstrip("/")
            if "/" + dir_pattern + "/" in path_str or path_str.startswith(dir_pattern + "/"):
                return True

        # 路径中的通配符匹配
        if "/" in pattern:
            regex = GitignoreParser._glob_to_regex(pattern)
            if regex.search(path_str):
                return True
        else:
            # 仅匹配文件名
            regex = GitignoreParser._glob_to_regex(pattern)
            if regex.search(name) or regex.search(path_str):
                return True

        return False

    @staticmethod
    def _glob_to_regex(pattern: str) -> re.Pattern:
        """将简单的 glob 模式转换为正则表达式。"""
        i = 0
        n = len(pattern)
        regex = ""
        while i < n:
            c = pattern[i]
            if c == "*":
                if i + 1 < n and pattern[i + 1] == "*":
                    regex += ".*"
                    i += 2
                    if i < n and pattern[i] == "/":
                        i += 1
                else:
                    regex += "[^/]*"
                    i += 1
            elif c == "?":
                regex += "[^/]"
                i += 1
            elif c == "[":
                j = i + 1
                if j < n and pattern[j] == "!":
                    j += 1
                if j < n and pattern[j] == "]":
                    j += 1
                while j < n and pattern[j] != "]":
                    j += 1
                if j >= n:
                    regex += "\\["
                else:
                    bracket = pattern[i + 1:j].replace("\\", "\\\\")
                    regex += f"[{bracket}]"
                    i = j + 1
            else:
                regex += re.escape(c)
                i += 1
        return re.compile(f"(^|/){regex}(/|$)")


# ---------------------------------------------------------------------------
# 文件扫描器
# ---------------------------------------------------------------------------

# 语言预设：文件扩展名到优先级的映射
LANGUAGE_PRESETS: Dict[str, Dict[str, int]] = {
    "python": {
        ".py": 10, ".pyx": 8, ".pyi": 7, ".ipynb": 6,
        ".cfg": 3, ".ini": 3, ".toml": 3, ".txt": 1, ".md": 2,
    },
    "javascript": {
        ".js": 10, ".jsx": 9, ".ts": 10, ".tsx": 9,
        ".mjs": 8, ".cjs": 8, ".json": 5, ".html": 4,
        ".css": 4, ".scss": 4, ".less": 4, ".vue": 8,
        ".svelte": 8, ".md": 2, ".yaml": 3, ".yml": 3,
    },
    "go": {
        ".go": 10, ".mod": 6, ".sum": 3, ".tmpl": 5,
        ".yaml": 3, ".yml": 3, ".md": 2, ".txt": 1,
    },
    "rust": {
        ".rs": 10, ".toml": 5, ".md": 2, ".txt": 1,
        ".lock": 1,
    },
    "java": {
        ".java": 10, ".kt": 9, ".scala": 9, ".gradle": 5,
        ".xml": 4, ".properties": 3, ".yaml": 3, ".yml": 3,
        ".md": 2, ".txt": 1,
    },
    "auto": {},
}

# 自动检测时各语言的标志性扩展名
AUTO_DETECT_MARKERS: Dict[str, Set[str]] = {
    "python": {".py", ".pyx", ".pyi"},
    "javascript": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"},
    "go": {".go"},
    "rust": {".rs"},
    "java": {".java", ".kt", ".scala"},
}

# 通用默认优先级（用于 auto 模式下非特定语言的文件）
DEFAULT_PRIORITY: Dict[str, int] = {
    ".py": 10, ".js": 10, ".ts": 10, ".jsx": 9, ".tsx": 9,
    ".go": 10, ".rs": 10, ".java": 10, ".kt": 9, ".scala": 9,
    ".c": 10, ".cpp": 10, ".h": 8, ".hpp": 8, ".cc": 10,
    ".rb": 10, ".php": 10, ".swift": 10, ".dart": 10,
    ".vue": 8, ".svelte": 8, ".html": 4, ".css": 4, ".scss": 4,
    ".json": 5, ".yaml": 3, ".yml": 3, ".toml": 3, ".xml": 4,
    ".md": 2, ".txt": 1, ".cfg": 3, ".ini": 3,
    ".sh": 7, ".bash": 7, ".zsh": 7, ".fish": 7,
    ".sql": 6, ".graphql": 6, ".proto": 6,
    ".dockerfile": 7, ".makefile": 7,
}

# 二进制文件扩展名（始终排除）
BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac", ".ogg",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".pyc", ".pyo", ".class", ".o", ".obj",
    ".db", ".sqlite", ".sqlite3",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
}


class FileEntry:
    """表示一个待处理的文件条目。"""

    __slots__ = ("path", "relative_path", "extension", "size", "priority")

    def __init__(
        self,
        path: Path,
        relative_path: Path,
        extension: str,
        size: int,
        priority: int,
    ) -> None:
        self.path = path
        self.relative_path = relative_path
        self.extension = extension
        self.size = size
        self.priority = priority

    def __repr__(self) -> str:
        return f"FileEntry({self.relative_path}, pri={self.priority})"


class Scanner:
    """文件系统扫描器，收集代码文件并按优先级排序。"""

    def __init__(
        self,
        root_path: Path,
        include_ext: Optional[Set[str]] = None,
        exclude_ext: Optional[Set[str]] = None,
        exclude_dirs: Optional[Set[str]] = None,
        max_depth: int = 0,
        use_gitignore: bool = True,
        language: str = "auto",
    ) -> None:
        """初始化扫描器。

        Args:
            root_path: 要扫描的根目录。
            include_ext: 仅包含的扩展名集合（含点号）。为 None 表示不限制。
            exclude_ext: 要排除的扩展名集合（含点号）。
            exclude_dirs: 要排除的目录名集合。
            max_depth: 最大扫描深度，0 表示无限制。
            use_gitignore: 是否使用 .gitignore 规则。
            language: 语言预设名称。
        """
        self.root_path = root_path.resolve()
        self.include_ext = include_ext
        self.exclude_ext = exclude_ext
        self.exclude_dirs = exclude_dirs or set()
        self.max_depth = max_depth
        self.use_gitignore = use_gitignore
        self.language = language

        # 加载 .gitignore
        self._gitignore: Optional[GitignoreParser] = None
        if self.use_gitignore:
            self._gitignore = GitignoreParser(self.root_path)

        # 确定优先级映射
        self._priority_map = self._build_priority_map()

    def _build_priority_map(self) -> Dict[str, int]:
        """根据语言预设构建文件优先级映射。"""
        if self.language != "auto" and self.language in LANGUAGE_PRESETS:
            return LANGUAGE_PRESETS[self.language].copy()
        return DEFAULT_PRIORITY.copy()

    def _detect_language(self, extensions_found: Set[str]) -> str:
        """根据发现的文件扩展名自动检测主要语言。"""
        scores: Dict[str, int] = {}
        for lang, markers in AUTO_DETECT_MARKERS.items():
            scores[lang] = len(extensions_found & markers)
        if not scores or max(scores.values()) == 0:
            return "auto"
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def scan(self) -> List[FileEntry]:
        """扫描目录树，返回按优先级排序的文件列表。"""
        entries: List[FileEntry] = []
        extensions_found: Set[str] = set()

        for dirpath, dirnames, filenames in os.walk(self.root_path):
            current = Path(dirpath)
            rel_dir = current.relative_to(self.root_path)

            # 深度检查
            if self.max_depth > 0:
                depth = len(rel_dir.parts)
                if depth > self.max_depth:
                    dirnames.clear()
                    continue

            # 过滤排除的目录（原地修改以阻止 os.walk 递归）
            dirnames[:] = [
                d
                for d in dirnames
                if d not in self.exclude_dirs
                and not d.startswith(".")
                if not self._is_dir_ignored(rel_dir / d)
            ]

            for filename in filenames:
                filepath = current / filename
                rel_path = filepath.relative_to(self.root_path)
                ext = filepath.suffix.lower()

                # 跳过二进制文件
                if ext in BINARY_EXTENSIONS:
                    continue

                # .gitignore 检查
                if self._gitignore and self._gitignore.is_ignored(rel_path):
                    continue

                # 扩展名过滤
                if self.include_ext and ext not in self.include_ext:
                    continue
                if self.exclude_ext and ext in self.exclude_ext:
                    continue

                # 获取优先级
                priority = self._priority_map.get(ext, 1)
                try:
                    size = filepath.stat().st_size
                except OSError:
                    size = 0

                entries.append(
                    FileEntry(filepath, rel_path, ext, size, priority)
                )
                extensions_found.add(ext)

        # 如果是 auto 模式，根据检测结果调整优先级
        if self.language == "auto" and extensions_found:
            detected = self._detect_language(extensions_found)
            if detected in LANGUAGE_PRESETS:
                detected_map = LANGUAGE_PRESETS[detected]
                for entry in entries:
                    entry.priority = detected_map.get(entry.extension, entry.priority)

        # 按优先级降序排列，同优先级按路径字母序
        entries.sort(key=lambda e: (-e.priority, str(e.relative_path)))
        return entries

    def _is_dir_ignored(self, rel_dir: Path) -> bool:
        """检查目录是否应被忽略。"""
        if self._gitignore:
            # 检查目录本身及目录下的 .gitignore 规则
            return self._gitignore.is_ignored(rel_dir / ".placeholder")
        return False

    def build_tree(self, entries: List[FileEntry]) -> str:
        """根据扫描结果构建目录树字符串。"""
        tree_lines: List[str] = [self.root_path.name + "/"]
        path_set = {str(e.relative_path) for e in entries}

        all_dirs: Set[str] = set()
        for p in path_set:
            parts = Path(p).parts
            for i in range(1, len(parts)):
                all_dirs.add("/".join(parts[:i]))

        sorted_dirs = sorted(all_dirs)
        sorted_files = sorted(path_set)

        # 构建树形结构
        tree_entries: List[Tuple[str, bool, str]] = []  # (path, is_file, indent_prefix)
        for d in sorted_dirs:
            tree_entries.append((d, False, ""))
        for f in sorted_files:
            tree_entries.append((f, True, ""))

        # 计算缩进
        for i, (path, is_file, _) in enumerate(tree_entries):
            parts = path.split("/")
            prefix_parts = []
            for j in range(len(parts) - 1):
                parent = "/".join(parts[: j + 1])
                # 检查是否有下一个兄弟
                has_sibling = False
                for k in range(i + 1, len(tree_entries)):
                    other = tree_entries[k][0]
                    if other.startswith(parent + "/"):
                        has_sibling = True
                        break
                if has_sibling:
                    prefix_parts.append("│   ")
                else:
                    prefix_parts.append("    ")
            prefix = "".join(prefix_parts)
            connector = "├── " if i < len(tree_entries) - 1 else "└── "
            if is_file:
                tree_lines.append(f"{prefix}{connector}{parts[-1]}")
            else:
                tree_lines.append(f"{prefix}{connector}{parts[-1]}/")

        return "\n".join(tree_lines)


# ---------------------------------------------------------------------------
# Token 估算器
# ---------------------------------------------------------------------------

class Tokenizer:
    """基于启发式规则的 token 数量估算器。

    对于英文文本，大约 1 token ≈ 4 个字符。
    对于 CJK（中日韩）文本，大约 1 token ≈ 1.5 个字符。
    """

    # CJK Unicode 范围
    CJK_RANGES = [
        (0x4E00, 0x9FFF),    # CJK Unified Ideographs
        (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
        (0x3000, 0x303F),    # CJK Symbols and Punctuation
        (0xFF00, 0xFFEF),    # Fullwidth Forms
        (0xAC00, 0xD7AF),    # Hangul Syllables
        (0x3040, 0x309F),    # Hiragana
        (0x30A0, 0x30FF),    # Katakana
    ]

    @classmethod
    def _is_cjk(cls, char: str) -> bool:
        """判断字符是否属于 CJK 字符。"""
        code = ord(char)
        return any(start <= code <= end for start, end in cls.CJK_RANGES)

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """估算文本的 token 数量。

        Args:
            text: 要估算的文本。

        Returns:
            估算的 token 数量。
        """
        if not text:
            return 0
        cjk_count = 0
        other_count = 0
        for char in text:
            if cls._is_cjk(char):
                cjk_count += 1
            else:
                other_count += 1
        # CJK: ~1.5 字符/token, 其他: ~4 字符/token
        cjk_tokens = int(cjk_count / 1.5)
        other_tokens = int(other_count / 4)
        return cjk_tokens + other_tokens

    @classmethod
    def truncate_to_budget(
        cls, text: str, budget: int, used: int = 0
    ) -> Tuple[str, int]:
        """将文本截断以适应 token 预算。

        Args:
            text: 要截断的文本。
            budget: 总 token 预算。
            used: 已使用的 token 数量。

        Returns:
            (截断后的文本, 实际使用的 token 数量) 元组。
        """
        remaining = budget - used
        if remaining <= 0:
            return "", used
        estimated = cls.estimate_tokens(text)
        if estimated <= remaining:
            return text, used + estimated

        # 按比例截断
        ratio = remaining / estimated
        target_chars = int(len(text) * ratio * 0.9)  # 留 10% 余量
        truncated = text[:target_chars]

        # 确保不在多字节字符中间截断
        if truncated and len(truncated) < len(text):
            truncated += "\n... [truncated to fit token budget]"
            actual_tokens = cls.estimate_tokens(truncated)
            return truncated, used + actual_tokens

        return truncated, used + cls.estimate_tokens(truncated)


# ---------------------------------------------------------------------------
# 格式化器
# ---------------------------------------------------------------------------

class Formatter:
    """将扫描结果格式化为多种输出格式。"""

    def __init__(self, root_path: Path, entries: List[FileEntry]) -> None:
        self.root_path = root_path
        self.entries = entries

    def _read_file(self, entry: FileEntry) -> str:
        """读取文件内容，处理编码问题。"""
        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
        for enc in encodings:
            try:
                return entry.path.read_text(encoding=enc)
            except (UnicodeDecodeError, OSError):
                continue
        return f"[无法读取文件: {entry.path}]"

    def format_markdown(
        self, token_budget: int = 50000, tree_only: bool = False
    ) -> str:
        """生成 Markdown 格式输出。

        Args:
            token_budget: 最大 token 预算。
            tree_only: 是否仅输出目录树。

        Returns:
            Markdown 格式字符串。
        """
        lines: List[str] = []
        lines.append(f"# Code Digest: {self.root_path.name}")
        lines.append("")
        lines.append(f"- **Path**: `{self.root_path}`")
        lines.append(f"- **Generated**: {datetime.now().isoformat()}")
        lines.append(f"- **Files**: {len(self.entries)}")
        lines.append("")

        # 目录树
        scanner = Scanner(self.root_path, language="auto")
        tree = scanner.build_tree(self.entries)
        lines.append("## Directory Structure")
        lines.append("")
        lines.append("```")
        lines.append(tree)
        lines.append("```")
        lines.append("")

        if tree_only:
            return "\n".join(lines)

        # 文件内容
        tokens_used = Tokenizer.estimate_tokens("\n".join(lines))
        lines.append("## File Contents")
        lines.append("")

        for entry in self.entries:
            if tokens_used >= token_budget:
                lines.append("")
                lines.append(
                    f"> **Note**: Token budget ({token_budget}) reached. "
                    f"{len(self.entries) - self.entries.index(entry)} files omitted."
                )
                break

            rel_str = str(entry.relative_path).replace("\\", "/")
            lines.append(f"### `{rel_str}`")
            lines.append("")

            content = self._read_file(entry)
            content, tokens_used = Tokenizer.truncate_to_budget(
                content, token_budget, tokens_used
            )

            lines.append("```" + entry.extension.lstrip("."))
            lines.append(content)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def format_json(
        self, token_budget: int = 50000, tree_only: bool = False
    ) -> str:
        """生成 JSON 格式输出。

        Args:
            token_budget: 最大 token 预算。
            tree_only: 是否仅输出目录树。

        Returns:
            JSON 格式字符串。
        """
        scanner = Scanner(self.root_path, language="auto")
        tree = scanner.build_tree(self.entries)

        result: Dict[str, Any] = {
            "path": str(self.root_path),
            "generated": datetime.now().isoformat(),
            "total_files": len(self.entries),
            "tree": tree,
        }

        if not tree_only:
            tokens_used = Tokenizer.estimate_tokens(json.dumps(result, ensure_ascii=False))
            files: List[Dict[str, Any]] = []

            for entry in self.entries:
                if tokens_used >= token_budget:
                    break

                content = self._read_file(entry)
                content, tokens_used = Tokenizer.truncate_to_budget(
                    content, token_budget, tokens_used
                )

                rel_str = str(entry.relative_path).replace("\\", "/")
                files.append({
                    "path": rel_str,
                    "extension": entry.extension,
                    "size": entry.size,
                    "priority": entry.priority,
                    "content": content,
                })

            result["files"] = files

        return json.dumps(result, ensure_ascii=False, indent=2)

    def format_xml(
        self, token_budget: int = 50000, tree_only: bool = False
    ) -> str:
        """生成 XML 格式输出。

        Args:
            token_budget: 最大 token 预算。
            tree_only: 是否仅输出目录树。

        Returns:
            XML 格式字符串。
        """
        root_el = ET.Element("codedigest")
        root_el.set("path", str(self.root_path))
        root_el.set("generated", datetime.now().isoformat())
        root_el.set("total_files", str(len(self.entries)))

        scanner = Scanner(self.root_path, language="auto")
        tree = scanner.build_tree(self.entries)

        tree_el = ET.SubElement(root_el, "tree")
        tree_el.text = tree

        if not tree_only:
            files_el = ET.SubElement(root_el, "files")
            tokens_used = Tokenizer.estimate_tokens(
                ET.tostring(root_el, encoding="unicode")
            )

            for entry in self.entries:
                if tokens_used >= token_budget:
                    break

                content = self._read_file(entry)
                content, tokens_used = Tokenizer.truncate_to_budget(
                    content, token_budget, tokens_used
                )

                file_el = ET.SubElement(files_el, "file")
                file_el.set("path", str(entry.relative_path).replace("\\", "/"))
                file_el.set("extension", entry.extension)
                file_el.set("size", str(entry.size))
                file_el.set("priority", str(entry.priority))
                file_el.text = content

        # 手动缩进美化输出
        rough_string = ET.tostring(root_el, encoding="unicode")
        try:
            import xml.dom.minidom as minidom
            dom = minidom.parseString(rough_string)
            return dom.toprettyxml(indent="  ", encoding=None)
        except Exception:
            return rough_string

    def format_text(
        self, token_budget: int = 50000, tree_only: bool = False
    ) -> str:
        """生成纯文本格式输出。

        Args:
            token_budget: 最大 token 预算。
            tree_only: 是否仅输出目录树。

        Returns:
            纯文本格式字符串。
        """
        lines: List[str] = []
        separator = "=" * 72

        lines.append(separator)
        lines.append(f"  Code Digest: {self.root_path.name}")
        lines.append(f"  Path: {self.root_path}")
        lines.append(f"  Generated: {datetime.now().isoformat()}")
        lines.append(f"  Files: {len(self.entries)}")
        lines.append(separator)
        lines.append("")

        scanner = Scanner(self.root_path, language="auto")
        tree = scanner.build_tree(self.entries)
        lines.append("[Directory Structure]")
        lines.append(tree)
        lines.append("")

        if tree_only:
            return "\n".join(lines)

        tokens_used = Tokenizer.estimate_tokens("\n".join(lines))
        lines.append("[File Contents]")
        lines.append("")

        for entry in self.entries:
            if tokens_used >= token_budget:
                lines.append("")
                lines.append(
                    f"--- Token budget ({token_budget}) reached. "
                    f"{len(self.entries) - self.entries.index(entry)} files omitted. ---"
                )
                break

            rel_str = str(entry.relative_path).replace("\\", "/")
            lines.append(f"--- {rel_str} ({entry.size} bytes, priority={entry.priority}) ---")
            lines.append("")

            content = self._read_file(entry)
            content, tokens_used = Tokenizer.truncate_to_budget(
                content, token_budget, tokens_used
            )
            lines.append(content)
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shell 补全安装说明
# ---------------------------------------------------------------------------

COMPLETION_INSTRUCTIONS = """
Shell Completion Installation Guide
====================================

Bash:
-----
Add the following to ~/.bashrc or ~/.bash_profile:

    _codedigest_completion() {
        local cur prev words cword
        _init_completion || return
        case ${prev} in
            codedigest)
                COMPREPLY=($(compgen -W "--output --format --token-budget --exclude --include --exclude-dirs --max-depth --language --no-gitignore --tree-only --stats --version --install-completion -o -f -t -x -i -e -d -l -v" -- "${cur}"))
                ;;
            *)
                _filedir
                ;;
        esac
    }
    complete -F _codedigest_completion codedigest

Then reload: source ~/.bashrc


Zsh:
-----
Add the following to ~/.zshrc:

    #compdef codedigest
    _codedigest() {
        local -a args
        args=(
            '--output[Output file path]:file:_files'
            '--format[Output format]:format:(markdown json xml text)'
            '--token-budget[Maximum token budget]:number:'
            '--exclude[Exclude extensions]:extensions:'
            '--include[Include extensions]:extensions:'
            '--exclude-dirs[Exclude directories]:dirs:'
            '--max-depth[Maximum depth]:number:'
            '--language[Language preset]:lang:(python javascript go rust java auto)'
            '--no-gitignore[Disable .gitignore]'
            '--tree-only[Only output tree]'
            '--stats[Show statistics]'
            '--version[Show version]'
            '--install-completion[Install completion]'
            '-o[Output file path]:file:_files'
            '-f[Output format]:format:(markdown json xml text)'
            '-t[Maximum token budget]:number:'
            '-x[Exclude extensions]:extensions:'
            '-i[Include extensions]:extensions:'
            '-e[Exclude directories]:dirs:'
            '-d[Maximum depth]:number:'
            '-l[Language preset]:lang:(python javascript go rust java auto)'
            '-v[Show version]'
            '*:path:_path_files -/'
        )
        _arguments -s $args
    }
    _codedigest

Then reload: source ~/.zshrc


Fish:
-----
Run the following command:

    complete -c codedigest -f
    complete -c codedigest -l output -s o -r
    complete -c codedigest -l format -s f -l 'markdown json xml text'
    complete -c codedigest -l token-budget -s t -r
    complete -c codedigest -l exclude -s x -r
    complete -c codedigest -l include -s i -r
    complete -c codedigest -l exclude-dirs -s e -r
    complete -c codedigest -l max-depth -s d -r
    complete -c codedigest -l language -s l -f -a 'python javascript go rust java auto'
    complete -c codedigest -l no-gitignore -f
    complete -c codedigest -l tree-only -f
    complete -c codedigest -l stats -f
    complete -c codedigest -l version -s v -f
    complete -c codedigest -l install-completion -f
"""


# ---------------------------------------------------------------------------
# CLI 参数解析与主入口
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        配置好的 ArgumentParser 实例。
    """
    parser = argparse.ArgumentParser(
        prog="codedigest",
        description=(
            "CodeDigest-CLI: 将代码仓库打包为 LLM 友好的摘要格式。\n"
            "扫描本地目录，提取代码文件内容，根据 token 预算智能裁剪，"
            "输出为 Markdown、JSON、XML 或纯文本格式。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  codedigest ./my-project\n"
            "  codedigest -f json -t 30000 -o output.json ./src\n"
            "  codedigest --tree-only --stats ./my-repo\n"
            "  codedigest -i py,js -x md,txt ./project\n"
        ),
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="要扫描的本地目录路径或 Git 仓库 URL（默认：当前目录）",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出文件路径。未指定则打印到标准输出",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["markdown", "json", "xml", "text"],
        default="markdown",
        help="输出格式（默认：markdown）",
    )
    parser.add_argument(
        "-t", "--token-budget",
        type=int,
        default=50000,
        help="最大 token 预算（默认：50000）",
    )
    parser.add_argument(
        "-x", "--exclude",
        default=None,
        help="要排除的文件扩展名，逗号分隔（如：png,jpg,svg）",
    )
    parser.add_argument(
        "-i", "--include",
        default=None,
        help="仅包含的文件扩展名，逗号分隔（如：py,js,ts）",
    )
    parser.add_argument(
        "-e", "--exclude-dirs",
        default="node_modules,.git,__pycache__,venv,.venv,dist,build,.next",
        help="要排除的目录名，逗号分隔（默认：node_modules,.git,__pycache__,venv,.venv,dist,build,.next）",
    )
    parser.add_argument(
        "-d", "--max-depth",
        type=int,
        default=0,
        help="最大目录扫描深度（默认：0 = 无限制）",
    )
    parser.add_argument(
        "-l", "--language",
        choices=["python", "javascript", "go", "rust", "java", "auto"],
        default="auto",
        help="语言预设（默认：auto，自动检测）",
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_true",
        default=False,
        help="禁用 .gitignore 模式匹配",
    )
    parser.add_argument(
        "--tree-only",
        action="store_true",
        default=False,
        help="仅输出目录树，不包含文件内容",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="显示统计信息（文件数、token 数等），不输出完整内容",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="显示版本号",
    )
    parser.add_argument(
        "--install-completion",
        action="store_true",
        default=False,
        help="打印 Shell 补全安装说明（bash/zsh/fish）",
    )

    return parser


def print_summary(
    file_count: int,
    total_tokens: int,
    output_format: str,
    output_path: Optional[str],
    elapsed: float,
) -> None:
    """在终端底部打印摘要信息行。

    Args:
        file_count: 处理的文件数量。
        total_tokens: 总 token 数量。
        output_format: 输出格式。
        output_path: 输出路径（None 表示 stdout）。
        elapsed: 耗时（秒）。
    """
    parts = [
        colors.green(str(file_count)) + " files",
        colors.cyan(str(total_tokens)) + " tokens",
        colors.yellow(output_format),
    ]
    if output_path:
        parts.append(f"-> {colors.bold(output_path)}")
    parts.append(f"({elapsed:.2f}s)")

    summary = "  ".join(parts)
    print(colors.dim(f"\n{'─' * 60}"), file=sys.stderr)
    print(f"  {colors.bold('CodeDigest')} {summary}", file=sys.stderr)
    print(colors.dim(f"{'─' * 60}"), file=sys.stderr)


def print_error(message: str) -> None:
    """打印用户友好的错误信息。

    Args:
        message: 错误描述。
    """
    print(
        f"  {colors.red('Error')}: {message}",
        file=sys.stderr,
    )


def print_stats(entries: List[FileEntry], token_budget: int) -> None:
    """打印统计信息。

    Args:
        entries: 扫描到的文件列表。
        token_budget: token 预算。
    """
    total_size = sum(e.size for e in entries)
    ext_counts: Dict[str, int] = {}
    for e in entries:
        ext_counts[e.extension] = ext_counts.get(e.extension, 0) + 1

    print(colors.bold("\n  CodeDigest Statistics"))
    print(colors.dim("  " + "─" * 40))
    print(f"  Total files:    {colors.green(str(len(entries)))}")
    print(f"  Total size:     {colors.cyan(_format_size(total_size))}")
    print(f"  Token budget:   {colors.yellow(str(token_budget))}")
    print(f"  Unique exts:    {len(ext_counts)}")

    if ext_counts:
        print(colors.dim("\n  Extension breakdown:"))
        sorted_exts = sorted(ext_counts.items(), key=lambda x: -x[1])
        for ext, count in sorted_exts[:15]:
            bar_len = min(count, 40)
            bar = colors.green("█" * bar_len) + colors.dim("░" * (40 - bar_len))
            print(f"    {ext or '(none)':>8s}  {bar} {count}")

    if entries:
        print(colors.dim("\n  Top priority files:"))
        for e in entries[:10]:
            print(f"    {colors.cyan(str(e.relative_path)):<50s} pri={e.priority}")


def _format_size(size: int) -> str:
    """将字节数格式化为人类可读的字符串。"""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 主入口函数。

    Args:
        argv: 命令行参数列表。为 None 时使用 sys.argv[1:]。

    Returns:
        退出码（0 成功，非 0 失败）。
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Shell 补全安装说明
    if args.install_completion:
        print(COMPLETION_INSTRUCTIONS)
        return 0

    start_time = time.time()

    # 解析路径参数
    target_path = Path(args.path).resolve()

    # 验证路径
    if not target_path.exists():
        print_error(f"路径不存在: {target_path}")
        return 1
    if not target_path.is_dir():
        print_error(f"路径不是目录: {target_path}")
        return 1

    # 解析扩展名过滤
    exclude_ext: Optional[Set[str]] = None
    if args.exclude:
        exclude_ext = {
            ext.strip().lower() if ext.strip().startswith(".") else "." + ext.strip().lower()
            for ext in args.exclude.split(",")
            if ext.strip()
        }

    include_ext: Optional[Set[str]] = None
    if args.include:
        include_ext = {
            ext.strip().lower() if ext.strip().startswith(".") else "." + ext.strip().lower()
            for ext in args.include.split(",")
            if ext.strip()
        }

    # 解析排除目录
    exclude_dirs: Set[str] = {d.strip() for d in args.exclude_dirs.split(",") if d.strip()}

    # 创建扫描器并扫描
    try:
        with ProgressIndicator(f"Scanning {target_path.name}"):
            scanner = Scanner(
                root_path=target_path,
                include_ext=include_ext,
                exclude_ext=exclude_ext,
                exclude_dirs=exclude_dirs,
                max_depth=args.max_depth,
                use_gitignore=not args.no_gitignore,
                language=args.language,
            )
            entries = scanner.scan()
    except (OSError, PermissionError) as exc:
        print_error(f"扫描失败: {exc}")
        return 1

    if not entries:
        print_error(f"未找到任何代码文件: {target_path}")
        return 1

    elapsed = time.time() - start_time

    # 统计模式
    if args.stats:
        print_stats(entries, args.token_budget)
        print_summary(len(entries), 0, "stats", None, elapsed)
        return 0

    # 格式化输出
    try:
        formatter = Formatter(target_path, entries)
        format_func = {
            "markdown": formatter.format_markdown,
            "json": formatter.format_json,
            "xml": formatter.format_xml,
            "text": formatter.format_text,
        }[args.format]

        output = format_func(
            token_budget=args.token_budget,
            tree_only=args.tree_only,
        )
    except Exception as exc:
        print_error(f"格式化输出失败: {exc}")
        return 1

    # 写入输出
    if args.output:
        try:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
        except (OSError, PermissionError) as exc:
            print_error(f"写入输出文件失败: {exc}")
            return 1
    else:
        print(output)

    # 估算输出 token 数
    total_tokens = Tokenizer.estimate_tokens(output)
    print_summary(len(entries), total_tokens, args.format, args.output, elapsed)

    return 0


if __name__ == "__main__":
    sys.exit(main())
