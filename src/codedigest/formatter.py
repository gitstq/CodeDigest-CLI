"""输出格式化模块 - 将代码摘要数据格式化为多种输出格式。

本模块支持以下输出格式：
- Markdown: 目录树 + 文件路径标题 + 围栏代码块
- JSON: 结构化 JSON 对象，包含元数据、目录树和文件内容
- XML: 结构化 XML 文档，具有适当的嵌套
- Plain Text: 带有清晰分隔符的纯文本格式
"""

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from xml.dom import minidom

from .scanner import FileEntry
from .tree import TreeGenerator, TreeOptions


class OutputFormatter:
    """输出格式化器基类。

    定义了格式化器的通用接口和共享方法。
    """

    def __init__(
        self,
        root_dir: str,
        files: List[Tuple[FileEntry, str, bool]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初始化输出格式化器。

        Args:
            root_dir: 扫描的根目录路径。
            files: 文件结果列表，每个元素为 (FileEntry, 内容, 是否截断)。
            metadata: 额外的元数据信息。
        """
        self.root_dir = os.path.abspath(root_dir)
        self.files = files
        self.metadata = metadata or {}
        self.generated_at = datetime.now().isoformat()

    def format(self) -> str:
        """格式化输出。子类必须实现此方法。

        Raises:
            NotImplementedError: 如果子类未实现此方法。
        """
        raise NotImplementedError("子类必须实现 format() 方法")

    @staticmethod
    def _detect_language(ext: str) -> str:
        """根据文件扩展名检测编程语言。

        Args:
            ext: 文件扩展名（含点号）。

        Returns:
            语言标识字符串，用于代码围栏标记。
        """
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".kt": "kotlin",
            ".scala": "scala",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".m": "objectivec",
            ".dart": "dart",
            ".lua": "lua",
            ".r": "r",
            ".R": "r",
            ".sql": "sql",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
            ".ps1": "powershell",
            ".bat": "batch",
            ".cmd": "batch",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".less": "less",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".md": "markdown",
            ".rst": "rst",
            ".proto": "protobuf",
            ".graphql": "graphql",
            ".tf": "hcl",
            ".hcl": "hcl",
            ".ex": "elixir",
            ".exs": "elixir",
            ".erl": "erlang",
            ".hs": "haskell",
            ".ml": "ocaml",
            ".clj": "clojure",
            ".sol": "solidity",
            ".vim": "vim",
            ".el": "emacs-lisp",
            ".dockerfile": "dockerfile",
            ".makefile": "makefile",
        }
        return language_map.get(ext.lower(), "")


class MarkdownFormatter(OutputFormatter):
    """Markdown 格式化器。

    生成格式：
    ```
    # CodeDigest: 项目名称

    > 生成时间: ...

    ## 目录结构

    ```
    project/
    ├── src/
    │   ├── main.py
    │   └── utils.py
    └── README.md
    ```

    ## 文件: src/main.py

    ```python
    # 文件内容...
    ```

    [已截断]
    ```
    """

    def format(self) -> str:
        """生成 Markdown 格式的输出。

        Returns:
            Markdown 格式的字符串。
        """
        lines: List[str] = []

        # 标题
        project_name = os.path.basename(self.root_dir)
        lines.append(f"# CodeDigest: {project_name}\n")

        # 生成信息
        lines.append(f"> 生成时间: {self.generated_at}")
        lines.append(f"> 文件数量: {len(self.files)}")
        lines.append("")

        # 目录树
        lines.append("## 目录结构\n")
        tree_gen = TreeGenerator(TreeOptions(show_sizes=True))
        tree_str = tree_gen.generate(self.root_dir, [f[0] for f in self.files])
        lines.append(f"```\n{tree_str}\n```\n")

        # 文件内容
        lines.append("---\n")
        lines.append("## 文件内容\n")

        for entry, content, truncated in self.files:
            language = self._detect_language(entry.extension)
            truncated_marker = " [已截断]" if truncated else ""

            lines.append(f"### 文件: `{entry.relative_path}`{truncated_marker}\n")
            lines.append(f"**大小:** {self._format_size(entry.size)} | "
                         f"**优先级:** {entry.priority} | "
                         f"**分类:** {entry.category}\n")

            lines.append(f"```{language}")
            lines.append(content)
            lines.append("```\n")

        return "\n".join(lines)

    @staticmethod
    def _format_size(size: int) -> str:
        """将字节大小格式化为人类可读的字符串。

        Args:
            size: 文件大小（字节）。

        Returns:
            格式化后的大小字符串。
        """
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class JsonFormatter(OutputFormatter):
    """JSON 格式化器。

    生成结构化的 JSON 对象：

    ```json
    {
        "metadata": {
            "project_name": "...",
            "generated_at": "...",
            "root_dir": "..."
        },
        "tree": "...",
        "files": [
            {
                "path": "...",
                "size": 1234,
                "extension": ".py",
                "priority": 100,
                "category": "entry",
                "content": "...",
                "truncated": false
            }
        ],
        "stats": {
            "total_files": 10,
            "included_files": 10
        }
    }
    ```
    """

    def format(self) -> str:
        """生成 JSON 格式的输出。

        Returns:
            JSON 格式的字符串。
        """
        project_name = os.path.basename(self.root_dir)

        # 生成目录树
        tree_gen = TreeGenerator(TreeOptions(show_sizes=True))
        tree_str = tree_gen.generate(self.root_dir, [f[0] for f in self.files])

        # 构建文件列表
        file_list = []
        for entry, content, truncated in self.files:
            file_list.append({
                "path": entry.relative_path,
                "size": entry.size,
                "extension": entry.extension,
                "priority": entry.priority,
                "category": entry.category,
                "modified_time": entry.modified_time.isoformat(),
                "content": content,
                "truncated": truncated,
            })

        # 构建完整输出
        output = {
            "metadata": {
                "project_name": project_name,
                "generated_at": self.generated_at,
                "root_dir": self.root_dir,
                **self.metadata,
            },
            "tree": tree_str,
            "files": file_list,
            "stats": {
                "total_files": len(file_list),
                "truncated_files": sum(1 for _, _, t in self.files if t),
            },
        }

        return json.dumps(output, ensure_ascii=False, indent=2)


class XmlFormatter(OutputFormatter):
    """XML 格式化器。

    生成结构化的 XML 文档：

    ```xml
    <?xml version="1.0" encoding="utf-8"?>
    <codedigest>
        <metadata>
            <project_name>...</project_name>
            <generated_at>...</generated_at>
        </metadata>
        <tree>...</tree>
        <files>
            <file path="..." priority="100" category="entry" truncated="false">
                <size>1234</size>
                <extension>.py</extension>
                <content><![CDATA[...]]></content>
            </file>
        </files>
    </codedigest>
    ```
    """

    def format(self) -> str:
        """生成 XML 格式的输出。

        Returns:
            XML 格式的字符串。
        """
        root = ET.Element("codedigest")

        # 元数据
        metadata_elem = ET.SubElement(root, "metadata")
        ET.SubElement(metadata_elem, "project_name").text = os.path.basename(self.root_dir)
        ET.SubElement(metadata_elem, "generated_at").text = self.generated_at
        ET.SubElement(metadata_elem, "root_dir").text = self.root_dir

        # 额外元数据
        for key, value in self.metadata.items():
            meta_item = ET.SubElement(metadata_elem, key)
            meta_item.text = str(value)

        # 目录树
        tree_gen = TreeGenerator(TreeOptions(show_sizes=True))
        tree_str = tree_gen.generate(self.root_dir, [f[0] for f in self.files])
        ET.SubElement(root, "tree").text = tree_str

        # 文件列表
        files_elem = ET.SubElement(root, "files")
        for entry, content, truncated in self.files:
            file_elem = ET.SubElement(files_elem, "file")
            file_elem.set("path", entry.relative_path)
            file_elem.set("priority", str(entry.priority))
            file_elem.set("category", entry.category)
            file_elem.set("truncated", str(truncated).lower())

            ET.SubElement(file_elem, "size").text = str(entry.size)
            ET.SubElement(file_elem, "extension").text = entry.extension
            ET.SubElement(file_elem, "modified_time").text = entry.modified_time.isoformat()

            # 使用 CDATA 包裹文件内容
            content_elem = ET.SubElement(file_elem, "content")
            content_elem.text = content

        # 美化 XML 输出
        rough_string = ET.tostring(root, encoding="unicode")
        parsed = minidom.parseString(rough_string)
        pretty_xml = parsed.toprettyxml(indent="  ", encoding=None)

        # 移除 minidom 添加的额外 XML 声明
        lines = pretty_xml.split("\n")
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        return "\n".join(line for line in lines if line.strip())


class PlainTextFormatter(OutputFormatter):
    """纯文本格式化器。

    生成带有清晰分隔符的纯文本输出：

    ```
    ============================================================
    CodeDigest: 项目名称
    生成时间: ...
    ============================================================

    [目录结构]
    project/
    ├── src/
    │   └── main.py
    └── README.md

    ============================================================
    文件: src/main.py
    大小: 1.2 KB | 优先级: 100 | 分类: entry
    ============================================================

    # 文件内容...

    ------------------------------------------------------------
    ```
    """

    SEPARATOR = "=" * 60
    THIN_SEPARATOR = "-" * 60

    def format(self) -> str:
        """生成纯文本格式的输出。

        Returns:
            纯文本格式的字符串。
        """
        lines: List[str] = []

        # 标题
        project_name = os.path.basename(self.root_dir)
        lines.append(self.SEPARATOR)
        lines.append(f"CodeDigest: {project_name}")
        lines.append(f"生成时间: {self.generated_at}")
        lines.append(f"文件数量: {len(self.files)}")
        lines.append(self.SEPARATOR)
        lines.append("")

        # 目录树
        lines.append("[目录结构]")
        tree_gen = TreeGenerator(TreeOptions(show_sizes=True))
        tree_str = tree_gen.generate(self.root_dir, [f[0] for f in self.files])
        lines.append(tree_str)
        lines.append("")

        # 文件内容
        for entry, content, truncated in self.files:
            truncated_marker = " [已截断]" if truncated else ""

            lines.append(self.SEPARATOR)
            lines.append(f"文件: {entry.relative_path}{truncated_marker}")
            lines.append(f"大小: {self._format_size(entry.size)} | "
                         f"优先级: {entry.priority} | "
                         f"分类: {entry.category}")
            lines.append(self.SEPARATOR)
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append(self.THIN_SEPARATOR)
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_size(size: int) -> str:
        """将字节大小格式化为人类可读的字符串。

        Args:
            size: 文件大小（字节）。

        Returns:
            格式化后的大小字符串。
        """
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


def create_formatter(
    format_type: str,
    root_dir: str,
    files: List[Tuple[FileEntry, str, bool]],
    metadata: Optional[Dict[str, Any]] = None,
) -> OutputFormatter:
    """工厂函数：根据格式类型创建对应的格式化器。

    Args:
        format_type: 输出格式类型（markdown/json/xml/plain）。
        root_dir: 扫描的根目录路径。
        files: 文件结果列表。
        metadata: 额外的元数据信息。

    Returns:
        对应的格式化器实例。

    Raises:
        ValueError: 如果格式类型不支持。
    """
    formatters = {
        "markdown": MarkdownFormatter,
        "md": MarkdownFormatter,
        "json": JsonFormatter,
        "xml": XmlFormatter,
        "plain": PlainTextFormatter,
        "text": PlainTextFormatter,
        "txt": PlainTextFormatter,
    }

    formatter_class = formatters.get(format_type.lower())
    if formatter_class is None:
        supported = ", ".join(sorted(set(formatters.keys())))
        raise ValueError(
            f"不支持的格式类型: '{format_type}'。支持的格式: {supported}"
        )

    return formatter_class(
        root_dir=root_dir,
        files=files,
        metadata=metadata,
    )
