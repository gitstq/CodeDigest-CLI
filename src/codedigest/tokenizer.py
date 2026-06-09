"""Token 估算模块 - 估算文本的 Token 数量并管理 Token 预算。

本模块负责：
- 基于字符的 Token 数量估算（英文约 4 字符/token，CJK 约 2 字符/token）
- Token 预算控制：根据预算决定包含哪些文件以及如何截断
- 智能截断：保留导入/导出/类签名，裁剪函数体
- 提供摘要统计信息
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .scanner import FileEntry


@dataclass
class TokenStats:
    """Token 统计信息数据类。

    Attributes:
        total_files: 扫描到的文件总数。
        total_tokens: 所有文件的总 Token 数估算。
        included_files: 包含在预算内的文件数。
        truncated_files: 被截断的文件数。
        excluded_files: 因超出预算被排除的文件数。
        budget_used: 实际使用的 Token 数。
        budget_total: 分配的总 Token 预算。
    """

    total_files: int = 0
    total_tokens: int = 0
    included_files: int = 0
    truncated_files: int = 0
    excluded_files: int = 0
    budget_used: int = 0
    budget_total: int = 0

    def summary(self) -> str:
        """生成统计摘要字符串。

        Returns:
            格式化的统计摘要。
        """
        lines = [
            f"总文件数: {self.total_files}",
            f"总 Token 数: {self.total_tokens:,}",
            f"包含文件数: {self.included_files}",
            f"截断文件数: {self.truncated_files}",
            f"排除文件数: {self.excluded_files}",
            f"已用预算: {self.budget_used:,} / {self.budget_total:,}",
        ]
        return "\n".join(lines)


class TokenEstimator:
    """Token 数量估算器。

    使用基于字符的启发式方法估算 Token 数量：
    - 英文文本：约 4 个字符对应 1 个 Token
    - CJK 文本：约 2 个字符对应 1 个 Token
    - 混合文本：按比例加权计算

    Usage:
        estimator = TokenEstimator()
        count = estimator.estimate("Hello, world!")
    """

    # CJK Unicode 范围
    CJK_RANGES = [
        (0x4E00, 0x9FFF),    # CJK 统一表意文字
        (0x3400, 0x4DBF),    # CJK 扩展 A
        (0x20000, 0x2A6DF),  # CJK 扩展 B
        (0x2A700, 0x2B73F),  # CJK 扩展 C
        (0x2B740, 0x2B81F),  # CJK 扩展 D
        (0x2B820, 0x2CEAF),  # CJK 扩展 E
        (0xF900, 0xFAFF),    # CJK 兼容表意文字
        (0x3000, 0x303F),    # CJK 标点符号
        (0xFF00, 0xFFEF),    # 全角字符
        (0xAC00, 0xD7AF),    # 韩文音节
        (0x3040, 0x309F),    # 平假名
        (0x30A0, 0x30FF),    # 片假名
    ]

    # 英文字符的 Token 比率（字符数 / Token 数）
    CHARS_PER_TOKEN_EN = 4.0
    # CJK 字符的 Token 比率
    CHARS_PER_TOKEN_CJK = 1.5

    def estimate(self, text: str) -> int:
        """估算给定文本的 Token 数量。

        Args:
            text: 要估算的文本。

        Returns:
            估算的 Token 数量。
        """
        if not text:
            return 0

        cjk_count = 0
        other_count = 0

        for char in text:
            code_point = ord(char)
            is_cjk = False
            for start, end in self.CJK_RANGES:
                if start <= code_point <= end:
                    is_cjk = True
                    break
            if is_cjk:
                cjk_count += 1
            else:
                other_count += 1

        tokens_from_cjk = cjk_count / self.CHARS_PER_TOKEN_CJK
        tokens_from_other = other_count / self.CHARS_PER_TOKEN_EN

        return max(1, int(tokens_from_cjk + tokens_from_other))

    def estimate_file(self, content: str) -> int:
        """估算文件内容的 Token 数量（含路径开销）。

        Args:
            content: 文件内容。

        Returns:
            估算的 Token 数量（包含路径标题开销）。
        """
        # 路径标题的 Token 开销（约 20 token）
        header_overhead = 20
        return self.estimate(content) + header_overhead


class TokenBudgetManager:
    """Token 预算管理器。

    根据给定的 Token 预算，决定哪些文件应完整包含、哪些应截断、哪些应排除。

    Usage:
        manager = TokenBudgetManager(budget=100000)
        results = manager.allocate(files, read_fn=read_file)
    """

    def __init__(
        self,
        budget: int = 100000,
        header_tokens_per_file: int = 20,
        min_tokens_per_file: int = 50,
    ) -> None:
        """初始化 Token 预算管理器。

        Args:
            budget: 总 Token 预算。
            header_tokens_per_file: 每个文件的标题/路径开销 Token 数。
            min_tokens_per_file: 每个文件的最小保留 Token 数。
        """
        self.budget = budget
        self.header_tokens_per_file = header_tokens_per_file
        self.min_tokens_per_file = min_tokens_per_file
        self.estimator = TokenEstimator()

    def allocate(
        self,
        files: List[FileEntry],
        read_fn,
    ) -> Tuple[List[Tuple[FileEntry, str, bool]], TokenStats]:
        """根据预算分配 Token 给文件。

        Args:
            files: 按优先级排序的文件列表。
            read_fn: 读取文件内容的函数，签名为 (str) -> str。

        Returns:
            元组：(文件结果列表, Token统计信息)。
            文件结果列表中每个元素为 (FileEntry, 内容, 是否被截断)。
        """
        stats = TokenStats(
            total_files=len(files),
            budget_total=self.budget,
        )

        results: List[Tuple[FileEntry, str, bool]] = []
        remaining_budget = self.budget

        for file_entry in files:
            if remaining_budget <= 0:
                stats.excluded_files += len(files) - len(results)
                break

            try:
                content = read_fn(file_entry.path)
            except (OSError, PermissionError) as e:
                # 跳过无法读取的文件
                stats.excluded_files += 1
                continue

            total_file_tokens = self.estimator.estimate_file(content)
            stats.total_tokens += total_file_tokens

            # 检查文件是否能完整放入预算
            available_for_content = remaining_budget - self.header_tokens_per_file

            if total_file_tokens <= remaining_budget:
                # 完整包含文件
                results.append((file_entry, content, False))
                remaining_budget -= total_file_tokens
                stats.included_files += 1
                stats.budget_used += total_file_tokens
            elif available_for_content >= self.min_tokens_per_file:
                # 需要截断文件
                content_tokens = self.estimator.estimate(content)
                target_tokens = available_for_content
                truncated_content = self._truncate_content(
                    content, content_tokens, target_tokens
                )
                actual_tokens = self.estimator.estimate(truncated_content) + self.header_tokens_per_file
                results.append((file_entry, truncated_content, True))
                remaining_budget -= actual_tokens
                stats.included_files += 1
                stats.truncated_files += 1
                stats.budget_used += actual_tokens
            else:
                # 预算不足，排除文件
                stats.excluded_files += 1

        return results, stats

    def _truncate_content(
        self, content: str, original_tokens: int, target_tokens: int
    ) -> str:
        """智能截断文件内容。

        截断策略：
        1. 保留文件顶部的导入/导出语句
        2. 保留类和函数签名
        3. 裁剪函数体内容
        4. 添加截断标记

        Args:
            content: 原始文件内容。
            original_tokens: 原始内容的 Token 数。
            target_tokens: 目标 Token 数。

        Returns:
            截断后的内容。
        """
        if target_tokens >= original_tokens:
            return content

        lines = content.split("\n")
        if len(lines) <= 5:
            # 文件太短，直接截断
            ratio = target_tokens / max(original_tokens, 1)
            target_lines = max(1, int(len(lines) * ratio))
            truncated = "\n".join(lines[:target_lines])
            return truncated + "\n... [内容已截断]"

        # 分析文件结构
        important_lines: List[str] = []  # 重要行（导入、签名等）
        body_lines: List[str] = []  # 函数体行
        in_function_body = False
        brace_depth = 0
        paren_depth = 0

        # 用于检测语言类型的简单启发式
        is_python = self._detect_python(lines)
        is_js_like = self._detect_js_like(lines)

        for line in lines:
            stripped = line.strip()

            # 空行
            if not stripped:
                if in_function_body:
                    body_lines.append(line)
                continue

            # 检测是否为导入/导出语句
            if self._is_import_or_export(stripped):
                important_lines.append(line)
                continue

            # 检测是否为类/函数/接口定义
            if self._is_definition(stripped, is_python, is_js_like):
                important_lines.append(line)
                if is_python:
                    in_function_body = True
                    continue
                else:
                    # 非 Python 语言，跟踪花括号
                    in_function_body = True
                    brace_depth = stripped.count("{") - stripped.count("}")
                    paren_depth = stripped.count("(") - stripped.count(")")
                    continue

            if in_function_body:
                if is_python:
                    # Python 通过缩进判断函数体
                    if line.startswith(" ") or line.startswith("\t"):
                        body_lines.append(line)
                    else:
                        in_function_body = False
                        important_lines.append(line)
                else:
                    brace_depth += stripped.count("{") - stripped.count("}")
                    paren_depth += stripped.count("(") - stripped.count(")")
                    if brace_depth <= 0 and paren_depth <= 0:
                        in_function_body = False
                        important_lines.append(line)
                    else:
                        body_lines.append(line)
            else:
                important_lines.append(line)

        # 计算重要行的 Token 数
        important_text = "\n".join(important_lines)
        important_tokens = self.estimator.estimate(important_text)

        if important_tokens <= target_tokens:
            # 重要行可以全部保留，按比例添加函数体
            remaining_tokens = target_tokens - important_tokens
            body_text = "\n".join(body_lines)
            body_tokens = self.estimator.estimate(body_text)

            if body_tokens <= remaining_tokens:
                # 函数体也能全部保留
                return content

            # 按比例截断函数体
            ratio = remaining_tokens / max(body_tokens, 1)
            target_body_lines = max(1, int(len(body_lines) * ratio))
            truncated_body = "\n".join(body_lines[:target_body_lines])

            result = important_text + "\n" + truncated_body
            result += "\n... [内容已截断，原文共 {} 行]".format(len(lines))
            return result
        else:
            # 即使只保留重要行也超出预算，按比例截断重要行
            ratio = target_tokens / max(important_tokens, 1)
            target_lines = max(1, int(len(important_lines) * ratio))
            truncated = "\n".join(important_lines[:target_lines])
            truncated += "\n... [内容已截断，原文共 {} 行]".format(len(lines))
            return truncated

    @staticmethod
    def _detect_python(lines: List[str]) -> bool:
        """检测文件是否为 Python 代码。

        Args:
            lines: 文件行列表。

        Returns:
            是否为 Python 代码。
        """
        python_indicators = [
            "def ", "class ", "import ", "from ", "if __name__",
            "print(", "self.", "# ", '"""', "'''",
        ]
        count = 0
        for line in lines[:20]:
            stripped = line.strip()
            for indicator in python_indicators:
                if indicator in stripped:
                    count += 1
                    break
        return count >= 2

    @staticmethod
    def _detect_js_like(lines: List[str]) -> bool:
        """检测文件是否为类 JavaScript 代码。

        Args:
            lines: 文件行列表。

        Returns:
            是否为类 JavaScript 代码。
        """
        js_indicators = [
            "function ", "const ", "let ", "var ", "=>",
            "require(", "export ", "import ", "module.exports",
            "console.log(", "async ", "await ",
        ]
        count = 0
        for line in lines[:20]:
            stripped = line.strip()
            for indicator in js_indicators:
                if indicator in stripped:
                    count += 1
                    break
        return count >= 2

    @staticmethod
    def _is_import_or_export(line: str) -> bool:
        """判断是否为导入/导出语句。

        Args:
            line: 去除首尾空白的行。

        Returns:
            是否为导入/导出语句。
        """
        import_patterns = [
            "import ", "from ", "require(",
            "export ", "module.exports",
            "#include", "#pragma",
            "using ", "use ",
        ]
        for pattern in import_patterns:
            if line.startswith(pattern):
                return True
        return False

    @staticmethod
    def _is_definition(line: str, is_python: bool, is_js_like: bool) -> bool:
        """判断是否为类/函数/接口定义行。

        Args:
            line: 去除首尾空白的行。
            is_python: 是否为 Python 文件。
            is_js_like: 是否为类 JS 文件。

        Returns:
            是否为定义行。
        """
        if is_python:
            if line.startswith("def ") or line.startswith("class "):
                return True
            if line.startswith("async def "):
                return True
            # 装饰器
            if line.startswith("@"):
                return True

        if is_js_like:
            if any(
                line.startswith(p)
                for p in [
                    "function ", "async function ",
                    "const ", "let ", "var ",
                    "class ", "interface ", "type ",
                    "export function ", "export default",
                    "export const ", "export class ",
                    "export interface ", "export type ",
                ]
            ):
                return True
            # 箭头函数
            if "=>" in line and ("function" in line or "(" in line):
                return True

        # 通用定义模式
        if any(
            line.startswith(p)
            for p in [
                "def ", "class ", "interface ", "struct ",
                "enum ", "fn ", "func ", "func (",
                "public ", "private ", "protected ",
                "static ", "abstract ", "final ",
            ]
        ):
            return True

        return False
