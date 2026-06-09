"""Git 仓库处理模块 - 检测、克隆和管理 Git 仓库。

本模块负责：
- 检测给定路径是否为 Git 仓库
- 克隆远程仓库（支持 GitHub/GitLab URL）到临时目录
- 提取仓库元数据（分支名、提交哈希、远程 URL）
- 清理临时目录
- 仅使用 subprocess 调用 git 命令（无 gitpython 依赖）
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class GitMetadata:
    """Git 仓库元数据。

    Attributes:
        branch: 当前分支名。
        commit_hash: 当前提交的完整哈希值。
        short_hash: 当前提交的短哈希值。
        remote_url: 远程仓库 URL（如果有）。
        repo_root: 仓库根目录的绝对路径。
        is_dirty: 工作区是否有未提交的修改。
        author: 最后一次提交的作者。
        date: 最后一次提交的日期。
    """

    branch: str = ""
    commit_hash: str = ""
    short_hash: str = ""
    remote_url: str = ""
    repo_root: str = ""
    is_dirty: bool = False
    author: str = ""
    date: str = ""


class GitHandler:
    """Git 仓库处理器。

    提供 Git 仓库的检测、克隆和元数据提取功能。
    所有 Git 操作均通过 subprocess 调用 git 命令行工具完成。

    Usage:
        handler = GitHandler()

        # 检测本地仓库
        if handler.is_git_repo("/path/to/repo"):
            metadata = handler.get_metadata("/path/to/repo")

        # 克隆远程仓库
        repo_path = handler.clone("https://github.com/user/repo.git")
        try:
            metadata = handler.get_metadata(repo_path)
            # ... 处理仓库 ...
        finally:
            handler.cleanup(repo_path)
    """

    def __init__(self, git_bin: str = "git") -> None:
        """初始化 Git 处理器。

        Args:
            git_bin: git 可执行文件的路径或名称。
        """
        self.git_bin = git_bin
        self._temp_dirs: List[str] = []

    def is_git_repo(self, path: str) -> bool:
        """检测给定路径是否为 Git 仓库。

        Args:
            path: 要检测的路径。

        Returns:
            True 如果是 Git 仓库，否则 False。
        """
        return self._run_git(
            ["rev-parse", "--is-inside-work-tree"],
            cwd=path,
            check=False,
            capture=True,
        ).returncode == 0

    def get_repo_root(self, path: str) -> Optional[str]:
        """获取 Git 仓库的根目录路径。

        Args:
            path: 仓库中的任意路径。

        Returns:
            仓库根目录的绝对路径，如果不是仓库则返回 None。
        """
        result = self._run_git(
            ["rev-parse", "--show-toplevel"],
            cwd=path,
            check=False,
            capture=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def get_metadata(self, path: str) -> GitMetadata:
        """提取 Git 仓库的元数据。

        Args:
            path: Git 仓库的路径。

        Returns:
            GitMetadata 对象，包含仓库的各种元信息。
        """
        metadata = GitMetadata(repo_root=os.path.abspath(path))

        # 获取当前分支名
        branch = self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path, check=False, capture=True,
        )
        if branch.returncode == 0:
            metadata.branch = branch.stdout.strip()

        # 获取提交哈希
        commit = self._run_git(
            ["rev-parse", "HEAD"],
            cwd=path, check=False, capture=True,
        )
        if commit.returncode == 0:
            metadata.commit_hash = commit.stdout.strip()
            metadata.short_hash = metadata.commit_hash[:7]

        # 获取远程 URL
        remote = self._run_git(
            ["remote", "get-url", "origin"],
            cwd=path, check=False, capture=True,
        )
        if remote.returncode == 0:
            metadata.remote_url = remote.stdout.strip()

        # 检查工作区状态
        status = self._run_git(
            ["status", "--porcelain"],
            cwd=path, check=False, capture=True,
        )
        metadata.is_dirty = status.returncode == 0 and bool(status.stdout.strip())

        # 获取最后一次提交的作者和日期
        log = self._run_git(
            ["log", "-1", "--format=%an|%aI"],
            cwd=path, check=False, capture=True,
        )
        if log.returncode == 0:
            parts = log.stdout.strip().split("|", 1)
            if len(parts) == 2:
                metadata.author = parts[0]
                metadata.date = parts[1]

        # 获取仓库根目录
        root = self.get_repo_root(path)
        if root:
            metadata.repo_root = root

        return metadata

    def clone(
        self,
        url: str,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        target_dir: Optional[str] = None,
    ) -> str:
        """克隆远程 Git 仓库到临时目录。

        Args:
            url: 远程仓库的 URL（支持 GitHub/GitLab 等）。
            branch: 要克隆的分支名。None 表示默认分支。
            depth: 克隆深度（浅克隆）。None 表示完整克隆。
            target_dir: 目标目录。None 表示自动创建临时目录。

        Returns:
            克隆后的仓库路径。

        Raises:
            RuntimeError: 如果克隆失败。
            FileNotFoundError: 如果 git 命令不可用。
        """
        # 检查 git 是否可用
        if not self._check_git_available():
            raise FileNotFoundError(
                "未找到 git 命令。请确保 git 已安装并在 PATH 中。"
            )

        # 规范化 URL
        url = self._normalize_url(url)

        # 创建目标目录
        if target_dir is None:
            target_dir = tempfile.mkdtemp(prefix="codedigest_")
            self._temp_dirs.append(target_dir)
        else:
            os.makedirs(target_dir, exist_ok=True)

        # 构建克隆命令
        cmd = ["clone", "--quiet"]
        if branch is not None:
            cmd.extend(["--branch", branch])
        if depth is not None and depth > 0:
            cmd.extend(["--depth", str(depth)])
        cmd.append(url)
        cmd.append(target_dir)

        result = self._run_git(cmd, check=False, capture=True)

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"克隆仓库失败: {error_msg}")

        return target_dir

    def cleanup(self, path: str) -> None:
        """清理克隆的临时目录。

        Args:
            path: 要清理的目录路径。
        """
        try:
            if path in self._temp_dirs:
                self._temp_dirs.remove(path)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass

    def cleanup_all(self) -> None:
        """清理所有由此处理器创建的临时目录。"""
        for path in list(self._temp_dirs):
            self.cleanup(path)

    def _check_git_available(self) -> bool:
        """检查 git 命令是否可用。

        Returns:
            git 是否可用。
        """
        try:
            result = subprocess.run(
                [self.git_bin, "--version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _normalize_url(self, url: str) -> str:
        """规范化 Git 仓库 URL。

        支持的格式：
        - https://github.com/user/repo.git
        - https://github.com/user/repo
        - git@github.com:user/repo.git
        - github.com/user/repo
        - user/repo（自动补全为 https://github.com/user/repo）

        Args:
            url: 原始 URL 字符串。

        Returns:
            规范化后的 URL。
        """
        url = url.strip()

        # 已经是完整的 URL
        if url.startswith(("https://", "http://", "git://", "ssh://", "git@")):
            return url

        # SSH 格式: git@host:user/repo.git
        if url.startswith("git@"):
            return url

        # 简写格式: github.com/user/repo
        if "/" in url and "." in url.split("/")[0]:
            return f"https://{url}"

        # 极简格式: user/repo (默认 GitHub)
        if "/" in url:
            return f"https://github.com/{url}"

        return url

    def _run_git(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        check: bool = False,
        capture: bool = False,
    ) -> subprocess.CompletedProcess:
        """执行 git 命令。

        Args:
            args: git 命令参数列表。
            cwd: 工作目录。
            check: 是否在非零退出码时抛出异常。
            capture: 是否捕获输出。

        Returns:
            subprocess.CompletedProcess 对象。
        """
        cmd = [self.git_bin] + args

        kwargs: Dict = {}
        if cwd:
            kwargs["cwd"] = cwd
        if capture:
            kwargs["capture_output"] = True
            kwargs["text"] = True
            kwargs["encoding"] = "utf-8"
            kwargs["errors"] = "replace"
        else:
            kwargs["stdout"] = subprocess.DEVNULL
            kwargs["stderr"] = subprocess.DEVNULL

        return subprocess.run(cmd, timeout=120, **kwargs)

    def __del__(self) -> None:
        """析构函数，确保清理临时目录。"""
        try:
            self.cleanup_all()
        except Exception:
            pass
