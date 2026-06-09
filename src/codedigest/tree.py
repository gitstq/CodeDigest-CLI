"""目录树可视化模块 - 生成 ASCII/Unicode 目录树结构。

本模块负责：
- 生成类似 `tree` 命令的目录树结构
- 在文件名旁显示文件大小和 Token 计数
- 支持可配置的最大深度
- 使用 Unicode 框线字符（├──, └──, │）绘制树形结构
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .scanner import FileEntry
from .tokenizer import TokenEstimator


@dataclass
class TreeOptions:
    """目录树生成选项。

    Attributes:
        max_depth: 最大显示深度。None 表示无限制。
        show_sizes: 是否显示文件大小。
        show_tokens: 是否显示 Token 计数。
        show_all: 是否显示隐藏文件（以 . 开头的文件）。
        unicode_chars: 是否使用 Unicode 框线字符。
    """

    max_depth: Optional[int] = None
    show_sizes: bool = False
    show_tokens: bool = False
    show_all: bool = True
    unicode_chars: bool = True


@dataclass
class TreeNode:
    """目录树节点。

    Attributes:
        name: 节点名称（文件名或目录名）。
        is_dir: 是否为目录。
        children: 子节点列表。
        file_entry: 关联的 FileEntry（仅叶子节点）。
        depth: 节点深度。
    """

    name: str
    is_dir: bool = False
    children: List["TreeNode"] = field(default_factory=list)
    file_entry: Optional[FileEntry] = None
    depth: int = 0


class TreeGenerator:
    """目录树生成器。

    根据文件列表构建目录树结构，并生成 ASCII/Unicode 文本表示。

    Usage:
        options = TreeOptions(show_sizes=True, show_tokens=True)
        generator = TreeGenerator(options)
        tree_str = generator.generate("/path/to/project", file_entries)
        print(tree_str)
    """

    # Unicode 框线字符
    BRANCH = "├── "
    LAST_BRANCH = "└── "
    VERTICAL = "│   "
    SPACE = "    "

    # ASCII 替代字符
    ASCII_BRANCH = "|-- "
    ASCII_LAST_BRANCH = "`-- "
    ASCII_VERTICAL = "|   "
    ASCII_SPACE = "    "

    def __init__(self, options: Optional[TreeOptions] = None) -> None:
        """初始化目录树生成器。

        Args:
            options: 目录树生成选项。如果为 None，使用默认选项。
        """
        self.options = options or TreeOptions()
        self.token_estimator = TokenEstimator()

    def generate(
        self,
        root_dir: str,
        files: List[FileEntry],
        root_name: Optional[str] = None,
    ) -> str:
        """生成目录树的文本表示。

        Args:
            root_dir: 扫描的根目录路径。
            files: 文件条目列表。
            root_name: 根目录的显示名称。如果为 None，使用实际目录名。

        Returns:
            目录树的字符串表示。
        """
        import os

        if root_name is None:
            root_name = os.path.basename(root_dir) or root_dir

        # 构建目录树结构
        root_node = self._build_tree(files)

        # 生成文本输出
        lines: List[str] = [root_name + "/"]
        self._render_node(root_node, "", True, lines)

        return "\n".join(lines)

    def _build_tree(self, files: List[FileEntry]) -> TreeNode:
        """根据文件列表构建目录树。

        Args:
            files: 文件条目列表。

        Returns:
            树的根节点。
        """
        root = TreeNode(name="", is_dir=True)

        for file_entry in files:
            parts = file_entry.relative_path.replace("\\", "/").split("/")
            current = root

            for i, part in enumerate(parts):
                is_last = (i == len(parts) - 1)

                if is_last:
                    # 叶子节点（文件）
                    node = TreeNode(
                        name=part,
                        is_dir=False,
                        file_entry=file_entry,
                        depth=i,
                    )
                    current.children.append(node)
                else:
                    # 目录节点
                    dir_node = self._find_or_create_child(current, part, i)
                    current = dir_node

        # 排序：目录在前，文件在后，各自按名称排序
        self._sort_tree(root)

        return root

    def _find_or_create_child(
        self, parent: TreeNode, name: str, depth: int
    ) -> TreeNode:
        """在父节点中查找或创建子目录节点。

        Args:
            parent: 父节点。
            name: 目录名称。
            depth: 节点深度。

        Returns:
            找到或创建的目录节点。
        """
        for child in parent.children:
            if child.is_dir and child.name == name:
                return child

        node = TreeNode(name=name, is_dir=True, depth=depth)
        parent.children.append(node)
        return node

    def _sort_tree(self, node: TreeNode) -> None:
        """递归排序树的子节点。

        排序规则：目录在前，文件在后，各自按名称排序。

        Args:
            node: 要排序的节点。
        """
        if not node.children:
            return

        # 分离目录和文件
        dirs = [c for c in node.children if c.is_dir]
        files = [c for c in node.children if not c.is_dir]

        # 各自按名称排序
        dirs.sort(key=lambda c: c.name.lower())
        files.sort(key=lambda c: c.name.lower())

        node.children = dirs + files

        # 递归排序子目录
        for child in node.children:
            if child.is_dir:
                self._sort_tree(child)

    def _render_node(
        self,
        node: TreeNode,
        prefix: str,
        is_root: bool,
        lines: List[str],
    ) -> None:
        """递归渲染树节点为文本行。

        Args:
            node: 当前节点。
            prefix: 当前行前缀（用于绘制连接线）。
            is_root: 是否为根节点。
            lines: 输出行列表。
        """
        use_unicode = self.options.unicode_chars

        if use_unicode:
            branch = self.BRANCH
            last_branch = self.LAST_BRANCH
            vertical = self.VERTICAL
            space = self.SPACE
        else:
            branch = self.ASCII_BRANCH
            last_branch = self.ASCII_LAST_BRANCH
            vertical = self.ASCII_VERTICAL
            space = self.ASCII_SPACE

        children = node.children
        if not children:
            return

        # 检查深度限制
        for i, child in enumerate(children):
            is_last = (i == len(children) - 1)

            # 深度限制检查
            if (
                self.options.max_depth is not None
                and child.depth >= self.options.max_depth
            ):
                if is_last:
                    connector = last_branch
                else:
                    connector = branch
                lines.append(f"{prefix}{connector}...")
                continue

            # 隐藏文件检查
            if not self.options.show_all and child.name.startswith("."):
                continue

            # 选择连接符
            if is_last:
                connector = last_branch
                child_prefix = prefix + space
            else:
                connector = branch
                child_prefix = prefix + vertical

            # 构建行内容
            display_name = child.name
            if child.is_dir:
                display_name += "/"

            # 添加文件大小和 Token 信息
            info_parts = []
            if self.options.show_sizes and child.file_entry is not None:
                info_parts.append(self._format_size(child.file_entry.size))
            if self.options.show_tokens and child.file_entry is not None:
                try:
                    with open(child.file_entry.path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    token_count = self.token_estimator.estimate(content)
                    info_parts.append(f"{token_count} tok")
                except (OSError, PermissionError):
                    pass

            if info_parts:
                info_str = " (" + ", ".join(info_parts) + ")"
                line = f"{prefix}{connector}{display_name}{info_str}"
            else:
                line = f"{prefix}{connector}{display_name}"

            lines.append(line)

            # 递归渲染子节点
            if child.is_dir:
                self._render_node(child, child_prefix, False, lines)

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
                if unit == "B":
                    return f"{size} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
