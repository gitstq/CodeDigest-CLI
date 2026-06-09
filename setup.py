"""
CodeDigest-CLI 安装配置。

使用 setuptools 进行包管理和分发。
支持 ``pip install .`` 或 ``pip install -e .`` 进行安装。
"""

import os
import sys

from setuptools import find_packages, setup

# 读取包版本
here = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(here, "src"))
from codedigest import __version__  # noqa: E402

# 读取 README（如果存在）
readme_path = os.path.join(here, "README.md")
long_description = ""
if os.path.isfile(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="codedigest-cli",
    version=__version__,
    description="Pack code repositories into LLM-friendly digest format",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="CodeDigest Contributors",
    license="MIT",
    python_requires=">=3.8",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "codedigest=codedigest.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
    project_urls={
        "Homepage": "https://github.com/codedigest/cli",
        "Bug Tracker": "https://github.com/codedigest/cli/issues",
    },
)
