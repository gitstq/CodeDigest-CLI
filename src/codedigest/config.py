"""配置模块 - 管理默认配置、扩展名列表和语言预设。

本模块负责：
- 定义默认配置（最大 Token 数、默认格式、默认排除项）
- 管理包含/排除扩展名列表
- 提供不同编程语言的预设配置
- 从 JSON 配置文件加载配置
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class CodeDigestConfig:
    """CodeDigest-CLI 的配置数据类。

    Attributes:
        max_tokens: 最大 Token 预算。
        output_format: 默认输出格式。
        include_extensions: 包含的文件扩展名集合。None 表示包含所有。
        exclude_extensions: 排除的文件扩展名集合。
        exclude_dirs: 排除的目录名称集合。
        respect_gitignore: 是否遵守 .gitignore 规则。
        max_depth: 最大扫描深度。None 表示无限制。
        show_tree: 是否在输出中显示目录树。
        show_sizes: 是否在目录树中显示文件大小。
        show_tokens: 是否在目录树中显示 Token 计数。
        language_preset: 语言预设名称。
        git_branch: 克隆时的目标分支。
        clone_depth: 克隆深度。None 表示完整克隆。
    """

    max_tokens: int = 100000
    output_format: str = "markdown"
    include_extensions: Optional[Set[str]] = None
    exclude_extensions: Set[str] = field(default_factory=set)
    exclude_dirs: Set[str] = field(default_factory=lambda: {
        ".git", "__pycache__", "node_modules", ".svn",
        ".hg", "dist", "build", ".tox", ".eggs",
    })
    respect_gitignore: bool = True
    max_depth: Optional[int] = None
    show_tree: bool = True
    show_sizes: bool = True
    show_tokens: bool = False
    language_preset: Optional[str] = None
    git_branch: Optional[str] = None
    clone_depth: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典。

        Returns:
            配置字典。
        """
        result: Dict[str, Any] = {}
        for key, value in self.__dict__.items():
            if isinstance(value, set):
                result[key] = sorted(value)
            elif isinstance(value, (str, int, bool, type(None))):
                result[key] = value
            # 跳过不可序列化的类型
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeDigestConfig":
        """从字典创建配置对象。

        Args:
            data: 配置字典。

        Returns:
            CodeDigestConfig 实例。
        """
        config = cls()

        for key, value in data.items():
            if not hasattr(config, key):
                continue

            if key in ("include_extensions", "exclude_extensions", "exclude_dirs"):
                if isinstance(value, (list, set)):
                    setattr(config, key, set(value))
                elif value is None:
                    setattr(config, key, None)
            else:
                try:
                    setattr(config, key, value)
                except (TypeError, AttributeError):
                    pass

        return config


# ============================================================
# 语言预设配置
# ============================================================

# Python 项目预设
PYTHON_PRESET: Dict[str, Any] = {
    "name": "Python",
    "description": "Python 项目默认配置",
    "include_extensions": {
        ".py", ".pyx", ".pxd", ".pyi",
        ".txt", ".md", ".rst", ".ini", ".cfg", ".toml",
        ".yaml", ".yml", ".json",
    },
    "exclude_extensions": {".pyc", ".pyo", ".whl", ".egg"},
    "exclude_dirs": {
        ".git", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".tox", ".eggs", "*.egg-info",
        "venv", ".venv", "env", ".env",
        "htmlcov", "coverage", ".coverage",
        "dist", "build", ".eggs",
    },
}

# JavaScript/TypeScript 项目预设
JAVASCRIPT_PRESET: Dict[str, Any] = {
    "name": "JavaScript",
    "description": "JavaScript/TypeScript 项目默认配置",
    "include_extensions": {
        ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
        ".json", ".md", ".yaml", ".yml",
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        ".graphql", ".gql",
    },
    "exclude_extensions": {
        ".min.js", ".min.css", ".map",
        ".lock", ".log",
    },
    "exclude_dirs": {
        ".git", "node_modules", ".next", ".nuxt",
        "dist", "build", ".output", ".vercel",
        ".cache", ".tmp", "coverage",
        ".turbo", ".parcel-cache",
    },
}

# Go 项目预设
GO_PRESET: Dict[str, Any] = {
    "name": "Go",
    "description": "Go 项目默认配置",
    "include_extensions": {
        ".go", ".mod", ".sum",
        ".md", ".txt", ".yaml", ".yml", ".json", ".toml",
        ".sql", ".html", ".css", ".js",
        ".tmpl", ".gotmpl",
        ".proto", ".graphql",
    },
    "exclude_extensions": {
        ".exe", ".dll", ".so", ".dylib",
        ".test", ".out",
    },
    "exclude_dirs": {
        ".git", "vendor", "dist", "build",
        ".cache", "tmp",
    },
}

# Rust 项目预设
RUST_PRESET: Dict[str, Any] = {
    "name": "Rust",
    "description": "Rust 项目默认配置",
    "include_extensions": {
        ".rs", ".toml",
        ".md", ".txt", ".json", ".yaml", ".yml",
        ".lock",
    },
    "exclude_extensions": {
        ".rlib", ".rmeta", ".d", ".o", ".a",
        ".exe", ".dll", ".so", ".dylib",
    },
    "exclude_dirs": {
        ".git", "target", "dist",
    },
}

# Java 项目预设
JAVA_PRESET: Dict[str, Any] = {
    "name": "Java",
    "description": "Java/Kotlin 项目默认配置",
    "include_extensions": {
        ".java", ".kt", ".kts",
        ".xml", ".properties", ".yml", ".yaml",
        ".json", ".toml", ".gradle",
        ".md", ".txt", ".html", ".css", ".js",
        ".sql", ".proto", ".graphql",
    },
    "exclude_extensions": {
        ".class", ".jar", ".war", ".ear",
        ".dex", ".apk",
    },
    "exclude_dirs": {
        ".git", ".gradle", "build", "target",
        ".idea", ".classpath", ".settings",
        "node_modules", "dist", "out",
        ".cache", "tmp",
    },
}

# C/C++ 项目预设
CPP_PRESET: Dict[str, Any] = {
    "name": "C++",
    "description": "C/C++ 项目默认配置",
    "include_extensions": {
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx",
        ".md", ".txt", ".cmake", ".json", ".yaml", ".yml", ".toml",
        ".xml", ".ini", ".cfg",
        ".proto", ".graphql",
    },
    "exclude_extensions": {
        ".o", ".obj", ".a", ".lib", ".so", ".dylib", ".dll",
        ".exe", ".out", ".pdb", ".ilk",
    },
    "exclude_dirs": {
        ".git", "build", "cmake-build-*",
        "dist", "out", "obj",
        ".cache", "tmp",
        "CMakeFiles", "CMakeCache.txt",
    },
}

# 所有预设的注册表
LANGUAGE_PRESETS: Dict[str, Dict[str, Any]] = {
    "python": PYTHON_PRESET,
    "javascript": JAVASCRIPT_PRESET,
    "js": JAVASCRIPT_PRESET,
    "typescript": JAVASCRIPT_PRESET,
    "ts": JAVASCRIPT_PRESET,
    "go": GO_PRESET,
    "rust": RUST_PRESET,
    "java": JAVA_PRESET,
    "kotlin": JAVA_PRESET,
    "cpp": CPP_PRESET,
    "c": CPP_PRESET,
    "c++": CPP_PRESET,
}


def get_preset_names() -> List[str]:
    """获取所有可用的语言预设名称列表。

    Returns:
        去重后的预设名称列表。
    """
    seen: Set[str] = set()
    names: List[str] = []
    for name, preset in LANGUAGE_PRESETS.items():
        display_name = preset["name"]
        if display_name not in seen:
            seen.add(display_name)
            names.append(name)
    return names


def apply_preset(config: CodeDigestConfig, preset_name: str) -> CodeDigestConfig:
    """将语言预设应用到配置对象。

    Args:
        config: 基础配置对象。
        preset_name: 预设名称。

    Returns:
        应用预设后的配置对象。

    Raises:
        ValueError: 如果预设名称不存在。
    """
    preset = LANGUAGE_PRESETS.get(preset_name.lower())
    if preset is None:
        available = ", ".join(sorted(LANGUAGE_PRESETS.keys()))
        raise ValueError(
            f"未知的语言预设: '{preset_name}'。可用预设: {available}"
        )

    # 应用预设中的扩展名和目录配置
    if "include_extensions" in preset:
        config.include_extensions = set(preset["include_extensions"])
    if "exclude_extensions" in preset:
        config.exclude_extensions = set(preset["exclude_extensions"])
    if "exclude_dirs" in preset:
        config.exclude_dirs = set(preset["exclude_dirs"])
    config.language_preset = preset_name.lower()

    return config


def load_config(config_path: Optional[str] = None) -> CodeDigestConfig:
    """从 JSON 配置文件加载配置。

    如果配置文件不存在或无法解析，则返回默认配置。

    配置文件格式示例：
    ```json
    {
        "max_tokens": 50000,
        "output_format": "json",
        "include_extensions": [".py", ".js"],
        "exclude_extensions": [".pyc"],
        "exclude_dirs": [".git", "node_modules"],
        "respect_gitignore": true,
        "max_depth": 5,
        "language_preset": "python"
    }
    ```

    Args:
        config_path: 配置文件的路径。如果为 None，按以下顺序查找：
            1. 当前目录下的 .codedigest.json
            2. 当前目录下的 codedigest.json
            3. 用户主目录下的 ~/.codedigest/config.json

    Returns:
        加载的配置对象。
    """
    config = CodeDigestConfig()

    # 查找配置文件
    if config_path is None:
        search_paths = [
            ".codedigest.json",
            "codedigest.json",
            os.path.expanduser("~/.codedigest/config.json"),
        ]
        for path in search_paths:
            if os.path.isfile(path):
                config_path = path
                break

    if config_path is None or not os.path.isfile(config_path):
        return config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = CodeDigestConfig.from_dict(data)

        # 如果指定了语言预设，应用预设
        if config.language_preset:
            apply_preset(config, config.language_preset)

    except (json.JSONDecodeError, OSError, PermissionError) as e:
        # 配置文件解析失败，使用默认配置
        import sys
        print(
            f"警告: 无法加载配置文件 '{config_path}': {e}。使用默认配置。",
            file=sys.stderr,
        )

    return config


def save_config(config: CodeDigestConfig, config_path: str) -> None:
    """将配置保存到 JSON 文件。

    Args:
        config: 要保存的配置对象。
        config_path: 目标配置文件路径。

    Raises:
        OSError: 如果写入文件失败。
    """
    # 确保父目录存在
    parent_dir = os.path.dirname(config_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    data = config.to_dict()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def create_default_config() -> CodeDigestConfig:
    """创建默认配置对象。

    Returns:
        使用所有默认值的 CodeDigestConfig 实例。
    """
    return CodeDigestConfig()
