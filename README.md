<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/Dependencies-Zero-success.svg" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/Tests-77%20Passed-brightgreen.svg" alt="77 Tests Passed">
  <img src="https://img.shields.io/badge/Version-1.0.0-orange.svg" alt="v1.0.0">
</p>

<h1 align="center">🦞 CodeDigest-CLI</h1>

<p align="center">
  <strong>Lightweight Terminal Code Intelligent Digest Engine</strong><br>
  Pack code repositories into LLM-friendly digest format
</p>

<p align="center">
  <a href="#-简体中文">简体中文</a> ·
  <a href="#-繁體中文">繁體中文</a> ·
  <a href="#-english">English</a>
</p>

---

<a id="-简体中文"></a>

## 🎉 项目介绍

**CodeDigest-CLI** 是一款轻量级终端代码智能摘要引擎，专为 AI 时代开发者打造。它能将任意代码仓库或目录快速转换为 **LLM 友好的结构化文本摘要**，是开发者使用 Claude、GPT、Gemini 等 AI 编程助手时的得力工具。

### 💡 灵感来源

在使用 AI 编程助手时，我们经常需要将整个项目代码喂给 LLM，但直接复制粘贴效率低下且容易超出 Token 限制。CodeDigest-CLI 正是为了解决这一痛点而生——**一键生成结构清晰、Token 可控的代码摘要**。

### 🌟 自研差异化亮点

- **🧠 智能 Token 预算控制**：自动根据预算裁剪内容，保留核心代码，裁剪冗余部分
- **📊 文件优先级评分**：入口文件 > 配置文件 > 源代码 > 文档 > 测试文件，确保最重要的代码优先展示
- **🎨 多格式输出**：支持 Markdown、JSON、XML、纯文本四种输出格式
- **🚫 零外部依赖**：纯 Python 标准库实现，无需安装任何第三方包
- **🌍 多语言支持**：内置 Python、JavaScript、Go、Rust、Java 语言预设，支持自动检测
- **🌈 彩色终端输出**：自动检测终端颜色支持，提供美观的 ANSI 彩色输出

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 📁 **目录扫描** | 递归扫描代码目录，自动排除二进制文件和无用文件 |
| 🔍 **智能过滤** | 支持按扩展名包含/排除、目录排除、.gitignore 规则匹配 |
| 🧮 **Token 估算** | 基于启发式算法精确估算 Token 数量（支持中英文混合文本） |
| ✂️ **智能裁剪** | Token 超出预算时自动裁剪，保留导入语句和函数签名 |
| 🌲 **目录树可视化** | 生成美观的 Unicode 目录树结构 |
| 📊 **统计面板** | 显示文件数量、大小分布、扩展名统计等信息 |
| 🎯 **语言预设** | 内置 6 种语言预设，自动检测项目主要语言 |
| 🖥️ **彩色输出** | 自动检测终端能力，提供 ANSI 彩色输出和进度动画 |
| 🐚 **Shell 补全** | 支持 Bash、Zsh、Fish 三种 Shell 自动补全 |

---

## 🚀 快速开始

### 环境要求

- **Python 3.8+**（无需安装任何第三方依赖）

### 安装

```bash
# 方式一：直接从源码安装
git clone https://github.com/gitstq/CodeDigest-CLI.git
cd CodeDigest-CLI
pip install .

# 方式二：开发模式安装
pip install -e .

# 方式三：无需安装，直接运行
cd CodeDigest-CLI
PYTHONPATH=src python -m codedigest [路径]
```

### 基本用法

```bash
# 扫描当前目录，输出 Markdown 格式到终端
codedigest .

# 扫描指定项目目录
codedigest ./my-project

# 仅输出目录树
codedigest --tree-only ./my-project

# 输出 JSON 格式到文件
codedigest -f json -o output.json ./src

# 限制 Token 预算为 30000
codedigest -t 30000 ./my-project

# 仅包含 Python 和 JavaScript 文件
codedigest -i py,js,ts ./my-project

# 查看统计信息
codedigest --stats ./my-project
```

### 完整参数

```
positional arguments:
  path                  要扫描的目录路径（默认：当前目录）

options:
  -o, --output          输出文件路径
  -f, --format          输出格式：markdown | json | xml | text（默认：markdown）
  -t, --token-budget    最大 Token 预算（默认：50000）
  -x, --exclude         排除的文件扩展名，逗号分隔
  -i, --include         仅包含的文件扩展名，逗号分隔
  -e, --exclude-dirs    排除的目录名，逗号分隔
  -d, --max-depth       最大扫描深度（默认：0 = 无限制）
  -l, --language        语言预设：python | javascript | go | rust | java | auto
  --no-gitignore        禁用 .gitignore 模式匹配
  --tree-only           仅输出目录树
  --stats               显示统计信息
  -v, --version         显示版本号
  --install-completion  打印 Shell 补全安装说明
```

---

## 📖 详细使用指南

### 场景一：将项目代码喂给 Claude/GPT

```bash
# 生成 JSON 格式摘要，复制粘贴到 AI 对话中
codedigest -f json -t 8000 -i py ./my-project > context.json
```

### 场景二：生成项目代码文档

```bash
# 生成完整的 Markdown 代码文档
codedigest -f markdown -o CODE_DOCS.md ./my-project
```

### 场景三：快速了解项目结构

```bash
# 仅查看目录树和统计信息
codedigest --tree-only --stats ./my-project
```

### 场景四：分析大型仓库

```bash
# 限制深度和 Token，聚焦核心代码
codedigest -d 3 -t 20000 -l python ./large-repo
```

---

## 💡 设计思路与迭代规划

### 设计理念

- **零依赖哲学**：纯 Python 标准库实现，降低安装门槛，提升兼容性
- **LLM 优先**：所有设计决策以"对 LLM 最友好"为第一原则
- **渐进式信息**：通过优先级评分确保最重要的代码最先被 LLM 看到

### 后续迭代计划

- [ ] 支持远程 Git 仓库直接处理（无需手动克隆）
- [ ] 添加交互式 TUI 模式（文件选择与预览）
- [ ] 支持自定义配置文件
- [ ] 添加 AST 级别的智能代码摘要（保留结构，去除实现细节）
- [ ] 支持 diff/patch 格式输出

---

## 📦 安装与部署

```bash
# 安装
pip install git+https://github.com/gitstq/CodeDigest-CLI.git

# 或从源码
git clone https://github.com/gitstq/CodeDigest-CLI.git
cd CodeDigest-CLI
pip install .

# 验证安装
codedigest --version

# 运行测试
python -m unittest discover -s tests -v
```

**兼容环境**：Python 3.8+ / Windows / macOS / Linux

---

## 🤝 贡献指南

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

提交规范遵循 Angular Convention：
- `feat:` 新增功能
- `fix:` 修复问题
- `docs:` 文档更新
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具链相关

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源。

---

<a id="-繁體中文"></a>

## 🎉 專案介紹

**CodeDigest-CLI** 是一款輕量級終端程式碼智慧摘要引擎，專為 AI 時代開發者打造。它能將任意程式碼倉庫或目錄快速轉換為 **LLM 友好的結構化文字摘要**，是開發者使用 Claude、GPT、Gemini 等 AI 程式設計助手時的得力工具。

### 💡 靈感來源

在使用 AI 程式設計助手時，我們經常需要將整個專案程式碼餵給 LLM，但直接複製貼上效率低下且容易超出 Token 限制。CodeDigest-CLI 正是為了解決這一痛點而生——**一鍵生成結構清晰、Token 可控的程式碼摘要**。

### 🌟 自研差異化亮點

- **🧠 智能 Token 預算控制**：自動根據預算裁剪內容，保留核心程式碼，裁剪冗餘部分
- **📊 檔案優先級評分**：入口檔案 > 設定檔 > 原始碼 > 文件 > 測試檔案，確保最重要的程式碼優先展示
- **🎨 多格式輸出**：支援 Markdown、JSON、XML、純文字四種輸出格式
- **🚫 零外部依賴**：純 Python 標準函式庫實作，無需安裝任何第三方套件
- **🌍 多語言支援**：內建 Python、JavaScript、Go、Rust、Java 語言預設，支援自動偵測
- **🌈 彩色終端輸出**：自動偵測終端色彩支援，提供美觀的 ANSI 彩色輸出

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 📁 **目錄掃描** | 遞迴掃描程式碼目錄，自動排除二進位檔案和無用檔案 |
| 🔍 **智慧過濾** | 支援按副檔名包含/排除、目錄排除、.gitignore 規則匹配 |
| 🧮 **Token 估算** | 基於啟發式演算法精確估算 Token 數量（支援中英文混合文字） |
| ✂️ **智慧裁剪** | Token 超出預算時自動裁剪，保留匯入語句和函式簽名 |
| 🌲 **目錄樹視覺化** | 生成美觀的 Unicode 目錄樹結構 |
| 📊 **統計面板** | 顯示檔案數量、大小分佈、副檔名統計等資訊 |
| 🎯 **語言預設** | 內建 6 種語言預設，自動偵測專案主要語言 |
| 🖥️ **彩色輸出** | 自動偵測終端能力，提供 ANSI 彩色輸出和進度動畫 |
| 🐚 **Shell 補全** | 支援 Bash、Zsh、Fish 三種 Shell 自動補全 |

---

## 🚀 快速開始

### 環境要求

- **Python 3.8+**（無需安裝任何第三方依賴）

### 安裝

```bash
# 方式一：直接從原始碼安裝
git clone https://github.com/gitstq/CodeDigest-CLI.git
cd CodeDigest-CLI
pip install .

# 方式二：開發模式安裝
pip install -e .

# 方式三：無需安裝，直接執行
cd CodeDigest-CLI
PYTHONPATH=src python -m codedigest [路徑]
```

### 基本用法

```bash
# 掃描目前目錄，輸出 Markdown 格式到終端
codedigest .

# 掃描指定專案目錄
codedigest ./my-project

# 僅輸出目錄樹
codedigest --tree-only ./my-project

# 輸出 JSON 格式到檔案
codedigest -f json -o output.json ./src

# 限制 Token 預算為 30000
codedigest -t 30000 ./my-project

# 僅包含 Python 和 JavaScript 檔案
codedigest -i py,js,ts ./my-project

# 查看統計資訊
codedigest --stats ./my-project
```

---

## 📖 詳細使用指南

### 場景一：將專案程式碼餵給 Claude/GPT

```bash
# 生成 JSON 格式摘要，複製貼上到 AI 對話中
codedigest -f json -t 8000 -i py ./my-project > context.json
```

### 場景二：生成專案程式碼文件

```bash
# 生成完整的 Markdown 程式碼文件
codedigest -f markdown -o CODE_DOCS.md ./my-project
```

### 場景三：快速了解專案結構

```bash
# 僅查看目錄樹和統計資訊
codedigest --tree-only --stats ./my-project
```

---

## 💡 設計思路與迭代規劃

### 設計理念

- **零依賴哲學**：純 Python 標準函式庫實作，降低安裝門檻，提升相容性
- **LLM 優先**：所有設計決策以「對 LLM 最友好」為第一原則
- **漸進式資訊**：透過優先級評分確保最重要的程式碼最先被 LLM 看到

### 後續迭代計畫

- [ ] 支援遠端 Git 倉庫直接處理
- [ ] 新增互動式 TUI 模式
- [ ] 支援自訂設定檔
- [ ] 新增 AST 級別的智慧程式碼摘要
- [ ] 支援 diff/patch 格式輸出

---

## 📦 安裝與部署

```bash
pip install git+https://github.com/gitstq/CodeDigest-CLI.git
```

**相容環境**：Python 3.8+ / Windows / macOS / Linux

---

## 🤝 貢獻指南

歡迎貢獻！請閱讀 [CONTRIBUTING.md](CONTRIBUTING.md) 了解詳情。

---

## 📄 開源協議

本專案基於 [MIT License](LICENSE) 開源。

---

<a id="-english"></a>

## 🎉 Introduction

**CodeDigest-CLI** is a lightweight terminal code intelligent digest engine designed for developers in the AI era. It quickly converts any code repository or directory into an **LLM-friendly structured text digest**, making it an essential tool when working with AI coding assistants like Claude, GPT, and Gemini.

### 💡 Inspiration

When using AI coding assistants, we often need to feed entire project codebases to LLMs. However, manual copy-pasting is inefficient and easily exceeds token limits. CodeDigest-CLI was born to solve this pain point — **generate structured, token-controlled code digests with a single command**.

### 🌟 Differentiated Highlights

- **🧠 Smart Token Budget Control**: Automatically trims content based on budget, preserving core code while reducing redundancy
- **📊 File Priority Scoring**: Entry files > Config files > Source code > Docs > Tests — ensures the most important code is presented first
- **🎨 Multi-Format Output**: Supports Markdown, JSON, XML, and Plain Text output formats
- **🚫 Zero Dependencies**: Built entirely with Python standard library — no third-party packages needed
- **🌍 Multi-Language Support**: Built-in presets for Python, JavaScript, Go, Rust, Java with auto-detection
- **🌈 Colored Terminal Output**: Auto-detects terminal color support with beautiful ANSI colored output

---

## ✨ Core Features

| Feature | Description |
|---------|-------------|
| 📁 **Directory Scanning** | Recursively scans code directories, auto-excluding binary and useless files |
| 🔍 **Smart Filtering** | Extension include/exclude, directory exclusion, .gitignore pattern matching |
| 🧮 **Token Estimation** | Heuristic-based accurate token estimation (supports CJK + English mixed text) |
| ✂️ **Smart Truncation** | Auto-trims when exceeding budget, preserving imports and function signatures |
| 🌲 **Tree Visualization** | Generates beautiful Unicode directory tree structures |
| 📊 **Statistics Panel** | Displays file count, size distribution, extension breakdown |
| 🎯 **Language Presets** | 6 built-in language presets with auto-detection |
| 🖥️ **Colored Output** | ANSI colored output with progress animation |
| 🐚 **Shell Completion** | Bash, Zsh, Fish auto-completion support |

---

## 🚀 Quick Start

### Requirements

- **Python 3.8+** (no third-party dependencies required)

### Installation

```bash
# Option 1: Install from source
git clone https://github.com/gitstq/CodeDigest-CLI.git
cd CodeDigest-CLI
pip install .

# Option 2: Development mode
pip install -e .

# Option 3: Run without installation
cd CodeDigest-CLI
PYTHONPATH=src python -m codedigest [path]
```

### Basic Usage

```bash
# Scan current directory, output Markdown to terminal
codedigest .

# Scan a specific project
codedigest ./my-project

# Output directory tree only
codedigest --tree-only ./my-project

# Output JSON format to file
codedigest -f json -o output.json ./src

# Limit token budget to 30000
codedigest -t 30000 ./my-project

# Include only Python and JavaScript files
codedigest -i py,js,ts ./my-project

# Show statistics
codedigest --stats ./my-project
```

### Full Arguments

```
positional arguments:
  path                  Directory path to scan (default: current directory)

options:
  -o, --output          Output file path
  -f, --format          Output format: markdown | json | xml | text (default: markdown)
  -t, --token-budget    Maximum token budget (default: 50000)
  -x, --exclude         File extensions to exclude, comma-separated
  -i, --include         File extensions to include only, comma-separated
  -e, --exclude-dirs    Directory names to exclude, comma-separated
  -d, --max-depth       Maximum scan depth (default: 0 = unlimited)
  -l, --language        Language preset: python | javascript | go | rust | java | auto
  --no-gitignore        Disable .gitignore pattern matching
  --tree-only           Output directory tree only
  --stats               Show statistics
  -v, --version         Show version
  --install-completion  Print shell completion installation guide
```

---

## 📖 Detailed Usage Guide

### Scenario 1: Feed Project Code to Claude/GPT

```bash
# Generate JSON digest, copy-paste into AI conversation
codedigest -f json -t 8000 -i py ./my-project > context.json
```

### Scenario 2: Generate Project Code Documentation

```bash
# Generate complete Markdown code documentation
codedigest -f markdown -o CODE_DOCS.md ./my-project
```

### Scenario 3: Quick Project Structure Overview

```bash
# View directory tree and statistics only
codedigest --tree-only --stats ./my-project
```

### Scenario 4: Analyze Large Repositories

```bash
# Limit depth and tokens, focus on core code
codedigest -d 3 -t 20000 -l python ./large-repo
```

---

## 💡 Design Philosophy & Roadmap

### Design Principles

- **Zero Dependency Philosophy**: Pure Python standard library for maximum compatibility
- **LLM-First**: All design decisions prioritize "LLM-friendliness"
- **Progressive Information**: Priority scoring ensures the most important code is seen first by LLMs

### Roadmap

- [ ] Remote Git repository direct processing (no manual cloning needed)
- [ ] Interactive TUI mode (file selection & preview)
- [ ] Custom configuration file support
- [ ] AST-level intelligent code summarization
- [ ] Diff/patch format output support

---

## 📦 Installation & Deployment

```bash
pip install git+https://github.com/gitstq/CodeDigest-CLI.git
```

**Compatible Environments**: Python 3.8+ / Windows / macOS / Linux

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

Commit convention follows Angular Convention:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation updates
- `refactor:` Code refactoring
- `test:` Test-related
- `chore:` Build/tooling

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  Made with 🦞 by SoloBot
</p>
